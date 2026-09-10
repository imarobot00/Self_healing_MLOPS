"""Prometheus relay for offline shadow evaluations."""

import json
import math
from datetime import datetime
from pathlib import Path

from prometheus_client import Gauge, REGISTRY


class ShadowMetrics:
    def __init__(self, reports_dir, registry=REGISTRY):
        self.path = Path(reports_dir) / "shadow_latest.json"
        self.score = Gauge("llm_shadow_score", "Paired Ragas mean score",
                           ["variant", "metric"], registry=registry)
        self.delta = Gauge("llm_shadow_delta", "Challenger minus champion Ragas score",
                           ["metric"], registry=registry)
        self.timestamp = Gauge("llm_shadow_report_timestamp_seconds",
                               "Timestamp of last complete shadow comparison", registry=registry)
        self.pairs = Gauge("llm_shadow_pairs", "Number of fully evaluated pairs", registry=registry)
        self.timestamp.set(float("nan"))
        self.pairs.set(float("nan"))

    def update(self):
        self.score.clear()
        self.delta.clear()
        self.timestamp.set(float("nan"))
        self.pairs.set(float("nan"))
        try:
            report = json.loads(self.path.read_text(encoding="utf-8"))
            if report.get("status") != "ok":
                return
            timestamp = datetime.fromisoformat(report["timestamp"])
            if timestamp.tzinfo is None:
                return
            values = []
            for metric in ("faithfulness", "answer_relevancy", "llm_context_precision_without_reference"):
                champion = float(report["champion_scores"][metric])
                challenger = float(report["challenger_scores"][metric])
                if not all(math.isfinite(value) and 0 <= value <= 1 for value in (champion, challenger)):
                    return
                values.append((metric, champion, challenger))
            pairs = int(report["num_pairs"])
            if pairs < 1:
                return
            for metric, champion, challenger in values:
                self.score.labels("champion", metric).set(champion)
                self.score.labels("challenger", metric).set(challenger)
                self.delta.labels(metric).set(challenger - champion)
            self.timestamp.set(timestamp.timestamp())
            self.pairs.set(pairs)
        except (OSError, ValueError, TypeError, KeyError):
            return