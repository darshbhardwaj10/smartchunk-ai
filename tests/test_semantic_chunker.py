import pytest

from chunking_engine.semantic_chunker import semantic_split_prose


def _fallback(text, max_chars, overlap):
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]


def test_single_sentence_uses_fallback_without_loading_model():
    result = semantic_split_prose("A single sentence.", 100, 0, _fallback)
    assert result == ["A single sentence."]


def test_invalid_threshold_is_rejected_before_model_load():
    with pytest.raises(ValueError):
        semantic_split_prose("One. Two.", 100, 0, _fallback, similarity_threshold=1.5)