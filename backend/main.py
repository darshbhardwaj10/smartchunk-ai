"""FastAPI API, request validation, document ingestion, and engine integration."""
from __future__ import annotations
from fastapi.responses import Response

import os
from pathlib import Path, PurePosixPath
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.normalizer import NormalizationError, NormalizedDocument, normalize_document
from chunking_engine.chunker import calculate_metrics, chunk_document, fixed_size_chunks

APP_VERSION = "1.0.0"
ALLOWED_EXTENSIONS = {".txt", ".md", ".html", ".htm", ".pdf", ".docx"}
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _max_upload_bytes() -> int:
    try:
        megabytes = int(os.getenv("SMARTCHUNK_MAX_UPLOAD_MB", "10"))
    except ValueError:
        megabytes = 10
    return max(1, megabytes) * 1024 * 1024


def _allowed_origins() -> list[str]:
    raw = os.getenv(
        "SMARTCHUNK_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(
    title="SmartChunk AI API",
    description="Document normalization and structure-aware RAG chunking API.",
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
    """Read an upload with an explicit limit before accumulating it in memory."""
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


async def _normalize_upload(upload: UploadFile) -> tuple[str, NormalizedDocument]:
    filename, raw = await _read_upload(upload)
    try:
        normalized = normalize_document(filename, raw)
    except NormalizationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filename, normalized


def _validate_chunk_settings(chunk_size: int, overlap: int) -> None:
    if not 200 <= chunk_size <= 2000:
        raise HTTPException(status_code=422, detail="chunk_size must be between 200 and 2000 characters.")
    if not 0 <= overlap <= min(400, chunk_size - 1):
        raise HTTPException(status_code=422, detail="overlap must be 0–400 and smaller than chunk_size.")


def _normalization_info(normalized: NormalizedDocument) -> dict:
    return {
        "source_format": normalized.source_format,
        "intermediate_format": "markdown",
        "warnings": normalized.warnings,
        "removed_repeated_margin_lines": normalized.removed_repeated_margin_lines,
        "normalized_character_count": len(normalized.markdown),
    }


class SourceInfo(BaseModel):
    file: str
    location: str
    page: int | None = None


class ChunkRecord(BaseModel):
    chunk_id: str
    text: str
    heading_path: list[str] = Field(default_factory=list)
    chunk_type: str
    source: SourceInfo
    parent_id: str | None = None
    char_count: int
    oversized: bool = False


class ChunkMetrics(BaseModel):
    chunk_count: int
    average_characters: float
    min_characters: int
    max_characters: int
    duplicate_rate: float
    total_characters: int
    oversized_chunk_count: int
    chunk_types: dict[str, int]


class NormalizationInfo(BaseModel):
    source_format: str
    intermediate_format: str = "markdown"
    warnings: list[str] = Field(default_factory=list)
    removed_repeated_margin_lines: int = 0
    normalized_character_count: int


class ProcessResponse(BaseModel):
    filename: str
    strategy: Literal["structure", "fixed"]
    normalization: NormalizationInfo
    chunks: list[ChunkRecord]
    metrics: ChunkMetrics


class NormalizeResponse(BaseModel):
    filename: str
    normalization: NormalizationInfo
    markdown_preview: str
    preview_truncated: bool


class BenchmarkResponse(BaseModel):
    filename: str
    chunk_size: int
    overlap: int
    normalization: NormalizationInfo
    baseline: ChunkMetrics
    smartchunk: ChunkMetrics
    note: str


@app.get("/")
def root() -> dict:
    return {
        "name": "SmartChunk AI API",
        "version": APP_VERSION,
        "health": "/health",
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "smartchunk-ai", "version": APP_VERSION}


@app.post("/normalize", response_model=NormalizeResponse)
async def normalize_endpoint(file: UploadFile = File(...)) -> dict:
    """Return a bounded preview of the canonical Markdown output for inspection."""
    filename, normalized = await _normalize_upload(file)
    preview_limit = 20_000
    return {
        "filename": filename,
        "normalization": _normalization_info(normalized),
        "markdown_preview": normalized.markdown[:preview_limit],
        "preview_truncated": len(normalized.markdown) > preview_limit,
    }


@app.post("/process", response_model=ProcessResponse)
async def process_document(
    file: UploadFile = File(...),
    strategy: Literal["structure", "fixed"] = Form("structure"),
    chunk_size: int = Form(700),
    overlap: int = Form(80),
    semantic: bool = Form(False),
) -> dict:
    _validate_chunk_settings(chunk_size, overlap)
    filename, normalized = await _normalize_upload(file)

    try:
        if strategy == "fixed":
            chunks = fixed_size_chunks(normalized.markdown, filename, chunk_size, overlap)
        else:
            chunks = chunk_document(
                normalized.markdown,
                filename,
                chunk_size,
                overlap,
                semantic=semantic,
            )
    except ImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "filename": filename,
        "strategy": strategy,
        "normalization": _normalization_info(normalized),
        "chunks": chunks,
        "metrics": calculate_metrics(chunks),
    }


@app.post("/benchmark", response_model=BenchmarkResponse)
async def benchmark_document(
    file: UploadFile = File(...),
    chunk_size: int = Form(700),
    overlap: int = Form(80),
) -> dict:
    _validate_chunk_settings(chunk_size, overlap)
    filename, normalized = await _normalize_upload(file)
    baseline = fixed_size_chunks(normalized.markdown, filename, chunk_size, overlap)
    smart = chunk_document(normalized.markdown, filename, chunk_size, overlap, semantic=False)
    return {
        "filename": filename,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "normalization": _normalization_info(normalized),
        "baseline": calculate_metrics(baseline),
        "smartchunk": calculate_metrics(smart),
        "note": "These are chunk-shape metrics, not a direct measure of retrieval or answer accuracy.",
    }
