# Evaluation File Manifest

This manifest describes every component included in this evaluation package.

## Entrypoints and runners

- `evaluate.py` — main CLI; runs the offline evaluation suites.
- `run_all_evaluations.py` — convenience wrapper for the full offline suite.
- `run_feature_evaluations.py` — controlled mutation checks, source-anchor preservation checks, format fixtures and a chunk-schema capability audit.
- `run_security_evaluations.py` — reports whether security-specific warnings are emitted for labelled security fixtures; it does not certify safety.
- `mentor_dataset/run_chunking_benchmark.py` — compares fixed-size and structure-aware chunking, structural integrity, lexical Hit@3/MRR@20, evidence coverage/completeness, source metadata coverage, processing time and normalization fixtures.

## Dataset and scenarios

- `mentor_dataset/documents/` — four synthetic Markdown documents.
- `mentor_dataset/source_formats/` — PDF, DOCX, HTML and TXT normalization fixtures.
- `mentor_dataset/security_cases/` — benign and suspicious-instruction example documents.
- `mentor_dataset/questions.json` — labelled source/topic questions.
- `mentor_dataset/multi_evidence_cases.json` — questions with multiple required evidence passages.
- `mentor_dataset/qa_cases.json` — Q&A acceptance scenarios, including abstention and injection-like content cases.
- `mentor_dataset/mutation_cases.json` — whitespace, repeated notice, deletion, missing reference and caption-separation mutations.
- `mentor_dataset/security_cases.json` — expected-risk labels for security test fixtures.
- `mentor_dataset/safesync_cases.json` — candidate publication and failure scenarios.
- `mentor_dataset/expected_structure.json` — expected document headings, structures and required text anchors.
- `mentor_dataset/evaluation_rubric.json` — metric definitions and comparison rules.
- `mentor_dataset/README_DATASET.md` — how to use and interpret the dataset.
- `mentor_dataset/REFERENCE_RUN.md` — reproducible run instructions; intentionally avoids pre-filled results for the expanded dataset.

## Automated tests

- `tests/test_dataset_contract.py` — validates paths and labelled evidence snippets.
- `tests/test_evaluation_metrics.py` — unit tests for evidence metrics and structural-integrity calculations.
- `tests/test_feature_evaluation_runners.py` — tests mutation, normalization-fixture and schema-audit runners.
- `tests/test_backend_workflow.py` — tests the updated FastAPI workflow for processing, Q&A, SafeSync and incident replay using isolated temporary storage.

## Generated output

`results/` holds generated JSON/CSV reports and is git-ignored except for `.gitkeep` and this README. Report files are intentionally not included as precomputed results; run the scripts against the exact branch you intend to demonstrate.

## Known scope limits

- The test corpus is synthetic and small.
- Evidence Completeness@k uses manually labelled exact text spans, not an LLM judge.
- The security runner detects whether the current normalizer emits relevant warnings; if it emits none, the report says no security-scan signal was observed.
- Mutation cases requiring reference-target resolution or caption relationships may be reported as requiring implementation.
- SafeSync tests exercise the local SQLite version store, not a remote vector database.
