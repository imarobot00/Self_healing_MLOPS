import json
import tempfile
import unittest
from pathlib import Path

from prometheus_client import CollectorRegistry, generate_latest
from api.llm_report_metrics import ShadowMetrics


class ShadowMetricsTests(unittest.TestCase):
    def test_valid_missing_and_corrupt_report(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = CollectorRegistry()
            metrics = ShadowMetrics(directory, registry)
            metrics.update()
            self.assertIn("llm_shadow_pairs NaN", generate_latest(registry).decode())
            scores = {metric: 0.5 for metric in (
                "faithfulness", "answer_relevancy", "llm_context_precision_without_reference")}
            report = {"status": "ok", "timestamp": "2026-09-10T00:00:00+00:00",
                      "num_pairs": 3, "champion_scores": scores, "challenger_scores": scores}
            path = Path(directory) / "shadow_latest.json"
            path.write_text(json.dumps(report))
            metrics.update()
            output = generate_latest(registry).decode()
            self.assertIn('llm_shadow_delta{metric="faithfulness"} 0.0', output)
            self.assertIn("llm_shadow_pairs 3.0", output)
            path.write_text("{")
            metrics.update()
            self.assertIn("llm_shadow_pairs NaN", generate_latest(registry).decode())
            self.assertNotIn('llm_shadow_score{', generate_latest(registry).decode())


if __name__ == "__main__":
    unittest.main()