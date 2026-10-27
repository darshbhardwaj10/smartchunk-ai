# Reference run instructions

The evaluation corpus has been expanded to include a fourth multi-evidence document plus mutation and security fixtures. Earlier numbers reported for the three-document corpus are **historical and are not comparable** to the expanded suite. This file intentionally does not pre-fill performance claims for the expanded corpus.

Run the current branch from the repository root:

```bash
python evaluation_data/evaluate.py --chunk-size 700 --overlap 80
```

The script creates these reports under `evaluation_data/results/`:

- `chunking_benchmark.json` and `.csv`
- `feature_evaluation.json` and `mutation_results.csv`
- `security_evaluation.json`

Also run the full test suite:

```bash
python -m pytest -q
```

When publishing a result, record the Git commit, Python version, dependency versions, command-line options, operating environment, and any optional dependencies. Include failures and limitations. Do not copy old reference figures into a report for the expanded corpus.
