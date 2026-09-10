"""Replay sampled production traces offline; never change the serving prompt."""

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

METRICS = ("faithfulness", "answer_relevancy", "llm_context_precision_without_reference")


def run_shadow_batch(samples, evaluate, reports_dir, pairs_dir, *,
                     challenger_version="2.0.0", canary_pct=0, client=None,
                     registry=None):
    if canary_pct != 0:
        raise ValueError("Canary routing is not implemented; canary_pct must remain 0")
    if not samples:
        raise ValueError("Shadow evaluation requires paired samples")
    if registry is None:
        from llm.prompt_registry import PromptRegistry
        registry = PromptRegistry()
    if client is None:
        from groq import Groq
        client = Groq(timeout=60, max_retries=2)

    prompt = registry.get_version("aqi_advisor", challenger_version)
    if prompt["version"] != challenger_version:
        raise ValueError("Challenger version does not match the requested version")
    challengers = []
    pairs = []
    for trace in samples:
        started = time.perf_counter()
        completion = client.chat.completions.create(
            model=prompt["model"], temperature=prompt["temperature"],
            messages=[
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": registry.render(
                    prompt, question=trace["query"], aqi_context=trace["retrieved_context"])},
            ],
        )
        answer = completion.choices[0].message.content
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Challenger returned an empty answer")
        challenger = dict(trace, response=answer, prompt_version=prompt["version"],
                          prompt_hash=prompt["hash"], model=prompt["model"],
                          latency_ms=round((time.perf_counter() - started) * 1000, 1))
        challengers.append(challenger)
        pairs.append({"champion": trace, "challenger": challenger, "served": False})

    timestamp = datetime.now(timezone.utc)
    stamp = timestamp.strftime("%Y%m%dT%H%M%S%fZ")
    pairs_dir = Path(pairs_dir)
    pairs_dir.mkdir(parents=True, exist_ok=True)
    with (pairs_dir / f"shadow_{stamp}.jsonl").open("x", encoding="utf-8") as handle:
        for pair in pairs:
            handle.write(json.dumps(pair, ensure_ascii=False, allow_nan=False) + "\n")

    champion_scores = evaluate(samples)
    challenger_scores = evaluate(challengers)
    for scores in (champion_scores, challenger_scores):
        if not scores or any(
            metric not in scores or not math.isfinite(scores[metric])
            or scores.get(f"{metric}_n") != len(samples)
            for metric in METRICS
        ):
            raise RuntimeError("Incomplete paired evaluation; watermark must not advance")
    report = {
        "timestamp": timestamp.isoformat(), "status": "ok", "mode": "offline_shadow",
        "canary_pct": canary_pct, "num_pairs": len(samples),
        "champion_versions": sorted({trace["prompt_version"] for trace in samples}),
        "challenger_version": prompt["version"], "challenger_hash": prompt["hash"],
        "challenger_model": prompt["model"],
        "champion_scores": champion_scores, "challenger_scores": challenger_scores,
        "delta": {metric: round(challenger_scores[metric] - champion_scores[metric], 4)
                  for metric in METRICS},
    }
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, allow_nan=False)
    (reports_dir / f"shadow_{stamp}.json").write_text(payload, encoding="utf-8")
    temporary = reports_dir / f".shadow_{stamp}.tmp"
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(reports_dir / "shadow_latest.json")
    return report