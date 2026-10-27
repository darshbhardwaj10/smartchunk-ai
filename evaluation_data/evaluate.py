"""Main SmartChunk evaluation entry point.

From repository root:
    python evaluation_data/evaluate.py --chunk-size 700 --overlap 80
    python evaluation_data/evaluate.py --suite chunking
    python evaluation_data/evaluate.py --suite mutations
    python evaluation_data/evaluate.py --suite security
    python evaluation_data/evaluate.py --suite all

The default suite is all offline evaluations. API end-to-end tests are run through pytest.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from evaluation_data.mentor_dataset.run_chunking_benchmark import parse_args as parse_benchmark_args, run as run_benchmark
from evaluation_data.run_feature_evaluations import parse_args as parse_feature_args, run as run_features
from evaluation_data.run_security_evaluations import run as run_security


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=['all','chunking','mutations','security'], default='all')
    parser.add_argument('--chunk-size', type=int, default=700)
    parser.add_argument('--overlap', type=int, default=80)
    parser.add_argument('--top-k', type=int, default=3)
    parser.add_argument('--timing-repeats', type=int, default=3)
    parser.add_argument('--output-dir', default=None)
    args = parser.parse_args(argv)
    if not 200 <= args.chunk_size <= 2000:
        parser.error('--chunk-size must be between 200 and 2000')
    if not 0 <= args.overlap <= min(400, args.chunk_size - 1):
        parser.error('--overlap must be 0-400 and smaller than chunk-size')
    if not 1 <= args.top_k <= 20:
        parser.error('--top-k must be between 1 and 20')
    output_dir = args.output_dir
    exit_codes = []
    if args.suite in {'all','chunking'}:
        print('\n=== CHUNKING AND RETRIEVAL BENCHMARK ===')
        bench = parse_benchmark_args(['--chunk-size', str(args.chunk_size), '--overlap', str(args.overlap), '--top-k', str(args.top_k), '--timing-repeats', str(args.timing_repeats)] + (['--output-dir', output_dir] if output_dir else []))
        exit_codes.append(run_benchmark(bench))
    if args.suite in {'all','mutations'}:
        print('\n=== MUTATION AND NORMALIZATION EVALUATIONS ===')
        features = parse_feature_args(['--chunk-size', str(args.chunk_size), '--overlap', str(args.overlap)] + (['--output-dir', output_dir] if output_dir else []))
        exit_codes.append(run_features(features))
    if args.suite in {'all','security'}:
        print('\n=== SECURITY FIXTURE DIAGNOSTICS ===')
        run_security(output_dir)
    return max(exit_codes or [0])

if __name__ == '__main__':
    raise SystemExit(main())
