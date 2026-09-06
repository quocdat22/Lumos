import logging
import random
import time
from typing import List, Optional
import httpx

from lumos.config import Settings, get_settings

logger = logging.getLogger(__name__)


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

    def _post_with_retry(
        self,
        client: httpx.Client,
        payload: dict,
        context_desc: str = "",
    ) -> List[dict]:
        """Send POST request to Jina API with exponential backoff and rate limit handling."""
        max_retries = getattr(self.settings, "jina_max_retries", 5)
        for attempt in range(max_retries + 1):
            try:
                response = client.post(self.api_url, headers=self._get_headers(), json=payload)
                if response.status_code == 200:
                    return response.json().get("data", [])

                if response.status_code == 429:
                    if attempt == max_retries:
                        raise RuntimeError(
                            f"Jina API rate limit (429) exceeded after {max_retries} retries: {response.text}"
                        )
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        wait_time = float(retry_after) + 1.0
                    else:
                        wait_time = min(60.0, (2 ** attempt) * 4.0) + random.uniform(0.5, 2.0)

                    desc = f" ({context_desc})" if context_desc else ""
                    logger.warning(
                        f"Jina rate limit hit (429){desc}. "
                        f"Backing off for {wait_time:.1f}s before retry (attempt {attempt + 1}/{max_retries})..."
                    )
                    time.sleep(wait_time)
                elif response.status_code in (502, 503, 504):
                    if attempt == max_retries:
                        raise RuntimeError(
                            f"Jina API server error ({response.status_code}): {response.text}"
                        )
                    wait_time = (2 ** attempt) * 2.0 + random.uniform(0.5, 1.5)
                    desc = f" ({context_desc})" if context_desc else ""
                    logger.warning(
                        f"Jina API transient error ({response.status_code}){desc}. "
                        f"Retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})..."
                    )
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(
                        f"Jina API error ({response.status_code}): {response.text}"
                    )
            except httpx.RequestError as exc:
                if attempt == max_retries:
                    raise RuntimeError(f"Network error connecting to Jina API: {exc}")
                wait_time = (2 ** attempt) * 2.0 + 1.0
                desc = f" ({context_desc})" if context_desc else ""
                logger.warning(
                    f"Network exception connecting to Jina API{desc}: {exc}. "
                    f"Retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})..."
                )
                time.sleep(wait_time)

        raise RuntimeError(f"Failed to obtain response from Jina API after {max_retries} retries.")

    def embed_documents(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        """Embed a list of text passages (chunks) in batches with rate-limiting and retry logic."""
        if not texts:
            return []

        actual_batch_size = batch_size or getattr(self.settings, "jina_batch_size", 16)
        rate_pause = getattr(self.settings, "jina_rate_limit_pause", 1.2)
        all_embeddings: List[List[float]] = []

        with httpx.Client(timeout=60.0) as client:
            total_batches = (len(texts) + actual_batch_size - 1) // actual_batch_size
            for b_idx, i in enumerate(range(0, len(texts), actual_batch_size)):
                batch = texts[i : i + actual_batch_size]
                payload = {
                    "model": self.model,
                    "task": "retrieval.passage",
                    "input": batch,
                }

                if b_idx > 0 and rate_pause > 0:
                    time.sleep(rate_pause)

                data = self._post_with_retry(
                    client=client,
                    payload=payload,
                    context_desc=f"batch {b_idx + 1}/{total_batches}",
                )

                # Sort data items by index to preserve input order
                sorted_items = sorted(data, key=lambda x: x.get("index", 0))
                for item in sorted_items:
                    all_embeddings.append(item["embedding"])

        return all_embeddings

    def embed_query(self, query: str) -> List[float]:
        """Embed a single search query string with retry logic."""
        if not query.strip():
            raise ValueError("Query string cannot be empty.")

        with httpx.Client(timeout=30.0) as client:
            payload = {
                "model": self.model,
                "task": "retrieval.query",
                "input": [query],
            }
            data = self._post_with_retry(
                client=client,
                payload=payload,
                context_desc="query embedding",
            )
            if not data:
                raise RuntimeError("Empty embedding response returned from Jina API.")
            return data[0]["embedding"]
