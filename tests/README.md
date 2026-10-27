# SmartChunk tests

The six core test modules are:

- `test_api.py` — API contract and upload validation.
- `test_chunker.py` — chunking/metadata invariants.
- `test_qa.py` — grounded source answers, citations, abstention.
- `test_safesync.py` — candidate release gate.
- `test_incident_replay.py` — deterministic reproduction.
- `test_integrity.py` — source-to-chunk lineage and integrity checks.

`conftest.py` creates a temporary SQLite store and provides a shared FastAPI `client` fixture.

Run from the repository root:

```bash
python -m pytest tests/test_api.py tests/test_chunker.py tests/test_qa.py tests/test_safesync.py tests/test_incident_replay.py tests/test_integrity.py -q
python -m pytest -q
```

See `TESTS_ARCHITECTURE.md` in the repository root for the detailed module architecture and coverage limits.
