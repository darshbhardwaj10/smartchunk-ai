from chunking_engine.chunker import calculate_metrics, chunk_document, fixed_size_chunks


def test_structure_chunking_keeps_heading_metadata():
    text = "# Student Handbook\n\n## Attendance\n\nStudents should maintain at least 75% attendance."
    chunks = chunk_document(text, "test.md", chunk_size=300, overlap=20)
    assert chunks
    assert any("Attendance" in chunk["heading_path"] for chunk in chunks)


def test_fixed_size_chunking_returns_metadata():
    chunks = fixed_size_chunks("A short document for testing.", "test.txt", 200, 20)
    assert len(chunks) == 1
    assert chunks[0]["source"]["file"] == "test.txt"
    assert chunks[0]["char_count"] > 0


def test_table_and_code_detection():
    text = """# Guide

| Item | Value |
|---|---|
| A | 1 |

```python
def answer():
    return 42
```
"""
    chunks = chunk_document(text, "guide.md", 300, 20)
    types = {chunk["chunk_type"] for chunk in chunks}
    assert "table" in types
    assert "code" in types


def test_duplicate_removal():
    repeated = "This is the same sentence used to test duplicate removal."
    text = f"# Topic\n\n{repeated}\n\n## Another Topic\n\n{repeated}"
    chunks = chunk_document(text, "duplicate.md", 300, 20)
    matches = [chunk for chunk in chunks if repeated in chunk["text"]]
    assert len(matches) == 1


def test_empty_metrics():
    metrics = calculate_metrics([])
    assert metrics["chunk_count"] == 0
    assert metrics["average_characters"] == 0.0
    assert metrics["duplicate_rate"] == 0.0


def test_invalid_chunk_settings_raise_value_error():
    try:
        chunk_document("Some text.", "x.md", chunk_size=100, overlap=100)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected invalid settings to raise ValueError")


def test_pdf_page_marker_is_preserved_as_source_metadata():
    text = "<!-- smartchunk:page=2 -->\n\n## Policies\n\nKeep the original page number."
    chunks = chunk_document(text, "manual.pdf", chunk_size=300, overlap=20)
    assert chunks
    assert all("smartchunk:page=" not in chunk["text"] for chunk in chunks)
    assert any(chunk["source"].get("page") == 2 for chunk in chunks)