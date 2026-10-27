"""Dependency-free lexical retrieval (BM25-style) over a single document's chunks.

This is a useful offline MVP retriever, not a replacement for evaluating embeddings,
hybrid retrieval, reranking, or domain-specific ranking on the team's corpus.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

TOKEN_RE = re.compile(r"[\w]+(?:['’-][\w]+)*", flags=re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_RE.findall(str(text or ""))]


def _chunk_document(chunk: dict[str, Any]) -> str:
    heading = " ".join(str(part) for part in (chunk.get("heading_path") or []))
    source = chunk.get("source") or {}
    return " ".join(
        part for part in [heading, str(chunk.get("text", "")), str(source.get("file", ""))] if part
    )


def retrieve_chunks(question: str, chunks: list[dict[str, Any]], top_k: int = 4) -> list[dict[str, Any]]:
    """Return top-k chunks ranked by a lightweight BM25-style lexical score."""
    query_tokens = tokenize(question)
    if not query_tokens or not chunks:
        return []
    top_k = max(1, min(int(top_k), 20))

    documents = [_chunk_document(chunk) for chunk in chunks]
    tokenized = [tokenize(document) for document in documents]
    lengths = [len(tokens) for tokens in tokenized]
    average_length = sum(lengths) / max(1, len(lengths))
    doc_freq: Counter[str] = Counter()
    term_counts = [Counter(tokens) for tokens in tokenized]
    for tokens in tokenized:
        doc_freq.update(set(tokens))

    k1 = 1.5
    b = 0.75
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for index, chunk in enumerate(chunks):
        score = 0.0
        counts = term_counts[index]
        doc_len = lengths[index]
        for term in query_tokens:
            frequency = counts.get(term, 0)
            if not frequency:
                continue
            idf = math.log(1 + (len(chunks) - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            denominator = frequency + k1 * (1 - b + b * doc_len / max(1.0, average_length))
            score += idf * (frequency * (k1 + 1)) / denominator
        if score > 0:
            item = dict(chunk)
            item["retrieval_score"] = round(score, 6)
            scored.append((score, index, item))

    scored.sort(key=lambda row: (-row[0], row[1]))
    return [item for _, _, item in scored[:top_k]]
