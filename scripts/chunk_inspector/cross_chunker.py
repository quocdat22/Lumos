"""Compatibility module providing cross-page chunking utilities for chunk_inspector.

Imports directly from core lumos.core.chunker where cross-page continuous chunking,
header/footer cleaning, and bidirectional linking are natively implemented.
"""

from lumos.core.chunker import (
    DEFAULT_FOOTER_PATTERNS,
    DocumentChunk,
    DocumentChunk as InspectorChunk,
    RecursiveChunker,
    RecursiveChunker as CrossPageChunker,
    clean_section_text,
    find_chunk_overlap,
)

__all__ = [
    "DEFAULT_FOOTER_PATTERNS",
    "clean_section_text",
    "find_chunk_overlap",
    "InspectorChunk",
    "CrossPageChunker",
    "DocumentChunk",
    "RecursiveChunker",
]

