"""Local candidate validation and release gate for SmartChunk SafeSync."""
from __future__ import annotations

from typing import Any

from backend.storage import SmartChunkStore


def build_validation_report(version: dict[str, Any], chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Create deterministic checks; no LLM or external service is used here."""
    markdown = str(version.get("normalized_markdown") or "")
    normalization = version.get("normalization") or {}
    warnings = list(normalization.get("warnings") or [])

    nonempty_chunks = [chunk for chunk in chunks if str(chunk.get("text", "")).strip()]
    missing_source = []
    missing_ids = []
    for index, chunk in enumerate(chunks):
        source = chunk.get("source") or {}
        if not chunk.get("chunk_id"):
            missing_ids.append(index)
        if not source.get("file") or not source.get("location"):
            missing_source.append(str(chunk.get("chunk_id") or index))

    checks = [
        {
            "check": "normalized_content_present",
            "passed": bool(markdown.strip()),
            "details": "Normalized Markdown must not be empty.",
        },
        {
            "check": "chunks_present",
            "passed": bool(chunks),
            "details": "At least one chunk must be generated.",
        },
        {
            "check": "chunk_text_present",
            "passed": len(nonempty_chunks) == len(chunks),
            "details": f"{len(nonempty_chunks)} of {len(chunks)} chunks contain text.",
        },
        {
            "check": "chunk_ids_present",
            "passed": not missing_ids,
            "details": f"Chunks missing IDs at positions: {missing_ids[:20]}" if missing_ids else "All chunks have IDs.",
        },
        {
            "check": "source_metadata_present",
            "passed": not missing_source,
            "details": f"Chunks missing source filename/location: {missing_source[:20]}" if missing_source else "All chunks include source filename and location.",
        },
        {
            "check": "no_known_empty_pdf_extraction",
            "passed": not any("no selectable text was extracted" in str(item).casefold() for item in warnings),
            "details": "Scanned PDFs without extracted text must be reviewed before publication.",
        },
    ]
    failures = [item for item in checks if not item["passed"]]
    oversized = sum(bool(chunk.get("oversized")) for chunk in chunks)
    return {
        "passed": not failures,
        "status": "PASS" if not failures else "BLOCK",
        "checks": checks,
        "failed_checks": [item["check"] for item in failures],
        "normalization_warnings": warnings,
        "oversized_chunk_count": oversized,
        "chunk_count": len(chunks),
        "note": "This prototype validates basic processing invariants; it is not a proof of factual correctness or complete security.",
    }


def validate_candidate(store: SmartChunkStore, version_id: str) -> dict[str, Any]:
    version = store.get_version(version_id)
    if not version:
        raise KeyError(f"Unknown version_id: {version_id}")
    if version["status"] not in {"candidate", "blocked", "validated"}:
        raise ValueError("Only an unpublished candidate can be validated.")
    chunks = store.get_chunks(version_id)
    report = build_validation_report(version, chunks)
    store.save_validation(version_id, report)
    return {"version_id": version_id, **report}


def publish_candidate(store: SmartChunkStore, version_id: str) -> dict[str, Any]:
    try:
        version = store.publish_version(version_id)
    except KeyError:
        raise
    except ValueError:
        raise
    return {
        "document_id": version["document_id"],
        "version_id": version["version_id"],
        "status": version["status"],
        "published": True,
        "message": "Validated version is now active.",
    }
