from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # OpenRouter LLM Settings
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "deepseek/deepseek-v4-flash-0731"

    # Jina Embedding Settings
    jina_api_key: str = ""
    jina_embedding_model: str = "jina-embeddings-v5-omni-small"
    jina_api_url: str = "https://api.jina.ai/v1/embeddings"

    # Storage & RAG Settings
    chroma_persist_dir: str = "./data/chroma_db"
    upload_dir: str = "./data/uploads"
    chunk_size: int = 512
    chunk_overlap: int = 100
    top_k: int = 5
    cross_page_chunking: bool = True
    clean_headers_footers: bool = True

    # Server & UI Settings
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_api_url: str = "http://localhost:8000"

    def ensure_directories(self) -> None:
        """Ensure necessary storage directories exist."""
        Path(self.upload_dir).mkdir(parents=True, exist_ok=True)
        Path(self.chroma_persist_dir).mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
