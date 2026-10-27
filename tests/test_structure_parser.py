from chunking_engine.structure_parser import parse_markdown_blocks


def test_nested_heading_path_is_preserved():
    blocks = parse_markdown_blocks("# Handbook\n\n## Attendance\n\nKeep attendance above 75%.")
    assert blocks
    assert blocks[-1]["heading_path"] == ["Handbook", "Attendance"]


def test_code_fence_is_single_code_block():
    text = "```python\ndef hello():\n    return 'hi'\n```"
    blocks = parse_markdown_blocks(text)
    assert len(blocks) == 1
    assert blocks[0]["chunk_type"] == "code"
    assert "def hello" in blocks[0]["text"]


def test_table_is_single_table_block():
    text = "| A | B |\n|---|---|\n| 1 | 2 |"
    blocks = parse_markdown_blocks(text)
    assert len(blocks) == 1
    assert blocks[0]["chunk_type"] == "table"


def test_page_marker_sets_page_number():
    text = "<!-- smartchunk:page=3 -->\n\nPage three content."
    blocks = parse_markdown_blocks(text)
    assert blocks
    assert blocks[0]["page"] == 3