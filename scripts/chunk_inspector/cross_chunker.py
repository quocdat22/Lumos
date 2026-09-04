"""Cross-page continuous chunker with bidirectional linking and layout cleaning for chunk_inspector.

Provides CrossPageChunker and InspectorChunk to enable natural chunk continuity
and overlap across page boundaries without touching core src/ modules.
"""

from dataclasses import dataclass, field
import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple

from lumos.core.chunker import RecursiveChunker
from lumos.core.parser import DocumentSection


DEFAULT_FOOTER_PATTERNS = [
    # Timestamp lines: e.g. "9/1/26, 12:59 AM" or "2026-09-01 12:59"
    re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?$", re.IGNORECASE),
    # URLs: e.g. "https://www.anthropic.com/engineering/building-effective-agents"
    re.compile(r"^https?://\S+$", re.IGNORECASE),
    # Page counts: e.g. "1/19", "2 / 19", "Page 1 of 19"
    re.compile(r"^\d+\s*/\s*\d+$"),
    re.compile(r"^(?:page\s+)?\d+(?:\s+of\s+\d+)?$", re.IGNORECASE),
]


def clean_section_text(
    text: str,
    book_title: str = "",
    footer_patterns: Optional[List[re.Pattern]] = None,
) -> str:
    """Removes common repeating PDF footer and header artifacts from page text."""
    if not text.strip():
        return ""

    patterns = footer_patterns or DEFAULT_FOOTER_PATTERNS
    lines = text.splitlines()
    cleaned_lines: List[str] = []

    norm_title = book_title.strip().lower()

    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            cleaned_lines.append("")
            continue

        # Check regex patterns
        if any(p.match(line) for p in patterns):
            continue

        # Check if line matches book_title and is near the top or bottom of the page
        is_edge_line = (idx < 3) or (idx >= len(lines) - 5)
        if is_edge_line and norm_title and (line.lower() == norm_title or norm_title.startswith(line.lower())):
            continue

        cleaned_lines.append(raw_line)

    return "\n".join(cleaned_lines).strip()


@dataclass
class InspectorChunk:
    """Extended chunk representation with cross-page span and bidirectional linking."""

    chunk_id: str
    chunk_index: int
    text: str
    book_title: str
    section: str
    source_file: str
    page_start: int
    page_end: int
    pages: List[int] = field(default_factory=list)
    prev_chunk_id: Optional[str] = None
    next_chunk_id: Optional[str] = None
    overlap_prev_text: str = ""
    overlap_prev_chars: int = 0

    @property
    def char_count(self) -> int:
        return len(self.text)

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    def to_metadata(self) -> Dict[str, Any]:
        """Converts chunk into primitive metadata compatible with ChromaDB."""
        meta: Dict[str, Any] = {
            "chunk_id": self.chunk_id,
            "book_title": self.book_title,
            "section": self.section,
            "source_file": self.source_file,
            "chunk_index": self.chunk_index,
            "page_start": self.page_start,
            "page_end": self.page_end,
        }
        if self.prev_chunk_id is not None:
            meta["prev_chunk_id"] = self.prev_chunk_id
        if self.next_chunk_id is not None:
            meta["next_chunk_id"] = self.next_chunk_id
        return meta

    def to_dict(self, include_full_text: bool = True) -> Dict[str, Any]:
        """Full serialization for JSON export and inspection."""
        data: Dict[str, Any] = {
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "book_title": self.book_title,
            "section": self.section,
            "source_file": self.source_file,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "pages": self.pages,
            "char_count": len(self.text),
            "word_count": len(self.text.split()),
            "overlap_prev_chars": self.overlap_prev_chars,
            "prev_chunk_id": self.prev_chunk_id,
            "next_chunk_id": self.next_chunk_id,
        }
        if include_full_text:
            data["text"] = self.text
            data["overlap_prev_text"] = self.overlap_prev_text
        else:
            data["preview"] = self.text[:100] + ("..." if len(self.text) > 100 else "")
            data["overlap_prev_preview"] = (
                self.overlap_prev_text[:80] + "..." if len(self.overlap_prev_text) > 80 else self.overlap_prev_text
            )
        return data


def find_chunk_overlap(text1: str, text2: str, max_check: int = 500) -> str:
    """Finds the longest suffix of text1 that is a prefix of text2."""
    if not text1 or not text2:
        return ""
    check_len = min(len(text1), len(text2), max_check)
    for length in range(check_len, 5, -1):
        suffix = text1[-length:]
        if text2.startswith(suffix):
            return suffix
    return ""


class CrossPageChunker:
    """Chunks documents across page boundaries preserving context continuity and overlap."""

    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 150,
        cross_page: bool = True,
        clean_headers_footers: bool = True,
    ):
        if chunk_overlap >= chunk_size:
            raise ValueError(f"chunk_overlap ({chunk_overlap}) must be strictly less than chunk_size ({chunk_size})")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.cross_page = cross_page
        self.clean_headers_footers = clean_headers_footers
        self._base_chunker = RecursiveChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def _extract_page_number(self, section_name: str, fallback_index: int) -> int:
        """Parses integer page number from section string like 'Page 3' or returns fallback."""
        m = re.search(r"Page\s+(\d+)", section_name, re.IGNORECASE)
        if m:
            return int(m.group(1))
        return fallback_index

    def chunk_sections(self, sections: List[DocumentSection]) -> List[InspectorChunk]:
        """Chunks a list of DocumentSections with cross-page continuity and bidirectional linking."""
        if not sections:
            return []

        if not self.cross_page:
            return self._chunk_sections_isolated(sections)

        return self._chunk_sections_continuous(sections)

    def _chunk_sections_continuous(self, sections: List[DocumentSection]) -> List[InspectorChunk]:
        """Builds a continuous document text stream, chunks across pages, and maps spans."""
        page_ranges: List[Tuple[int, int, int, str, DocumentSection]] = []
        combined_parts: List[str] = []
        curr_offset = 0

        for i, sec in enumerate(sections):
            page_num = self._extract_page_number(sec.section, i + 1)
            raw_text = sec.text or ""
            text = clean_section_text(raw_text, sec.book_title) if self.clean_headers_footers else raw_text
            text = text.strip()
            if not text:
                continue

            if combined_parts:
                combined_parts.append("\n\n")
                curr_offset += 2

            start_offset = curr_offset
            end_offset = curr_offset + len(text)
            combined_parts.append(text)
            curr_offset = end_offset
            page_ranges.append((start_offset, end_offset, page_num, sec.section, sec))

        full_text = "".join(combined_parts)
        if not full_text:
            return []

        raw_chunks = self._base_chunker.split_text(full_text)
        if not raw_chunks:
            return []

        chunks: List[InspectorChunk] = []
        book_title = sections[0].book_title
        source_file = sections[0].source_file
        search_pos = 0

        for idx, chunk_text in enumerate(raw_chunks):
            # Locate chunk offset within continuous full_text
            c_start = full_text.find(chunk_text, search_pos)
            if c_start == -1:
                c_start = full_text.find(chunk_text)
            if c_start == -1:
                # Fallback to search_pos if exact slice cannot be found
                c_start = search_pos
            c_end = c_start + len(chunk_text)
            search_pos = max(search_pos, c_start + 1)

            # Find all pages that overlap with [c_start, c_end]
            matched_pages: List[int] = []
            for p_start, p_end, p_num, _, _ in page_ranges:
                if c_start < p_end and c_end > p_start:
                    matched_pages.append(p_num)

            if not matched_pages:
                matched_pages = [1]

            p_start = min(matched_pages)
            p_end = max(matched_pages)

            if p_start == p_end:
                sec_label = f"Page {p_start}"
            else:
                sec_label = f"Pages {p_start} - {p_end}"

            chunk_id = hashlib.sha256(
                f"{source_file}_{sec_label}_{idx}_{chunk_text[:50]}".encode("utf-8")
            ).hexdigest()[:16]

            chunks.append(
                InspectorChunk(
                    chunk_id=chunk_id,
                    chunk_index=idx,
                    text=chunk_text,
                    book_title=book_title,
                    section=sec_label,
                    source_file=source_file,
                    page_start=p_start,
                    page_end=p_end,
                    pages=matched_pages,
                )
            )

        # Wire up bidirectional linking and overlap info
        for idx, c in enumerate(chunks):
            if idx > 0:
                c.prev_chunk_id = chunks[idx - 1].chunk_id
                ov = find_chunk_overlap(chunks[idx - 1].text, c.text)
                c.overlap_prev_text = ov
                c.overlap_prev_chars = len(ov)
            if idx < len(chunks) - 1:
                c.next_chunk_id = chunks[idx + 1].chunk_id

        return chunks

    def _chunk_sections_isolated(self, sections: List[DocumentSection]) -> List[InspectorChunk]:
        """Fallback mode: chunks sections in isolation (legacy behavior)."""
        chunks: List[InspectorChunk] = []
        global_index = 0

        for i, sec in enumerate(sections):
            page_num = self._extract_page_number(sec.section, i + 1)
            raw_text = sec.text or ""
            text = clean_section_text(raw_text, sec.book_title) if self.clean_headers_footers else raw_text
            text_chunks = self._base_chunker.split_text(text)

            for chunk_str in text_chunks:
                chunk_id = hashlib.sha256(
                    f"{sec.source_file}_{sec.section}_{global_index}_{chunk_str[:50]}".encode("utf-8")
                ).hexdigest()[:16]

                chunk = InspectorChunk(
                    chunk_id=chunk_id,
                    chunk_index=global_index,
                    text=chunk_str,
                    book_title=sec.book_title,
                    section=sec.section,
                    source_file=sec.source_file,
                    page_start=page_num,
                    page_end=page_num,
                    pages=[page_num],
                )
                chunks.append(chunk)
                global_index += 1

        # Wire up links and overlap
        for idx, c in enumerate(chunks):
            if idx > 0:
                c.prev_chunk_id = chunks[idx - 1].chunk_id
                ov = find_chunk_overlap(chunks[idx - 1].text, c.text)
                c.overlap_prev_text = ov
                c.overlap_prev_chars = len(ov)
            if idx < len(chunks) - 1:
                c.next_chunk_id = chunks[idx + 1].chunk_id

        return chunks
