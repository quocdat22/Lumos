from typing import List
import httpx

from lumos.config import Settings, get_settings


class JinaEmbedder:
    """Client for generating vector embeddings via Jina's Embeddings API."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.api_key = self.settings.jina_api_key
        self.api_url = self.settings.jina_api_url
        self.model = self.settings.jina_embedding_model

    def _get_headers(self) -> dict:
        if not self.api_key:
            raise ValueError(
                "Jina API key is not configured. Please set JINA_API_KEY in your .env file."
            )
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def embed_documents(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Embed a list of text passages (chunks) in batches."""
        if not texts:
            return []

        all_embeddings: List[List[float]] = []

        with httpx.Client(timeout=60.0) as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                payload = {
                    "model": self.model,
                    "task": "retrieval.passage",
                    "input": batch,
                }
                
                response = client.post(self.api_url, headers=self._get_headers(), json=payload)
                if response.status_code != 200:
                    raise RuntimeError(
                        f"Jina API error ({response.status_code}): {response.text}"
                    )
                
                data = response.json().get("data", [])
                # Sort data items by index to preserve input order
                sorted_items = sorted(data, key=lambda x: x.get("index", 0))
                for item in sorted_items:
                    all_embeddings.append(item["embedding"])

        return all_embeddings

    def embed_query(self, query: str) -> List[float]:
        """Embed a single search query string."""
        if not query.strip():
            raise ValueError("Query string cannot be empty.")

        with httpx.Client(timeout=30.0) as client:
            payload = {
                "model": self.model,
                "task": "retrieval.query",
                "input": [query],
            }
            response = client.post(self.api_url, headers=self._get_headers(), json=payload)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Jina API error ({response.status_code}): {response.text}"
                )
            data = response.json().get("data", [])
            if not data:
                raise RuntimeError("Empty embedding response returned from Jina API.")
            return data[0]["embedding"]
