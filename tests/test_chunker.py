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
    assert chunks[0].next_chunk_id == chunks[1].chunk_id
    assert chunks[1].prev_chunk_id == chunks[0].chunk_id


def test_cross_page_chunking_continuous():
    """Verifies continuous chunking across page boundaries with linking and page spans."""
    from lumos.core.chunker import RecursiveChunker
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

    chunker = RecursiveChunker(chunk_size=160, chunk_overlap=40, cross_page=True, clean_headers_footers=True)
    chunks = chunker.chunk_sections([sec1, sec2])

    assert len(chunks) >= 2
    # Verify bidirectional linking
    assert chunks[0].prev_chunk_id is None
    assert chunks[0].next_chunk_id == chunks[1].chunk_id
    assert chunks[1].prev_chunk_id == chunks[0].chunk_id

    # Verify at least one chunk spans across pages or has overlap
    has_cross_span = any(c.page_start != c.page_end for c in chunks)
    has_overlap = any(c.overlap_prev_chars > 0 for c in chunks[1:])
    assert has_cross_span or has_overlap
    assert all(c.char_count > 0 for c in chunks)


def test_header_footer_cleaning():
    """Verifies that clean_section_text strips timestamps, URLs, page counts, and edge title repetitions."""
    from lumos.core.chunker import clean_section_text

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


def test_chunk_to_metadata_chroma_compatible():
    """Asserts that all fields returned by to_metadata are primitive types acceptable by ChromaDB."""
    from lumos.core.chunker import DocumentChunk

    chunk = DocumentChunk(
        chunk_id="chk123",
        text="Sample chunk content",
        book_title="Test Book",
        section="Pages 1 - 2",
        source_file="test.pdf",
        chunk_index=0,
        page_start=1,
        page_end=2,
        pages=[1, 2],
        prev_chunk_id=None,
        next_chunk_id="chk124",
        overlap_prev_text="Sample",
        overlap_prev_chars=6,
    )

    meta = chunk.to_metadata()
    assert isinstance(meta, dict)
    for k, v in meta.items():
        assert isinstance(v, (str, int, float, bool)), f"Metadata key {k} has unsupported type {type(v)}"
    assert meta["page_start"] == 1
    assert meta["page_end"] == 2
    assert "prev_chunk_id" not in meta  # None should be omitted
    assert meta["next_chunk_id"] == "chk124"


def test_isolated_mode_fallback():
    """Verifies that cross_page=False isolates section boundaries."""
    from lumos.core.chunker import RecursiveChunker
    from lumos.core.parser import DocumentSection

    sec1 = DocumentSection(
        text="Section 1 content. " * 5,
        book_title="Book",
        section="Page 1",
        source_file="book.pdf",
    )
    sec2 = DocumentSection(
        text="Section 2 content. " * 5,
        book_title="Book",
        section="Page 2",
        source_file="book.pdf",
    )

    chunker = RecursiveChunker(chunk_size=120, chunk_overlap=30, cross_page=False)
    chunks = chunker.chunk_sections([sec1, sec2])

    assert len(chunks) >= 2
    assert all(c.page_start == c.page_end for c in chunks)
    assert chunks[0].next_chunk_id == chunks[1].chunk_id
    assert chunks[1].prev_chunk_id == chunks[0].chunk_id

