"""CLI Entrypoint for PDF Bounding Box Visualizer.

Usage:
    python -m scripts.pdf_bbox_tool.main
    python scripts/pdf_bbox_tool/main.py
    python -m scripts.pdf_bbox_tool.main --input data/uploads/BuildingEffectiveAIAgents_Anthropic.pdf
    python -m scripts.pdf_bbox_tool.main --show-lines --export-images
"""

import argparse
import json
from pathlib import Path
import sys

# Support running both as a module and directly as a script file
try:
    from scripts.pdf_bbox_tool.annotator import PDFBoundingBoxAnnotator
except ModuleNotFoundError:
    # Add parent directory if executed directly
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    try:
        from scripts.pdf_bbox_tool.annotator import PDFBoundingBoxAnnotator
    except ModuleNotFoundError:
        from annotator import PDFBoundingBoxAnnotator



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PDF Bounding Box Visualizer - Annotates text and image elements on PDF pages."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default="data/uploads/BuildingEffectiveAIAgents_Anthropic.pdf",
        help="Path to the input PDF file (default: data/uploads/BuildingEffectiveAIAgents_Anthropic.pdf)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Path to save the annotated PDF (default: <input_dir>/<file_stem>/<file_stem>_bbox.pdf)",
    )
    parser.add_argument(
        "--show-lines",
        action="store_true",
        default=False,
        help="Also draw bounding boxes around individual text lines within blocks",
    )
    parser.add_argument(
        "--export-images",
        action="store_true",
        default=False,
        help="Export annotated pages as PNG images into an output directory",
    )
    parser.add_argument(
        "--images-dir",
        type=str,
        default=None,
        help="Directory to save PNG preview images (default: <input_dir>/<file_stem>/bbox_previews)",
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
        default=False,
        help="Export extracted bounding box metadata as a JSON file",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[Error] Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Place outputs into a folder named after the input file
    doc_dir = input_path.parent / input_path.stem
    doc_dir.mkdir(parents=True, exist_ok=True)

    output_path = Path(args.output) if args.output else (doc_dir / f"{input_path.stem}_bbox.pdf")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.export_images:
        images_dir = Path(args.images_dir) if args.images_dir else (doc_dir / "bbox_previews")
        images_dir.mkdir(parents=True, exist_ok=True)
    else:
        images_dir = None

    print("=" * 65)
    print("           Lumos PDF Bounding Box Visualizer")
    print("=" * 65)
    print(f" Input File     : {input_path}")
    print(f" Output Folder  : {doc_dir}")
    print(f" Output PDF     : {output_path}")
    print(f" Show Lines     : {args.show_lines}")
    print(f" Export Previews: {args.export_images} ({images_dir if args.export_images else 'N/A'})")
    if args.max_pages:
        print(f" Max Pages      : {args.max_pages}")
    print("-" * 65)

    annotator = PDFBoundingBoxAnnotator(
        show_lines=args.show_lines,
        show_images=True,
        show_labels=True,
        show_legend=True,
    )

    analyses = annotator.process_file(
        input_path=input_path,
        output_path=output_path,
        max_pages=args.max_pages,
        export_images_dir=images_dir,
        dpi=args.dpi,
    )

    total_blocks = sum(len(a.blocks) for a in analyses)
    total_text_blocks = sum(a.text_block_count for a in analyses)
    total_images = sum(a.image_block_count for a in analyses)
    total_lines = sum(a.line_count for a in analyses)
    total_words = sum(a.word_count for a in analyses)

    print(f"\n[Done] Annotated {len(analyses)} pages successfully!")
    print(f"  * Total Elements : {total_blocks} ({total_text_blocks} text blocks, {total_images} image blocks)")
    print(f"  * Total Lines    : {total_lines}")
    print(f"  * Total Words    : {total_words}")
    print(f"  * Output PDF     : {output_path.resolve()} ({output_path.stat().st_size / 1024:.1f} KB)")

    if args.export_images and images_dir:
        exported_imgs = list(images_dir.glob("page_*_bbox.png"))
        print(f"  * Preview Images : {len(exported_imgs)} images saved in {images_dir}/")

    if args.save_json:
        json_path = output_path.with_suffix(".json")
        data = {
            "source_file": str(input_path),
            "page_count": len(analyses),
            "summary": {
                "total_blocks": total_blocks,
                "text_blocks": total_text_blocks,
                "image_blocks": total_images,
                "lines": total_lines,
                "words": total_words,
            },
            "pages": [
                {
                    "page": a.page_number,
                    "width": a.page_width,
                    "height": a.page_height,
                    "text_blocks": a.text_block_count,
                    "image_blocks": a.image_block_count,
                    "blocks": [b.to_dict() for b in a.blocks],
                }
                for a in analyses
            ],
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  * JSON Metadata  : {json_path.resolve()}")

    print("=" * 65)


if __name__ == "__main__":
    main()
