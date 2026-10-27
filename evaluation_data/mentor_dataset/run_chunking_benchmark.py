"""Run offline baseline-vs-SmartChunk evaluations from the repository root.

Example:
    python evaluation_data/mentor_dataset/run_chunking_benchmark.py --chunk-size 700 --overlap 80

This is a lexical/structural diagnostic benchmark, not a claim of general RAG answer accuracy.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EVALUATION_DIR = HERE.parent
PROJECT_ROOT = EVALUATION_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.normalizer import NormalizationError, normalize_document
from chunking_engine.chunker import calculate_metrics, chunk_document, fixed_size_chunks
from chunking_engine.structure_parser import parse_markdown_blocks

try:
    from backend.retrieval import retrieve_chunks
except Exception:  # pragma: no cover - fallback supports older branches
    retrieve_chunks = None

STOP_WORDS = {
    "a", "an", "the", "and", "or", "is", "are", "to", "of", "in", "on", "for",
    "what", "which", "how", "can", "does", "do", "should", "be", "by", "with", "it",
    "this", "that", "their", "from", "at", "as", "up", "when", "where", "must", "not",
    "who", "why", "long", "many", "much", "does", "your", "into", "after", "before",
}


def tokens(value: str) -> list[str]:
    return [w for w in re.findall(r"[\w]+(?:['’-][\w]+)*", value.casefold(), flags=re.UNICODE) if w not in STOP_WORDS]


def normalize_text(value: str) -> str:
    """Normalize whitespace and case for exact evidence-span checks."""
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def lexical_score(query: str, chunk: dict[str, Any]) -> float:
    query_tokens = set(tokens(query))
    chunk_tokens = set(tokens(" ".join(chunk.get("heading_path", [])) + " " + str(chunk.get("text", ""))))
    return len(query_tokens & chunk_tokens) / max(1, len(query_tokens))


def rank_chunks(question: str, chunks: list[dict[str, Any]], top_k: int = 20) -> list[dict[str, Any]]:
    """Rank chunks with the backend retriever when available; otherwise use lexical overlap."""
    if not chunks:
        return []
    if retrieve_chunks is not None:
        try:
            return retrieve_chunks(question, chunks, top_k=min(max(1, top_k), 20))
        except Exception:
            pass
    ranked = sorted(enumerate(chunks), key=lambda pair: (-lexical_score(question, pair[1]), pair[0]))
    output = []
    for _, chunk in ranked[:top_k]:
        score = lexical_score(question, chunk)
        if score > 0:
            value = dict(chunk)
            value["retrieval_score"] = score
            output.append(value)
    return output


def expected_topic_in_chunk(chunk: dict[str, Any], topic: str) -> bool:
    haystack = normalize_text(" ".join(chunk.get("heading_path", [])) + " " + str(chunk.get("text", "")))
    target = normalize_text(topic)
    return target in haystack if target else True


def required_evidence_items(question: dict[str, Any]) -> list[dict[str, str]]:
    raw = question.get("required_evidence") or []
    result: list[dict[str, str]] = []
    for index, item in enumerate(raw, start=1):
        if isinstance(item, str):
            evidence_id, text = f"evidence_{index}", item
        elif isinstance(item, dict):
            evidence_id, text = str(item.get("evidence_id") or f"evidence_{index}"), str(item.get("text") or "")
        else:
            continue
        if text.strip():
            result.append({"evidence_id": evidence_id, "text": text})
    return result


def evidence_metrics(questions: list[dict[str, Any]], chunks: list[dict[str, Any]], top_k: int = 3) -> dict[str, Any]:
    """Compute evidence completeness and coverage from human-labelled text spans.

    A span is counted as found when its normalized text is present in at least one
    retrieved chunk. Manually verify source spans; this metric is not an answer judge.
    """
    eligible = [q for q in questions if required_evidence_items(q)]
    if not eligible:
        return {
            "question_count": 0, "evidence_item_count": 0, "evidence_items_found": 0,
            "evidence_coverage_at_k": None, "evidence_completeness_at_k": None, "details": [],
        }
    question_count_complete = 0
    total_items = 0
    found_items = 0
    details: list[dict[str, Any]] = []
    for question in eligible:
        evidences = required_evidence_items(question)
        source_name = question.get("expected_source")
        scoped_chunks = [c for c in chunks if (c.get("source") or {}).get("file") == source_name] if source_name else chunks
        ranked = rank_chunks(str(question.get("question", "")), scoped_chunks, top_k=top_k)
        retrieved_texts = [normalize_text(c.get("text", "")) for c in ranked]
        evidence_rows = []
        found_count = 0
        for evidence in evidences:
            needle = normalize_text(evidence["text"])
            found = bool(needle) and any(needle in source for source in retrieved_texts)
            found_count += int(found)
            evidence_rows.append({"evidence_id": evidence["evidence_id"], "text": evidence["text"], "found_in_top_k": found})
        total_items += len(evidences)
        found_items += found_count
        complete = bool(evidences) and found_count == len(evidences)
        question_count_complete += int(complete)
        details.append({
            "question_id": question.get("question_id"),
            "question": question.get("question"),
            "top_k": top_k,
            "required_evidence_count": len(evidences),
            "evidence_items_found": found_count,
            "complete": complete,
            "evidence": evidence_rows,
            "retrieved_chunk_ids": [str(c.get("chunk_id", "")) for c in ranked],
        })
    return {
        "question_count": len(eligible),
        "evidence_item_count": total_items,
        "evidence_items_found": found_items,
        "evidence_coverage_at_k": round(found_items / total_items, 4) if total_items else 0.0,
        "evidence_completeness_at_k": round(question_count_complete / len(eligible), 4) if eligible else 0.0,
        "details": details,
    }


def _normalize_block(text: str) -> str:
    return normalize_text(text)


def structural_units(markdown: str) -> list[dict[str, str]]:
    return [
        {"type": str(block["chunk_type"]), "text": str(block["text"])}
        for block in parse_markdown_blocks(markdown)
        if block.get("chunk_type") in {"table", "code", "list"} and str(block.get("text", "")).strip()
    ]


def structural_integrity(markdown: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    units = structural_units(markdown)
    chunk_texts = [_normalize_block(chunk.get("text", "")) for chunk in chunks]
    breakdown: dict[str, dict[str, int]] = {}
    for kind in ("table", "code", "list"):
        selected = [unit for unit in units if unit["type"] == kind]
        intact = sum(1 for unit in selected if any(_normalize_block(unit["text"]) in text for text in chunk_texts))
        breakdown[kind] = {"expected": len(selected), "intact": intact}
    total = len(units)
    intact_total = sum(row["intact"] for row in breakdown.values())
    return {
        "expected_structural_units": total,
        "intact_structural_units": intact_total,
        "integrity_rate": round(intact_total / total, 4) if total else 1.0,
        "by_type": breakdown,
    }


def _run_strategy(markdown: str, filename: str, size: int, overlap: int, strategy: str, repeats: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    function = fixed_size_chunks if strategy == "fixed" else chunk_document
    samples = []
    last_chunks: list[dict[str, Any]] = []
    for _ in range(max(1, repeats)):
        start = time.perf_counter()
        if strategy == "fixed":
            last_chunks = function(markdown, filename, size, overlap)
        else:
            last_chunks = function(markdown, filename, size, overlap, semantic=False)
        samples.append((time.perf_counter() - start) * 1000)
    metrics = calculate_metrics(last_chunks)
    source_coverage_count = sum(
        bool((chunk.get("source") or {}).get("file")) and bool((chunk.get("source") or {}).get("location"))
        for chunk in last_chunks
    )
    count = len(last_chunks)
    oversized = int(metrics.get("oversized_chunk_count", 0))
    result = {
        "strategy": strategy,
        "filename": filename,
        **metrics,
        "size_compliance_rate": round((count - oversized) / count, 4) if count else 1.0,
        "chunks_with_source_location": source_coverage_count,
        "source_metadata_coverage": round(source_coverage_count / count, 4) if count else 1.0,
        "structural_integrity": structural_integrity(markdown, last_chunks),
        "processing_time_ms_median": round(statistics.median(samples), 3),
        "timing_repeats": max(1, repeats),
    }
    return result, last_chunks


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run(args: argparse.Namespace) -> int:
    docs_dir = HERE / "documents"
    questions = _load_json(HERE / "questions.json")
    multi_bundle = _load_json(HERE / "multi_evidence_cases.json")
    multi_questions = multi_bundle.get("cases", [])
    all_questions = questions + multi_questions
    document_names = sorted({str(question["expected_source"]) for question in all_questions})
    output_dir = Path(args.output_dir).resolve() if args.output_dir else EVALUATION_DIR / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    all_chunks: dict[str, list[dict[str, Any]]] = {"fixed": [], "structure": []}
    per_file: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []

    for filename in document_names:
        path = docs_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Question references a missing document: {path}")
        normalized = normalize_document(filename, path.read_bytes())
        per_file[filename] = {
            "normalization": {
                "source_format": normalized.source_format,
                "normalized_characters": len(normalized.markdown),
                "warnings": list(normalized.warnings),
                "removed_repeated_margin_lines": normalized.removed_repeated_margin_lines,
            },
            "strategies": {},
        }
        print(f"\nDOCUMENT: {filename} | format={normalized.source_format} | chars={len(normalized.markdown)}")
        for strategy in ("fixed", "structure"):
            result, chunks = _run_strategy(normalized.markdown, filename, args.chunk_size, args.overlap, strategy, args.timing_repeats)
            per_file[filename]["strategies"][strategy] = result
            all_chunks[strategy].extend(chunks)
            row = {key: value for key, value in result.items() if key != "chunk_types" and key != "structural_integrity"}
            row.update({
                "structural_units": result["structural_integrity"]["expected_structural_units"],
                "intact_structural_units": result["structural_integrity"]["intact_structural_units"],
                "structural_integrity_rate": result["structural_integrity"]["integrity_rate"],
            })
            rows.append(row)
            si = result["structural_integrity"]
            print(
                f"  {strategy:9s} chunks={result['chunk_count']:3d} avg_chars={result['average_characters']:7.2f} "
                f"oversized={result['oversized_chunk_count']:2d} structural={si['intact_structural_units']}/{si['expected_structural_units']} "
                f"({si['integrity_rate'] * 100:.1f}%) time_median={result['processing_time_ms_median']:.2f}ms"
            )

    source_topic_report: dict[str, Any] = {}
    for strategy, chunks in all_chunks.items():
        hits_at_3 = 0
        reciprocal_rank_sum = 0.0
        details = []
        for question in questions:
            ranked = rank_chunks(str(question["question"]), chunks, top_k=20)
            relevant_rank = next((rank for rank, chunk in enumerate(ranked, start=1)
                if (chunk.get("source") or {}).get("file") == question["expected_source"]
                and expected_topic_in_chunk(chunk, question.get("expected_topic", ""))), None)
            hit = relevant_rank is not None and relevant_rank <= 3
            hits_at_3 += int(hit)
            reciprocal_rank_sum += (1.0 / relevant_rank if relevant_rank else 0.0)
            details.append({
                "question_id": question.get("question_id"),
                "question": question["question"],
                "expected_source": question["expected_source"],
                "expected_topic": question.get("expected_topic", ""),
                "hit_at_3": bool(hit),
                "first_relevant_rank_within_20": relevant_rank,
                "reciprocal_rank_at_20": round(1.0 / relevant_rank, 4) if relevant_rank else 0.0,
                "top3_chunk_ids": [str(item.get("chunk_id", "")) for item in ranked[:3]],
                "top3_sources": [(item.get("source") or {}).get("file", "") for item in ranked[:3]],
            })
        source_topic_report[strategy] = {
            "question_count": len(questions),
            "hit_at_3_count": hits_at_3,
            "hit_at_3_rate": round(hits_at_3 / len(questions), 4) if questions else 0.0,
            "mrr_at_20": round(reciprocal_rank_sum / len(questions), 4) if questions else 0.0,
            "details": details,
        }

    multi_report: dict[str, Any] = {}
    for strategy, chunks in all_chunks.items():
        multi_report[strategy] = evidence_metrics(multi_questions, chunks, top_k=args.top_k)

    fixture_results: list[dict[str, Any]] = []
    fixtures_dir = HERE / "source_formats"
    supported = {".txt", ".md", ".html", ".htm", ".pdf", ".docx"}
    for fixture in sorted(fixtures_dir.iterdir()):
        if not fixture.is_file() or fixture.suffix.lower() not in supported:
            continue
        try:
            normalized = normalize_document(fixture.name, fixture.read_bytes())
            blocks = parse_markdown_blocks(normalized.markdown)
            entry = {
                "filename": fixture.name,
                "source_format": normalized.source_format,
                "normalized_characters": len(normalized.markdown),
                "heading_count": len(re.findall(r"^#{1,6}\s+", normalized.markdown, flags=re.MULTILINE)),
                "table_blocks": sum(block.get("chunk_type") == "table" for block in blocks),
                "code_blocks": sum(block.get("chunk_type") == "code" for block in blocks),
                "list_blocks": sum(block.get("chunk_type") == "list" for block in blocks),
                "removed_repeated_margin_lines": normalized.removed_repeated_margin_lines,
                "warnings": list(normalized.warnings),
                "status": "ok" if normalized.markdown.strip() else "empty",
            }
        except Exception as exc:
            entry = {"filename": fixture.name, "status": "error", "error": f"{type(exc).__name__}: {exc}"}
        fixture_results.append(entry)
        print(f"FORMAT FIXTURE: {entry['filename']} -> {entry['status']}")

    report = {
        "dataset": "SmartChunk synthetic mentor corpus",
        "settings": {"chunk_size_characters": args.chunk_size, "overlap_characters": args.overlap,
                     "semantic": False, "retrieval_method": "backend BM25-style lexical retriever when available",
                     "evidence_top_k": args.top_k, "timing_repeats": args.timing_repeats},
        "per_document": per_file,
        "expected_source_topic_retrieval": source_topic_report,
        "multi_evidence_retrieval": multi_report,
        "normalization_fixtures": fixture_results,
        "limitations": [
            "The corpus is synthetic and small; do not generalize scores to real-world documents.",
            "Hit@3 and MRR measure lexical retrieval ranking, not generated-answer accuracy.",
            "Evidence spans must be manually verified against the documents.",
            "Processing-time results are local measurements; use repeated runs and the same hardware for comparisons.",
            "The benchmark does not by itself measure prompt-injection resistance, authorization, or external index synchronization."
        ],
    }
    json_path = output_dir / "chunking_benchmark.json"
    csv_path = output_dir / "chunking_benchmark.csv"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        fieldnames = list(rows[0].keys()) if rows else ["filename", "strategy"]
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print("\nSOURCE/TOPIC RETRIEVAL")
    for strategy, value in source_topic_report.items():
        print(f"{strategy:9s} Hit@3={value['hit_at_3_count']}/{value['question_count']} "
              f"({value['hit_at_3_rate'] * 100:.1f}%), MRR@20={value['mrr_at_20']:.4f}")
    for strategy, value in multi_report.items():
        coverage = value['evidence_coverage_at_k']
        completeness = value['evidence_completeness_at_k']
        print(f"{strategy:9s} Evidence Coverage@{args.top_k}={coverage if coverage is not None else 'n/a'} "
              f"Evidence Completeness@{args.top_k}={completeness if completeness is not None else 'n/a'}")
    print(f"\nReports written:\n  {json_path}\n  {csv_path}")
    print("Interpret results as diagnostics; report improvements and regressions honestly.")
    return 0 if all(item.get("status") == "ok" for item in fixture_results) else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunk-size", type=int, default=700, help="Chunk size in characters (default: 700)")
    parser.add_argument("--overlap", type=int, default=80, help="Fixed baseline overlap in characters (default: 80)")
    parser.add_argument("--top-k", type=int, default=3, help="k for evidence coverage/completeness (default: 3)")
    parser.add_argument("--timing-repeats", type=int, default=3, help="Repeated chunking runs for median processing time")
    parser.add_argument("--output-dir", default=None, help="Optional output directory; defaults to evaluation_data/results")
    args = parser.parse_args(argv)
    if args.chunk_size < 200 or args.chunk_size > 2000:
        parser.error("chunk-size must be between 200 and 2000")
    if args.overlap < 0 or args.overlap >= args.chunk_size or args.overlap > 400:
        parser.error("overlap must be 0-400 and smaller than chunk-size")
    if args.top_k < 1 or args.top_k > 20:
        parser.error("top-k must be between 1 and 20")
    if args.timing_repeats < 1 or args.timing_repeats > 10:
        parser.error("timing-repeats must be between 1 and 10")
    return args


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
