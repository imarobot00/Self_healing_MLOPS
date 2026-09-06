"""
Append-only JSONL trace logger for LLM interactions.

Every call to the assistant produces one trace line in
logs/llm_traces/YYYY-MM-DD.jsonl containing the query, response,
retrieved context, query embedding, and prompt version metadata.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

DEFAULT_TRACE_DIR = Path(__file__).resolve().parent.parent / "logs" / "llm_traces"


class TraceLogger:
    def __init__(self, trace_dir: Path = DEFAULT_TRACE_DIR):
        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()  # FastAPI handles requests concurrently

    def _current_file(self) -> Path:
        """One file per day: 2026-09-03.jsonl -> natural rotation, easy cleanup."""
        return self.trace_dir / f"{datetime.now(timezone.utc).date().isoformat()}.jsonl"

    def log(
        self,
        query: str,
        response: str,
        retrieved_context: str,
        prompt_version: str,
        prompt_hash: Optional[str] = None,
        model: Optional[str] = None,
        embedding: Optional[Sequence[float]] = None,
        latency_ms: Optional[float] = None,
    ) -> dict:
        trace = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "response": response,
            "retrieved_context": retrieved_context,
            "prompt_version": prompt_version,
            "prompt_hash": prompt_hash,
            "model": model,
            "latency_ms": latency_ms,
            # np.ndarray isn't JSON-serializable; store as a plain list of floats
            "embedding": [round(float(x), 6) for x in embedding] if embedding is not None else None,
        }
        line = json.dumps(trace, ensure_ascii=False)
        with self._lock:
            with open(self._current_file(), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        return trace