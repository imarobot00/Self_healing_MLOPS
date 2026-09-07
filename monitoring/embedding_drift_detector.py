"""
Embedding Drift Detector for LLM query monitoring.

Compares recent production query embeddings (from logs/llm_traces/*.jsonl)
against the reference baseline (monitoring/embedding_baseline.npz) using:
  1. Cosine centroid drift  - cheap signal: has the average topic moved?
  2. MMD with RBF kernel    - rigorous kernel two-sample test with a
                              permutation-derived p-value.

Mirrors the class shape of monitoring/drift_detector.py.

Usage:
    python monitoring/embedding_drift_detector.py
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent


class EmbeddingDriftDetector:
    """Detects distribution drift between baseline and recent query embeddings."""

    def __init__(self, config_path: str = "monitoring/drift_config.yaml"):
        self.config = self._load_config(config_path)
        self.baseline = self._load_baseline()

    def _load_config(self, config_path: str) -> dict:
        path = Path(config_path)
        if not path.is_absolute():
            path = REPO_ROOT / config_path
        with open(path, "r") as f:
            full = yaml.safe_load(f)
        cfg = full.get("embedding_drift")
        if cfg is None:
            raise KeyError("No 'embedding_drift' section in drift_config.yaml")
        return cfg

    def _load_baseline(self) -> Dict:
        path = REPO_ROOT / self.config["baseline_file"]
        if not path.exists():
            raise FileNotFoundError(
                f"Baseline not found: {path}. Run monitoring/generate_embedding_baseline.py"
            )
        data = np.load(path, allow_pickle=False)
        baseline = {
            "embeddings": data["embeddings"],
            "centroid": data["centroid"],
            "model_name": str(data["model_name"]),
        }
        logger.info(
            f"Baseline loaded: {baseline['embeddings'].shape[0]} vectors, "
            f"model={baseline['model_name']}"
        )
        return baseline

    def load_recent_embeddings(self) -> Optional[np.ndarray]:
        """Read the newest trace files and pull out the last window_size embeddings."""
        traces_dir = REPO_ROOT / self.config["traces_dir"]
        window = self.config.get("window_size", 200)

        if not traces_dir.exists():
            logger.warning(f"Traces dir not found: {traces_dir}")
            return None

        embeddings: List[List[float]] = []
        # newest files first, stop once the window is full
        for f in sorted(traces_dir.glob("*.jsonl"), reverse=True):
            for line in f.read_text(encoding="utf-8").splitlines():
                try:
                    trace = json.loads(line)
                except json.JSONDecodeError:
                    continue  # a torn line must not kill the nightly job
                if trace.get("embedding"):
                    embeddings.append(trace["embedding"])
            if len(embeddings) >= window:
                break

        if not embeddings:
            return None
        return np.array(embeddings[-window:], dtype=np.float32)

    # ---------- detector 1: cosine centroid drift ----------

    def cosine_centroid_drift(self, recent: np.ndarray) -> Dict:
        baseline_c = self.baseline["centroid"]
        recent_c = recent.mean(axis=0)

        cos_sim = float(
            np.dot(baseline_c, recent_c)
            / (np.linalg.norm(baseline_c) * np.linalg.norm(recent_c))
        )
        distance = 1.0 - cos_sim
        threshold = self.config["thresholds"]["cosine_distance"]

        return {
            "cosine_similarity": round(cos_sim, 4),
            "cosine_distance": round(distance, 4),
            "threshold": threshold,
            "drift_detected": distance > threshold,
        }

    # ---------- detector 2: MMD + permutation test ----------

    @staticmethod
    def _rbf_kernel(a: np.ndarray, b: np.ndarray, sigma: float) -> np.ndarray:
        # ||a-b||^2 = ||a||^2 + ||b||^2 - 2ab, computed for all pairs at once
        sq_dists = (
            np.sum(a**2, axis=1)[:, None]
            + np.sum(b**2, axis=1)[None, :]
            - 2.0 * (a @ b.T)
        )
        return np.exp(-sq_dists / (2.0 * sigma**2))

    @staticmethod
    def _median_sigma(pooled: np.ndarray) -> float:
        """Median heuristic: sigma = sqrt(median pairwise squared distance / 2)."""
        sq_dists = (
            np.sum(pooled**2, axis=1)[:, None]
            + np.sum(pooled**2, axis=1)[None, :]
            - 2.0 * (pooled @ pooled.T)
        )
        off_diag = sq_dists[~np.eye(len(pooled), dtype=bool)]
        return float(np.sqrt(np.median(off_diag) / 2.0) + 1e-12)

    @staticmethod
    def _mmd_from_kernel(K: np.ndarray, m: int, n: int) -> float:
        """Unbiased MMD^2 given the full (m+n)x(m+n) kernel matrix."""
        Kxx, Kyy, Kxy = K[:m, :m], K[m:, m:], K[:m, m:]
        # exclude the diagonal: a point's similarity to itself is not evidence
        mmd2 = (
            (Kxx.sum() - np.trace(Kxx)) / (m * (m - 1))
            + (Kyy.sum() - np.trace(Kyy)) / (n * (n - 1))
            - 2.0 * Kxy.mean()
        )
        return float(mmd2)

    def mmd_test(self, recent: np.ndarray) -> Dict:
        rng = np.random.default_rng(42)  # reproducible nightly results
        baseline = self.baseline["embeddings"]
        m, n = len(baseline), len(recent)

        pooled = np.vstack([baseline, recent]).astype(np.float64)
        sigma = self.config["mmd"].get("rbf_sigma") or self._median_sigma(pooled)

        # kernel matrix computed ONCE; permutations only reshuffle indices
        K = self._rbf_kernel(pooled, pooled, sigma)
        observed = self._mmd_from_kernel(K, m, n)

        n_perm = self.config["mmd"].get("n_permutations", 200)
        count_ge = 0
        for _ in range(n_perm):
            idx = rng.permutation(m + n)
            K_perm = K[np.ix_(idx, idx)]
            if self._mmd_from_kernel(K_perm, m, n) >= observed:
                count_ge += 1

        # add-one smoothing: p can never be exactly 0 from a finite test
        p_value = (count_ge + 1) / (n_perm + 1)
        threshold = self.config["thresholds"]["mmd_p_value"]

        return {
            "mmd_squared": round(observed, 6),
            "p_value": round(p_value, 4),
            "sigma": round(sigma, 4),
            "n_permutations": n_perm,
            "threshold_p_value": threshold,
            "drift_detected": p_value < threshold,
        }

    # ---------- orchestration ----------

    def run_drift_check(self) -> Dict:
        report: Dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "baseline_model": self.baseline["model_name"],
            "status": "ok",
        }

        recent = self.load_recent_embeddings()
        min_samples = self.config.get("min_samples", 20)

        if recent is None or len(recent) < min_samples:
            found = 0 if recent is None else len(recent)
            report.update({
                "status": "insufficient_data",
                "num_recent_samples": found,
                "min_samples": min_samples,
            })
            logger.warning(f"Only {found} traces (< {min_samples}); skipping drift tests")
            return report

        dim = self.baseline["embeddings"].shape[1]
        if recent.shape[1] != dim:
            raise ValueError(
                f"Embedding dim mismatch: baseline {dim} vs traces {recent.shape[1]}. "
                "Baseline and traces must use the same embedding model."
            )

        report["num_recent_samples"] = int(len(recent))
        report["cosine"] = self.cosine_centroid_drift(recent)
        report["mmd"] = self.mmd_test(recent)
        report["drift_detected"] = (
            report["cosine"]["drift_detected"] or report["mmd"]["drift_detected"]
        )
        return report

    def save_report(self, report: Dict) -> Path:
        reports_dir = REPO_ROOT / self.config["reporting"]["reports_dir"]
        reports_dir.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = reports_dir / f"embedding_drift_{stamp}.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        # stable filename the API reads to relay gauges to Prometheus
        (reports_dir / "embedding_drift_latest.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        logger.info(f"Report saved: {path}")
        return path


if __name__ == "__main__":
    detector = EmbeddingDriftDetector()
    report = detector.run_drift_check()
    detector.save_report(report)

    print("\n" + "=" * 50)
    print("EMBEDDING DRIFT REPORT")
    print("=" * 50)
    print(json.dumps(report, indent=2))

    # Drift is a *signal* for Prometheus alerts, not a job failure.
    # Exit non-zero only on real errors (unhandled exceptions above).