# SmartChunk AI — Team Implementation Guide

## Agreed architecture and format

**Each original document is normalized to Markdown separately.** The chunker reads that Markdown and returns metadata-rich chunk dictionaries. The API returns JSON; the frontend exports one JSON object per line as `.jsonl`.

Shared chunk schema:

```json
{
  "chunk_id": "student_manual_chunk_001",
  "text": "Section: Student Handbook > Attendance Rules\n\nStudents should maintain 75% attendance.",
  "heading_path": ["Student Handbook", "Attendance Rules"],
  "chunk_type": "prose",
  "source": {
    "file": "student_manual.pdf",
    "location": "lines 10-12",
    "page": 4
  },
  "parent_id": null,
  "char_count": 76,
  "oversized": false
}
```

`source.page` is optional and is included when the PDF extractor knows the page. The example values are illustrative, not actual extraction results. `parent_id` is reserved for future parent-child chunk support.

## Rishi — Frontend

Owned files: `frontend/`.

1. Install Node.js.
2. Run `cd frontend`, `npm install`, `npm run dev`.
3. Upload the included `evaluation_data/documents/sample_manual.md`.
4. Test Process, Preview normalized Markdown, Compare against baseline, chunk inspection, and JSONL export.
5. For UI changes, run `npm run build` and check for errors.
6. Do not rename API fields without coordinating with Darsh and Shagun.

## Darsh — Backend and integration

Owned files: `backend/`, `requirements*.txt`, `tests/test_api.py`.

1. Create and activate `.venv`; run `pip install -r requirements-dev.txt`.
2. Read `backend/normalizer.py`: source-specific extraction converges into Markdown.
3. Read `backend/main.py`: upload-size/extension checks, validation, CORS, `/health`, `/normalize`, `/process`, `/benchmark`.
4. Run `uvicorn backend.main:app --reload`.
5. Test endpoints using `/docs`, then `python -m pytest -q`.
6. Improve security and reliability (allowed CORS origins, tests, request validation, extraction warnings). Keep the output schema stable.

## Shagun — Chunking engine

Owned files: `chunking_engine/`, `tests/test_chunker.py`.

1. Run `python -m pytest -q` before changes.
2. Read `parse_markdown_blocks()`, `_create_structure_chunks()`, `_split_prose()`, `_deduplicate()`, `chunk_document()`, and `fixed_size_chunks()`.
3. Structural blocks (code/list/table) are kept intact even if they exceed the configured size; such chunks are tagged `oversized: true`. Prose is grouped or split at sentence/word boundaries.
4. Default mode does not require an embedding model. Optional semantic mode uses `sentence-transformers` for prose blocks while structural blocks stay intact.
5. Add a regression test for every algorithm change and preserve the shared response schema.

## Arpita — Data and evaluation

Owned files: `evaluation_data/`.

1. Review the documents under `evaluation_data/documents/`.
2. Add test files with known section titles, tables, code, lists, repeated PDF margin lines, and edge cases.
3. Add questions whose expected source/topic is verified by a human.
4. Run `python evaluation_data/evaluate.py`. Treat this as a small lexical top-3 source/topic smoke test, not full semantic retrieval evaluation.
5. Save measured baseline vs SmartChunk outcomes. Avoid claiming answer accuracy based only on chunk-count metrics.

## Integration sequence

1. All teammates clone the same repository and pull the shared `main` branch.
2. Each teammate creates their own branch from that base:
   - `rishi-frontend`
   - `darsh-backend`
   - `shagun-chunking`
   - `arpita-evaluation`
3. Agree that `/process` request/response fields remain stable.
4. Merge backend/normalization and engine changes, then frontend and evaluation changes through pull requests.
5. From `main`, run `python -m pytest -q`, `python evaluation_data/evaluate.py`, `npm run build`, then test the complete application with both terminals running.

## Local development ports

- FastAPI: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`
- React/Vite: usually `http://localhost:5173`

For teammates on separate laptops, set `SMARTCHUNK_ALLOWED_ORIGINS` on the backend and `VITE_API_BASE_URL` on the frontend to trusted LAN addresses. Do not expose the unauthenticated development server publicly.
