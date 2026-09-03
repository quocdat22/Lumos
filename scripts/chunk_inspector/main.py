"""CLI Entrypoint for Lumos Document Chunk Inspector and Visualizer.

Splits documents using Lumos's RecursiveChunker, inspects the post-chunking content,
detects chunk overlaps, and generates detailed JSON/Markdown reports along with
annotated PDFs and page preview images.

Usage:
    uv run python -m scripts.chunk_inspector.main
    uv run python scripts/chunk_inspector/main.py
    uv run python -m scripts.chunk_inspector.main --print-chunks
    uv run python -m scripts.chunk_inspector.main --chunk-size 600 --chunk-overlap 100
    uv run python -m scripts.chunk_inspector.main --export-images --save-markdown
"""

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

# Support running both as a module and directly as a script file
try:
    from scripts.chunk_inspector.annotator import (
        ChunkBBoxInfo,
        PageAnalysis,
        PDFChunkAnnotator,
        find_chunk_overlap,
    )
except ModuleNotFoundError:
    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))
    try:
        from scripts.chunk_inspector.annotator import (
            ChunkBBoxInfo,
            PageAnalysis,
            PDFChunkAnnotator,
            find_chunk_overlap,
        )
    except ModuleNotFoundError:
        from annotator import (
            ChunkBBoxInfo,
            PageAnalysis,
            PDFChunkAnnotator,
            find_chunk_overlap,
        )

from lumos.core.chunker import DocumentChunk


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lumos Chunk Inspector & PDF Visualizer - Inspect post-chunking content and layout bounding boxes."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default="data/uploads/BuildingEffectiveAIAgents_Anthropic.pdf",
        help="Path to the input document (PDF or EPUB). Default: data/uploads/BuildingEffectiveAIAgents_Anthropic.pdf",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Path to save the annotated PDF (default: <input_dir>/<file_stem>/<file_stem>_chunk_bbox.pdf)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=800,
        help="Target maximum character size for each chunk (default: 800)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=150,
        help="Character overlap size between consecutive chunks (default: 150)",
    )
    parser.add_argument(
        "--show-lines",
        action="store_true",
        default=False,
        help="Draw bounding boxes around individual text lines within chunks",
    )
    parser.add_argument(
        "--export-images",
        action="store_true",
        default=False,
        help="Export annotated pages as PNG images into the images directory",
    )
    parser.add_argument(
        "--images-dir",
        type=str,
        default=None,
        help="Directory to save preview PNG images (default: <input_dir>/<file_stem>/bbox_previews)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=140,
        help="DPI for exported preview images (default: 140)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limit processing to first N pages (optional)",
    )
    parser.add_argument(
        "--save-json",
        action="store_true",
        default=True,
        help="Export full chunked content and metadata as JSON (default: True)",
    )
    parser.add_argument(
        "--no-json",
        action="store_false",
        dest="save_json",
        help="Disable JSON export",
    )
    parser.add_argument(
        "--json-path",
        type=str,
        default=None,
        help="Custom file path for JSON export (defaults to <output_stem>_chunks.json)",
    )
    parser.add_argument(
        "--save-markdown",
        action="store_true",
        default=True,
        help="Export a human-readable Markdown report with all chunk contents (default: True)",
    )
    parser.add_argument(
        "--no-markdown",
        action="store_false",
        dest="save_markdown",
        help="Disable Markdown export",
    )
    parser.add_argument(
        "--markdown-path",
        type=str,
        default=None,
        help="Custom file path for Markdown export (defaults to <output_stem>_chunks.md)",
    )
    parser.add_argument(
        "--print-chunks",
        action="store_true",
        default=False,
        help="Print the full content of all chunks directly in the terminal",
    )
    parser.add_argument(
        "--preview-chunks",
        type=int,
        default=3,
        help="Number of chunk previews to display in terminal (default: 3; 0 to disable)",
    )
    return parser.parse_args()


def build_markdown_report(
    book_title: str,
    source_file: str,
    chunk_size: int,
    chunk_overlap: int,
    chunks: List[DocumentChunk],
    analyses: List[PageAnalysis],
    summary: Dict[str, Any],
) -> str:
    """Generates a structured Markdown inspection document showing full chunk contents."""
    md_lines = [
        f"# Lumos Chunking Inspection Report: {book_title}",
        "",
        "> This document provides complete post-chunking content and metadata generated by `RecursiveChunker`.",
        "",
        "## Execution Summary",
        "",
        f"- **Source Document**: `{source_file}`",
        f"- **Book Title**: {book_title}",
        f"- **Chunk Configuration**: `chunk_size = {chunk_size}`, `chunk_overlap = {chunk_overlap}`",
        f"- **Total Chunks Generated**: {summary['total_chunks']}",
        f"- **Average Chunk Length**: {summary['avg_chunk_chars']:.1f} characters ({summary['avg_chunk_words']:.1f} words)",
        f"- **Length Range (Min / Max)**: {summary['min_chunk_chars']} / {summary['max_chunk_chars']} characters",
        f"- **Overlapping Chunks**: {summary['overlapping_chunks_count']} chunks have overlap with preceding chunks (avg: {summary['avg_overlap_chars']:.1f} chars)",
        "",
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| Total Chunks | `{summary['total_chunks']}` |",
        f"| Total Characters | `{summary['total_chars']:,}` |",
        f"| Total Words | `{summary['total_words']:,}` |",
        f"| Min Characters | `{summary['min_chunk_chars']}` |",
        f"| Max Characters | `{summary['max_chunk_chars']}` |",
        f"| Avg Characters | `{summary['avg_chunk_chars']:.1f}` |",
        f"| Avg Words | `{summary['avg_chunk_words']:.1f}` |",
        f"| Overlap Pairs | `{summary['overlapping_chunks_count']}` |",
        "",
        "---",
        "",
        "## Chunk Details",
        "",
    ]

    for idx, c in enumerate(chunks):
        prev_overlap = ""
        if idx > 0:
            prev_overlap = find_chunk_overlap(chunks[idx - 1].text, c.text)

        overlap_len = len(prev_overlap)
        word_count = len(c.text.split())

        md_lines.append(f"### Chunk #{c.chunk_index} (`{c.chunk_id}`)")
        md_lines.append("")
        md_lines.append(f"- **Section**: `{c.section}`")
        md_lines.append(f"- **Length**: `{len(c.text)}` chars | `{word_count}` words")
        if overlap_len > 0:
            preview_overlap = prev_overlap.replace("\n", " ").strip()
            if len(preview_overlap) > 100:
                preview_overlap = preview_overlap[:100] + "..."
            md_lines.append(f"- **Overlap with Chunk #{idx - 1}**: `{overlap_len}` chars")
            md_lines.append(f"  > *\"{preview_overlap}\"*")
        else:
            md_lines.append("- **Overlap**: None (New section boundary or start)")

        md_lines.append("")
        md_lines.append("```text")
        md_lines.append(c.text)
        md_lines.append("```")
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")

    return "\n".join(md_lines)


def print_terminal_preview(chunks: List[DocumentChunk], count: int) -> None:
    """Displays formatted chunk inspection cards in terminal."""
    if count == 0 or not chunks:
        return

    show_count = len(chunks) if count < 0 else min(count, len(chunks))
    print(f"\n[Chunk Inspection Preview] (Showing {show_count} of {len(chunks)} chunks)")
    print("=" * 68)

    for i in range(show_count):
        c = chunks[i]
        overlap_text = ""
        if i > 0:
            overlap_text = find_chunk_overlap(chunks[i - 1].text, c.text)

        overlap_info = f" | Overlap: {len(overlap_text)} chars" if overlap_text else ""
        header = f"┌─ Chunk #{c.chunk_index} [ID: {c.chunk_id}] ── ({c.section} | {len(c.text)} chars | {len(c.text.split())} words{overlap_info})"
        print(header)

        if overlap_text:
            overlap_clean = overlap_text.strip()
            print("│ ╔═ [Overlap with previous chunk]")
            for line in overlap_clean.splitlines()[:3]:
                print(f"│ ║ {line}")
            if len(overlap_clean.splitlines()) > 3:
                print("│ ║ ...")
            print("│ ╚════════════════════════════════")

        print("│ [Chunk Content]:")
        for line in c.text.splitlines():
            print(f"│   {line}")
        print("└" + "─" * 67)
        print()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[Error] Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Place outputs into a dedicated folder named after the input file
    doc_dir = input_path.parent / input_path.stem
    doc_dir.mkdir(parents=True, exist_ok=True)

    output_pdf_path = (
        Path(args.output) if args.output else (doc_dir / f"{input_path.stem}_chunk_bbox.pdf")
    )
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    if args.export_images:
        images_dir = Path(args.images_dir) if args.images_dir else (doc_dir / "bbox_previews")
        images_dir.mkdir(parents=True, exist_ok=True)
    else:
        images_dir = None

    print("=" * 68)
    print("        Lumos Document Chunk Inspector & Visualizer")
    print("=" * 68)
    print(f" Input File       : {input_path.resolve()}")
    print(f" Output Folder    : {doc_dir.resolve()}")
    print(f" Chunk Size       : {args.chunk_size}")
    print(f" Chunk Overlap    : {args.chunk_overlap}")
    print(f" Output PDF       : {output_pdf_path.resolve()}")
    print(f" Export Previews  : {args.export_images} ({images_dir if args.export_images else 'Disabled'})")
    if args.max_pages:
        print(f" Max Pages        : {args.max_pages}")
    print("-" * 68)

    annotator = PDFChunkAnnotator(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        show_lines=args.show_lines,
        show_images=True,
        show_labels=True,
        show_legend=True,
        show_overlap=True,
    )

    analyses, chunks = annotator.process_file(
        input_path=input_path,
        output_path=output_pdf_path if input_path.suffix.lower() == ".pdf" else None,
        max_pages=args.max_pages,
        export_images_dir=images_dir,
        dpi=args.dpi,
    )

    if not chunks:
        print("[Warning] No text chunks were generated from the document.")
        return

    # Compute aggregate statistics
    book_title = chunks[0].book_title if chunks else input_path.stem
    total_chars = sum(len(c.text) for c in chunks)
    total_words = sum(len(c.text.split()) for c in chunks)
    min_chars = min(len(c.text) for c in chunks)
    max_chars = max(len(c.text) for c in chunks)
    avg_chars = total_chars / len(chunks)
    avg_words = total_words / len(chunks)

    overlap_count = 0
    overlap_chars_total = 0
    for idx in range(1, len(chunks)):
        ov = find_chunk_overlap(chunks[idx - 1].text, chunks[idx].text)
        if ov:
            overlap_count += 1
            overlap_chars_total += len(ov)

    avg_overlap = (overlap_chars_total / overlap_count) if overlap_count > 0 else 0.0

    summary_stats = {
        "total_chunks": len(chunks),
        "total_pages": len(analyses),
        "total_chars": total_chars,
        "total_words": total_words,
        "min_chunk_chars": min_chars,
        "max_chunk_chars": max_chars,
        "avg_chunk_chars": round(avg_chars, 1),
        "avg_chunk_words": round(avg_words, 1),
        "overlapping_chunks_count": overlap_count,
        "avg_overlap_chars": round(avg_overlap, 1),
    }

    print(f"\n[Done] Successfully chunked document into {len(chunks)} chunks across {len(analyses)} pages!")
    print(f"  * Total Chunks        : {len(chunks)}")
    print(f"  * Characters Range    : {min_chars} min / {avg_chars:.1f} avg / {max_chars} max")
    print(f"  * Word Count          : {total_words:,} total (avg {avg_words:.1f} words/chunk)")
    print(f"  * Overlapping Chunks  : {overlap_count} chunks with preceding overlap (avg {avg_overlap:.1f} chars)")

    if input_path.suffix.lower() == ".pdf" and output_pdf_path.exists():
        print(f"  * Annotated PDF       : {output_pdf_path.resolve()} ({output_pdf_path.stat().st_size / 1024:.1f} KB)")

    if args.export_images and images_dir:
        exported_imgs = list(images_dir.glob("page_*_chunk_bbox.png"))
        print(f"  * Preview Images      : {len(exported_imgs)} images saved in {images_dir}/")

    # 1. Save JSON metadata with full chunk text content
    if args.save_json:
        json_path = (
            Path(args.json_path) if args.json_path else doc_dir / f"{input_path.stem}_chunks.json"
        )
        json_path.parent.mkdir(parents=True, exist_ok=True)

        chunks_by_page: Dict[int, List[Dict[str, Any]]] = {}
        for a in analyses:
            chunks_by_page[a.page_number] = [c.to_dict(include_full_text=True) for c in a.chunks]

        export_data = {
            "source_file": str(input_path),
            "book_title": book_title,
            "chunk_settings": {
                "chunk_size": args.chunk_size,
                "chunk_overlap": args.chunk_overlap,
            },
            "summary": summary_stats,
            "chunks": [
                {
                    "chunk_id": c.chunk_id,
                    "chunk_index": c.chunk_index,
                    "section": c.section,
                    "book_title": c.book_title,
                    "source_file": c.source_file,
                    "char_count": len(c.text),
                    "word_count": len(c.text.split()),
                    "overlap_prev_chars": (
                        len(find_chunk_overlap(chunks[idx - 1].text, c.text)) if idx > 0 else 0
                    ),
                    "overlap_prev_text": (
                        find_chunk_overlap(chunks[idx - 1].text, c.text) if idx > 0 else ""
                    ),
                    "text": c.text,  # Full content after chunking!
                }
                for idx, c in enumerate(chunks)
            ],
            "pages": [
                {
                    "page": a.page_number,
                    "width": a.page_width,
                    "height": a.page_height,
                    "chunk_count": a.chunk_count,
                    "image_count": a.image_count,
                    "chunks": chunks_by_page.get(a.page_number, []),
                    "images": [img.to_dict() for img in a.images],
                }
                for a in analyses
            ],
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        print(f"  * Full JSON Metadata  : {json_path.resolve()} ({json_path.stat().st_size / 1024:.1f} KB)")

    # 2. Save Markdown report
    if args.save_markdown:
        md_path = (
            Path(args.markdown_path)
            if args.markdown_path
            else doc_dir / f"{input_path.stem}_chunks.md"
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_content = build_markdown_report(
            book_title=book_title,
            source_file=str(input_path),
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            chunks=chunks,
            analyses=analyses,
            summary=summary_stats,
        )
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"  * Markdown Report     : {md_path.resolve()} ({md_path.stat().st_size / 1024:.1f} KB)")

    # 3. Print terminal preview of chunk content
    if args.print_chunks:
        print_terminal_preview(chunks, count=-1)
    elif args.preview_chunks > 0:
        print_terminal_preview(chunks, count=args.preview_chunks)

    print("=" * 68)


if __name__ == "__main__":
    main()
