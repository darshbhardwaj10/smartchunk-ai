"""Structure-aware document chunking and benchmark metrics for SmartChunk AI."""
from __future__ import annotations

from collections import Counter
import re
from typing import Any

from .deduplicator import deduplicate_chunks, normalize_for_dedup
from .metadata import heading_context, make_chunk
from .semantic_chunker import semantic_split_prose
from .structure_parser import clean_text, parse_markdown_blocks

PAGE_MARKER = re.compile(r"^\s*<!--\s*smartchunk:page=(\d+)\s*-->\s*$", re.IGNORECASE)


def _validate_settings(chunk_size: int, overlap: int) -> None:
    if not isinstance(chunk_size, int) or isinstance(chunk_size, bool):
        raise ValueError("chunk_size must be an integer")
    if not 1 <= chunk_size:
        raise ValueError("chunk_size must be positive")
    if not isinstance(overlap, int) or isinstance(overlap, bool):
        raise ValueError("overlap must be an integer")
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")


def _split_words(text: str, max_chars: int) -> list[str]:
    """Split long prose at whitespace; a single overlong token is preserved."""
    words = text.split()
    if not words:
        return []
    pieces: list[str] = []
    current = ""
    for word in words:
        if len(word) > max_chars:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(word)
        elif not current or len(current) + len(word) + 1 <= max_chars:
            current = f"{current} {word}".strip()
        else:
            pieces.append(current)
            current = word
    if current:
        pieces.append(current)
    return pieces


def _split_prose(text: str, max_chars: int, overlap: int = 0) -> list[str]:
    """Split prose on sentence boundaries; overlap copies complete trailing sentences when possible."""
    text = text.strip()
    if not text:
        return []
    max_chars = max(1, max_chars)
    # Heading context reduces the real available size; cap overlap accordingly.
    overlap = max(0, min(overlap, max_chars - 1))
    if len(text) <= max_chars:
        return [text]

    sentences = [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+|\n{2,}", text)
        if part.strip()
    ] or [text]

    expanded: list[str] = []
    for sentence in sentences:
        if len(sentence) > max_chars:
            expanded.extend(_split_words(sentence, max_chars))
        else:
            expanded.append(sentence)

    chunks: list[str] = []
    current: list[str] = []
    for sentence in expanded:
        current_text = " ".join(current)
        if current and len(f"{current_text} {sentence}") > max_chars:
            chunks.append(current_text)
            carry: list[str] = []
            if overlap > 0:
                for previous in reversed(current):
                    candidate = " ".join([previous, *carry]) if carry else previous
                    if len(candidate) > overlap:
                        break
                    carry.insert(0, previous)
            current = carry
            if current and len(" ".join([*current, sentence])) > max_chars:
                current = []
        current_text = " ".join(current)
        if current and len(f"{current_text} {sentence}") > max_chars:
            chunks.append(current_text)
            current = []
        current.append(sentence)

    if current:
        final_text = " ".join(current)
        if not chunks or final_text != chunks[-1]:
            chunks.append(final_text)
    return chunks


def _semantic_or_regular_split(
    text: str,
    max_chars: int,
    overlap: int,
    semantic: bool,
) -> list[str]:
    if semantic:
        return semantic_split_prose(text, max_chars, overlap, _split_prose)
    return _split_prose(text, max_chars, overlap)


def _create_structure_chunks(
    text: str,
    filename: str,
    chunk_size: int,
    overlap: int,
    semantic: bool,
) -> list[dict[str, Any]]:
    blocks = parse_markdown_blocks(text)
    raw_chunks: list[dict[str, Any]] = []
    index = 0

    while index < len(blocks):
        block = blocks[index]
        kind = block["chunk_type"]
        path = block["heading_path"]
        page = block["page"]
        start_line = block["start_line"]
        end_line = block["end_line"]
        context = heading_context(path)
        available = max(1, chunk_size - len(context))

        if kind == "prose":
            group = [block]
            combined_length = len(block["text"])
            cursor = index + 1
            while cursor < len(blocks):
                next_block = blocks[cursor]
                if (
                    next_block["chunk_type"] != "prose"
                    or next_block["heading_path"] != path
                    or next_block["page"] != page
                ):
                    break
                addition = len(next_block["text"]) + 2
                if combined_length + addition > available:
                    break
                group.append(next_block)
                combined_length += addition
                cursor += 1

            content = "\n\n".join(item["text"] for item in group)
            pieces = _semantic_or_regular_split(content, available, overlap, semantic)
            group_end = group[-1]["end_line"]
            for piece in pieces:
                chunk_text = context + piece
                raw_chunks.append(make_chunk(
                    chunk_text,
                    filename,
                    len(raw_chunks) + 1,
                    path,
                    "prose",
                    f"lines {start_line}-{group_end}",
                    page=page,
                    oversized=len(chunk_text) > chunk_size,
                ))
            index = cursor
            continue

        # Keep table/list/code blocks intact when possible; mark them oversized otherwise.
        chunk_text = context + block["text"]
        raw_chunks.append(make_chunk(
            chunk_text,
            filename,
            len(raw_chunks) + 1,
            path,
            kind,
            f"lines {start_line}-{end_line}",
            page=page,
            oversized=len(chunk_text) > chunk_size,
        ))
        index += 1

    return deduplicate_chunks(raw_chunks, filename, remove_near_duplicates=True)


def fixed_size_chunks(
    text: str,
    filename: str,
    chunk_size: int = 700,
    overlap: int = 80,
) -> list[dict[str, Any]]:
    """Naive character-window baseline. Deliberately does not deduplicate."""
    _validate_settings(chunk_size, overlap)
    cleaned = clean_text(PAGE_MARKER.sub("", str(text or "")))
    if not cleaned:
        return []

    chunks: list[dict[str, Any]] = []
    start = 0
    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        if end < len(cleaned):
            candidates = [
                cleaned.rfind("\n", start + int(chunk_size * 0.60), end),
                cleaned.rfind(" ", start + int(chunk_size * 0.60), end),
            ]
            boundary = max(candidates)
            if boundary > start:
                end = boundary

        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(make_chunk(
                piece,
                filename,
                len(chunks) + 1,
                [],
                "prose",
                f"characters {start}-{end}",
                oversized=len(piece) > chunk_size,
            ))
        if end >= len(cleaned):
            break
        start = max(start + 1, end - overlap)
    return chunks


def chunk_document(
    text: str,
    filename: str,
    chunk_size: int = 700,
    overlap: int = 80,
    semantic: bool = False,
) -> list[dict[str, Any]]:
    """Chunk normalized Markdown while retaining structure and source metadata.

    Tables, lists and code blocks are kept intact even when their size exceeds
    chunk_size; in that case ``oversized=True`` makes the condition explicit.
    """
    _validate_settings(chunk_size, overlap)
    # Keep page markers until parse_markdown_blocks() consumes them so PDF page
    # numbers can be attached to source metadata. The parser never puts markers
    # into returned chunk text.
    cleaned = clean_text(str(text or ""))
    if not cleaned:
        return []
    return _create_structure_chunks(cleaned, filename, chunk_size, overlap, semantic)


def calculate_metrics(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate structural statistics for the chunk list (not answer accuracy)."""
    lengths = [len(str(chunk.get("text", ""))) for chunk in chunks]
    normalized = [normalize_for_dedup(str(chunk.get("text", ""))) for chunk in chunks]
    count = len(chunks)
    duplicate_count = len(normalized) - len(set(normalized))
    types = Counter(str(chunk.get("chunk_type", "unknown")) for chunk in chunks)
    return {
        "chunk_count": count,
        "average_characters": round(sum(lengths) / count, 2) if count else 0.0,
        "min_characters": min(lengths) if lengths else 0,
        "max_characters": max(lengths) if lengths else 0,
        "duplicate_rate": round(duplicate_count / count, 4) if count else 0.0,
        "total_characters": sum(lengths),
        "oversized_chunk_count": sum(bool(chunk.get("oversized")) for chunk in chunks),
        "chunk_types": dict(types),
    }