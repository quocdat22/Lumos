from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lumos.api.routes import router as api_router
from lumos.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure directories exist upon startup
    settings = get_settings()
    settings.ensure_directories()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Lumos - Native E-Book RAG API",
        description="Native RAG Chatbot API using DeepSeek on OpenRouter, Jina Embeddings, and ChromaDB",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "lumos.api.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
    )
