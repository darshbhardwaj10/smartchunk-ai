# SmartChunk AI — Integrated GRAPHITE 2026 Project

SmartChunk AI normalizes supported documents into a common Markdown representation, creates structure-aware chunks with source metadata, and compares them with a fixed-size baseline. It is a document-preprocessing prototype for a downstream RAG pipeline; it is not itself a complete retrieval-and-answer application.

## Team ownership

- **Rishi — Frontend:** `frontend/` (React + Vite upload UI, normalization preview, chunk explorer, comparison, JSONL export)
- **Darsh — Backend/integration:** `backend/` (FastAPI routes, upload validation, normalization integration, errors, API tests)
- **Shagun — Chunking engine:** `chunking_engine/` (fixed baseline, structure-aware parser, semantic option, metadata, duplicate removal)
- **Arpita — Evaluation:** `evaluation_data/` and test documents (sample questions/documents, topic/source smoke test, real evaluation notes)

## Architecture

```text
Original document (TXT / MD / HTML / PDF / DOCX)
                    |
                    v
     FastAPI upload validation + extraction
                    |
                    v
       Canonical Markdown normalization
                    |
                    v
        +-----------+------------+
        |                        |
        v                        v
 Fixed-size baseline       Structure-aware engine
                                  |
                     Optional sentence embeddings
                     for prose boundary decisions
        |                        |
        +-----------+------------+
                    v
       Chunks + source metadata + metrics
                    |
                    v
          React UI / JSONL export
```

## Requirements

- Python 3.11–3.13 recommended
- Node.js 20 LTS or newer
- Git for the shared team workflow

Python 3.14 may work with compatible packages, but use Python 3.12 or 3.13 if a dependency installation fails.

## Run on Windows (PowerShell)

Open VS Code at the **project root** (the folder containing `backend`, `chunking_engine`, and `frontend`).

### 1. Set up Python dependencies

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

If activation is blocked by the PowerShell execution policy, use the environment's Python executable directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

### 2. Run the backend (Terminal 1)

```powershell
uvicorn backend.main:app --reload
```

- Health check: <http://127.0.0.1:8000/health>
- Interactive API docs: <http://127.0.0.1:8000/docs>

### 3. Run the frontend (Terminal 2)

```powershell
cd frontend
npm install
npm run dev
```

Open the URL shown by Vite, usually <http://localhost:5173>.

### 4. Test the code

From the project root in an activated Python environment:

```powershell
python -m pytest -q
python evaluation_data/evaluate.py
```

Build the frontend before the demo:

```powershell
cd frontend
npm run build
```

## Optional semantic mode

The normal structure-aware path works without an embedding model. To use the optional embedding-based topic boundary mode:

```powershell
pip install -r requirements-semantic.txt
```

Enable **Semantic boundary mode** in the frontend. The first run downloads `sentence-transformers/all-MiniLM-L6-v2`, which requires a working internet connection and may take time. Leave semantic mode off for a stable demo if the model is not already downloaded.

## Supported file formats

- `.md` and `.txt`: UTF-8 text extraction; Markdown structure is retained if present.
- `.html` and `.htm`: convert common headings, paragraphs, lists, tables, blockquotes, and code blocks into Markdown.
- `.docx`: converts heading paragraphs, ordinary paragraphs, code-style paragraphs, and tables into Markdown in document order.
- `.pdf`: extracts selectable text per page, adds internal page markers, and removes lines repeated in page margins when the evidence is strong enough.

**Limitations:** scanned PDFs require OCR, which is not included. Complex multi-column PDF reading order and complex DOCX/HTML layouts may not convert perfectly. Review the normalized Markdown preview before relying on the resulting chunks.

## API contract

### `GET /health`
Returns service status.

### `POST /normalize`
Multipart form field `file`. Returns source format, warnings, and up to 20,000 characters of normalized Markdown preview.

### `POST /process`
Multipart form fields:
- `file`: required uploaded document
- `strategy`: `structure` or `fixed` (default `structure`)
- `chunk_size`: integer 200–2000 (default 700)
- `overlap`: integer 0–400 and smaller than `chunk_size` (default 80)
- `semantic`: `true` / `false` (default false)

Response fields include `filename`, `strategy`, `normalization`, `chunks`, and `metrics`. A chunk includes `chunk_id`, `text`, `heading_path`, `chunk_type`, `source`, `parent_id`, `char_count`, and `oversized`.

### `POST /benchmark`
Multipart fields `file`, `chunk_size`, and `overlap`. Compares fixed-size chunk-shape metrics against structure-aware metrics. Semantic mode is intentionally off for repeatable baseline comparisons.

## Consistent data formats

- **Intermediate format:** Markdown. Each input file is normalized separately; documents are not merged together.
- **API transport:** JSON.
- **Export:** JSONL, one JSON object per chunk.
- **Source metadata:** source filename, approximate line-range location in normalized text, and optional page number for PDFs.

## GitHub workflow

1. One teammate pushes the integrated starter to `main` (or merges a setup branch to `main`).
2. Each teammate creates a branch from the updated `main`.
3. Each teammate modifies their owned folder and adds tests for behavior changes.
4. Push the branch and open a pull request into `main`.
5. Merge only after the backend tests pass and the complete UI-to-API workflow is retested.

Do not commit `.venv`, `node_modules`, credentials, or private documents. Keep the API response contract stable unless all teammates agree on a change.

## Evaluation integrity

`evaluation_data/evaluate.py` is a small lexical top-3 source/topic smoke test. It is **not** a full semantic retrieval benchmark and does not prove answer accuracy. For a credible demo, evaluate more representative test documents and record actual results from the integrated system. Never invent improvement percentages.
