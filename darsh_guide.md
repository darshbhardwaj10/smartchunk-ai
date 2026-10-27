# Darsh — Backend Developer and Integration Guide

Darsh owns the `backend/` package and backend/API tests. The backend uses the shared SmartChunk chunking engine and normalized Markdown contract.

## Files
- `backend/main.py`: FastAPI app, routes, request validation, upload-size enforcement, CORS, API response models, engine integration.
- `backend/normalizer.py`: converts supported TXT, MD, HTML, PDF, and DOCX inputs to normalized Markdown; emits normalization diagnostics and PDF page markers.
- `backend/__init__.py`: marks `backend` as a Python package.
- `tests/test_api.py`: tests the API endpoints, successful processing, benchmark, and expected error responses.
- `requirements.txt`: runtime dependencies.
- `requirements-dev.txt`: runtime dependencies plus pytest/httpx.

## macOS setup
Run from the repository root (the folder containing `backend`, `chunking_engine`, and `frontend`):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## Test backend and engine
```bash
python -m pytest tests/test_api.py tests/test_chunker.py tests/test_structure_parser.py tests/test_deduplicator.py tests/test_semantic_chunker.py -v
```

## Run API
```bash
python -m uvicorn backend.main:app --reload
```
Visit `http://127.0.0.1:8000/health` and `http://127.0.0.1:8000/docs`.

## API
- `GET /health`
- `POST /normalize` with multipart field `file`
- `POST /process` with `file`, `strategy`, `chunk_size`, `overlap`, `semantic`
- `POST /benchmark` with `file`, `chunk_size`, `overlap`

## Integration rules
- Do not rename the engine functions `chunk_document`, `fixed_size_chunks`, or `calculate_metrics` without coordinating with Shagun.
- Do not change the JSON response fields without coordinating with Rishi.
- Normalized documents use Markdown as the intermediate format; separate source files remain separate.
- The current backend is a hackathon prototype without authentication, persistent storage, or OCR for scanned PDFs. Do not expose it publicly without appropriate security controls.

## Git
Work on branch `darsh-backend`. Commit only backend files and backend-specific tests/dependency files assigned to Darsh. Open a pull request into `main` after testing.
