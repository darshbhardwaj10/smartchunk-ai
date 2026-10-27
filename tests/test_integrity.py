"""Source-to-chunk lineage and SafeSync integrity checks."""
from __future__ import annotations

from backend.safesync import build_validation_report
from chunking_engine.chunker import chunk_document


SOURCE = """# Equipment Guide

## Return process

Every returned device must be inspected for damage before it is checked back into inventory.

The technician must record the asset tag and return date in the service log.

| Field | Required |
|---|---|
| Asset tag | Yes |
| Return date | Yes |
"""


def _version(markdown: str) -> dict:
    return {
        "normalized_markdown": markdown,
        "normalization": {"warnings": [], "source_format": "markdown"},
    }


def test_every_source_anchor_is_preserved_in_one_or_more_chunks():
    chunks = chunk_document(SOURCE, "equipment.md", chunk_size=260, overlap=20)
    joined = "\n".join(chunk["text"] for chunk in chunks)

    assert chunks
    assert "inspected for damage" in joined
    assert "asset tag and return date" in joined
    assert "| Asset tag | Yes |" in joined
    assert "| Return date | Yes |" in joined


def test_each_chunk_has_source_file_location_and_unique_id():
    chunks = chunk_document(SOURCE, "equipment.md", chunk_size=260, overlap=20)
    ids = [chunk["chunk_id"] for chunk in chunks]

    assert len(ids) == len(set(ids))
    assert all(chunk["text"].strip() for chunk in chunks)
    assert all(chunk["source"]["file"] == "equipment.md" for chunk in chunks)
    assert all(chunk["source"].get("location") for chunk in chunks)
    assert all(chunk["char_count"] == len(chunk["text"]) for chunk in chunks)


def test_safe_validation_passes_for_well_formed_source_chunks():
    chunks = chunk_document(SOURCE, "equipment.md", chunk_size=260, overlap=20)
    report = build_validation_report(_version(SOURCE), chunks)

    assert report["passed"] is True
    assert report["status"] == "PASS"
    assert report["failed_checks"] == []


def test_safe_validation_blocks_chunks_missing_ids_and_source_metadata():
    malformed_chunks = [{"chunk_id": "", "text": "Some extracted content", "source": {}}]
    report = build_validation_report(_version("# Source\n\nSome extracted content."), malformed_chunks)

    assert report["passed"] is False
    assert report["status"] == "BLOCK"
    assert "chunk_ids_present" in report["failed_checks"]
    assert "source_metadata_present" in report["failed_checks"]


def test_safe_validation_blocks_empty_normalized_source_and_missing_chunks():
    report = build_validation_report(
        {"normalized_markdown": "  ", "normalization": {"warnings": []}},
        [],
    )

    assert report["passed"] is False
    assert "normalized_content_present" in report["failed_checks"]
    assert "chunks_present" in report["failed_checks"]


def test_pdf_page_marker_moves_to_source_metadata_not_chunk_text():
    markdown = "<!-- smartchunk:page=4 -->\n\n# Warranty\n\nRetain this record for two years."
    chunks = chunk_document(markdown, "warranty.pdf", chunk_size=250, overlap=20)

    assert chunks
    assert all("smartchunk:page=" not in chunk["text"] for chunk in chunks)
    assert any(chunk["source"].get("page") == 4 for chunk in chunks)
