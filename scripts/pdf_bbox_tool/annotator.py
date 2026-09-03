"""PDF Bounding Box Annotator.

Extracts layout elements (text blocks, lines, images) from PDF documents
and draws visual bounding boxes with labels and color coding.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pymupdf


@dataclass
class BBoxInfo:
    """Stores bounding box coordinates and metadata."""
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    element_type: str  # 'text', 'image', 'line'
    index: int
    text_preview: str = ""
    line_count: int = 0
    image_width: int = 0
    image_height: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bbox": [round(c, 2) for c in self.bbox],
            "type": self.element_type,
            "index": self.index,
            "line_count": self.line_count,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "preview": self.text_preview[:80],
        }


@dataclass
class PageAnalysis:
    """Stores analysis results for a single page."""
    page_number: int  # 1-indexed
    page_width: float
    page_height: float
    blocks: List[BBoxInfo] = field(default_factory=list)
    line_count: int = 0
    word_count: int = 0

    @property
    def text_block_count(self) -> int:
        return sum(1 for b in self.blocks if b.element_type == "text")

    @property
    def image_block_count(self) -> int:
        return sum(1 for b in self.blocks if b.element_type == "image")


class PDFBoundingBoxAnnotator:
    """Annotates PDF pages by drawing colored bounding boxes around layout elements."""

    # Colors as RGB tuples (0.0 to 1.0)
    COLOR_TEXT_BLOCK = (0.12, 0.53, 0.90)       # Blue (#1E88E5)
    COLOR_TEXT_LINE = (0.0, 0.70, 0.75)         # Teal (#00B4D8)
    COLOR_IMAGE_BLOCK = (0.95, 0.45, 0.05)      # Orange (#F3722C)
    COLOR_HEADER_FOOTER = (0.45, 0.45, 0.45)    # Gray (#737373)
    COLOR_WHITE = (1.0, 1.0, 1.0)

    def __init__(
        self,
        show_lines: bool = False,
        show_images: bool = True,
        show_labels: bool = True,
        show_legend: bool = True,
        fill_opacity: float = 0.07,
    ):
        self.show_lines = show_lines
        self.show_images = show_images
        self.show_labels = show_labels
        self.show_legend = show_legend
        self.fill_opacity = fill_opacity

    def analyze_page(self, page: pymupdf.Page, page_num: int) -> PageAnalysis:
        """Extracts bounding boxes and metadata from a page."""
        page_dict = page.get_text("dict")
        analysis = PageAnalysis(
            page_number=page_num,
            page_width=page.rect.width,
            page_height=page.rect.height,
        )

        blocks = page_dict.get("blocks", [])
        for block_idx, block in enumerate(blocks):
            btype = block.get("type", 0)
            bbox = tuple(block.get("bbox", (0, 0, 0, 0)))

            if btype == 0:
                # Text block
                lines = block.get("lines", [])
                lines_count = len(lines)
                analysis.line_count += lines_count

                # Extract preview text
                text_snippets = []
                for line in lines:
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if text:
                            text_snippets.append(text)
                            analysis.word_count += len(text.split())

                preview = " ".join(text_snippets)
                analysis.blocks.append(
                    BBoxInfo(
                        bbox=bbox,
                        element_type="text",
                        index=block_idx,
                        text_preview=preview,
                        line_count=lines_count,
                    )
                )
            elif btype == 1 and self.show_images:
                # Image block
                w = block.get("width", 0)
                h = block.get("height", 0)
                analysis.blocks.append(
                    BBoxInfo(
                        bbox=bbox,
                        element_type="image",
                        index=block_idx,
                        image_width=w,
                        image_height=h,
                    )
                )

        return analysis

    def annotate_page(self, page: pymupdf.Page, analysis: PageAnalysis) -> None:
        """Draws bounding boxes and labels onto the page."""
        # 1. Draw individual line bounding boxes if enabled
        if self.show_lines:
            page_dict = page.get_text("dict")
            for block in page_dict.get("blocks", []):
                if block.get("type") == 0:
                    for line in block.get("lines", []):
                        l_rect = pymupdf.Rect(line["bbox"])
                        page.draw_rect(
                            l_rect,
                            color=self.COLOR_TEXT_LINE,
                            width=0.4,
                            stroke_opacity=0.6,
                        )

        # 2. Draw block bounding boxes
        for block_info in analysis.blocks:
            rect = pymupdf.Rect(block_info.bbox)

            if block_info.element_type == "text":
                stroke = self.COLOR_TEXT_BLOCK
                fill = self.COLOR_TEXT_BLOCK
                label = f"B{block_info.index}: Text ({block_info.line_count}L)"
            else:
                stroke = self.COLOR_IMAGE_BLOCK
                fill = self.COLOR_IMAGE_BLOCK
                label = f"IMG {block_info.index}: {block_info.image_width}x{block_info.image_height}"

            # Outline and semi-transparent fill
            page.draw_rect(
                rect,
                color=stroke,
                fill=fill,
                fill_opacity=self.fill_opacity,
                width=1.0,
            )

            # Draw label badge
            if self.show_labels:
                self._draw_badge(page, rect, label, stroke)

        # 3. Draw legend in top-right corner
        if self.show_legend:
            self._draw_legend(page)

    def _draw_badge(
        self,
        page: pymupdf.Page,
        rect: pymupdf.Rect,
        label: str,
        color: Tuple[float, float, float],
    ) -> None:
        """Draws a compact label badge attached to the bounding box."""
        badge_w = min(max(len(label) * 4.8 + 6, 40), max(rect.width, 40))
        badge_h = 9.0

        # Position badge at top-left of box; if too close to page top, place it inside
        if rect.y0 >= badge_h + 2:
            badge_rect = pymupdf.Rect(rect.x0, rect.y0 - badge_h, rect.x0 + badge_w, rect.y0)
        else:
            badge_rect = pymupdf.Rect(rect.x0, rect.y0, rect.x0 + badge_w, rect.y0 + badge_h)

        page.draw_rect(badge_rect, color=color, fill=color)
        page.insert_text(
            (badge_rect.x0 + 2.5, badge_rect.y1 - 2.0),
            label,
            fontsize=5.5,
            color=self.COLOR_WHITE,
        )

    def _draw_legend(self, page: pymupdf.Page) -> None:
        """Draws an informative legend box at the top right margin."""
        legend_w = 190
        legend_h = 16
        x1 = page.rect.width - 15
        x0 = x1 - legend_w
        y0 = 6
        y1 = y0 + legend_h

        # Background container
        page.draw_rect(
            pymupdf.Rect(x0, y0, x1, y1),
            color=(0.8, 0.8, 0.8),
            fill=(0.96, 0.96, 0.96),
            width=0.6,
        )

        # Text block indicator
        page.draw_rect(pymupdf.Rect(x0 + 6, y0 + 4, x0 + 14, y0 + 12), color=self.COLOR_TEXT_BLOCK, fill=self.COLOR_TEXT_BLOCK)
        page.insert_text((x0 + 18, y0 + 11), "Text Block", fontsize=6, color=(0.1, 0.1, 0.1))

        # Image indicator
        page.draw_rect(pymupdf.Rect(x0 + 68, y0 + 4, x0 + 76, y0 + 12), color=self.COLOR_IMAGE_BLOCK, fill=self.COLOR_IMAGE_BLOCK)
        page.insert_text((x0 + 80, y0 + 11), "Image/Figure", fontsize=6, color=(0.1, 0.1, 0.1))

        # Line indicator (if active)
        if self.show_lines:
            page.draw_rect(pymupdf.Rect(x0 + 138, y0 + 4, x0 + 146, y0 + 12), color=self.COLOR_TEXT_LINE, fill=self.COLOR_TEXT_LINE)
            page.insert_text((x0 + 150, y0 + 11), "Text Line", fontsize=6, color=(0.1, 0.1, 0.1))

    def process_file(
        self,
        input_path: str | Path,
        output_path: str | Path,
        max_pages: Optional[int] = None,
        export_images_dir: Optional[str | Path] = None,
        dpi: int = 150,
    ) -> List[PageAnalysis]:
        """Main processing pipeline: opens PDF, draws bounding boxes, and saves output."""
        in_path = Path(input_path)
        out_path = Path(output_path)

        if not in_path.exists():
            raise FileNotFoundError(f"Input PDF not found: {in_path}")

        out_path.parent.mkdir(parents=True, exist_ok=True)

        doc = pymupdf.open(str(in_path))
        num_pages = len(doc)
        pages_to_process = min(num_pages, max_pages) if max_pages else num_pages

        analyses: List[PageAnalysis] = []
        img_dir = Path(export_images_dir) if export_images_dir else None
        if img_dir:
            img_dir.mkdir(parents=True, exist_ok=True)

        for i in range(pages_to_process):
            page = doc[i]
            analysis = self.analyze_page(page, page_num=i + 1)
            analyses.append(analysis)

            self.annotate_page(page, analysis)

            if img_dir:
                pix = page.get_pixmap(dpi=dpi)
                img_path = img_dir / f"page_{i + 1:02d}_bbox.png"
                pix.save(str(img_path))

        doc.save(str(out_path))
        doc.close()
        return analyses
