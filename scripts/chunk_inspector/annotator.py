"""PDF & Document Chunk Annotator and Visualizer for Lumos.

Extracts sections using DocumentParser, splits them into overlapping chunks using
RecursiveChunker, maps chunks to PDF layout coordinates, and renders visually
annotated PDFs and preview images with full chunk inspection capabilities.
"""

from dataclasses import dataclass, field
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

# Support direct execution as script as well as module import
project_root = str(Path(__file__).resolve().parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from lumos.config import Settings, get_settings
from lumos.core.chunker import DocumentChunk, RecursiveChunker
from lumos.core.parser import DocumentParser, DocumentSection

try:
    from scripts.chunk_inspector.cross_chunker import (
        CrossPageChunker,
        InspectorChunk,
        find_chunk_overlap,
    )
except ModuleNotFoundError:
    try:
        from cross_chunker import (
            CrossPageChunker,
            InspectorChunk,
            find_chunk_overlap,
        )
    except ModuleNotFoundError:
        from .cross_chunker import (
            CrossPageChunker,
            InspectorChunk,
            find_chunk_overlap,
        )


def group_lines_into_boxes(
    line_boxes: List[Tuple[float, float, float, float]],
    line_gap_threshold: float = 12.0,
) -> List[Tuple[float, float, float, float]]:
    """Groups vertically adjacent line bounding boxes into paragraph-level boxes."""
    if not line_boxes:
        return []
    sorted_boxes = sorted(line_boxes, key=lambda b: (b[1], b[0]))
    grouped: List[Tuple[float, float, float, float]] = []
    current_group = [sorted_boxes[0]]

    for b in sorted_boxes[1:]:
        prev_b = current_group[-1]
        # If line starts shortly after previous line's bottom, group together
        if b[1] - prev_b[3] <= line_gap_threshold:
            current_group.append(b)
        else:
            gx0 = min(box[0] for box in current_group)
            gy0 = min(box[1] for box in current_group)
            gx1 = max(box[2] for box in current_group)
            gy1 = max(box[3] for box in current_group)
            grouped.append((gx0, gy0, gx1, gy1))
            current_group = [b]

    if current_group:
        gx0 = min(box[0] for box in current_group)
        gy0 = min(box[1] for box in current_group)
        gx1 = max(box[2] for box in current_group)
        gy1 = max(box[3] for box in current_group)
        grouped.append((gx0, gy0, gx1, gy1))

    return grouped


@dataclass
class ChunkBBoxInfo:
    """Stores full post-chunking content, metadata, and visual coordinates for a chunk."""

    chunk_id: str
    chunk_index: int
    section: str
    book_title: str
    source_file: str
    text: str  # Full content after chunking
    char_count: int
    word_count: int
    page_number: int  # 1-indexed
    overlap_prev_text: str = ""
    overlap_prev_chars: int = 0
    bboxes: List[Tuple[float, float, float, float]] = field(default_factory=list)
    union_bbox: Optional[Tuple[float, float, float, float]] = None
    overlap_bboxes: List[Tuple[float, float, float, float]] = field(default_factory=list)
    color_rgb: Tuple[float, float, float] = (0.12, 0.53, 0.90)

    def to_dict(self, include_full_text: bool = True) -> Dict[str, Any]:
        """Serializes chunk data including post-chunking content and bounding boxes."""
        data: Dict[str, Any] = {
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "section": self.section,
            "book_title": self.book_title,
            "source_file": self.source_file,
            "page": self.page_number,
            "char_count": self.char_count,
            "word_count": self.word_count,
            "overlap_prev_chars": self.overlap_prev_chars,
            "bboxes": [[round(c, 2) for c in b] for b in self.bboxes],
            "union_bbox": [round(c, 2) for c in self.union_bbox] if self.union_bbox else None,
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


@dataclass
class ImageBBoxInfo:
    """Stores bounding box coordinates and size for image elements."""

    bbox: Tuple[float, float, float, float]
    index: int
    image_width: int = 0
    image_height: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bbox": [round(c, 2) for c in self.bbox],
            "type": "image",
            "index": self.index,
            "image_width": self.image_width,
            "image_height": self.image_height,
        }


@dataclass
class PageAnalysis:
    """Stores chunking and layout analysis results for a single page."""

    page_number: int  # 1-indexed
    page_width: float
    page_height: float
    chunks: List[ChunkBBoxInfo] = field(default_factory=list)
    images: List[ImageBBoxInfo] = field(default_factory=list)
    line_count: int = 0
    word_count: int = 0
    char_count: int = 0

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    @property
    def image_count(self) -> int:
        return len(self.images)

    @property
    def blocks(self) -> List[Any]:
        return self.chunks + self.images

    @property
    def text_block_count(self) -> int:
        return len(self.chunks)

    @property
    def image_block_count(self) -> int:
        return len(self.images)


class PDFChunkAnnotator:
    """Chunks documents using RecursiveChunker and annotates layout/bounding boxes."""

    CHUNK_COLORS = [
        (0.12, 0.53, 0.90),  # Blue (#1E88E5)
        (0.06, 0.72, 0.51),  # Emerald (#10B981)
        (0.55, 0.36, 0.96),  # Purple (#8B5CF6)
        (0.96, 0.62, 0.04),  # Amber (#F59E0B)
        (0.02, 0.71, 0.83),  # Cyan (#06B6D4)
        (0.88, 0.11, 0.28),  # Rose (#E11D48)
        (0.39, 0.40, 0.95),  # Indigo (#6366F1)
    ]

    COLOR_OVERLAP = (0.91, 0.12, 0.39)      # Magenta/Rose (#E91E63)
    COLOR_IMAGE_BLOCK = (0.95, 0.45, 0.05)   # Orange (#F3722C)
    COLOR_LINE = (0.40, 0.70, 0.85)          # Soft blue/cyan
    COLOR_WHITE = (1.0, 1.0, 1.0)
    COLOR_DARK = (0.12, 0.12, 0.12)

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        show_lines: bool = False,
        show_images: bool = True,
        show_labels: bool = True,
        show_legend: bool = True,
        show_overlap: bool = True,
        fill_opacity: float = 0.08,
        cross_page: Optional[bool] = None,
        clean_headers_footers: Optional[bool] = None,
        settings: Optional[Settings] = None,
    ):
        s = settings or get_settings()
        self.chunk_size = chunk_size if chunk_size is not None else s.chunk_size
        self.chunk_overlap = chunk_overlap if chunk_overlap is not None else s.chunk_overlap
        self.show_lines = show_lines
        self.show_images = show_images
        self.show_labels = show_labels
        self.show_legend = show_legend
        self.show_overlap = show_overlap
        self.fill_opacity = fill_opacity
        self.cross_page = cross_page if cross_page is not None else s.cross_page_chunking
        self.clean_headers_footers = (
            clean_headers_footers if clean_headers_footers is not None else s.clean_headers_footers
        )

        self.parser = DocumentParser()
        self.chunker = CrossPageChunker(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            cross_page=self.cross_page,
            clean_headers_footers=self.clean_headers_footers,
            settings=s,
        )

    def analyze_document(
        self,
        file_path: str | Path,
    ) -> Tuple[List[DocumentSection], List[Any]]:
        """Parses document sections and generates continuous overlapping chunks."""
        sections = self.parser.parse(file_path)
        chunks = self.chunker.chunk_sections(sections)
        return sections, chunks

    def analyze_page_chunks(
        self,
        page: pymupdf.Page,
        page_num: int,
        all_chunks: List[Any],
    ) -> PageAnalysis:
        """Locates chunks on a PDF page and groups their visual bounding boxes."""
        analysis = PageAnalysis(
            page_number=page_num,
            page_width=page.rect.width,
            page_height=page.rect.height,
        )

        page_dict = page.get_text("dict")
        lines_with_text: List[Dict[str, Any]] = []

        # Extract text lines and image blocks from the page
        image_idx = 0
        for block in page_dict.get("blocks", []):
            btype = block.get("type", 0)
            if btype == 0:
                for line in block.get("lines", []):
                    analysis.line_count += 1
                    line_text = "".join(s.get("text", "") for s in line.get("spans", [])).strip()
                    if line_text:
                        lines_with_text.append({
                            "bbox": tuple(line["bbox"]),
                            "text": line_text,
                        })
                        analysis.word_count += len(line_text.split())
                        analysis.char_count += len(line_text)
            elif btype == 1 and self.show_images:
                analysis.images.append(
                    ImageBBoxInfo(
                        bbox=tuple(block.get("bbox", (0, 0, 0, 0))),
                        index=image_idx,
                        image_width=block.get("width", 0),
                        image_height=block.get("height", 0),
                    )
                )
                image_idx += 1

        # Chunks corresponding to this page
        page_section_name = f"Page {page_num}"
        page_chunks = [
            c for c in all_chunks
            if (hasattr(c, "pages") and page_num in c.pages)
            or (hasattr(c, "page_start") and c.page_start <= page_num <= c.page_end)
            or c.section == page_section_name
        ]

        for c in page_chunks:
            overlap_text = getattr(c, "overlap_prev_text", "")
            overlap_chars = getattr(c, "overlap_prev_chars", 0)
            if not overlap_text and c.chunk_index > 0:
                prev_c = all_chunks[c.chunk_index - 1]
                overlap_text = find_chunk_overlap(prev_c.text, c.text)
                overlap_chars = len(overlap_text)

            matched_lines: List[Tuple[float, float, float, float]] = []
            overlap_lines: List[Tuple[float, float, float, float]] = []

            for item in lines_with_text:
                lt = item["text"]
                if lt in c.text or (len(lt) > 15 and (lt[:20] in c.text or lt[-20:] in c.text)):
                    matched_lines.append(item["bbox"])
                    if overlap_text and (lt in overlap_text or (len(lt) > 15 and lt[:20] in overlap_text)):
                        overlap_lines.append(item["bbox"])

            if not matched_lines:
                continue

            chunk_boxes = group_lines_into_boxes(matched_lines)
            overlap_boxes = group_lines_into_boxes(overlap_lines)

            union_bbox = None
            if matched_lines:
                union_bbox = (
                    min(b[0] for b in matched_lines),
                    min(b[1] for b in matched_lines),
                    max(b[2] for b in matched_lines),
                    max(b[3] for b in matched_lines),
                )

            color = self.CHUNK_COLORS[c.chunk_index % len(self.CHUNK_COLORS)]

            chunk_info = ChunkBBoxInfo(
                chunk_id=c.chunk_id,
                chunk_index=c.chunk_index,
                section=c.section,
                book_title=c.book_title,
                source_file=c.source_file,
                text=c.text,
                char_count=len(c.text),
                word_count=len(c.text.split()),
                page_number=page_num,
                overlap_prev_text=overlap_text,
                overlap_prev_chars=overlap_chars,
                bboxes=chunk_boxes,
                union_bbox=union_bbox,
                overlap_bboxes=overlap_boxes,
                color_rgb=color,
            )
            analysis.chunks.append(chunk_info)

        return analysis

    def annotate_page(self, page: pymupdf.Page, analysis: PageAnalysis) -> None:
        """Renders bounding boxes, badges, overlap highlights, and legend onto the page."""
        if self.show_lines:
            page_dict = page.get_text("dict")
            for block in page_dict.get("blocks", []):
                if block.get("type") == 0:
                    for line in block.get("lines", []):
                        page.draw_rect(
                            pymupdf.Rect(line["bbox"]),
                            color=self.COLOR_LINE,
                            width=0.4,
                            stroke_opacity=0.5,
                        )

        if self.show_images:
            for img in analysis.images:
                rect = pymupdf.Rect(img.bbox)
                page.draw_rect(
                    rect,
                    color=self.COLOR_IMAGE_BLOCK,
                    fill=self.COLOR_IMAGE_BLOCK,
                    fill_opacity=0.12,
                    width=1.0,
                )
                if self.show_labels:
                    label = f"IMG #{img.index}: {img.image_width}x{img.image_height}"
                    self._draw_badge(page, rect, label, self.COLOR_IMAGE_BLOCK)

        for chunk_info in analysis.chunks:
            color = chunk_info.color_rgb

            for b_idx, bbox in enumerate(chunk_info.bboxes):
                rect = pymupdf.Rect(bbox)
                page.draw_rect(
                    rect,
                    color=color,
                    fill=color,
                    fill_opacity=self.fill_opacity,
                    width=1.2,
                )

                if self.show_labels and b_idx == 0:
                    badge_parts = [f"Chunk #{chunk_info.chunk_index}"]
                    if chunk_info.section and chunk_info.section.startswith("Pages"):
                        badge_parts.append(chunk_info.section)
                    badge_parts.append(f"{chunk_info.char_count}c")
                    if chunk_info.overlap_prev_chars > 0:
                        badge_parts.append(f"Overlap {chunk_info.overlap_prev_chars}c")
                    label = " | ".join(badge_parts)
                    self._draw_badge(page, rect, label, color)

            if self.show_overlap and chunk_info.overlap_prev_chars > 0:
                for o_bbox in chunk_info.overlap_bboxes:
                    o_rect = pymupdf.Rect(o_bbox)
                    page.draw_rect(
                        o_rect,
                        color=self.COLOR_OVERLAP,
                        dashes="[3 2]",
                        width=1.5,
                    )

        if self.show_legend:
            self._draw_legend(page)

    def _draw_badge(
        self,
        page: pymupdf.Page,
        rect: pymupdf.Rect,
        label: str,
        color: Tuple[float, float, float],
    ) -> None:
        badge_w = min(max(len(label) * 4.9 + 8, 50), max(rect.width, 50))
        badge_h = 10.0

        if rect.y0 >= badge_h + 2:
            badge_rect = pymupdf.Rect(rect.x0, rect.y0 - badge_h, rect.x0 + badge_w, rect.y0)
        else:
            badge_rect = pymupdf.Rect(rect.x0, rect.y0, rect.x0 + badge_w, rect.y0 + badge_h)

        page.draw_rect(badge_rect, color=color, fill=color)
        page.insert_text(
            (badge_rect.x0 + 3.0, badge_rect.y1 - 2.2),
            label,
            fontsize=6.0,
            color=self.COLOR_WHITE,
        )

    def _draw_legend(self, page: pymupdf.Page) -> None:
        legend_w = 260
        legend_h = 18
        x1 = page.rect.width - 15
        x0 = x1 - legend_w
        y0 = 6
        y1 = y0 + legend_h

        page.draw_rect(
            pymupdf.Rect(x0, y0, x1, y1),
            color=(0.75, 0.75, 0.75),
            fill=(0.97, 0.97, 0.97),
            width=0.6,
        )

        page.draw_rect(
            pymupdf.Rect(x0 + 6, y0 + 5, x0 + 14, y0 + 13),
            color=self.CHUNK_COLORS[0],
            fill=self.CHUNK_COLORS[0],
        )
        page.insert_text((x0 + 17, y0 + 12), "Chunk Box", fontsize=6, color=self.COLOR_DARK)

        page.draw_rect(
            pymupdf.Rect(x0 + 75, y0 + 5, x0 + 83, y0 + 13),
            color=self.COLOR_OVERLAP,
            dashes="[2 2]",
            width=1.0,
        )
        page.insert_text((x0 + 86, y0 + 12), "Chunk Overlap", fontsize=6, color=self.COLOR_DARK)

        page.draw_rect(
            pymupdf.Rect(x0 + 155, y0 + 5, x0 + 163, y0 + 13),
            color=self.COLOR_IMAGE_BLOCK,
            fill=self.COLOR_IMAGE_BLOCK,
        )
        page.insert_text((x0 + 166, y0 + 12), "Image/Fig", fontsize=6, color=self.COLOR_DARK)

        if self.show_lines:
            page.draw_rect(
                pymupdf.Rect(x0 + 215, y0 + 5, x0 + 223, y0 + 13),
                color=self.COLOR_LINE,
                width=0.6,
            )
            page.insert_text((x0 + 226, y0 + 12), "Lines", fontsize=6, color=self.COLOR_DARK)

    def process_file(
        self,
        input_path: str | Path,
        output_path: Optional[str | Path] = None,
        max_pages: Optional[int] = None,
        export_images_dir: Optional[str | Path] = None,
        dpi: int = 140,
    ) -> Tuple[List[PageAnalysis], List[DocumentChunk]]:
        in_path = Path(input_path)
        if not in_path.exists():
            raise FileNotFoundError(f"Input file not found: {in_path}")

        sections, chunks = self.analyze_document(in_path)
        analyses: List[PageAnalysis] = []
        is_pdf = in_path.suffix.lower() == ".pdf"

        if not is_pdf:
            return analyses, chunks

        doc = pymupdf.open(str(in_path))
        num_pages = len(doc)
        pages_to_process = min(num_pages, max_pages) if max_pages else num_pages

        img_dir = Path(export_images_dir) if export_images_dir else None
        if img_dir:
            img_dir.mkdir(parents=True, exist_ok=True)

        for i in range(pages_to_process):
            page = doc[i]
            analysis = self.analyze_page_chunks(page, page_num=i + 1, all_chunks=chunks)
            analyses.append(analysis)

            self.annotate_page(page, analysis)

            if img_dir:
                pix = page.get_pixmap(dpi=dpi)
                img_path = img_dir / f"page_{i + 1:02d}_chunk_bbox.png"
                pix.save(str(img_path))

        if output_path:
            out_path = Path(output_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            doc.save(str(out_path))

        doc.close()
        return analyses, chunks
