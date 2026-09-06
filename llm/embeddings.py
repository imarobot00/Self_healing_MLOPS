"""
Shared embedding utilities for the LLM layer.

Loads a sentence-transformers model once (cached) and exposes
embed_text / embed_batch for tracing and baseline generation.
"""

from functools import lru_cache
from typing import List

import numpy as np

MODEL_NAME = "all-MiniLM-L6-v2"  # 384-dim, ~90MB, good quality/speed tradeoff

@lru_cache(maxsize=1)
def get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME)

def embed_text(text: str) -> np.ndarray:
    """Embed a single string -> 1D float32 array of shape (384,)."""
    return get_model().encode(text, normalize_embeddings=True)


def embed_batch(texts: List[str]) -> np.ndarray:
    """Embed many strings at once -> 2D array of shape (len(texts), 384)."""
    return get_model().encode(texts, normalize_embeddings=True, show_progress_bar=True)