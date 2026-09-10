import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch

from llm.eval.shadow_runner import METRICS, run_shadow_batch
from llm.prompt_registry import PromptRegistry


class ShadowRunnerTests(unittest.TestCase):
    def test_sampler_preserves_watermark_on_shadow_failure(self):
        from llm.eval import ragas_sampler
        trace = {"query": "AQI?", "response": "Unknown", "ts": "2026-09-10T00:00:00Z"}
        with patch.object(ragas_sampler, "load_watermark", return_value=""), \
             patch.object(ragas_sampler, "collect_new_traces", return_value=[trace]), \
             patch.object(ragas_sampler, "run_shadow_batch", side_effect=RuntimeError("failed")), \
             patch.object(ragas_sampler, "save_report"), \
             patch.object(ragas_sampler, "save_watermark") as save:
            with self.assertRaises(RuntimeError):
                ragas_sampler.main()
            save.assert_not_called()

    def test_idle_report_preserves_last_scores(self):
        from llm.eval import ragas_sampler
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(ragas_sampler.CONFIG, reports_dir=Path(directory)):
            ragas_sampler.save_report({"status": "ok", "scores": {"faithfulness": 0.5}})
            previous = (Path(directory) / "ragas_latest.json").read_text()
            ragas_sampler.save_report({"status": "no_new_traces"})
            self.assertEqual((Path(directory) / "ragas_latest.json").read_text(), previous)

    def test_paired_replay_preserves_production(self):
        registry = PromptRegistry()
        production = registry.get_production_version("aqi_advisor")
        trace = {"query": "Can I run?", "retrieved_context": "PM2.5: 82 ug/m3",
                 "response": "Original answer", "prompt_version": production}
        client = Mock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Shadow answer"))])
        scores = {metric: 0.5 for metric in METRICS}
        scores.update({f"{metric}_n": 1 for metric in METRICS})
        evaluate = Mock(return_value=scores)
        with tempfile.TemporaryDirectory() as directory:
            report = run_shadow_batch([trace], evaluate, directory, directory,
                                      client=client, registry=registry)
            self.assertEqual(report["num_pairs"], 1)
            self.assertEqual(report["delta"]["faithfulness"], 0)
            self.assertTrue((Path(directory) / "shadow_latest.json").exists())
            self.assertEqual(len(list(Path(directory).glob("*.jsonl"))), 1)
        challenger = evaluate.call_args_list[1].args[0][0]
        self.assertEqual(challenger["retrieved_context"], trace["retrieved_context"])
        self.assertEqual(challenger["response"], "Shadow answer")
        self.assertEqual(trace["response"], "Original answer")
        self.assertEqual(registry.get_production_version("aqi_advisor"), production)

    def test_canary_is_rejected_before_any_calls(self):
        with self.assertRaisesRegex(ValueError, "canary_pct"):
            run_shadow_batch([], Mock(), ".", ".", canary_pct=5)

    def test_failed_judging_does_not_publish_success(self):
        client = Mock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Shadow"))])
        trace = {"query": "AQI?", "retrieved_context": "No data",
                 "response": "Unknown", "prompt_version": "1.0.0"}
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "Incomplete"):
                run_shadow_batch([trace], Mock(return_value=None), directory, directory,
                                 client=client)
            self.assertFalse((Path(directory) / "shadow_latest.json").exists())


if __name__ == "__main__":
    unittest.main()