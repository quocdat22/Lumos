import hashlib
from dataclasses import dataclass
from typing import List

from lumos.core.parser import DocumentSection


@dataclass
class DocumentChunk:
    chunk_id: str
    text: str
    book_title: str
    section: str
    source_file: str
    chunk_index: int

    def to_metadata(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "book_title": self.book_title,
            "section": self.section,
            "source_file": self.source_file,
            "chunk_index": self.chunk_index,
        }


class RecursiveChunker:
    """Splits document sections into overlapping chunks using natural character boundaries."""

    DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", " ", ""]

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150):
        if chunk_overlap >= chunk_size:
            raise ValueError(f"chunk_overlap ({chunk_overlap}) must be strictly less than chunk_size ({chunk_size})")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str, separators: List[str] | None = None) -> List[str]:
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
        """Processes a list of DocumentSections and returns all resulting DocumentChunks with metadata."""
        chunks: List[DocumentChunk] = []
        global_index = 0

        for sec in sections:
            text_chunks = self.split_text(sec.text)
            for chunk_str in text_chunks:
                # Deterministic chunk ID
                chunk_id = hashlib.sha256(
                    f"{sec.source_file}_{sec.section}_{global_index}_{chunk_str[:50]}".encode("utf-8")
                ).hexdigest()[:16]

                chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    text=chunk_str,
                    book_title=sec.book_title,
                    section=sec.section,
                    source_file=sec.source_file,
                    chunk_index=global_index,
                )
                chunks.append(chunk)
                global_index += 1

        return chunks
