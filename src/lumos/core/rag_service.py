from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from lumos.config import Settings, get_settings
from lumos.core.chunker import RecursiveChunker
from lumos.core.embedder import JinaEmbedder
from lumos.core.llm import OpenRouterLLM
from lumos.core.parser import DocumentParser
from lumos.core.vector_store import ChromaVectorStore, SearchResult


class RAGService:
    """Unified service coordinating parser, chunker, embedder, vector store, and LLM."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.parser = DocumentParser()
        self.chunker = RecursiveChunker(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
            cross_page=self.settings.cross_page_chunking,
            clean_headers_footers=self.settings.clean_headers_footers,
        )
        self.embedder = JinaEmbedder(self.settings)
        self.vector_store = ChromaVectorStore(self.settings)
        self.llm = OpenRouterLLM(self.settings)

    def ingest_file(self, file_path: str | Path, original_filename: Optional[str] = None) -> Dict[str, any]:
        """Ingest a single e-book file (PDF or EPUB) into the ChromaDB collection."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # 1. Parse document sections
        sections = self.parser.parse(path)
        if not sections:
            raise ValueError(f"No readable text could be extracted from {path.name}")

        # Override source_file name with original_filename if provided
        if original_filename:
            for s in sections:
                s.source_file = original_filename

        book_title = sections[0].book_title if sections else path.stem

        # 2. Chunk document into overlapping passages
        chunks = self.chunker.chunk_sections(sections)
        if not chunks:
            raise ValueError(f"Failed to generate text chunks from {path.name}")

        # 3. Pipeline Ingestion: Embed & Upsert in batches to prevent memory bloat and save progress incrementally
        pipeline_batch_size = 64
        total_chunks = len(chunks)
        indexed_count = 0

        for i in range(0, total_chunks, pipeline_batch_size):
            batch_chunks = chunks[i : i + pipeline_batch_size]
            batch_texts = [c.text for c in batch_chunks]
            batch_embeddings = self.embedder.embed_documents(batch_texts)
            self.vector_store.add_chunks(batch_chunks, batch_embeddings)
            indexed_count += len(batch_chunks)
            pct = (indexed_count / total_chunks) * 100
            print(f"[{path.name}] Ingestion progress: {indexed_count}/{total_chunks} chunks indexed ({pct:.1f}%)")

        return {
            "source_file": original_filename or path.name,
            "book_title": book_title,
            "sections_count": len(sections),
            "chunks_count": indexed_count,
        }

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[SearchResult]:
        """Embed search query and retrieve most similar passages from the library."""
        k = top_k or self.settings.top_k
        query_vector = self.embedder.embed_query(query)
        return self.vector_store.query(query_vector, top_k=k)

    def ask(self, query: str, top_k: Optional[int] = None) -> Dict[str, any]:
        """Complete single-turn QA: retrieve passages and generate comprehensive answer."""
        results = self.retrieve(query, top_k=top_k)
        answer = self.llm.generate(query, results)
        return {
            "query": query,
            "answer": answer,
            "citations": results,
        }

    def ask_stream(self, query: str, top_k: Optional[int] = None) -> Tuple[Iterator[str], List[SearchResult]]:
        """Streaming QA: retrieve passages and stream token generation with citation metadata."""
        results = self.retrieve(query, top_k=top_k)
        token_stream = self.llm.stream(query, results)
        return token_stream, results

    def list_books(self) -> List[Dict[str, any]]:
        return self.vector_store.list_books()

    def delete_book(self, source_file: str) -> int:
        return self.vector_store.delete_book(source_file)
