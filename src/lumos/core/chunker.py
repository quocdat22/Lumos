from dataclasses import dataclass, field
import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple

from lumos.config import Settings, get_settings
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


@dataclass
class DocumentChunk:
    chunk_id: str
    text: str
    book_title: str
    section: str
    source_file: str
    chunk_index: int
    page_start: Optional[int] = None
    page_end: Optional[int] = None
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
        }
        if self.page_start is not None:
            meta["page_start"] = self.page_start
        if self.page_end is not None:
            meta["page_end"] = self.page_end
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


class RecursiveChunker:
    """Splits document sections into overlapping chunks using natural character boundaries,
    supporting seamless cross-page continuous chunking and bidirectional linking."""

    DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", " ", ""]

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        cross_page: Optional[bool] = None,
        clean_headers_footers: Optional[bool] = None,
        settings: Optional[Settings] = None,
    ):
        s = settings or get_settings()
        self.chunk_size = chunk_size if chunk_size is not None else s.chunk_size
        self.chunk_overlap = chunk_overlap if chunk_overlap is not None else s.chunk_overlap
        self.cross_page = cross_page if cross_page is not None else s.cross_page_chunking
        self.clean_headers_footers = (
            clean_headers_footers if clean_headers_footers is not None else s.clean_headers_footers
        )

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(f"chunk_overlap ({self.chunk_overlap}) must be strictly less than chunk_size ({self.chunk_size})")

    def _extract_page_number(self, section_name: str, fallback_index: int) -> int:
        """Parses integer page number from section string like 'Page 3' or returns fallback."""
        m = re.search(r"Page\s+(\d+)", section_name, re.IGNORECASE)
        if m:
            return int(m.group(1))
        return fallback_index

    def split_text(self, text: str, separators: Optional[List[str]] = None) -> List[str]:
        """Recursively splits a text into chunks not exceeding chunk_size."""
        if len(text) <= self.chunk_size:
            return [text.strip()] if text.strip() else []

        if separators is None:
            separators = list(self.DEFAULT_SEPARATORS)

        # Find the best separator that exists in text
        chosen_sep = separators[-1]
        for sep in separators:
            if sep == "":
                chosen_sep = ""
                break
            if sep in text:
                chosen_sep = sep
                break

        # Split using chosen separator
        if chosen_sep != "":
            splits = text.split(chosen_sep)
        else:
            # Character-level fallback
            splits = list(text)

        # Recursively break down pieces that are still larger than chunk_size
        next_separators = separators[separators.index(chosen_sep) + 1:] if chosen_sep in separators else []
        pieces: List[str] = []
        for piece in splits:
            piece_stripped = piece.strip()
            if not piece_stripped:
                continue
            if len(piece) > self.chunk_size and next_separators:
                pieces.extend(self.split_text(piece, next_separators))
            else:
                pieces.append(piece)

        # Merge pieces into overlapping chunks
        merged_chunks: List[str] = []
        current_chunk: List[str] = []
        current_length = 0

        for piece in pieces:
            piece_len = len(piece) + (len(chosen_sep) if current_chunk else 0)
            if current_length + piece_len <= self.chunk_size:
                current_chunk.append(piece)
                current_length += piece_len
            else:
                if current_chunk:
                    joined = chosen_sep.join(current_chunk).strip()
                    if joined:
                        merged_chunks.append(joined)

                    # Compute overlap from the end of current_chunk
                    overlap_pieces: List[str] = []
                    overlap_len = 0
                    for prev_piece in reversed(current_chunk):
                        if overlap_len + len(prev_piece) <= self.chunk_overlap:
                            overlap_pieces.insert(0, prev_piece)
                            overlap_len += len(prev_piece)
                        else:
                            break
                    current_chunk = overlap_pieces
                    current_length = sum(len(p) for p in current_chunk) + (len(chosen_sep) * max(0, len(current_chunk) - 1))

                current_chunk.append(piece)
                current_length += len(piece) + (len(chosen_sep) if len(current_chunk) > 1 else 0)

        if current_chunk:
            joined = chosen_sep.join(current_chunk).strip()
            if joined and (not merged_chunks or merged_chunks[-1] != joined):
                merged_chunks.append(joined)

        return merged_chunks

    def chunk_sections(self, sections: List[DocumentSection]) -> List[DocumentChunk]:
        """Processes a list of DocumentSections with cross-page continuity and bidirectional linking."""
        if not sections:
            return []

        if not self.cross_page:
            return self._chunk_sections_isolated(sections)

        return self._chunk_sections_continuous(sections)

    def _chunk_sections_continuous(self, sections: List[DocumentSection]) -> List[DocumentChunk]:
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

        raw_chunks = self.split_text(full_text)
        if not raw_chunks:
            return []

        chunks: List[DocumentChunk] = []
        book_title = sections[0].book_title
        source_file = sections[0].source_file
        search_pos = 0

        # Check if all sections follow "Page \d+" naming
        is_page_format = all(re.match(r"^Page\s+\d+$", s.section.strip(), re.IGNORECASE) for s in sections)

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

            # Find all pages/sections that overlap with [c_start, c_end]
            matched_pages: List[int] = []
            matched_sec_names: List[str] = []
            for p_start_off, p_end_off, p_num, sec_name, _ in page_ranges:
                if c_start < p_end_off and c_end > p_start_off:
                    matched_pages.append(p_num)
                    matched_sec_names.append(sec_name)

            if not matched_pages:
                matched_pages = [page_ranges[0][2] if page_ranges else 1]

            p_start = min(matched_pages)
            p_end = max(matched_pages)

            if is_page_format:
                if p_start == p_end:
                    sec_label = f"Page {p_start}"
                else:
                    sec_label = f"Pages {p_start} - {p_end}"
            else:
                if matched_sec_names:
                    if matched_sec_names[0] == matched_sec_names[-1]:
                        sec_label = matched_sec_names[0]
                    else:
                        sec_label = f"{matched_sec_names[0]} - {matched_sec_names[-1]}"
                else:
                    sec_label = f"Page {p_start}" if p_start == p_end else f"Pages {p_start} - {p_end}"

            chunk_id = hashlib.sha256(
                f"{source_file}_{sec_label}_{idx}_{chunk_text[:50]}".encode("utf-8")
            ).hexdigest()[:16]

            chunks.append(
                DocumentChunk(
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

    def _chunk_sections_isolated(self, sections: List[DocumentSection]) -> List[DocumentChunk]:
        """Fallback mode: chunks sections in isolation (legacy behavior)."""
        chunks: List[DocumentChunk] = []
        global_index = 0

        for i, sec in enumerate(sections):
            page_num = self._extract_page_number(sec.section, i + 1)
            raw_text = sec.text or ""
            text = clean_section_text(raw_text, sec.book_title) if self.clean_headers_footers else raw_text
            text_chunks = self.split_text(text)

            for chunk_str in text_chunks:
                chunk_id = hashlib.sha256(
                    f"{sec.source_file}_{sec.section}_{global_index}_{chunk_str[:50]}".encode("utf-8")
                ).hexdigest()[:16]

                chunk = DocumentChunk(
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


# Compatibility aliases
CrossPageChunker = RecursiveChunker
InspectorChunk = DocumentChunk

