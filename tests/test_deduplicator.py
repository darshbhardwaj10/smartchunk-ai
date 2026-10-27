from chunking_engine.deduplicator import deduplicate_chunks, normalize_for_dedup


def _chunk(text, heading="Heading", kind="prose"):
    return {
        "chunk_id": "tmp",
        "text": text,
        "heading_path": [heading],
        "chunk_type": kind,
        "source": {"file": "in.md", "location": "section"},
        "parent_id": None,
        "char_count": len(text),
        "oversized": False,
    }


def test_normalization_ignores_injected_heading_context():
    assert normalize_for_dedup("Section: A > B\n\nHello, World!") == normalize_for_dedup("Hello World")


def test_exact_duplicates_removed_across_sections():
    chunks = [_chunk("Same content.", "A"), _chunk("Same content.", "B")]
    output = deduplicate_chunks(chunks, "doc.md", remove_near_duplicates=False)
    assert len(output) == 1


def test_distinct_chunk_types_are_kept_for_near_duplicate_check():
    content = "word " * 40
    chunks = [_chunk(content, "A", "prose"), _chunk(content + "different", "A", "table")]
    output = deduplicate_chunks(chunks, "doc.md", remove_near_duplicates=True)
    # Exact dedup still applies across types; the test uses different content to confirm both remain.
    assert len(output) == 2