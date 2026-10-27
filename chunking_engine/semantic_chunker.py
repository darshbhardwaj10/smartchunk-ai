"""Optional embedding-based splitting for prose blocks.

Install the optional dependencies from requirements-semantic.txt to enable this
module. The default structure-aware pipeline does not need an embedding model.
"""
from __future__ import annotations

from functools import lru_cache
import re
from collections.abc import Callable


@lru_cache(maxsize=1)
def load_embedding_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ImportError(
            "Semantic mode requires sentence-transformers. Install the optional "
            "dependencies from requirements-semantic.txt; the first run downloads a model."
        ) from exc
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def semantic_split_prose(
    text: str,
    max_chars: int,
    overlap: int,
    fallback_splitter: Callable[[str, int, int], list[str]],
    similarity_threshold: float = 0.42,
) -> list[str]:
    """Group neighboring sentences when embedding similarity is sufficiently high.

    Structural blocks are passed into this function only when they are prose.
    Similarity is a boundary hint; max_chars is still enforced by fallback_splitter.
    """
    if not 0.0 <= similarity_threshold <= 1.0:
        raise ValueError("similarity_threshold must be between 0 and 1")

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|\n{2,}", str(text).strip())
        if sentence.strip()
    ]
    if len(sentences) < 2:
        return fallback_splitter(text, max_chars, overlap)

    model = load_embedding_model()
    embeddings = model.encode(
        sentences,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    groups: list[str] = []
    current = sentences[0]
    for index in range(1, len(sentences)):
        sentence = sentences[index]
        # SentenceTransformer returns normalized vectors, so dot product approximates cosine similarity.
        similarity = float(embeddings[index - 1] @ embeddings[index])
        fits = len(current) + len(sentence) + 1 <= max_chars
        if fits and similarity >= similarity_threshold:
            current += " " + sentence
        else:
            groups.extend(fallback_splitter(current, max_chars, overlap))
            current = sentence
    if current:
        groups.extend(fallback_splitter(current, max_chars, overlap))
    return groups