import json
from pathlib import Path
import shutil
from typing import Generator
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from lumos.api.schemas import (
    BookItem,
    BooksListResponse,
    ChatRequest,
    ChatResponse,
    CitationItem,
    DeleteResponse,
    HealthResponse,
    IngestResponse,
)
from lumos.config import get_settings
from lumos.core.parser import DocumentParser
from lumos.core.rag_service import RAGService

router = APIRouter(prefix="/api", tags=["RAG E-Book Chatbot"])
settings = get_settings()
rag_service = RAGService(settings)


@router.get("/health", response_model=HealthResponse)
def health_check():
    books = rag_service.list_books()
    total_chunks = rag_service.vector_store.get_total_chunks()
    return HealthResponse(
        status="healthy",
        openrouter_configured=bool(settings.openrouter_api_key),
        jina_configured=bool(settings.jina_api_key),
        total_books=len(books),
        total_chunks=total_chunks,
    )


@router.post("/ingest", response_model=IngestResponse)
async def ingest_book(file: UploadFile = File(...)):
    filename = file.filename or "unknown.bin"
    ext = Path(filename).suffix.lower()
    if ext not in DocumentParser.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Only {DocumentParser.SUPPORTED_EXTENSIONS} are supported.",
        )

    # Save uploaded file into UPLOAD_DIR
    target_path = Path(settings.upload_dir) / filename
    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Ingest through RAG pipeline
        result = rag_service.ingest_file(target_path, original_filename=filename)
        return IngestResponse(
            message=f"Successfully parsed and indexed {filename}",
            source_file=result["source_file"],
            book_title=result["book_title"],
            sections_count=result["sections_count"],
            chunks_count=result["chunks_count"],
        )
    except Exception as e:
        # Clean up file on failure
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest {filename}: {str(e)}",
        )


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    if not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty",
        )

    try:
        if request.stream:
            token_stream, citations = rag_service.ask_stream(request.query, top_k=request.top_k)

            def sse_event_stream() -> Generator[str, None, None]:
                # Send citations first as metadata event
                citations_data = [
                    CitationItem(
                        chunk_id=c.chunk_id,
                        book_title=c.book_title,
                        section=c.section,
                        source_file=c.source_file,
                        score=c.score,
                        text=c.text,
                    ).model_dump()
                    for c in citations
                ]
                yield f"event: citations\ndata: {json.dumps(citations_data)}\n\n"

                # Stream tokens
                for token in token_stream:
                    yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"

                yield "event: done\ndata: {}\n\n"

            return StreamingResponse(sse_event_stream(), media_type="text/event-stream")

        # Non-streaming response
        response = rag_service.ask(request.query, top_k=request.top_k)
        citation_items = [
            CitationItem(
                chunk_id=c.chunk_id,
                book_title=c.book_title,
                section=c.section,
                source_file=c.source_file,
                score=c.score,
                text=c.text,
            )
            for c in response["citations"]
        ]
        return ChatResponse(
            query=response["query"],
            answer=response["answer"],
            citations=citation_items,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat generation error: {str(e)}",
        )


@router.get("/documents", response_model=BooksListResponse)
def get_documents():
    books = rag_service.list_books()
    items = [
        BookItem(
            source_file=b["source_file"],
            book_title=b["book_title"],
            chunk_count=b["chunk_count"],
        )
        for b in books
    ]
    return BooksListResponse(total_books=len(items), books=items)


@router.delete("/documents/{filename}", response_model=DeleteResponse)
def delete_document(filename: str):
    deleted_count = rag_service.delete_book(filename)
    if deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{filename}' not found in library.",
        )

    # Also remove raw file from uploads if present
    file_path = Path(settings.upload_dir) / filename
    if file_path.exists():
        file_path.unlink()

    return DeleteResponse(
        message=f"Successfully deleted {filename}",
        source_file=filename,
        deleted_chunks=deleted_count,
    )
