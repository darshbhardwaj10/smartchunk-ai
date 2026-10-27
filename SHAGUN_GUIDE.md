# Shagun â€” Chunking Engine Files and Setup

This bundle contains Shagun's chunking-engine modules and focused tests. Extract the ZIP at the repository root so the `chunking_engine/` and `tests/` folders merge into the shared project.

## Owned modules

- `chunking_engine/chunker.py`: public API and orchestration. Keep `chunk_document`, `fixed_size_chunks`, and `calculate_metrics` available because Darsh's FastAPI backend imports them.
- `chunking_engine/structure_parser.py`: parses Markdown headings, prose, lists, simple GFM tables, fenced code blocks, and internal PDF page markers.
- `chunking_engine/semantic_chunker.py`: optional sentence-embedding splitting of prose blocks only.
- `chunking_engine/deduplicator.py`: exact duplicate removal and conservative near-duplicate detection.
- `chunking_engine/metadata.py`: creates the shared chunk data schema.
- `chunking_engine/__init__.py`: exports the public functions.
- `tests/test_chunker.py`, `tests/test_structure_parser.py`, `tests/test_deduplicator.py`, `tests/test_semantic_chunker.py`: focused automated tests.

## Install and test on macOS

From the root of `smartchunk-ai`:

```bash
source .venv/bin/activate
python -m pytest tests/test_chunker.py tests/test_structure_parser.py tests/test_deduplicator.py tests/test_semantic_chunker.py -v
```

If you have not yet installed pytest:

```bash
python -m pip install pytest
```

The default structural mode does not require the embedding model. To enable semantic mode, install the optional dependencies from `requirements-semantic.txt`:

```bash
python -m pip install -r requirements-semantic.txt
```

The first semantic run downloads `sentence-transformers/all-MiniLM-L6-v2`; it requires internet access and can take time. Keep semantic mode disabled until the structural pipeline and backend integration are stable.

## API contract requirements

`chunk_document(text, filename, chunk_size=700, overlap=80, semantic=False)` returns a list of dictionaries. Each dictionary includes:

- `chunk_id`
- `text`
- `heading_path`
- `chunk_type`
- `source` (`file`, `location`, and optional `page`)
- `parent_id`
- `char_count`
- `oversized`

`fixed_size_chunks(text, filename, chunk_size=700, overlap=80)` implements the baseline and deliberately does not deduplicate. `calculate_metrics(chunks)` returns the metric keys expected by FastAPI's response model.

## Known behavior to describe accurately

- Chunk-size values are characters, not tokens.
- Prose is split around sentence and word boundaries where feasible.
- Code/list/table blocks are kept intact; an oversized structural block is retained and marked `oversized: true` rather than silently destroyed.
- Exact duplicate detection normalizes whitespace/punctuation and ignores the injected `Section:` prefix. Optional near-duplicate filtering is conservative and uses token-set Jaccard similarity within matching chunk type and heading path.
- Semantic mode only changes prose splitting. It is not a full end-to-end RAG pipeline and does not generate answers.
- The parser handles a useful Markdown subset, not the full CommonMark/GFM specification. Add tests when extending it.

## Git workflow

```bash
git switch main
git pull origin main
git switch -c shagun-chunking
# copy/merge these files into the repo
python -m pytest -q
git add chunking_engine/ tests/test_chunker.py tests/test_structure_parser.py tests/test_deduplicator.py tests/test_semantic_chunker.py SHAGUN_GUIDE.md requirements-semantic.txt
git commit -m "Modularize structure-aware chunking engine"
git push -u origin shagun-chunking
```

Open a pull request into `main` after the tests pass and coordinate with Darsh before changing field names or function signatures.
