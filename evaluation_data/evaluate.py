"""Backward-compatible entry point for the labelled mentor evaluation.

Run from the smartchunk-ai project root:
    python evaluation_data/evaluate.py --chunk-size 700 --overlap 80
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation_data.mentor_dataset.run_chunking_benchmark import parse_args, run


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
