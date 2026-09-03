from dataclasses import dataclass
from typing import Dict, List, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings

from lumos.config import Settings, get_settings
from lumos.core.chunker import DocumentChunk


@dataclass
class SearchResult:
    chunk_id: str
    text: str
    book_title: str
    section: str
    source_file: str
    score: float


class ChromaVectorStore:
    """Manages persistent vector storage and similarity retrieval via ChromaDB."""

    COLLECTION_NAME = "ebook_rag_collection"

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.client = chromadb.PersistentClient(
            path=self.settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, chunks: List[DocumentChunk], embeddings: List[List[float]]) -> int:
        """Upsert document chunks with their corresponding embedding vectors."""
        if not chunks:
            return 0
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Chunks count ({len(chunks)}) does not match embeddings count ({len(embeddings)})"
            )

        ids = [c.chunk_id for c in chunks]
        texts = [c.text for c in chunks]
        metadatas = [c.to_metadata() for c in chunks]

        # ChromaDB supports batch upserts
        batch_size = 200
        for i in range(0, len(ids), batch_size):
            self.collection.upsert(
                ids=ids[i : i + batch_size],
                embeddings=embeddings[i : i + batch_size],
                documents=texts[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
            )

        return len(ids)

    def query(self, query_embedding: List[float], top_k: int = 5) -> List[SearchResult]:
        """Perform cosine similarity vector search across all indexed books."""
        count = self.collection.count()
        if count == 0:
            return []

        actual_k = min(top_k, count)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=actual_k,
            include=["documents", "metadatas", "distances"],
        )

        search_results: List[SearchResult] = []
        if not results or not results["ids"] or not results["ids"][0]:
            return []

        ids = results["ids"][0]
        docs = results["documents"][0] if results["documents"] else []
        metas = results["metadatas"][0] if results["metadatas"] else []
        distances = results["distances"][0] if results["distances"] else []

        for i in range(len(ids)):
            dist = distances[i] if i < len(distances) else 1.0
            # With cosine distance in Chroma: similarity = 1.0 - distance
            similarity = max(0.0, min(1.0, 1.0 - dist))
            meta = metas[i] if i < len(metas) else {}

            search_results.append(
                SearchResult(
                    chunk_id=ids[i],
                    text=docs[i] if i < len(docs) else "",
                    book_title=str(meta.get("book_title", "Unknown")),
                    section=str(meta.get("section", "General")),
                    source_file=str(meta.get("source_file", "Unknown")),
                    score=round(similarity, 4),
                )
            )

        return search_results

    def list_books(self) -> List[Dict[str, any]]:
        """List all indexed books, their source filenames, and total chunk counts."""
        count = self.collection.count()
        if count == 0:
            return []

        # Fetch all metadata records to group by source_file
        data = self.collection.get(include=["metadatas"])
        metadatas = data.get("metadatas", [])

        book_stats: Dict[str, Dict[str, any]] = {}
        for meta in metadatas:
            if not meta:
                continue
            source_file = str(meta.get("source_file", "unknown"))
            book_title = str(meta.get("book_title", source_file))

            if source_file not in book_stats:
                book_stats[source_file] = {
                    "source_file": source_file,
                    "book_title": book_title,
                    "chunk_count": 0,
                }
            book_stats[source_file]["chunk_count"] += 1

        return list(book_stats.values())

    def delete_book(self, source_file: str) -> int:
        """Delete all chunks belonging to a specific source file."""
        # Get count before
        records = self.collection.get(
            where={"source_file": source_file},
            include=["metadatas"],
        )
        ids_to_delete = records.get("ids", [])
        if ids_to_delete:
            self.collection.delete(ids=ids_to_delete)
        return len(ids_to_delete)

    def get_total_chunks(self) -> int:
        return self.collection.count()
