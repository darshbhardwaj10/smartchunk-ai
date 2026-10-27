# SmartChunk AI — Evaluation Package

This folder contains the synthetic mentor corpus, offline benchmarks, controlled mutation fixtures, security diagnostic fixtures, and automated workflow tests for the updated SmartChunk backend architecture.

## Run offline evaluations

From the repository root:

```bash
python evaluation_data/evaluate.py --chunk-size 700 --overlap 80
```

Run individual suites:

```bash
python evaluation_data/evaluate.py --suite chunking
python evaluation_data/evaluate.py --suite mutations
python evaluation_data/evaluate.py --suite security
```

Reports are written under `evaluation_data/results/`.

## Run the automated tests

```bash
python -m pytest -q
```

The tests in `evaluation_data/tests/test_backend_workflow.py` require the matching updated backend (`backend/storage.py`, `backend/retrieval.py`, `backend/qa.py`, `backend/llm_provider.py`, `backend/safesync.py`, `backend/incident_replay.py`). The tests use a temporary SQLite store and do not call an external LLM.

## Important interpretation limits

- The corpus is synthetic and is not a real-world benchmark.
- Hit@3 and MRR are lexical retrieval diagnostics, not answer-accuracy scores.
- Evidence Completeness@k checks manually labelled text spans in retrieved chunks. Expected spans must be verified against source documents.
- Mutation cases expose fragility; a required capability that the current code does not implement is reported as a gap, not passed.
- Security fixtures test whether the current normalizer emits specific warnings. No warning does not mean safe, and this package is not a security certification.
- Local SafeSync tests exercise the SQLite candidate lifecycle. They do not verify synchronization with an external vector store.
