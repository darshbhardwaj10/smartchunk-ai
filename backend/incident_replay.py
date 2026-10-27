"""Re-run a recorded chunking/validation case against its saved normalized snapshot.

This replay reproduces normalization-output -> chunking -> local validation. It does
not reproduce the original PDF/DOCX extraction unless raw source bytes are separately
and securely retained in a future version of the system.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.safesync import build_validation_report
from backend.storage import SmartChunkStore
from chunking_engine.chunker import chunk_document, fixed_size_chunks
from backend.retrieval import retrieve_chunks, tokenize


def _chunk_signature(chunks: list[dict[str, Any]]) -> str:
    stable_fields = []
    for chunk in chunks:
        stable_fields.append({
            "chunk_id": chunk.get("chunk_id"),
            "text": chunk.get("text"),
            "heading_path": chunk.get("heading_path", []),
            "chunk_type": chunk.get("chunk_type"),
            "source": chunk.get("source", {}),
            "parent_id": chunk.get("parent_id"),
            "oversized": bool(chunk.get("oversized", False)),
        })
    raw = json.dumps(stable_fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def replay_incident(store: SmartChunkStore, incident_id: str) -> dict[str, Any]:
    incident = store.get_incident(incident_id)
    if not incident:
        raise KeyError(f"Unknown incident_id: {incident_id}")
    version = store.get_version(incident["version_id"])
    if not version:
        raise KeyError("The source version for this incident is missing.")

    markdown = str(version.get("normalized_markdown") or "")
    config = incident.get("config") or {}
    strategy = str(config.get("strategy") or version.get("strategy") or "structure")
    chunk_size = int(config.get("chunk_size") or version.get("chunk_size") or 700)
    overlap = int(config.get("overlap") if config.get("overlap") is not None else version.get("overlap", 80))
    semantic = bool(config.get("semantic", version.get("semantic", False)))
    if strategy not in {"fixed", "structure"}:
        raise ValueError("Incident strategy must be 'fixed' or 'structure'.")
    if chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Recorded chunk settings are invalid.")

    filename = str(version.get("filename") or "replay.md")
    if strategy == "fixed":
        replayed_chunks = fixed_size_chunks(markdown, filename, chunk_size, overlap)
    else:
        replayed_chunks = chunk_document(markdown, filename, chunk_size, overlap, semantic=semantic)

    recorded_chunks = store.get_chunks(version["version_id"])
    same_as_saved = _chunk_signature(replayed_chunks) == _chunk_signature(recorded_chunks)
    integrity_report = build_validation_report(version, replayed_chunks)
    details = incident.get("details") or {}
    checks = list(integrity_report["checks"])

    must_contain = [str(item) for item in details.get("must_contain", []) if str(item)]
    must_not_contain = [str(item) for item in details.get("must_not_contain", []) if str(item)]
    all_text = "\n".join(str(chunk.get("text", "")) for chunk in replayed_chunks).casefold()
    for expected in must_contain:
        checks.append({
            "check": f"required_text:{expected[:80]}",
            "passed": expected.casefold() in all_text,
            "details": "Required text must remain represented in replayed chunks.",
        })
    for forbidden in must_not_contain:
        checks.append({
            "check": f"forbidden_text_absent:{forbidden[:80]}",
            "passed": forbidden.casefold() not in all_text,
            "details": "Forbidden/stale text must not appear in replayed chunks.",
        })

    question = str(details.get("question") or "").strip()
    required_evidence_terms = [str(item) for item in details.get("required_evidence_terms", []) if str(item)]
    if question and required_evidence_terms:
        top_k = max(1, min(int(details.get("top_k", 4)), 20))
        ranked = retrieve_chunks(question, replayed_chunks, top_k=top_k)
        retrieved_text = "\n".join(str(chunk.get("text", "")) for chunk in ranked).casefold()
        missing_terms = [term for term in required_evidence_terms if term.casefold() not in retrieved_text]
        checks.append({
            "check": "required_evidence_retrieved",
            "passed": not missing_terms,
            "details": {"top_k": top_k, "missing_terms": missing_terms, "retrieved_chunk_ids": [item.get("chunk_id") for item in ranked]},
        })

    failed = [check for check in checks if not check.get("passed")]
    report = {
        "incident_id": incident_id,
        "document_id": incident["document_id"],
        "version_id": version["version_id"],
        "strategy": strategy,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "semantic": semantic,
        "same_as_saved_chunk_output": same_as_saved,
        "replayed_chunk_count": len(replayed_chunks),
        "checks": checks,
        "failed_checks": [check["check"] for check in failed],
        "resolved": not failed,
        "note": "A matching chunk signature indicates deterministic reproduction under this runtime; it does not reproduce original binary extraction or prove factual correctness.",
    }
    replay_id = store.save_replay_run(incident_id, report)
    report["replay_id"] = replay_id
    return report
