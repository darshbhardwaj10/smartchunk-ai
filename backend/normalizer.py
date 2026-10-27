"""Convert supported office/document formats to a canonical Markdown representation."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil
from pathlib import Path
import re

from bs4 import BeautifulSoup, NavigableString, Tag
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader
import io


@dataclass
class NormalizedDocument:
    """Normalized document and diagnostics returned by the ingestion layer."""

    markdown: str
    source_format: str
    warnings: list[str] = field(default_factory=list)
    removed_repeated_margin_lines: int = 0


class NormalizationError(ValueError):
    """Raised when a supported file cannot be decoded or extracted."""


def normalize_newlines(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_line_for_repeat(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip().casefold()


def remove_repeated_pdf_margins(pages: list[str]) -> tuple[list[str], int]:
    """Remove lines repeated in page margins; do not remove repeated body text.

    Only the first two and last two non-empty lines on each page are candidates.
    A candidate must occur in the margins of at least half the pages (minimum 2).
    """
    if len(pages) < 2:
        return pages, 0

    from collections import Counter

    counts: Counter[str] = Counter()
    for page in pages:
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        candidates = set(lines[:2] + lines[-2:])
        for line in candidates:
            normalized = _normalize_line_for_repeat(line)
            if len(normalized) >= 4:
                counts[normalized] += 1

    threshold = max(2, ceil(len(pages) * 0.5))
    repeated = {line for line, count in counts.items() if count >= threshold}
    if not repeated:
        return pages, 0

    cleaned: list[str] = []
    removed = 0
    for page in pages:
        lines = page.splitlines()
        nonempty_positions = [i for i, value in enumerate(lines) if value.strip()]
        margin_positions = set(nonempty_positions[:2] + nonempty_positions[-2:])
        output = []
        for index, line in enumerate(lines):
            normalized = _normalize_line_for_repeat(line)
            if index in margin_positions and normalized in repeated:
                removed += 1
                continue
            output.append(line)
        cleaned.append("\n".join(output).strip())
    return cleaned, removed


def _table_to_markdown(rows: list[list[str]]) -> str:
    clean_rows = [[re.sub(r"\s+", " ", cell).strip().replace("|", r"\|") for cell in row] for row in rows]
    clean_rows = [row for row in clean_rows if any(cell for cell in row)]
    if not clean_rows:
        return ""
    width = max(len(row) for row in clean_rows)
    clean_rows = [row + [""] * (width - len(row)) for row in clean_rows]
    header = clean_rows[0]
    separator = ["---"] * width
    output = ["| " + " | ".join(header) + " |", "| " + " | ".join(separator) + " |"]
    output.extend("| " + " | ".join(row) + " |" for row in clean_rows[1:])
    return "\n".join(output)


def _html_table_to_markdown(table: Tag) -> str:
    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"], recursive=False)
        if cells:
            rows.append([cell.get_text(" ", strip=True) for cell in cells])
    return _table_to_markdown(rows)


def _html_list_to_markdown(tag: Tag, depth: int = 0) -> str:
    ordered = tag.name == "ol"
    lines: list[str] = []
    index = int(tag.get("start", 1) or 1)
    for li in tag.find_all("li", recursive=False):
        text_parts: list[str] = []
        nested: list[Tag] = []
        for child in li.contents:
            if isinstance(child, Tag) and child.name in {"ul", "ol"}:
                nested.append(child)
            elif isinstance(child, Tag):
                text_parts.append(child.get_text(" ", strip=True))
            elif isinstance(child, NavigableString):
                value = str(child).strip()
                if value:
                    text_parts.append(value)
        marker = f"{index}." if ordered else "-"
        lines.append("  " * depth + marker + " " + " ".join(part for part in text_parts if part))
        for child_list in nested:
            nested_md = _html_list_to_markdown(child_list, depth + 1)
            if nested_md:
                lines.append(nested_md)
        index += 1
    return "\n".join(lines)


def _html_node_to_markdown(node: Tag | NavigableString) -> str:
    if isinstance(node, NavigableString):
        value = str(node).strip()
        return value

    name = (node.name or "").lower()
    if name in {"script", "style", "noscript", "svg"}:
        return ""
    if name in {f"h{i}" for i in range(1, 7)}:
        level = int(name[1])
        value = node.get_text(" ", strip=True)
        return f"{'#' * level} {value}" if value else ""
    if name == "p":
        value = node.get_text("", strip=False).strip()
        return value
    if name in {"ul", "ol"}:
        return _html_list_to_markdown(node)
    if name == "table":
        return _html_table_to_markdown(node)
    if name == "pre":
        code_tag = node.find("code")
        value = (code_tag or node).get_text("\n", strip=False).strip("\n")
        language = ""
        if code_tag:
            for item in code_tag.get("class", []):
                if item.startswith("language-"):
                    language = item.split("-", 1)[1]
                    break
        return f"```{language}\n{value}\n```"
    if name == "blockquote":
        value = node.get_text("\n", strip=True)
        return "\n".join("> " + line for line in value.splitlines())
    if name == "br":
        return "\n"
    if name == "hr":
        return "---"
    # Containers can wrap meaningful blocks. Process their children recursively.
    values = [_html_node_to_markdown(child) for child in node.children]
    return "\n\n".join(value for value in values if value)


def html_to_markdown(raw: bytes) -> str:
    soup = BeautifulSoup(raw.decode("utf-8-sig", errors="replace"), "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    root = soup.body or soup
    blocks = [_html_node_to_markdown(child) for child in root.children]
    return normalize_newlines("\n\n".join(block for block in blocks if block))


def _docx_table_markdown(table: Table) -> str:
    rows = [[cell.text.replace("\n", " ").strip() for cell in row.cells] for row in table.rows]
    return _table_to_markdown(rows)


def docx_to_markdown(raw: bytes) -> str:
    doc = Document(io.BytesIO(raw))
    parts: list[str] = []
    body = doc.element.body
    code_buffer: list[str] = []

    def flush_code() -> None:
        nonlocal code_buffer
        if code_buffer:
            parts.append("```\n" + "\n".join(code_buffer) + "\n```")
            code_buffer = []

    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph = Paragraph(child, doc)
            text = paragraph.text.strip()
            if not text:
                continue
            style_name = (paragraph.style.name or "").lower() if paragraph.style else ""
            heading_match = re.search(r"heading\s*(\d+)", style_name)
            if heading_match:
                flush_code()
                level = min(6, max(1, int(heading_match.group(1))))
                parts.append("#" * level + " " + text)
            elif "code" in style_name or "preformatted" in style_name:
                code_buffer.append(paragraph.text)
            else:
                flush_code()
                parts.append(text)
        elif tag == "tbl":
            flush_code()
            table = Table(child, doc)
            table_md = _docx_table_markdown(table)
            if table_md:
                parts.append(table_md)
    flush_code()
    return normalize_newlines("\n\n".join(parts))


def pdf_to_markdown(raw: bytes) -> tuple[str, int, list[str]]:
    reader = PdfReader(io.BytesIO(raw))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    if not pages:
        raise NormalizationError("The PDF contains no pages.")
    cleaned_pages, removed = remove_repeated_pdf_margins(pages)
    blocks: list[str] = []
    warnings: list[str] = []
    if removed:
        warnings.append(f"Removed {removed} repeated page-margin line occurrence(s) from the PDF.")
    if all(not page for page in cleaned_pages):
        warnings.append("No selectable text was extracted. This may be a scanned PDF; OCR is not enabled.")
    for page_number, text in enumerate(cleaned_pages, start=1):
        # This marker is consumed by the chunker and is not included in chunk text.
        blocks.append(f"<!-- smartchunk:page={page_number} -->\n\n{text}".strip())
    return normalize_newlines("\n\n".join(blocks)), removed, warnings


def normalize_document(filename: str, raw: bytes) -> NormalizedDocument:
    """Convert one supported input into Markdown while preserving useful structure."""
    suffix = Path(filename).suffix.lower()
    warnings: list[str] = []
    removed_margin_lines = 0
    try:
        if suffix == ".md":
            markdown = raw.decode("utf-8-sig", errors="replace")
            source_format = "markdown"
        elif suffix == ".txt":
            markdown = raw.decode("utf-8-sig", errors="replace")
            source_format = "text"
        elif suffix in {".html", ".htm"}:
            markdown = html_to_markdown(raw)
            source_format = "html"
        elif suffix == ".docx":
            markdown = docx_to_markdown(raw)
            source_format = "docx"
        elif suffix == ".pdf":
            markdown, removed_margin_lines, pdf_warnings = pdf_to_markdown(raw)
            warnings.extend(pdf_warnings)
            source_format = "pdf"
        else:
            raise NormalizationError(f"Unsupported file format: {suffix or '(no extension)'}")
    except NormalizationError:
        raise
    except Exception as exc:  # Keep extraction details in server-side diagnostics.
        raise NormalizationError(f"Could not extract text from {suffix} file: {exc}") from exc

    markdown = normalize_newlines(markdown)
    meaningful_markdown = re.sub(r"<!--\s*smartchunk:page=\d+\s*-->", "", markdown, flags=re.IGNORECASE).strip()
    if not meaningful_markdown:
        if source_format == "pdf":
            raise NormalizationError("No selectable text was extracted from this PDF. It may be scanned and require OCR.")
        raise NormalizationError("No readable text was found in the document.")
    return NormalizedDocument(
        markdown=markdown,
        source_format=source_format,
        warnings=warnings,
        removed_repeated_margin_lines=removed_margin_lines,
    )
