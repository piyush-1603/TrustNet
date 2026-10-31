"""PR text similarity, with optional local embeddings and an offline baseline."""

import numpy as np
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def similarity_matrix(texts, use_embeddings=True):
    """Return an NxN cosine matrix and whether the entire embedding batch worked."""
    texts = list(texts)
    if not all(isinstance(text, str) for text in texts):
        raise TypeError("texts must contain strings")
    if not texts:
        return np.empty((0, 0)), False
    try:
        features = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b").fit_transform(texts)
        baseline = cosine_similarity(features)
    except ValueError as exc:
        if "empty vocabulary" not in str(exc):
            raise
        baseline = np.zeros((len(texts), len(texts)))
    if not use_embeddings:
        return baseline, False
    try:
        response = requests.post(
            "http://localhost:11434/api/embed",
            json={"model": "nomic-embed-text", "input": texts},
            timeout=(2, 10),
        )
        response.raise_for_status()
        # /api/embed returns {"embeddings": [[float, ...], ...]}, one row per input.
        vectors = np.asarray(response.json()["embeddings"], dtype=float)
        if (vectors.ndim != 2 or vectors.shape[0] != len(texts)
                or vectors.shape[1] == 0 or not np.isfinite(vectors).all()
                or np.any(np.linalg.norm(vectors, axis=1) == 0)):
            raise ValueError("invalid Ollama embedding batch")
        return np.maximum(baseline, np.clip(cosine_similarity(vectors), 0, 1)), True
    except Exception:
        # Model/HTTP/JSON errors must not stop the offline detector.
        return baseline, False
