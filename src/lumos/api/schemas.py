from typing import List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The user's question or search query")
    top_k: Optional[int] = Field(default=5, ge=1, le=20, description="Number of context chunks to retrieve")
    stream: Optional[bool] = Field(default=False, description="Whether to stream response tokens via SSE")


class CitationItem(BaseModel):
    chunk_id: str
    book_title: str
    section: str
    source_file: str
    score: float
    text: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    prev_chunk_id: Optional[str] = None
    next_chunk_id: Optional[str] = None


class ChatResponse(BaseModel):
    query: str
    answer: str
    citations: List[CitationItem]


class IngestResponse(BaseModel):
    message: str
    source_file: str
    book_title: str
    sections_count: int
    chunks_count: int


class BookItem(BaseModel):
    source_file: str
    book_title: str
    chunk_count: int


class BooksListResponse(BaseModel):
    total_books: int
    books: List[BookItem]


class DeleteResponse(BaseModel):
    message: str
    source_file: str
    deleted_chunks: int


class HealthResponse(BaseModel):
    status: str
    openrouter_configured: bool
    jina_configured: bool
    total_books: int
    total_chunks: int
