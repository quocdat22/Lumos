from unittest.mock import MagicMock, patch
import httpx
import pytest

from lumos.config import Settings
from lumos.core.embedder import JinaEmbedder


@pytest.fixture
def mock_settings():
    return Settings(
        jina_api_key="test_jina_key",
        jina_api_url="https://api.jina.ai/v1/embeddings",
        jina_embedding_model="jina-embeddings-v5-omni-small",
        jina_batch_size=2,
        jina_rate_limit_pause=0.0,
        jina_max_retries=3,
    )


def test_missing_api_key_raises_error():
    settings = Settings(jina_api_key="")
    embedder = JinaEmbedder(settings)
    with pytest.raises(ValueError, match="Jina API key is not configured"):
        embedder.embed_documents(["Test passage"])


def test_embed_documents_empty_list(mock_settings):
    embedder = JinaEmbedder(mock_settings)
    assert embedder.embed_documents([]) == []


def test_embed_documents_successful_batches(mock_settings):
    embedder = JinaEmbedder(mock_settings)
    texts = ["passage 1", "passage 2", "passage 3"]

    def mock_post(url, headers, json):
        batch = json["input"]
        data = [{"index": idx, "embedding": [0.1 * (idx + 1)] * 4} for idx in range(len(batch))]
        return httpx.Response(status_code=200, json={"data": data})

    with patch("httpx.Client.post", side_effect=mock_post):
        embeddings = embedder.embed_documents(texts, batch_size=2)
        assert len(embeddings) == 3
        assert len(embeddings[0]) == 4


def test_embed_documents_429_rate_limit_retry_success(mock_settings):
    embedder = JinaEmbedder(mock_settings)
    texts = ["chunk 1", "chunk 2"]

    call_count = 0

    def mock_post_with_429(url, headers, json):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                status_code=429,
                headers={"Retry-After": "0"},
                json={"detail": "Token rate limit exceeded: 101,274/100,000 tokens per minute."},
            )
        data = [{"index": 0, "embedding": [0.5] * 4}, {"index": 1, "embedding": [0.6] * 4}]
        return httpx.Response(status_code=200, json={"data": data})

    with patch("httpx.Client.post", side_effect=mock_post_with_429), patch("time.sleep") as mock_sleep:
        embeddings = embedder.embed_documents(texts, batch_size=2)
        assert len(embeddings) == 2
        assert call_count == 2
        assert mock_sleep.called


def test_embed_documents_exhausted_retries_raises_runtime_error(mock_settings):
    embedder = JinaEmbedder(mock_settings)
    texts = ["chunk 1"]

    def mock_post_always_429(url, headers, json):
        return httpx.Response(
            status_code=429,
            json={"detail": "Token rate limit exceeded."},
        )

    with patch("httpx.Client.post", side_effect=mock_post_always_429), patch("time.sleep"):
        with pytest.raises(RuntimeError, match="Jina API rate limit \\(429\\) exceeded after 3 retries"):
            embedder.embed_documents(texts)


def test_embed_query_success_and_retry(mock_settings):
    embedder = JinaEmbedder(mock_settings)
    call_count = 0

    def mock_post_query(url, headers, json):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(status_code=503, text="Service Unavailable")
        return httpx.Response(
            status_code=200,
            json={"data": [{"index": 0, "embedding": [0.9, 0.8, 0.7, 0.6]}]},
        )

    with patch("httpx.Client.post", side_effect=mock_post_query), patch("time.sleep"):
        vec = embedder.embed_query("machine learning models")
        assert len(vec) == 4
        assert vec[0] == 0.9
        assert call_count == 2


def test_embed_query_empty_raises_value_error(mock_settings):
    embedder = JinaEmbedder(mock_settings)
    with pytest.raises(ValueError, match="Query string cannot be empty"):
        embedder.embed_query("   ")
