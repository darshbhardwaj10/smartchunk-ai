"""Run controlled mutation, source-preservation, normalization, and capability evaluations.

Usage from repository root:
    python evaluation_data/run_feature_evaluations.py --chunk-size 700 --overlap 80
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATASET = HERE / "mentor_dataset"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.normalizer import normalize_document
from chunking_engine.chunker import chunk_document, fixed_size_chunks, calculate_metrics
from chunking_engine.structure_parser import parse_markdown_blocks


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def mutate_document(source: str, case: dict[str, Any]) -> tuple[str, list[str]]:
    operation = case.get("operation")
    expected_removed: list[str] = list(case.get("expected_removed") or [])
    if operation == "replace_once":
        target, replacement = str(case.get("target", "")), str(case.get("replacement", ""))
        if not target or target not in source:
            raise ValueError(f"Mutation target not found for {case.get('case_id')}: {target[:100]}")
        return source.replace(target, replacement, 1), expected_removed
    if operation == "append_text":
        return source.rstrip() + "\n\n" + str(case.get("append_text", "")).lstrip(), expected_removed
    if operation == "insert_after":
        target, insert_text = str(case.get("target", "")), str(case.get("insert_text", ""))
        if not target or target not in source:
            raise ValueError(f"Insertion target not found for {case.get('case_id')}: {target[:100]}")
        return source.replace(target, target + insert_text, 1), expected_removed
    raise ValueError(f"Unsupported mutation operation: {operation}")


def choose_chunks(markdown: str, filename: str, strategy: str, chunk_size: int, overlap: int) -> list[dict[str, Any]]:
    if strategy == "fixed":
        return fixed_size_chunks(markdown, filename, chunk_size, overlap)
    return chunk_document(markdown, filename, chunk_size, overlap, semantic=False)


def structural_integrity(markdown: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    units = [block for block in parse_markdown_blocks(markdown) if block.get("chunk_type") in {"table", "list", "code"}]
    texts = [norm(chunk.get("text", "")) for chunk in chunks]
    by_type: dict[str, dict[str, int]] = {}
    for kind in ("table", "list", "code"):
        selected = [unit for unit in units if unit.get("chunk_type") == kind]
        kept = sum(1 for unit in selected if any(norm(unit.get("text", "")) in text for text in texts))
        by_type[kind] = {"expected": len(selected), "preserved": kept}
    total = len(units)
    preserved = sum(item["preserved"] for item in by_type.values())
    return {"expected": total, "preserved": preserved, "rate": round(preserved / total, 4) if total else 1.0, "by_type": by_type}


def evaluate_mutations(chunk_size: int = 700, overlap: int = 80) -> dict[str, Any]:
    cases = load_json(DATASET / "mutation_cases.json")["cases"]
    docs_dir = DATASET / "documents"
    case_rows = []
    for case in cases:
        source_path = docs_dir / str(case["document"])
        original = source_path.read_text(encoding="utf-8")
        mutated, expected_removed = mutate_document(original, case)
        filename = source_path.name
        strategy_reports = {}
        for strategy in ("fixed", "structure"):
            chunks = choose_chunks(mutated, filename, strategy, chunk_size, overlap)
            combined = norm("\n".join(str(chunk.get("text", "")) for chunk in chunks))
            must_preserve = list(case.get("must_preserve") or [])
            missing = [fragment for fragment in must_preserve if norm(fragment) not in combined]
            unexpectedly_present = [fragment for fragment in expected_removed if norm(fragment) in combined]
            metrics = calculate_metrics(chunks)
            structural = structural_integrity(mutated, chunks)
            checks_pass = not missing and not unexpectedly_present
            strategy_reports[strategy] = {
                "chunk_count": metrics.get("chunk_count", len(chunks)),
                "average_characters": metrics.get("average_characters", 0),
                "oversized_chunk_count": metrics.get("oversized_chunk_count", 0),
                "structural_integrity": structural,
                "must_preserve_count": len(must_preserve),
                "missing_required_fragments": missing,
                "expected_removed_fragments_still_present": unexpectedly_present,
                "content_assertions_passed": checks_pass,
            }
        capability = case.get("capability_required")
        if capability:
            # The current chunker schema has no generic relationship graph/caption link field.
            capability_status = "REQUIRES_IMPLEMENTATION_OR_EXPLICIT_TEST"
        else:
            capability_status = "NOT_APPLICABLE"
        case_rows.append({
            "case_id": case["case_id"],
            "name": case["name"],
            "purpose": case.get("purpose", ""),
            "operation": case.get("operation"),
            "capability_required": capability,
            "capability_status": capability_status,
            "strategies": strategy_reports,
        })
    return {
        "dataset": "SmartChunk controlled mutation cases",
        "settings": {"chunk_size": chunk_size, "overlap": overlap, "semantic": False},
        "case_count": len(case_rows),
        "cases": case_rows,
        "limitations": [
            "Mutation cases are synthetic probes, not a full robustness benchmark.",
            "Whitespace normalization is used for anchor matching; this is not byte-level integrity.",
            "A required feature that is not implemented is reported as a capability gap, not a passing test.",
        ],
    }


def evaluate_normalization_fixtures() -> dict[str, Any]:
    fixtures_dir = DATASET / "source_formats"
    security_dir = DATASET / "security_cases"
    supported = {".txt", ".md", ".html", ".htm", ".pdf", ".docx"}
    rows = []
    for path in sorted(list(fixtures_dir.iterdir()) + list(security_dir.iterdir())):
        if not path.is_file() or path.suffix.lower() not in supported:
            continue
        try:
            result = normalize_document(path.name, path.read_bytes())
            blocks = parse_markdown_blocks(result.markdown)
            rows.append({
                "filename": path.name,
                "relative_path": str(path.relative_to(DATASET)).replace("\\", "/"),
                "source_format": result.source_format,
                "normalized_characters": len(result.markdown),
                "heading_count": len(re.findall(r"(?m)^#{1,6}\s+", result.markdown)),
                "table_blocks": sum(b.get("chunk_type") == "table" for b in blocks),
                "code_blocks": sum(b.get("chunk_type") == "code" for b in blocks),
                "list_blocks": sum(b.get("chunk_type") == "list" for b in blocks),
                "warnings": list(result.warnings),
                "status": "ok" if result.markdown.strip() else "empty",
            })
        except Exception as exc:
            rows.append({"filename": path.name, "status": "error", "error": f"{type(exc).__name__}: {exc}"})
    return {"fixture_count": len(rows), "fixtures": rows, "all_nonempty_or_error_reported": all(r.get("status") in {"ok", "empty", "error"} for r in rows)}


def capability_audit() -> dict[str, Any]:
    """Report whether advanced fields are actually exposed by current source modules.

    This is a source/schema audit, not a security certification.
    """
    try:
        from chunking_engine.metadata import make_chunk
        sample = make_chunk("sample", "audit.md", 1, [], "prose", "lines 1-1")
    except Exception as exc:
        return {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}
    chunk_fields = sorted(sample.keys())
    checks = {
        "boundary_reason_field": "boundary_reason" in chunk_fields,
        "stable_source_element_ids": "source_element_ids" in sample or "source_element_id" in sample,
        "related_chunk_ids": "related_chunk_ids" in sample,
        "access_control_metadata": "access_control" in sample,
        "security_warning_metadata": "security" in sample or "security_warnings" in sample,
    }
    return {
        "status": "completed",
        "chunk_schema_fields": chunk_fields,
        "capabilities": checks,
        "not_implemented_or_not_exposed": [name for name, present in checks.items() if not present],
        "note": "A field being present does not prove its behavior is correct; each capability still needs behavior tests.",
    }


def run(args: argparse.Namespace) -> int:
    output = Path(args.output_dir).resolve() if args.output_dir else HERE / "results"
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "mutations": evaluate_mutations(args.chunk_size, args.overlap),
        "normalization_fixtures": evaluate_normalization_fixtures(),
        "capability_audit": capability_audit(),
    }
    path = output / "feature_evaluation.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    mutation_csv = output / "mutation_results.csv"
    with mutation_csv.open("w", newline="", encoding="utf-8") as f:
        import csv
        fields = ["case_id", "name", "capability_required", "capability_status", "fixed_chunk_count", "fixed_assertions_passed", "structure_chunk_count", "structure_assertions_passed"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for case in report["mutations"]["cases"]:
            writer.writerow({
                "case_id": case["case_id"], "name": case["name"],
                "capability_required": case["capability_required"], "capability_status": case["capability_status"],
                "fixed_chunk_count": case["strategies"]["fixed"]["chunk_count"],
                "fixed_assertions_passed": case["strategies"]["fixed"]["content_assertions_passed"],
                "structure_chunk_count": case["strategies"]["structure"]["chunk_count"],
                "structure_assertions_passed": case["strategies"]["structure"]["content_assertions_passed"],
            })
    print(f"Mutation cases: {report['mutations']['case_count']}")
    for case in report["mutations"]["cases"]:
        struct = case["strategies"]["structure"]
        print(f"  {case['case_id']} {case['name']}: structure assertions={'PASS' if struct['content_assertions_passed'] else 'FAIL'}; capability={case['capability_status']}")
    print(f"Normalization fixtures: {report['normalization_fixtures']['fixture_count']}")
    print("Chunk schema capability gaps:", ", ".join(report["capability_audit"].get("not_implemented_or_not_exposed", [])) or "none detected")
    print(f"Reports written: {path} and {mutation_csv}")
    # Exit nonzero only for malformed or failed preservation assertions; unimplemented optional
    # capabilities are reported separately so users can run the suite before implementing them.
    assertion_failures = any(not row["strategies"]["structure"]["content_assertions_passed"] for row in report["mutations"]["cases"])
    normalization_errors = any(row.get("status") == "error" for row in report["normalization_fixtures"]["fixtures"])
    return 1 if assertion_failures or normalization_errors else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunk-size", type=int, default=700)
    parser.add_argument("--overlap", type=int, default=80)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)
    if not 200 <= args.chunk_size <= 2000:
        parser.error("chunk-size must be between 200 and 2000")
    if not 0 <= args.overlap <= min(400, args.chunk_size - 1):
        parser.error("overlap must be 0-400 and smaller than chunk-size")
    return args


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
