import json
from pathlib import Path
import sys
import tempfile

import pymupdf
import pytest

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.chunk_inspector.annotator import (
    ChunkBBoxInfo,
    PDFChunkAnnotator,
    find_chunk_overlap,
    group_lines_into_boxes,
)
from scripts.chunk_inspector.main import build_markdown_report, main as chunk_inspector_main
from scripts.pdf_bbox_tool.annotator import PDFBoundingBoxAnnotator
from scripts.pdf_bbox_tool.main import main as pdf_bbox_main


def test_find_chunk_overlap():
    text1 = "Natural language processing enables machines to understand human language."
    text2 = "understand human language. Deep learning models provide strong capabilities."
    overlap = find_chunk_overlap(text1, text2)
    assert overlap == "understand human language."

    assert find_chunk_overlap("", "some text") == ""
    assert find_chunk_overlap("some text", "") == ""
    assert find_chunk_overlap("apple", "banana") == ""


def test_group_lines_into_boxes():
    lines = [
        (50.0, 100.0, 300.0, 112.0),
        (50.0, 116.0, 310.0, 128.0),
        (50.0, 200.0, 300.0, 212.0),
    ]
    boxes = group_lines_into_boxes(lines, line_gap_threshold=10.0)
    assert len(boxes) == 2
    assert boxes[0][0] == 50.0
    assert boxes[0][1] == 100.0
    assert boxes[0][2] == 310.0
    assert boxes[0][3] == 128.0
    assert boxes[1] == (50.0, 200.0, 300.0, 212.0)


def test_chunk_inspector_processing():
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "test_doc.pdf"
        out_pdf_path = Path(tmpdir) / "annotated.pdf"
        img_dir = Path(tmpdir) / "previews"

        doc = pymupdf.open()
        page = doc.new_page(width=500, height=500)
        page.insert_text((50, 60), "Artificial intelligence has transformed computing.")
        page.insert_text((50, 80), "Neural networks learn representations from data.")
        page.insert_text((50, 100), "Deep architectures achieve state-of-the-art results.")
        page.insert_text((50, 150), "Evaluation metrics include precision, recall, and F1 score.")
        doc.set_metadata({"title": "AI Concepts"})
        doc.save(str(pdf_path))
        doc.close()

        annotator = PDFChunkAnnotator(chunk_size=120, chunk_overlap=30)
        analyses, chunks = annotator.process_file(
            input_path=pdf_path,
            output_path=out_pdf_path,
            export_images_dir=img_dir,
            dpi=100,
        )

        assert len(chunks) >= 1
        assert len(analyses) == 1
        assert out_pdf_path.exists()
        assert (img_dir / "page_01_chunk_bbox.png").exists()

        # Verify chunk contains actual post-chunking content
        first_chunk = chunks[0]
        assert first_chunk.book_title == "AI Concepts"
        assert len(first_chunk.text) > 0
        assert "Artificial intelligence" in first_chunk.text

        page_analysis = analyses[0]
        assert page_analysis.chunk_count >= 1
        chunk_info = page_analysis.chunks[0]
        assert isinstance(chunk_info, ChunkBBoxInfo)
        assert chunk_info.text == first_chunk.text
        assert chunk_info.char_count == len(first_chunk.text)
        assert len(chunk_info.bboxes) > 0

        # Test to_dict contains full text
        serialized = chunk_info.to_dict(include_full_text=True)
        assert "text" in serialized
        assert serialized["text"] == chunk_info.text


def test_chunk_inspector_cli(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "cli_sample.pdf"
        out_pdf = Path(tmpdir) / "cli_sample_bbox.pdf"
        json_path = Path(tmpdir) / "chunks.json"
        md_path = Path(tmpdir) / "chunks.md"

        doc = pymupdf.open()
        p1 = doc.new_page(width=400, height=400)
        p1.insert_text((40, 50), "Line one of page one content.")
        p1.insert_text((40, 80), "Line two of page one content.")
        doc.set_metadata({"title": "Sample CLI Book"})
        doc.save(str(pdf_path))
        doc.close()

        test_args = [
            "chunk_inspector",
            "-i",
            str(pdf_path),
            "-o",
            str(out_pdf),
            "--chunk-size",
            "100",
            "--chunk-overlap",
            "20",
            "--json-path",
            str(json_path),
            "--markdown-path",
            str(md_path),
            "--preview-chunks",
            "1",
        ]
        monkeypatch.setattr("sys.argv", test_args)

        chunk_inspector_main()

        assert out_pdf.exists()
        assert json_path.exists()
        assert md_path.exists()

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["book_title"] == "Sample CLI Book"
        assert data["summary"]["total_chunks"] >= 1
        assert len(data["chunks"]) >= 1
        assert "text" in data["chunks"][0]
        assert "Line one of page one" in data["chunks"][0]["text"]

        with open(md_path, "r", encoding="utf-8") as f:
            md_text = f.read()
        assert "Lumos Chunking Inspection Report" in md_text
        assert "Sample CLI Book" in md_text


def test_original_pdf_bbox_tool():
    """Verifies that the original pdf_bbox_tool remains fully intact and functioning."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "original_sample.pdf"
        out_pdf = Path(tmpdir) / "original_bbox.pdf"

        doc = pymupdf.open()
        p1 = doc.new_page(width=300, height=300)
        p1.insert_text((30, 40), "Layout analysis text block.")
        doc.save(str(pdf_path))
        doc.close()

        annotator = PDFBoundingBoxAnnotator(show_lines=True)
        analyses = annotator.process_file(input_path=pdf_path, output_path=out_pdf)

        assert len(analyses) == 1
        assert analyses[0].text_block_count >= 1
        assert out_pdf.exists()


def test_outputs_in_named_subfolder(monkeypatch):
    """Verifies that all outputs default to a subfolder named after the input file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "SpecialReport.pdf"

        doc = pymupdf.open()
        p = doc.new_page(width=400, height=400)
        p.insert_text((50, 50), "Special report content line 1.")
        p.insert_text((50, 80), "Special report content line 2.")
        doc.save(str(pdf_path))
        doc.close()

        # 1. Run pdf_bbox_tool with default output paths
        monkeypatch.setattr(
            "sys.argv",
            ["pdf_bbox_tool", "-i", str(pdf_path), "--save-json", "--export-images"],
        )
        pdf_bbox_main()

        expected_dir = Path(tmpdir) / "SpecialReport"
        assert expected_dir.exists()
        assert expected_dir.is_dir()
        assert (expected_dir / "SpecialReport_bbox.pdf").exists()
        assert (expected_dir / "SpecialReport_bbox.json").exists()
        assert (expected_dir / "bbox_previews").exists()

        # 2. Run chunk_inspector with default output paths
        monkeypatch.setattr(
            "sys.argv",
            ["chunk_inspector", "-i", str(pdf_path), "--export-images", "--preview-chunks", "0"],
        )
        chunk_inspector_main()

        assert (expected_dir / "SpecialReport_chunk_bbox.pdf").exists()
        assert (expected_dir / "SpecialReport_chunks.json").exists()
        assert (expected_dir / "SpecialReport_chunks.md").exists()

        # Check that no outputs were placed loose side-by-side with SpecialReport.pdf
        loose_files = [f.name for f in Path(tmpdir).iterdir() if f.is_file()]
        assert loose_files == ["SpecialReport.pdf"]


def test_cross_page_chunker_unit():
    """Verifies that CrossPageChunker seamlessly connects sections and preserves bidirectional links."""
    from scripts.chunk_inspector.cross_chunker import CrossPageChunker, clean_section_text
    from lumos.core.parser import DocumentSection

    sec1 = DocumentSection(
        text="Alpha section contains introductory remarks and concepts. " * 3,
        book_title="AI Architecture",
        section="Page 1",
        source_file="ai_arch.pdf",
    )
    sec2 = DocumentSection(
        text="Beta section discusses multi-agent coordination systems. " * 3,
        book_title="AI Architecture",
        section="Page 2",
        source_file="ai_arch.pdf",
    )

    # Chunker with small size so it bridges across the boundary
    chunker = CrossPageChunker(chunk_size=160, chunk_overlap=40, cross_page=True, clean_headers_footers=True)
    chunks = chunker.chunk_sections([sec1, sec2])

    assert len(chunks) >= 2
    # Verify bidirectional linking
    assert chunks[0].prev_chunk_id is None
    assert chunks[0].next_chunk_id == chunks[1].chunk_id
    assert chunks[1].prev_chunk_id == chunks[0].chunk_id

    # Verify at least one chunk spans across pages or has cross-page overlap
    has_cross_span = any(c.page_start != c.page_end for c in chunks)
    has_overlap = any(c.overlap_prev_chars > 0 for c in chunks[1:])
    assert has_cross_span or has_overlap
    assert all(c.char_count > 0 for c in chunks)


def test_header_footer_cleaning_unit():
    """Verifies that clean_section_text strips timestamps, URLs, page counts, and edge title repetitions."""
    from scripts.chunk_inspector.cross_chunker import clean_section_text

    raw_text = (
        "Building Effective AI Agents \\ Anthropic\n"
        "Here is the core body of page 1 text.\n"
        "It describes multi-agent workflows.\n"
        "9/1/26, 12:59 AM\n"
        "Building Effective AI Agents \\ Anthropic\n"
        "https://www.anthropic.com/engineering/building-effective-agents\n"
        "1/19"
    )

    cleaned = clean_section_text(raw_text, book_title="Building Effective AI Agents \\ Anthropic")
    assert "Here is the core body" in cleaned
    assert "multi-agent workflows" in cleaned
    assert "9/1/26" not in cleaned
    assert "https://" not in cleaned
    assert "1/19" not in cleaned


def test_annotator_cross_page_pdf():
    """Verifies that PDFChunkAnnotator maps and visualizes chunks spanning multiple pages."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "two_page_doc.pdf"
        out_pdf = Path(tmpdir) / "annotated_cross.pdf"
        img_dir = Path(tmpdir) / "previews"

        doc = pymupdf.open()
        p1 = doc.new_page(width=400, height=400)
        p1.insert_text((40, 50), "First page sentence that leads to concepts.")
        p1.insert_text((40, 70), "Continuity text that should bridge across the boundary.")
        p1.insert_text((40, 380), "1/2")

        p2 = doc.new_page(width=400, height=400)
        p2.insert_text((40, 50), "Second page beginning with further agent details.")
        p2.insert_text((40, 70), "Conclusion of the multi-agent topic.")
        p2.insert_text((40, 380), "2/2")

        doc.set_metadata({"title": "MultiPage Guide"})
        doc.save(str(pdf_path))
        doc.close()

        annotator = PDFChunkAnnotator(
            chunk_size=120,
            chunk_overlap=30,
            cross_page=True,
            clean_headers_footers=True,
        )
        analyses, chunks = annotator.process_file(
            input_path=pdf_path,
            output_path=out_pdf,
            export_images_dir=img_dir,
            dpi=100,
        )

        assert len(analyses) == 2
        assert len(chunks) >= 2
        assert out_pdf.exists()

        # Check that previews were exported for both pages
        assert (img_dir / "page_01_chunk_bbox.png").exists()
        assert (img_dir / "page_02_chunk_bbox.png").exists()

        # Check that page 1 and page 2 have chunks analyzed
        assert analyses[0].chunk_count >= 1
        assert analyses[1].chunk_count >= 1

        # Check linking
        assert chunks[0].next_chunk_id == chunks[1].chunk_id
        assert chunks[1].prev_chunk_id == chunks[0].chunk_id

