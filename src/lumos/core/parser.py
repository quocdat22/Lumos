from dataclasses import dataclass
from pathlib import Path
from typing import List
import warnings
import zipfile

from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub
import pymupdf


@dataclass
class DocumentSection:
    text: str
    book_title: str
    section: str
    source_file: str


class DocumentParser:
    """Extracts structured text sections and metadata from PDF and EPUB e-books."""

    SUPPORTED_EXTENSIONS = {".pdf", ".epub"}

    @classmethod
    def is_supported(cls, file_path: str | Path) -> bool:
        return Path(file_path).suffix.lower() in cls.SUPPORTED_EXTENSIONS

    def parse(self, file_path: str | Path) -> List[DocumentSection]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        ext = path.suffix.lower()
        if ext == ".pdf":
            return self._parse_pdf(path)
        elif ext == ".epub":
            return self._parse_epub(path)
        else:
            raise ValueError(f"Unsupported file format '{ext}'. Supported formats: {self.SUPPORTED_EXTENSIONS}")

    def _parse_pdf(self, path: Path) -> List[DocumentSection]:
        sections: List[DocumentSection] = []
        with pymupdf.open(str(path)) as doc:
            book_title = path.stem
            if doc.metadata and doc.metadata.get("title"):
                extracted_title = doc.metadata.get("title", "").strip()
                if extracted_title:
                    book_title = extracted_title

            for i, page in enumerate(doc):
                # Extract text blocks: (x0, y0, x1, y1, "text", block_no, block_type)
                # block_type 0 is text, 1 is image
                blocks = page.get_text("blocks")
                text_blocks: List[str] = []
                for b in blocks:
                    if len(b) >= 7 and b[6] == 0:
                        block_text = b[4].strip()
                        if block_text:
                            text_blocks.append(block_text)

                page_text = "\n\n".join(text_blocks).strip()
                if not page_text:
                    continue

                sections.append(
                    DocumentSection(
                        text=page_text,
                        book_title=book_title,
                        section=f"Page {i + 1}",
                        source_file=path.name,
                    )
                )
        return sections

    def _parse_epub(self, path: Path) -> List[DocumentSection]:
        """Parse EPUB using ebooklib with an automatic zip-extraction fallback."""
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                book = epub.read_epub(str(path), options={"ignore_ncx": True})
            return self._extract_from_ebooklib(book, path)
        except Exception:
            # Fallback to direct zip extraction if ebooklib fails on non-standard TOC/NCX
            return self._extract_epub_from_zip(path)

    def _extract_from_ebooklib(self, book: epub.EpubBook, path: Path) -> List[DocumentSection]:
        book_title = path.stem
        titles = book.get_metadata("DC", "title")
        if titles and len(titles) > 0 and titles[0][0]:
            extracted_title = str(titles[0][0]).strip()
            if extracted_title:
                book_title = extracted_title

        sections: List[DocumentSection] = []
        item_index = 1

        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                content = item.get_content()
                soup = BeautifulSoup(content, "html.parser")

                for s in soup(["script", "style"]):
                    s.decompose()

                heading = soup.find(["h1", "h2", "h3", "title"])
                section_name = heading.get_text().strip() if heading and heading.get_text().strip() else f"Section {item_index}"

                text = soup.get_text(separator="\n").strip()
                if not text:
                    continue

                sections.append(
                    DocumentSection(
                        text=text,
                        book_title=book_title,
                        section=section_name[:80],
                        source_file=path.name,
                    )
                )
                item_index += 1

        return sections

    def _extract_epub_from_zip(self, path: Path) -> List[DocumentSection]:
        sections: List[DocumentSection] = []
        book_title = path.stem
        item_index = 1

        with zipfile.ZipFile(str(path), "r") as z:
            # Try to read book title from OPF file
            for filename in z.namelist():
                if filename.lower().endswith(".opf"):
                    try:
                        opf_soup = BeautifulSoup(z.read(filename), "html.parser")
                        title_tag = opf_soup.find(["dc:title", "title"])
                        if title_tag and title_tag.get_text().strip():
                            book_title = title_tag.get_text().strip()
                            break
                    except Exception:
                        pass

            for filename in sorted(z.namelist()):
                if filename.lower().endswith((".xhtml", ".html", ".htm")) and not filename.lower().endswith("toc.ncx"):
                    content = z.read(filename)
                    soup = BeautifulSoup(content, "html.parser")
                    for s in soup(["script", "style"]):
                        s.decompose()

                    heading = soup.find(["h1", "h2", "h3", "title"])
                    section_name = heading.get_text().strip() if heading and heading.get_text().strip() else f"Section {item_index}"
                    text = soup.get_text(separator="\n").strip()
                    if not text:
                        continue

                    sections.append(
                        DocumentSection(
                            text=text,
                            book_title=book_title,
                            section=section_name[:80],
                            source_file=path.name,
                        )
                    )
                    item_index += 1

        return sections
