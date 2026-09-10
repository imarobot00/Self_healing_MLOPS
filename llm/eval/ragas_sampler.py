"""
Nightly Ragas evaluation on sampled production traces.

Reservoir-samples ~1% (min 3, max 10) of traces newer than the last
watermark, judges them with Groq (faithfulness, answer relevancy,
context precision), and writes monitoring/reports/ragas_latest.json
for the API to relay to Prometheus.

Usage:
    python llm/eval/ragas_sampler.py
"""

import json
import logging
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from llm.eval.shadow_runner import run_shadow_batch

load_dotenv(REPO_ROOT / ".env")  # GROQ_API_KEY, same file the assistant uses

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CONFIG = {
    "traces_dir": REPO_ROOT / "logs" / "llm_traces",
    "state_file": Path(__file__).parent / ".eval_state.json",
    "reports_dir": REPO_ROOT / "monitoring" / "reports",
    "sample_rate": 0.01,
    "min_samples": 3,
    "max_samples": 10,          # hard cap = judge-call budget per night
    "judge_model": "openai/gpt-oss-120b",  # llama-3.3-70b-versatile was decommissioned on Groq (404)
    "shadow_enabled": True,
    "challenger_version": "2.0.0",
    "canary_pct": 0,
    "shadow_pairs_dir": REPO_ROOT / "logs" / "llm_shadow",
}


def load_watermark() -> str:
    try:
        return json.loads(CONFIG["state_file"].read_text())["last_processed_ts"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return ""  # first run: everything is new


def save_watermark(ts: str) -> None:
    CONFIG["state_file"].write_text(json.dumps({
        "last_processed_ts": ts,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))


def collect_new_traces(watermark: str) -> List[Dict]:
    """All traces strictly newer than the watermark (pass 1 of two-pass sampling)."""
    traces = []
    for f in sorted(CONFIG["traces_dir"].glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                t = json.loads(line)
            except json.JSONDecodeError:
                continue
            # skip synthetic/test traffic and anything already processed
            if t.get("prompt_version") == "test":
                continue
            if t.get("ts", "") > watermark and t.get("query") and t.get("response"):
                traces.append(t)
    return traces


def reservoir_sample(stream: List[Dict], k: int, seed: int = None) -> List[Dict]:
    """Algorithm R: uniform k-sample in one pass, O(k) memory."""
    rng = random.Random(seed)
    reservoir: List[Dict] = []
    for i, item in enumerate(stream):
        if i < k:
            reservoir.append(item)
        else:
            j = rng.randint(0, i)  # accept with prob k/(i+1)
            if j < k:
                reservoir[j] = item
    return reservoir


def run_ragas(samples: List[Dict]) -> Optional[Dict[str, float]]:
    """Judge the sampled traces. Imports are lazy: ragas is heavy."""
    from ragas import evaluate, EvaluationDataset, SingleTurnSample
    from ragas.metrics import Faithfulness, ResponseRelevancy, LLMContextPrecisionWithoutReference
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from langchain_groq import ChatGroq
    from langchain_huggingface import HuggingFaceEmbeddings
    from ragas.run_config import RunConfig

    judge = LangchainLLMWrapper(ChatGroq(model=CONFIG["judge_model"], temperature=0.0))
    local_emb = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    )

    dataset = EvaluationDataset(samples=[
        SingleTurnSample(
            user_input=t["query"],
            response=t["response"],
            retrieved_contexts=[t["retrieved_context"]],
        )
        for t in samples
    ])

    result = evaluate(
        dataset=dataset,
        metrics=[Faithfulness(), ResponseRelevancy(), LLMContextPrecisionWithoutReference()],
        llm=judge,
        embeddings=local_emb,
        run_config=RunConfig(max_workers=1, max_retries=2, timeout=120),
    )

    df = result.to_pandas()
    scores = {}
    for col in df.columns:
        if df[col].dtype.kind == "f":  # metric columns are floats
            valid = df[col].dropna()   # judge failures come back as NaN
            if len(valid):
                scores[col] = round(float(valid.mean()), 4)
                scores[f"{col}_n"] = int(len(valid))
    return scores or None


def save_report(report: Dict) -> None:
    CONFIG["reports_dir"].mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    (CONFIG["reports_dir"] / f"ragas_{stamp}.json").write_text(json.dumps(report, indent=2))
    if report.get("status") == "ok":
        temporary = CONFIG["reports_dir"] / "ragas_latest.tmp"
        temporary.write_text(json.dumps(report, indent=2), encoding="utf-8")
        temporary.replace(CONFIG["reports_dir"] / "ragas_latest.json")
    logger.info(f"Report saved: ragas_{stamp}.json")


def main() -> None:
    if CONFIG["canary_pct"] != 0:
        raise ValueError("Canary routing is not implemented; canary_pct must remain 0")
    watermark = load_watermark()
    new_traces = collect_new_traces(watermark)
    logger.info(f"{len(new_traces)} new traces since watermark '{watermark or 'never'}'")

    report: Dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "judge_model": CONFIG["judge_model"],
        "num_new_traces": len(new_traces),
        "status": "ok",
    }

    if not new_traces:
        report["status"] = "no_new_traces"
        save_report(report)
        return  # exit 0: nothing to do is not a failure

    # 1% with a floor (tiny traffic still yields signal) and a ceiling (cost cap)
    k = max(CONFIG["min_samples"], math.ceil(CONFIG["sample_rate"] * len(new_traces)))
    k = min(k, CONFIG["max_samples"], len(new_traces))
    samples = reservoir_sample(new_traces, k)
    report["num_sampled"] = len(samples)
    logger.info(f"Sampled {len(samples)} of {len(new_traces)} traces for judging")

    try:
        if CONFIG["shadow_enabled"]:
            comparison = run_shadow_batch(
                samples, run_ragas, CONFIG["reports_dir"], CONFIG["shadow_pairs_dir"],
                challenger_version=CONFIG["challenger_version"],
                canary_pct=CONFIG["canary_pct"],
            )
            scores = comparison["champion_scores"]
            report["shadow_challenger_version"] = comparison["challenger_version"]
        else:
            scores = run_ragas(samples)
    except Exception:
        report["status"] = "evaluation_failed"
        save_report(report)
        raise
    if scores is None:
        report["status"] = "all_judgments_failed"
        save_report(report)
        raise RuntimeError("All judgments failed; watermark unchanged")

    report["scores"] = scores
    report["sampled_queries"] = [t["query"][:80] for t in samples]  # audit trail
    save_report(report)
    # advance the watermark over EVERYTHING seen, not just the sampled ones
    save_watermark(max(t["ts"] for t in new_traces))


if __name__ == "__main__":
    main()