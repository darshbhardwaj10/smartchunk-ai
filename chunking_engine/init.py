"""SmartChunk's document chunking engine.

Public API:
    chunk_document: structure-aware chunking
    fixed_size_chunks: naive baseline
    calculate_metrics: chunk statistics
    parse_markdown_blocks: inspect parsed structural blocks
"""

from .chunker import calculate_metrics, chunk_document, fixed_size_chunks
from .structure_parser import parse_markdown_blocks

__all__ = [
    "calculate_metrics",
    "chunk_document",
    "fixed_size_chunks",
    "parse_markdown_blocks",
]