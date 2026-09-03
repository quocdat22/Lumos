import tempfile
from pathlib import Path
import ebooklib
from ebooklib import epub
import pymupdf

from lumos.core.parser import DocumentParser


def test_parse_pdf():
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "sample_book.pdf"

        # Create a 2-page PDF with pymupdf
        doc = pymupdf.open()
        p1 = doc.new_page(width=400, height=400)
        p1.insert_text((20, 50), "First page content with AI concepts.")
        p2 = doc.new_page(width=400, height=400)
        p2.insert_text((20, 50), "Second page content with neural networks.")
        doc.set_metadata({"title": "Artificial Intelligence Concepts"})
        doc.save(str(pdf_path))
        doc.close()

        parser = DocumentParser()
        assert parser.is_supported(pdf_path)
        sections = parser.parse(pdf_path)
        assert len(sections) == 2
        assert sections[0].book_title == "Artificial Intelligence Concepts"
        assert sections[0].section == "Page 1"
        assert "AI concepts" in sections[0].text
        assert sections[1].section == "Page 2"
        assert "neural networks" in sections[1].text


def test_parse_pdf_blank_page():
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "blank.pdf"
        doc = pymupdf.open()
        doc.new_page(width=200, height=200)
        doc.save(str(pdf_path))
        doc.close()

        parser = DocumentParser()
        sections = parser.parse(pdf_path)
        assert sections == []


def test_parse_epub():
    with tempfile.TemporaryDirectory() as tmpdir:
        epub_path = Path(tmpdir) / "sample_book.epub"

        # Create a tiny EPUB with ebooklib
        book = epub.EpubBook()
        book.set_identifier("lumos-test-123")
        book.set_title("Philosophy of Science")
        book.set_language("en")

        c1 = epub.EpubHtml(title="Introduction", file_name="intro.xhtml", lang="en")
        c1.content = "<h1>Chapter 1</h1><p>Empiricism emphasizes evidence from sensory experience.</p>"
        book.add_item(c1)

        c2 = epub.EpubHtml(title="Methodology", file_name="method.xhtml", lang="en")
        c2.content = "<h2>Chapter 2</h2><p>Falsificationism was formulated by Karl Popper.</p>"
        book.add_item(c2)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        book.spine = ["nav", c1, c2]

        epub.write_epub(str(epub_path), book, {})

        parser = DocumentParser()
        assert parser.is_supported(epub_path)
        sections = parser.parse(epub_path)

        assert len(sections) >= 2
        assert sections[0].book_title == "Philosophy of Science"
        assert any("Empiricism" in s.text for s in sections)
        assert any("Falsificationism" in s.text for s in sections)
