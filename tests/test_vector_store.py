import tempfile
from lumos.config import Settings
from lumos.core.chunker import DocumentChunk
from lumos.core.vector_store import ChromaVectorStore


def test_chroma_vector_store_operations():
    with tempfile.TemporaryDirectory() as tmpdir:
        settings = Settings(chroma_persist_dir=tmpdir)
        store = ChromaVectorStore(settings)

        assert store.get_total_chunks() == 0

        # Create dummy chunks
        chunk1 = DocumentChunk(
            chunk_id="chunk_1",
            text="Vector search uses mathematical distances to evaluate semantic similarity.",
            book_title="Information Retrieval",
            section="Page 5",
            source_file="ir.pdf",
            chunk_index=0,
        )
        chunk2 = DocumentChunk(
            chunk_id="chunk_2",
            text="Deep learning models compute high-dimensional dense representations.",
            book_title="Neural Nets",
            section="Chapter 1",
            source_file="nn.epub",
            chunk_index=0,
        )

        # 4-dimensional mock embeddings
        emb1 = [1.0, 0.0, 0.0, 0.0]
        emb2 = [0.0, 1.0, 0.0, 0.0]

        count = store.add_chunks([chunk1, chunk2], [emb1, emb2])
        assert count == 2
        assert store.get_total_chunks() == 2

        # Query vector close to emb1
        results = store.query([0.9, 0.1, 0.0, 0.0], top_k=2)
        assert len(results) == 2
        assert results[0].chunk_id == "chunk_1"
        assert results[0].book_title == "Information Retrieval"
        assert results[0].score > 0.8

        # Test listing books
        books = store.list_books()
        assert len(books) == 2
        source_files = {b["source_file"] for b in books}
        assert "ir.pdf" in source_files
        assert "nn.epub" in source_files

        # Test deleting a book
        deleted = store.delete_book("ir.pdf")
        assert deleted == 1
        assert store.get_total_chunks() == 1
        books_after = store.list_books()
        assert len(books_after) == 1
        assert books_after[0]["source_file"] == "nn.epub"
