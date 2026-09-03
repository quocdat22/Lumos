from fastapi.testclient import TestClient
from lumos.api.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "openrouter_configured" in data
    assert "jina_configured" in data
    assert "total_books" in data
    assert "total_chunks" in data


def test_documents_empty_initially():
    response = client.get("/api/documents")
    assert response.status_code == 200
    data = response.json()
    assert "total_books" in data
    assert "books" in data


def test_unsupported_file_format_ingest():
    # Send a .txt file which is not in [.pdf, .epub]
    files = {"file": ("test.txt", b"plain text content", "text/plain")}
    response = client.post("/api/ingest", files=files)
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_empty_query_chat():
    response = client.post("/api/chat", json={"query": "   ", "top_k": 5})
    assert response.status_code == 400
