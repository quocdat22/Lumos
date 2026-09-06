from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from lumos.config import Settings
from lumos.core.chunker import DocumentChunk
from lumos.core.parser import DocumentSection
from lumos.core.rag_service import RAGService


def test_rag_service_ingest_file_pipeline_batching():
    with tempfile.TemporaryDirectory() as tmpdir:
        settings = Settings(
            chroma_persist_dir=tmpdir,
            jina_api_key="mock_key",
            jina_batch_size=4,
            jina_rate_limit_pause=0.0,
        )
        service = RAGService(settings)

        fake_file = Path(tmpdir) / "sample_book.pdf"
        fake_file.write_text("dummy content")

        mock_sections = [
            DocumentSection(
                text="Content for chapter 1 with several sentences.",
                book_title="Sample ML Book",
                section="Chapter 1",
                source_file="sample_book.pdf",
            ),
        ]

        # Generate 150 mock chunks to test multiple pipeline batches (pipeline_batch_size is 64)
        mock_chunks = [
            DocumentChunk(
                chunk_id=f"chunk_{i}",
                text=f"This is chunk number {i} with some sample text for testing.",
                book_title="Sample ML Book",
                section="Chapter 1",
                source_file="sample_book.pdf",
                chunk_index=i,
            )
            for i in range(150)
        ]

        with patch.object(service.parser, "parse", return_value=mock_sections), \
             patch.object(service.chunker, "chunk_sections", return_value=mock_chunks), \
             patch.object(service.embedder, "embed_documents", side_effect=lambda texts: [[0.1, 0.2, 0.3, 0.4]] * len(texts)) as mock_embed:

            result = service.ingest_file(fake_file, original_filename="sample_book.pdf")

            assert result["source_file"] == "sample_book.pdf"
            assert result["book_title"] == "Sample ML Book"
            assert result["sections_count"] == 1
            assert result["chunks_count"] == 150

            # 150 chunks with pipeline_batch_size=64 means embed_documents was called 3 times:
            # batch 1: 64, batch 2: 64, batch 3: 22
            assert mock_embed.call_count == 3

            # Verify all 150 chunks are indexed in vector store
            assert service.vector_store.get_total_chunks() == 150
