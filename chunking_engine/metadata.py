"""Creation and formatting of the common SmartChunk chunk schema."""
from __future__ import annotations

import re
from typing import Any


def safe_stem(filename: str) -> str:
    """Return a filesystem-safe, readable ID prefix derived from a filename."""
    name = str(filename or "document").replace("\\", "/").rsplit("/", 1)[-1]
    stem = name.rsplit(".", 1)[0] if "." in name else name
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_")
    return (stem or "document")[:40]


def heading_context(heading_path: list[str]) -> str:
    """Add the heading path to chunk text to make isolated chunks more contextual."""
    clean_path = [str(item).strip() for item in heading_path if str(item).strip()]
    if not clean_path:
        return ""
    return "Section: " + " > ".join(clean_path) + "\n\n"


def make_chunk(
    text: str,
    filename: str,
    number: int,
    heading_path: list[str] | None,
    chunk_type: str,
    location: str,
    page: int | None = None,
    oversized: bool = False,
) -> dict[str, Any]:
    """Create a chunk object that follows API_CONTRACT.md."""
    source: dict[str, Any] = {
        "file": str(filename),
        "location": str(location),
    }
    if page is not None:
        source["page"] = page

    value = str(text)
    return {
        "chunk_id": f"{safe_stem(filename)}_chunk_{number:03d}",
        "text": value,
        "heading_path": list(heading_path or []),
        "chunk_type": str(chunk_type),
        "source": source,
        "parent_id": None,
        "char_count": len(value),
        "oversized": bool(oversized),
    }