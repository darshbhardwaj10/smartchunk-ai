# Reference benchmark run

This report records an actual run of `run_chunking_benchmark.py` using the current SmartChunk chunking engine in the authoring environment. Re-run the script on your own checked-out branch before presenting these values, because code versions and dependencies may differ.

Settings: `chunk_size=700` characters, `overlap=80`, semantic mode disabled. The corpus is synthetic.

## Structural block integrity

| Document | Fixed-size baseline | SmartChunk structure-aware |
|---|---:|---:|
| `01_structure_stress_test.md` | 0/3 (0.0%) | 3/3 (100.0%) |
| `02_api_integration_guide.md` | 3/4 (75.0%) | 4/4 (100.0%) |
| `03_student_data_policy.md` | 3/3 (100.0%) | 3/3 (100.0%) |

The metric checks whether each entire parsed table, code block, or list appears inside at least one chunk. It does not measure semantic retrieval or answer accuracy. SmartChunk kept two structural blocks intact even though they exceeded the 700-character limit and were flagged as oversized.

## Expected source/topic lexical Hit@3 and MRR

| Method | Hit@3 | Rate | MRR |
|---|---:|---:|---:|
| Fixed-size | 10/12 | 83.3% | 0.7750 |
| SmartChunk | 10/12 | 83.3% | 0.7272 |

This tiny lexical diagnostic did not show an improvement in source/topic Hit@3. In this run MRR (first relevant source/topic rank) was 0.7750 for fixed-size and 0.7272 for SmartChunk; therefore this sample does not show a retrieval-ranking improvement for SmartChunk. Do not claim otherwise. The clearest demonstrated difference was structural block integrity on the stress-test and API documents.

## PDF normalization

The repeated-page-margin PDF fixture was normalized and the normalizer reported 8 repeated page-margin line occurrences removed. Check the generated Markdown preview on your own machine to confirm the expected header/footer lines were removed and body content remains intact.

## How to reproduce

From the main `smartchunk-ai` repository root:

```bash
python evaluation_data/mentor_dataset/run_chunking_benchmark.py --chunk-size 700 --overlap 80
```

The run writes fresh `benchmark_results.json` and `benchmark_results.csv` beside the script. Present fresh results from the exact branch you demonstrate.
