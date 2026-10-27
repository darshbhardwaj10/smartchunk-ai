"""Run a repeatable baseline-vs-SmartChunk benchmark on the mentor dataset.

Run from the project root:
    python evaluation_data/mentor_dataset/run_chunking_benchmark.py
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.normalizer import normalize_document
from chunking_engine.chunker import calculate_metrics, chunk_document, fixed_size_chunks
from chunking_engine.structure_parser import parse_markdown_blocks

STOP_WORDS = {
    "a", "an", "the", "and", "or", "is", "are", "to", "of", "in", "on", "for",
    "what", "which", "how", "can", "does", "do", "should", "be", "by", "with", "it",
    "this", "that", "their", "from", "at", "as", "up", "when", "where", "must", "not",
}


def tokens(value: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", value.casefold()) if w not in STOP_WORDS]


def lexical_score(query: str, chunk: dict[str, Any]) -> float:
    q = set(tokens(query))
    if not q:
        return 0.0
    d = set(tokens(str(chunk.get("text", ""))))
    return len(q & d) / len(q)


def expected_topic_in_chunk(chunk: dict[str, Any], topic: str) -> bool:
    haystack = " ".join(tokens(" ".join(chunk.get("heading_path", [])) + " " + str(chunk.get("text", ""))))
    expected = " ".join(tokens(topic))
    return expected in haystack if expected else True


def _normalize_block(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def structural_units(markdown: str) -> list[dict[str, str]]:
    blocks = parse_markdown_blocks(markdown)
    return [
        {"type": str(b["chunk_type"]), "text": str(b["text"])}
        for b in blocks
        if b["chunk_type"] in {"table", "code", "list"} and str(b["text"]).strip()
    ]


def structural_integrity(markdown: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    units = structural_units(markdown)
    # Avoid matching an entire table/code/list block accidentally across adjacent chunks.
    chunk_texts = [str(c.get("text", "")) for c in chunks]
    breakdown: dict[str, dict[str, int]] = {}
    for kind in ("table", "code", "list"):
        subset = [u for u in units if u["type"] == kind]
        intact = sum(
            1 for unit in subset
            if any(_normalize_block(unit["text"]) in _normalize_block(value) for value in chunk_texts)
        )
        breakdown[kind] = {"expected": len(subset), "intact": intact}
    total = len(units)
    intact_total = sum(row["intact"] for row in breakdown.values())
    return {
        "expected_structural_units": total,
        "intact_structural_units": intact_total,
        "integrity_rate": round(intact_total / total, 4) if total else 1.0,
        "by_type": breakdown,
    }


def summarize_strategy(markdown: str, filename: str, size: int, overlap: int, strategy: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if strategy == "fixed":
        chunks = fixed_size_chunks(markdown, filename, size, overlap)
    else:
        chunks = chunk_document(markdown, filename, size, overlap, semantic=False)
    metrics = calculate_metrics(chunks)
    result = {
        "strategy": strategy,
        "filename": filename,
        **metrics,
        "structural_integrity": structural_integrity(markdown, chunks),
        "normalization": None,
    }
    return result, chunks


def run(args: argparse.Namespace) -> int:
    docs_dir = HERE / "documents"
    questions = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
    selected_names = sorted({item["expected_source"] for item in questions})
    all_chunks: dict[str, list[dict[str, Any]]] = {"fixed": [], "structure": []}
    rows: list[dict[str, Any]] = []
    per_file: dict[str, dict[str, Any]] = {}

    for filename in selected_names:
        path = docs_dir / filename
        normalized = normalize_document(filename, path.read_bytes())
        per_file[filename] = {"normalized": normalized, "results": {}}
        print(f"\nDOCUMENT: {filename} | format={normalized.source_format} | chars={len(normalized.markdown)}")
        for strategy in ("fixed", "structure"):
            row, chunks = summarize_strategy(normalized.markdown, filename, args.chunk_size, args.overlap, strategy)
            row["normalization"] = {
                "warnings": normalized.warnings,
                "removed_repeated_margin_lines": normalized.removed_repeated_margin_lines,
            }
            per_file[filename]["results"][strategy] = row
            all_chunks[strategy].extend(chunks)
            rows.append(row)
            integrity = row["structural_integrity"]
            print(
                f"  {strategy:9s} chunks={row['chunk_count']:3d} avg_chars={row['average_characters']:7.2f} "
                f"oversized={row['oversized_chunk_count']:2d} structural_integrity="
                f"{integrity['intact_structural_units']}/{integrity['expected_structural_units']} "
                f"({integrity['integrity_rate'] * 100:.1f}%)"
            )

    source_hits: dict[str, dict[str, Any]] = {}
    total_questions = len(questions)
    for strategy in ("fixed", "structure"):
        hits = 0
        reciprocal_rank_sum = 0.0
        details = []
        for q in questions:
            ranked = sorted(
                all_chunks[strategy],
                key=lambda c: lexical_score(q["question"], c),
                reverse=True,
            )
            top_three = ranked[:3]
            relevant_rank = next(
                (
                    rank for rank, chunk in enumerate(ranked, start=1)
                    if chunk.get("source", {}).get("file") == q["expected_source"]
                    and expected_topic_in_chunk(chunk, q["expected_topic"])
                ),
                None,
            )
            hit = relevant_rank is not None and relevant_rank <= 3
            reciprocal_rank = 1.0 / relevant_rank if relevant_rank else 0.0
            hits += int(hit)
            reciprocal_rank_sum += reciprocal_rank
            details.append({
                "question": q["question"], "expected_source": q["expected_source"],
                "expected_topic": q["expected_topic"], "hit_at_3": bool(hit),
                "first_relevant_rank": relevant_rank,
                "reciprocal_rank": round(reciprocal_rank, 4),
                "top3_sources": [c.get("source", {}).get("file", "") for c in top_three],
            })
        source_hits[strategy] = {
            "hits": hits,
            "total": total_questions,
            "rate": round(hits / total_questions, 4) if total_questions else 0.0,
            "mrr": round(reciprocal_rank_sum / total_questions, 4) if total_questions else 0.0,
            "details": details,
        }

    # Test format-normalization fixtures independently, including the PDF margin fixture.
    fixture_results = []
    for path in sorted((HERE / "source_formats").iterdir()):
        if path.suffix.lower() not in {".txt", ".md", ".html", ".htm", ".pdf", ".docx"}:
            continue
        try:
            normalized = normalize_document(path.name, path.read_bytes())
            blocks = parse_markdown_blocks(normalized.markdown)
            entry = {
                "filename": path.name,
                "source_format": normalized.source_format,
                "normalized_characters": len(normalized.markdown),
                "heading_count": len(re.findall(r"^#{1,6}\s+", normalized.markdown, flags=re.MULTILINE)),
                "table_blocks": sum(b["chunk_type"] == "table" for b in blocks),
                "code_blocks": sum(b["chunk_type"] == "code" for b in blocks),
                "list_blocks": sum(b["chunk_type"] == "list" for b in blocks),
                "removed_repeated_margin_lines": normalized.removed_repeated_margin_lines,
                "warnings": normalized.warnings,
                "status": "ok" if normalized.markdown.strip() else "empty",
            }
        except Exception as exc:
            entry = {"filename": path.name, "status": "error", "error": str(exc)}
        fixture_results.append(entry)
        print(f"\nFORMAT FIXTURE: {entry['filename']} -> {entry['status']}")
        if entry["status"] == "ok":
            print(f"  format={entry['source_format']} chars={entry['normalized_characters']} "
                  f"headings={entry['heading_count']} tables={entry['table_blocks']} "
                  f"code={entry['code_blocks']} lists={entry['list_blocks']} "
                  f"margin_lines_removed={entry['removed_repeated_margin_lines']}")

    report = {
        "dataset": "SmartChunk synthetic mentor demo corpus",
        "settings": {"chunk_size_characters": args.chunk_size, "overlap_characters": args.overlap, "semantic": False},
        "per_document": per_file,
        "expected_source_topic_hit_at_3": source_hits,
        "normalization_fixtures": fixture_results,
        "warning": "Synthetic diagnostic benchmark. Structural integrity and lexical hit@3 are not proof of RAG answer accuracy.",
    }

    # Make report JSON serializable without dataclass objects.
    json_report = {
        "dataset": report["dataset"], "settings": report["settings"],
        "per_document": {
            name: {
                "normalization": {
                    "source_format": val["normalized"].source_format,
                    "warnings": val["normalized"].warnings,
                    "removed_repeated_margin_lines": val["normalized"].removed_repeated_margin_lines,
                    "normalized_characters": len(val["normalized"].markdown),
                },
                "results": val["results"],
            } for name, val in per_file.items()
        },
        "expected_source_topic_hit_at_3": source_hits,
        "normalization_fixtures": fixture_results,
        "warning": report["warning"],
    }
    (HERE / "benchmark_results.json").write_text(json.dumps(json_report, indent=2), encoding="utf-8")
    with (HERE / "benchmark_results.csv").open("w", newline="", encoding="utf-8") as file:
        flat_rows = []
        for filename, value in per_file.items():
            for strategy, row in value["results"].items():
                flat_rows.append({
                    "filename": filename, "strategy": strategy,
                    "chunk_count": row["chunk_count"],
                    "average_characters": row["average_characters"],
                    "min_characters": row["min_characters"],
                    "max_characters": row["max_characters"],
                    "duplicate_rate": row["duplicate_rate"],
                    "oversized_chunk_count": row["oversized_chunk_count"],
                    "structural_units": row["structural_integrity"]["expected_structural_units"],
                    "intact_structural_units": row["structural_integrity"]["intact_structural_units"],
                    "structural_integrity_rate": row["structural_integrity"]["integrity_rate"],
                })
        writer = csv.DictWriter(file, fieldnames=list(flat_rows[0].keys()) if flat_rows else ["filename"])
        writer.writeheader()
        writer.writerows(flat_rows)

    print("\nEXPECTED SOURCE/TOPIC LEXICAL METRICS")
    for strategy, result in source_hits.items():
        print(
            f"  {strategy:9s} Hit@3={result['hits']}/{result['total']} "
            f"({result['rate'] * 100:.1f}%), MRR={result['mrr']:.4f}"
        )
    print("\nReports written:")
    print(f"  {HERE / 'benchmark_results.json'}")
    print(f"  {HERE / 'benchmark_results.csv'}")
    print("Note: report genuine outcomes; these small lexical checks are diagnostics, not answer accuracy.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunk-size", type=int, default=700, help="Maximum chunk size in characters (default: 700)")
    parser.add_argument("--overlap", type=int, default=80, help="Fixed-size baseline overlap in characters (default: 80)")
    args = parser.parse_args()
    if args.chunk_size < 1 or args.overlap < 0 or args.overlap >= args.chunk_size:
        parser.error("chunk-size must be positive and overlap must be non-negative and smaller than chunk-size")
    return args


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
