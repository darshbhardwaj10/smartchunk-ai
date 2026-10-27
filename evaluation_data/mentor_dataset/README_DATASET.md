# SmartChunk Evaluation Dataset

## Purpose

This is a **synthetic** evaluation corpus for development and hackathon demonstration. It is not an official university document and contains no real student information. It includes realistic-looking Markdown structures and normalization fixtures for HTML, TXT, DOCX and a text-based PDF with repeated page margins.

## Run the complete offline evaluation

From the repository root, after installing backend dependencies:

```bash
python evaluation_data/evaluate.py --chunk-size 700 --overlap 80
```

This runs the core baseline-vs-SmartChunk benchmark, controlled mutation cases, format-normalization fixtures and a security-fixture diagnostic. Outputs are written under `evaluation_data/results/`. Security fixture results intentionally do not mean that the current application is secure; they report whether the normalizer exposes security-specific warnings.

Run one component at a time:

```bash
python evaluation_data/evaluate.py --suite chunking
python evaluation_data/evaluate.py --suite mutations
python evaluation_data/evaluate.py --suite security
```

Run the evaluation and backend workflow tests:

```bash
python -m pytest -q
```

The API workflow tests require the updated backend modules (`storage.py`, `retrieval.py`, `qa.py`, `llm_provider.py`, `safesync.py`, and `incident_replay.py`). They use a temporary SQLite store and do not call an external LLM.

## Dataset contents

- `documents/`: four synthetic Markdown documents. The fourth contains cross-section evidence, role-based durations, exceptions and retention rules.
- `source_formats/`: HTML, TXT, DOCX and PDF normalizer fixtures.
- `questions.json`: single-source/topic retrieval questions.
- `multi_evidence_cases.json`: multi-passage questions with manually labelled required evidence spans.
- `expected_structure.json`: heading and structural expectations.
- `evaluation_rubric.json`: definitions and fair-comparison rules.
- `mutation_cases.json`: controlled whitespace, duplication, deletion, reference and caption mutations.
- `security_cases/` plus `security_cases.json`: benign and suspicious-instruction fixtures. These are test inputs, not a security certification.
- `qa_cases.json`: Q&A acceptance scenarios for citations, evidence retrieval and abstention.
- `safesync_cases.json`: candidate publication scenarios.
- `run_chunking_benchmark.py`: baseline/SmartChunk benchmark runner.

## Metrics

- **Structural integrity:** a source table, fenced code block or list is intact if its full normalized text appears in at least one output chunk. This does not prove semantic correctness.
- **Size compliance:** fraction of chunks not marked oversized. Oversized structural blocks can be an intentional trade-off.
- **Source metadata coverage:** fraction of chunks with both source filename and source location.
- **Hit@3:** one expected source/topic match appears in the top three lexical retrieval results.
- **MRR@20:** mean reciprocal rank of the first expected source/topic match within the top 20 ranked results.
- **Evidence Coverage@k:** proportion of manually labelled evidence spans found in retrieved chunks.
- **Evidence Completeness@k:** proportion of multi-evidence questions for which all required spans are found in the top-k retrieved chunks.
- **Processing time:** median wall-clock time over repeated chunking runs; compare on the same host and settings.

The evidence metrics use exact normalized text-span matching against retrieved chunks. All evidence spans must be manually checked against their source documents. Lexical retrieval metrics are not semantic retrieval quality and neither retrieval metrics nor source metadata alone prove generated answer correctness.

## Mutation and security interpretation

Mutation cases probe output behavior under controlled changes. A case with `capability_required` records a known capability gap if the current chunk schema cannot expose or validate that behavior; it is not silently marked as passed.

Security fixtures check whether specific security warnings are emitted. No warning does **not** mean a document is safe. Access control must be enforced by a downstream identity-aware retrieval application, and LLM prompt-injection resistance requires separate end-to-end testing.

## Fair comparison rules

1. Use the same source document, question set, chunk size and overlap for baseline and SmartChunk.
2. Keep semantic mode disabled for the default baseline comparison unless both configurations explicitly enable and document it.
3. Manually verify expected source snippets and question evidence before publishing results.
4. Report missing evidence, oversized blocks, warnings and regressions as well as successful cases.
5. Do not alter the corpus after inspecting scores without recording a dataset version change.
6. The dataset is small and synthetic; do not generalize scores to real-world documents.
