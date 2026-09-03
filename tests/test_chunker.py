from lumos.core.chunker import RecursiveChunker
from lumos.core.parser import DocumentSection


def test_chunker_basic_split():
    chunker = RecursiveChunker(chunk_size=100, chunk_overlap=20)
    text = (
        "Artificial intelligence is transforming industries. "
        "Natural language processing allows machines to understand text. "
        "Deep learning leverages multi-layer neural networks to solve complex problems. "
    )
    chunks = chunker.split_text(text)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 120  # generous bound around chunk size


def test_chunker_with_sections():
    chunker = RecursiveChunker(chunk_size=150, chunk_overlap=30)
    sec1 = DocumentSection(
        text="Chapter 1 introduces basic concepts and foundational definitions. " * 3,
        book_title="Foundations of AI",
        section="Chapter 1",
        source_file="ai_book.epub",
    )
    sec2 = DocumentSection(
        text="Chapter 2 covers neural network architectures and backpropagation. " * 3,
        book_title="Foundations of AI",
        section="Chapter 2",
        source_file="ai_book.epub",
    )

    chunks = chunker.chunk_sections([sec1, sec2])
    assert len(chunks) >= 2
    assert chunks[0].book_title == "Foundations of AI"
    assert chunks[0].source_file == "ai_book.epub"
    assert chunks[0].chunk_id != ""
