"""Run security-related normalization diagnostics on synthetic fixtures.

This script does NOT certify documents as safe. It checks whether the current
normalizer exposes security-specific warnings for the included test cases.
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from typing import Any
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATASET = HERE / 'mentor_dataset'
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from backend.normalizer import normalize_document

SECURITY_WORDS = ('prompt injection', 'instruction-like', 'malicious instruction', 'security warning', 'suspicious instruction', 'untrusted instruction')


def run(output_dir: str | None = None) -> dict[str, Any]:
    spec = json.loads((DATASET / 'security_cases.json').read_text(encoding='utf-8'))
    rows = []
    for case in spec['cases']:
        path = DATASET / 'security_cases' / case['file']
        try:
            normalized = normalize_document(path.name, path.read_bytes())
            warnings = [str(item) for item in normalized.warnings]
            security_warning = any(any(term in warning.casefold() for term in SECURITY_WORDS) for warning in warnings)
            observed = 'warning_detected' if security_warning else 'not_detected_by_normalizer'
            rows.append({
                'case_id': case['case_id'], 'filename': case['file'], 'expected_risk': case['expected_risk'],
                'expected_warning': case['should_warn'], 'observed': observed,
                'expected_detection_met': (security_warning if case['should_warn'] else not security_warning),
                'normalization_warnings': warnings,
                'normalized_characters': len(normalized.markdown),
            })
        except Exception as exc:
            rows.append({'case_id': case['case_id'], 'filename': case['file'], 'observed':'normalization_error', 'error':f'{type(exc).__name__}: {exc}'})
    positive_cases = [r for r in rows if r.get('expected_warning') is True]
    detected_positive = sum(bool(r.get('observed') == 'warning_detected') for r in positive_cases)
    benign_cases = [r for r in rows if r.get('expected_warning') is False]
    benign_false_alarms = sum(bool(r.get('observed') == 'warning_detected') for r in benign_cases)
    scanner_present = detected_positive > 0
    report = {
        'dataset': 'synthetic SmartChunk security fixtures',
        'case_count': len(rows),
        'observed_security_scanner_status': 'SOME_SECURITY_WARNINGS_OBSERVED' if scanner_present else 'NO_SECURITY_SCANNER_SIGNAL_OBSERVED',
        'positive_cases_detected': detected_positive,
        'positive_case_count': len(positive_cases),
        'benign_false_alarms': benign_false_alarms,
        'benign_case_count': len(benign_cases),
        'cases': rows,
        'limitations': [
            'No security warning does not mean the document is safe.',
            'These fixtures do not prove prompt-injection resistance of an LLM.',
            'Access-control enforcement must be tested in the retrieval application, not inferred from chunk metadata.',
            'The present backend may not implement a prompt-injection detector; the report calls this out rather than treating cases as safe.'
        ]
    }
    target = Path(output_dir).resolve() if output_dir else HERE / 'results'
    target.mkdir(parents=True, exist_ok=True)
    outfile = target / 'security_evaluation.json'
    outfile.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Security fixtures tested: {len(rows)}; security detector signal: {report['observed_security_scanner_status']}")
    print(f"Positive cases detected: {detected_positive}/{len(positive_cases)}; benign warnings: {benign_false_alarms}/{len(benign_cases)}")
    print(f"Report written: {outfile}")
    return report


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default=None)
    return parser.parse_args(argv)

if __name__ == '__main__':
    run(parse_args().output_dir)
