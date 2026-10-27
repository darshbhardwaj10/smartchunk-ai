"""SmartChunk AI API: normalization, chunking, Q&A, SafeSync and incident replay."""
from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.incident_replay import replay_incident
from backend.normalizer import NormalizationError, NormalizedDocument, normalize_document
from backend.qa import QANotReadyError, answer_question
from backend.safesync import publish_candidate, validate_candidate
from backend.storage import STORE
from chunking_engine.chunker import calculate_metrics, chunk_document, fixed_size_chunks

APP_VERSION = "1.1.0"
ALLOWED_EXTENSIONS = {".txt", ".md", ".html", ".htm", ".pdf", ".docx"}
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _max_upload_bytes() -> int:
    try:
        megabytes = int(os.getenv("SMARTCHUNK_MAX_UPLOAD_MB", "10"))
    except ValueError:
        megabytes = 10
    return max(1, min(megabytes, 100)) * 1024 * 1024


def _allowed_origins() -> list[str]:
    raw = os.getenv(
        "SMARTCHUNK_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(
    title="SmartChunk AI API",
    description="Document normalization, chunking, document Q&A, SafeSync validation and incident replay.",
    version=APP_VERSION,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


async def _read_upload(upload: UploadFile) -> tuple[str, bytes]:
    """Read an upload with a size limit and sanitize its displayed filename."""
    original_name = upload.filename or "uploaded_document.txt"
    filename = PurePosixPath(original_name.replace("\\", "/")).name
    if not filename or filename in {".", ".."}:
        raise HTTPException(status_code=400, detail="A valid filename is required.")
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(status_code=415, detail=f"Unsupported file type. Allowed: {allowed}")
    max_bytes = _max_upload_bytes()
    contents = bytearray()
    try:
        while True:
            block = await upload.read(64 * 1024)
            if not block:
                break
            contents.extend(block)
            if len(contents) > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"File is too large. Maximum upload size is {max_bytes // (1024 * 1024)} MB.",
                )
    finally:
        await upload.close()
    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    return filename, bytes(contents)


async def _normalize_upload(upload: UploadFile) -> tuple[str, bytes, NormalizedDocument]:
    filename, raw = await _read_upload(upload)
    try:
        normalized = normalize_document(filename, raw)
    except NormalizationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filename, raw, normalized


def _validate_chunk_settings(chunk_size: int, overlap: int) -> None:
    if not 200 <= chunk_size <= 2000:
        raise HTTPException(status_code=422, detail="chunk_size must be between 200 and 2000 characters.")
    if not 0 <= overlap <= min(400, chunk_size - 1):
        raise HTTPException(status_code=422, detail="overlap must be 0–400 and smaller than chunk_size.")


def _normalization_info(normalized: NormalizedDocument) -> dict[str, Any]:
    return {
        "source_format": normalized.source_format,
        "intermediate_format": "markdown",
        "warnings": list(normalized.warnings),
        "removed_repeated_margin_lines": normalized.removed_repeated_margin_lines,
        "normalized_character_count": len(normalized.markdown),
    }


def _recommend_strategy(markdown: str) -> dict[str, Any]:
    headings = len(re.findall(r"(?m)^\s{0,3}#{1,6}\s+\S", markdown))
    list_items = len(re.findall(r"(?m)^\s*(?:[-*+]|\d+[.)])\s+", markdown))
    table_rows = sum(1 for line in markdown.splitlines() if line.strip().startswith("|") and line.strip().endswith("|"))
    has_code = "```" in markdown or "~~~" in markdown
    features = []
    if headings:
        features.append(f"{headings} heading(s)")
    if table_rows >= 3:
        features.append("Markdown table")
    if list_items >= 2:
        features.append("List items")
    if has_code:
        features.append("Fenced code block")
    if features:
        return {"strategy": "structure", "detected_features": features,
                "reason": "Recognizable structural elements were detected; structure-aware chunking is suggested."}
    return {"strategy": "fixed", "detected_features": [],
            "reason": "Few recognizable Markdown structure markers were detected; fixed-size chunking is a reasonable baseline."}


def _chunk(normalized: NormalizedDocument, filename: str, strategy: str,
           chunk_size: int, overlap: int, semantic: bool) -> list[dict[str, Any]]:
    try:
        if strategy == "fixed":
            return fixed_size_chunks(normalized.markdown, filename, chunk_size, overlap)
        return chunk_document(normalized.markdown, filename, chunk_size, overlap, semantic=semantic)
    except ImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class QARequest(BaseModel):
    document_id: str = Field(min_length=5, max_length=80)
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=4, ge=1, le=10)


class IncidentCreateRequest(BaseModel):
    document_id: str = Field(min_length=5, max_length=80)
    version_id: str = Field(min_length=5, max_length=80)
    failure_type: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=1000)
    config: dict[str, Any] = Field(default_factory=dict)
    details: dict[str, Any] = Field(default_factory=dict)


class IncidentCreateResponse(BaseModel):
    incident_id: str
    status: str = "open"


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "name": "SmartChunk AI API",
        "version": APP_VERSION,
        "health": "/health",
        "docs": "/docs",
        "features": ["normalize", "process", "benchmark", "qa", "safesync", "incident_replay"],
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "smartchunk-ai", "version": APP_VERSION}


@app.post("/normalize")
async def normalize_endpoint(file: UploadFile = File(...)) -> dict[str, Any]:
    """Return a bounded Markdown preview and a simple, rule-based recommendation."""
    filename, _, normalized = await _normalize_upload(file)
    preview_limit = 20_000
    return {
        "filename": filename,
        "normalization": _normalization_info(normalized),
        "markdown_preview": normalized.markdown[:preview_limit],
        "preview_truncated": len(normalized.markdown) > preview_limit,
        "strategy_recommendation": _recommend_strategy(normalized.markdown),
    }


@app.post("/process")
async def process_document(
    file: UploadFile = File(...),
    strategy: Literal["structure", "fixed"] = Form("structure"),
    chunk_size: int = Form(700),
    overlap: int = Form(80),
    semantic: bool = Form(False),
) -> dict[str, Any]:
    """Process and save a new active document version for later document-scoped Q&A."""
    _validate_chunk_settings(chunk_size, overlap)
    filename, raw, normalized = await _normalize_upload(file)
    chunks = _chunk(normalized, filename, strategy, chunk_size, overlap, semantic)
    doc_id = STORE.create_document(filename)
    version_id = STORE.save_version(
        document_id=doc_id, filename=filename, source_bytes=raw,
        normalized_markdown=normalized.markdown, normalization=_normalization_info(normalized),
        chunks=chunks, strategy=strategy, chunk_size=chunk_size, overlap=overlap,
        semantic=semantic, status="active",
    )
    return {
        "filename": filename,
        "document_id": doc_id,
        "version_id": version_id,
        "version_status": "active",
        "strategy": strategy,
        "normalization": _normalization_info(normalized),
        "chunks": chunks,
        "metrics": calculate_metrics(chunks),
    }


@app.post("/benchmark")
async def benchmark_document(
    file: UploadFile = File(...),
    chunk_size: int = Form(700),
    overlap: int = Form(80),
) -> dict[str, Any]:
    """Run fixed-size and structure-aware chunking only when explicitly requested."""
    _validate_chunk_settings(chunk_size, overlap)
    filename, _, normalized = await _normalize_upload(file)
    baseline = fixed_size_chunks(normalized.markdown, filename, chunk_size, overlap)
    smart = chunk_document(normalized.markdown, filename, chunk_size, overlap, semantic=False)
    return {
        "filename": filename,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "normalization": _normalization_info(normalized),
        "baseline": calculate_metrics(baseline),
        "smartchunk": calculate_metrics(smart),
        "baseline_chunks": baseline,
        "smartchunk_chunks": smart,
        "note": "Chunk-shape metrics are not a direct measure of retrieval or answer accuracy.",
    }


@app.get("/documents")
def list_documents() -> dict[str, Any]:
    return {"documents": STORE.list_documents()}


@app.get("/documents/{document_id}/versions")
def list_document_versions(document_id: str) -> dict[str, Any]:
    if not STORE.document_exists(document_id):
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"document_id": document_id, "versions": STORE.list_versions(document_id)}


@app.post("/qa/ask")
def ask_document_question(request: QARequest) -> dict[str, Any]:
    """Answer from the active version of one document; returns an extractive fallback without a key."""
    try:
        return answer_question(STORE, request.document_id, request.question, request.top_k)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except QANotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/safesync/prepare")
async def prepare_safesync_candidate(
    file: UploadFile = File(...),
    document_id: str | None = Form(None),
    strategy: Literal["structure", "fixed"] = Form("structure"),
    chunk_size: int = Form(700),
    overlap: int = Form(80),
    semantic: bool = Form(False),
) -> dict[str, Any]:
    """Build a candidate version without making it active."""
    _validate_chunk_settings(chunk_size, overlap)
    filename, raw, normalized = await _normalize_upload(file)
    chunks = _chunk(normalized, filename, strategy, chunk_size, overlap, semantic)
    if document_id:
        if not STORE.document_exists(document_id):
            raise HTTPException(status_code=404, detail="Document ID does not exist.")
        doc_id = document_id
    else:
        doc_id = STORE.create_document(filename)
    version_id = STORE.save_version(
        document_id=doc_id, filename=filename, source_bytes=raw,
        normalized_markdown=normalized.markdown, normalization=_normalization_info(normalized),
        chunks=chunks, strategy=strategy, chunk_size=chunk_size, overlap=overlap,
        semantic=semantic, status="candidate",
    )
    return {
        "document_id": doc_id,
        "version_id": version_id,
        "status": "candidate",
        "chunk_count": len(chunks),
        "message": "Candidate created but not published. Validate it before publishing.",
    }


@app.post("/safesync/validate/{version_id}")
def validate_safesync_candidate(version_id: str) -> dict[str, Any]:
    try:
        report = validate_candidate(STORE, version_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not report.get("passed"):
        version = STORE.get_version(version_id)
        if version:
            try:
                incident_id = STORE.create_incident(
                    document_id=version["document_id"], version_id=version_id,
                    failure_type="safesync_validation_failed",
                    summary="SafeSync candidate failed one or more mandatory checks.",
                    config={"strategy": version["strategy"], "chunk_size": version["chunk_size"], "overlap": version["overlap"], "semantic": version["semantic"]},
                    details={"validation_report": report},
                )
                report["incident_id"] = incident_id
            except (KeyError, ValueError):
                pass
    return report


@app.post("/safesync/publish/{version_id}")
def publish_safesync_candidate(version_id: str) -> dict[str, Any]:
    try:
        return publish_candidate(STORE, version_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/safesync/status/{document_id}")
def safesync_status(document_id: str) -> dict[str, Any]:
    document = STORE.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    active = STORE.get_active_version(document_id)
    active_summary = None
    if active:
        active_summary = {key: active.get(key) for key in (
            "version_id", "document_id", "filename", "source_sha256", "normalized_sha256",
            "strategy", "chunk_size", "overlap", "semantic", "status", "validation", "created_at"
        )}
    return {
        "document": document,
        "active_version": active_summary,
        "versions": STORE.list_versions(document_id),
    }


@app.post("/incidents", response_model=IncidentCreateResponse)
def create_incident(request: IncidentCreateRequest) -> dict[str, Any]:
    try:
        incident_id = STORE.create_incident(
            document_id=request.document_id, version_id=request.version_id,
            failure_type=request.failure_type, summary=request.summary,
            config=request.config, details=request.details,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"incident_id": incident_id, "status": "open"}


@app.get("/incidents")
def list_incidents(limit: int = 100) -> dict[str, Any]:
    return {"incidents": STORE.list_incidents(limit)}


@app.get("/incidents/{incident_id}")
def get_incident(incident_id: str) -> dict[str, Any]:
    incident = STORE.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return incident


@app.get("/incidents/{incident_id}/replays")
def list_incident_replays(incident_id: str) -> dict[str, Any]:
    if not STORE.get_incident(incident_id):
        raise HTTPException(status_code=404, detail="Incident not found.")
    return {"incident_id": incident_id, "replays": STORE.list_replays(incident_id)}


@app.post("/incidents/{incident_id}/replay")
def run_incident_replay(incident_id: str) -> dict[str, Any]:
    try:
        return replay_incident(STORE, incident_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

