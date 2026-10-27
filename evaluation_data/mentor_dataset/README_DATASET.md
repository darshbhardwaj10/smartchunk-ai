# SmartChunk Mentor Demo Dataset

## Purpose
This is a **synthetic** evaluation corpus designed for the SmartChunk AI hackathon demo. It is not an official university document or real student data. It deliberately includes Markdown headings, prose, lists, tables, fenced code, duplicate notices, HTML, plain text, DOCX, and a multi-page PDF with repeated margin lines.

## Recommended live demo
1. Open the application and set `chunk_size=700`, `overlap=80`, `semantic=false`.
2. Upload `documents/01_structure_stress_test.md` and compare the fixed-size baseline against SmartChunk.
3. Inspect actual table/code chunks, heading paths, `chunk_type`, and the `oversized` flag.
4. Upload `documents/02_api_integration_guide.md` and `documents/03_student_data_policy.md` as additional cases.
5. Test `source_formats/sample_service_desk.html`, `source_formats/sample_service_desk.txt`, `source_formats/sample_equipment_return.docx`, and `source_formats/repeated_page_margins.pdf` through `/normalize`.
6. Run the benchmark script and report its output honestly.

## Run benchmark script
Run from the **main `smartchunk-ai` project root** after installing backend dependencies:

```bash
python evaluation_data/mentor_dataset/run_chunking_benchmark.py
```

The script compares fixed-size and structure-aware chunking on the three Markdown documents and all source-format fixtures. It writes `benchmark_results.json` and `benchmark_results.csv` into this folder. It reports chunk counts, size metrics, oversized chunks, structural block integrity for tables/code/lists, normalized PDF margin removals, and a small lexical expected-source/topic Hit@3 and MRR diagnostic.

Optional settings:

```bash
python evaluation_data/mentor_dataset/run_chunking_benchmark.py --chunk-size 700 --overlap 80
```

## Metrics and limitations
- **Structural block integrity:** a source table, fenced code block, or list is counted as intact if the entire extracted block appears inside at least one generated chunk. This is a simple deterministic proxy, not a general document-understanding score.
- **Expected source/topic Hit@3:** a simple lexical ranking over labelled questions; a hit requires a relevant source/topic match among the top three ranked chunks.
- **MRR:** mean reciprocal rank of the first chunk that matches the labelled source/topic; questions without a match contribute zero. It is based on lexical ranking, not embedding retrieval or answer accuracy.
- **Oversized chunks:** SmartChunk may preserve a structural block intact even when it exceeds the configured chunk size; this is an explicit trade-off recorded by an `oversized` flag.
- **Near duplicates:** the engine's existing conservative lexical detector may miss paraphrases or remove some similar content. Review output manually.
- **PDF extraction:** the PDF fixture tests repeated page margins only for text-based PDFs. Scanned PDFs require OCR and are not covered.
- All results must be measured by running the script. No performance improvement is guaranteed in advance.

## Dataset files
- `documents/`: three Markdown documents for baseline comparison.
- `source_formats/`: HTML, TXT, DOCX, and PDF fixtures for normalization tests.
- `questions.json`: hand-labelled question/source/topic test set.
- `expected_structure.json`: structural expectations per document.
- `evaluation_rubric.json`: consistent metric definitions and comparison rules.
- `run_chunking_benchmark.py`: deterministic benchmark script.
