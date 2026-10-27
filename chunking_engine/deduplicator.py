"""Exact and conservative near-duplicate removal for chunk objects."""
from __future__ import annotations

import hashlib
import re
from typing import Any


def normalize_for_dedup(text: str) -> str:
    """Normalize content for duplicate comparison, ignoring injected section text."""
    value = str(text or "").strip()
    value = re.sub(r"^Section:[^\n]*\n\n", "", value, flags=re.IGNORECASE)
    return re.sub(r"\W+", " ", value.casefold(), flags=re.UNICODE).strip()


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def deduplicate_chunks(
    chunks: list[dict[str, Any]],
    filename: str,
    *,
    remove_near_duplicates: bool = True,
    near_duplicate_threshold: float = 0.96,
    near_duplicate_min_chars: int = 120,
) -> list[dict[str, Any]]:
    """Remove exact duplicates; optionally drop very similar chunks in same type/section.

    Near-duplicate checking uses Jaccard similarity over unique word tokens. It is
    deliberately conservative and is not a semantic guarantee. It only compares
    chunks with the same chunk type and heading path.
    """
    if not 0.0 <= near_duplicate_threshold <= 1.0:
        raise ValueError("near_duplicate_threshold must be between 0 and 1")
    if near_duplicate_min_chars < 1:
        raise ValueError("near_duplicate_min_chars must be positive")

    from .metadata import safe_stem

    kept: list[dict[str, Any]] = []
    exact_seen: set[str] = set()
    near_candidates: dict[tuple[str, tuple[str, ...]], list[set[str]]] = {}

    for original in chunks:
        normalized = normalize_for_dedup(original.get("text", ""))
        if not normalized:
            continue

        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        if digest in exact_seen:
            continue

        chunk_type = str(original.get("chunk_type", "prose"))
        heading_path = tuple(str(item) for item in original.get("heading_path", []))
        key = (chunk_type, heading_path)
        tokens = set(normalized.split())
        is_near_duplicate = False

        if remove_near_duplicates and len(normalized) >= near_duplicate_min_chars and tokens:
            for previous_tokens in near_candidates.get(key, [])[-100:]:
                if _jaccard(tokens, previous_tokens) >= near_duplicate_threshold:
                    is_near_duplicate = True
                    break
        if is_near_duplicate:
            continue

        exact_seen.add(digest)
        chunk = dict(original)
        chunk["chunk_id"] = f"{safe_stem(filename)}_chunk_{len(kept) + 1:03d}"
        chunk["char_count"] = len(str(chunk.get("text", "")))
        # Ensure all chunks meet the common schema even if a caller omits fields.
        chunk.setdefault("heading_path", [])
        chunk.setdefault("chunk_type", "prose")
        chunk.setdefault("source", {"file": filename, "location": "unknown"})
        chunk.setdefault("parent_id", None)
        chunk.setdefault("oversized", False)
        kept.append(chunk)

        if remove_near_duplicates and len(normalized) >= near_duplicate_min_chars and tokens:
            near_candidates.setdefault(key, []).append(tokens)

    return kept