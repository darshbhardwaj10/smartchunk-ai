"""A lightweight Markdown/GFM structural parser for SmartChunk.

This parser is intentionally dependency-free. It recognizes ATX headings,
fenced code blocks, simple lists, and pipe-style Markdown tables. It does not
attempt to implement the complete CommonMark specification.
"""
from __future__ import annotations

import re
from typing import Any

PAGE_MARKER = re.compile(r"^\s*<!--\s*smartchunk:page=(\d+)\s*-->\s*$", re.IGNORECASE)
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
LIST_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
TABLE_SEPARATOR_RE = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$"
)


def clean_text(text: str) -> str:
    """Normalize newlines and excessive blank lines without stripping Markdown."""
    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _classify_buffer(kind: str) -> str:
    return kind if kind in {"code", "list", "table"} else "prose"


def parse_markdown_blocks(text: str) -> list[dict[str, Any]]:
    """Parse text into heading-aware blocks.

    Each result has text, heading_path, chunk_type, start_line, end_line, and
    page. Heading lines are recorded in heading_path and are not emitted as
    standalone content chunks. The normalizer can insert page control comments
    of the form ``<!-- smartchunk:page=3 -->`` for PDF page tracking.
    """
    lines = str(text or "").splitlines()
    blocks: list[dict[str, Any]] = []
    heading_stack: list[tuple[int, str]] = []
    buffer: list[str] = []
    buffer_kind = "prose"
    start_line = 1
    current_page: int | None = None
    fence_marker: str | None = None

    def flush(end_line: int) -> None:
        nonlocal buffer
        content = "\n".join(buffer).strip()
        if content:
            blocks.append({
                "text": content,
                "heading_path": [title for _, title in heading_stack],
                "chunk_type": _classify_buffer(buffer_kind),
                "start_line": start_line,
                "end_line": max(start_line, end_line),
                "page": current_page,
            })
        buffer = []

    for line_number, line in enumerate(lines, start=1):
        page_match = PAGE_MARKER.match(line)
        if page_match and fence_marker is None:
            flush(line_number - 1)
            current_page = int(page_match.group(1))
            start_line = line_number + 1
            buffer_kind = "prose"
            continue

        fence_match = FENCE_RE.match(line)
        if fence_marker is not None:
            buffer.append(line)
            if fence_match and fence_match.group(1)[0] == fence_marker[0]:
                flush(line_number)
                fence_marker = None
                buffer_kind = "prose"
                start_line = line_number + 1
            continue

        if fence_match:
            flush(line_number - 1)
            buffer_kind = "code"
            fence_marker = fence_match.group(1)
            start_line = line_number
            buffer = [line]
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match:
            flush(line_number - 1)
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            heading_stack = [
                (old_level, old_title)
                for old_level, old_title in heading_stack
                if old_level < level
            ]
            heading_stack.append((level, title))
            buffer_kind = "prose"
            start_line = line_number + 1
            continue

        if not line.strip():
            flush(line_number - 1)
            buffer_kind = "prose"
            start_line = line_number + 1
            continue

        is_table = "|" in line or bool(TABLE_SEPARATOR_RE.match(line))
        if LIST_RE.match(line):
            line_kind = "list"
        elif is_table:
            line_kind = "table"
        else:
            line_kind = "prose"

        # Flush when switching into/out of structural groups.
        if buffer and buffer_kind != line_kind and (
            buffer_kind in {"list", "table"} or line_kind in {"list", "table"}
        ):
            flush(line_number - 1)
            start_line = line_number

        if not buffer:
            start_line = line_number
        buffer_kind = line_kind
        buffer.append(line)

    # Also flushes an unclosed code fence; treating it as code is safest.
    flush(len(lines))
    return blocks