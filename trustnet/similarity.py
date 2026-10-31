"""PR text similarity, with optional local embeddings and an offline baseline."""

import numpy as np
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BATCH = 32  # texts per Ollama request, so a large network does not hit one request timeout


def _keyword_matrix(texts):
    try:
        features = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b").fit_transform(texts)
        return cosine_similarity(features)
    except ValueError as exc:
        if "empty vocabulary" not in str(exc):
            raise
        return np.zeros((len(texts), len(texts)))


def _embedding_matrix(texts):
    """Cosine matrix from nomic-embed-text via a local Ollama server, or None if it is unavailable."""
    try:
        vectors = []
        for start in range(0, len(texts), BATCH):
            response = requests.post(
                "http://localhost:11434/api/embed",
                json={"model": "nomic-embed-text", "input": texts[start:start + BATCH]},
                timeout=(2, 30),
            )
            response.raise_for_status()
            # Verified locally: /api/embed returned {"embeddings": [[float, ...], ...]},
            # shape (n, 768) for n nomic-embed-text inputs (2026-10-31).
            vectors.extend(response.json()["embeddings"])
        vectors = np.asarray(vectors, dtype=float)
        if (vectors.ndim != 2 or vectors.shape[0] != len(texts)
                or vectors.shape[1] == 0 or not np.isfinite(vectors).all()
                or np.any(np.linalg.norm(vectors, axis=1) == 0)):
            raise ValueError("invalid Ollama embedding batch")
        return np.clip(cosine_similarity(vectors), 0, 1)
    except Exception:
        # Model/HTTP/JSON errors must not stop the offline detector.
        return None


def similarity_matrices(texts, use_embeddings=True):
    """Return (keyword matrix, embedding matrix or None). Both are NxN cosine matrices.

    They are kept apart because the two scores run on different scales: reworded text scores near 0
    with keywords but about 0.7 to 0.9 with the model, so each gets its own threshold.
    """
    texts = list(texts)
    if not all(isinstance(text, str) for text in texts):
        raise TypeError("texts must contain strings")
    if not texts:
        return np.empty((0, 0)), None
    keyword = _keyword_matrix(texts)
    return keyword, (_embedding_matrix(texts) if use_embeddings else None)


def similarity_matrix(texts, use_embeddings=True):
    """Return an NxN matrix (the higher of the two scores) and whether the embedding batch worked."""
    keyword, embedding = similarity_matrices(texts, use_embeddings)
    if embedding is None:
        return keyword, False
    return np.maximum(keyword, embedding), True
