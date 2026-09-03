# 📚 Lumos — Native E-Book RAG Chatbot

An ultra-fast, native Retrieval-Augmented Generation (RAG) chatbot tailored for analyzing and questioning English e-books (PDF & EPUB) across diverse domains.

Built with **pure Python logic** (no heavy LangChain or LlamaIndex frameworks), powered by **DeepSeek** via **OpenRouter**, **Jina Embeddings**, **ChromaDB**, and managed cleanly with **uv**.

---

## ✨ Features

- **Native / Vanilla Python RAG Pipeline**: Complete transparency and control over document parsing, recursive chunking with overlap, embedding batching, cosine vector retrieval, and prompt context synthesis.
- **Multi-Format E-Book Ingestion**:
  - **PDF (`.pdf`)**: Page-by-page text extraction with metadata via `pypdf`.
  - **EPUB (`.epub`)**: Structural chapter and section extraction via `ebooklib` + `BeautifulSoup4` with automatic zip-fallback for non-standard EPUBs.
- **State-of-the-Art Embedding & LLM**:
  - **Embedding**: `jina-embeddings-v5-omni-small` using task-specific passage/query modes via Jina's API.
  - **LLM**: `deepseek/deepseek-v4-flash-0731` via OpenRouter API.
- **Embedded Persistent Vector Database**: ChromaDB stores vectors, passages, and chapter/page metadata locally in `./data/chroma_db`.
- **Global Multi-Book Synthesis**: Queries search across all indexed books, and the LLM synthesizes comprehensive answers with exact source citations.
- **Decoupled Architecture**:
  - **FastAPI REST API**: Endpoints for document ingest, streaming chat (SSE), and library inspection.
  - **Streamlit Web UI**: Intuitive UI with drag-and-drop e-book upload, real-time token streaming, and expandable source citation inspector.
- **Dependency Management**: Powered by modern, blazingly fast `uv`.

---

## 🏗️ Project Architecture

```
Lumos/
├── .env.example              # Template for API keys and configuration
├── .env                      # Active environment variables
├── pyproject.toml            # Dependencies and CLI scripts managed by uv
├── README.md                 # Complete documentation
├── data/
│   ├── uploads/              # Raw uploaded PDF & EPUB books
│   └── chroma_db/            # ChromaDB local vector storage
├── src/lumos/
│   ├── config.py             # Pydantic Settings & environment loader
│   ├── cli.py                # Unified CLI runner (uv run lumos api/ui)
│   ├── core/
│   │   ├── parser.py         # PDF & EPUB document extractor
│   │   ├── chunker.py        # Recursive character chunker with overlap
│   │   ├── embedder.py       # Jina Embeddings API client
│   │   ├── vector_store.py   # ChromaDB client & similarity search
│   │   ├── llm.py            # OpenRouter DeepSeek client (streaming SSE)
│   │   └── rag_service.py    # Unified RAG coordinator
│   ├── api/
│   │   ├── main.py           # FastAPI application entrypoint
│   │   ├── routes.py         # REST endpoints (/ingest, /chat, /documents)
│   │   └── schemas.py        # Pydantic request/response schemas
│   └── ui/
│       └── app.py            # Streamlit Web UI application
└── tests/
    ├── test_api.py           # FastAPI endpoint tests
    ├── test_chunker.py       # Recursive chunking unit tests
    ├── test_parser.py        # PDF & EPUB parser tests
    └── test_vector_store.py  # ChromaDB vector store tests
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python `>= 3.12`
- [uv](https://github.com/astral-sh/uv) installed:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### 2. Configure API Keys
Copy `.env.example` to `.env` (or edit the existing `.env` file):
```bash
cp .env.example .env
```
Open `.env` and fill in your API keys:
```env
# OpenRouter API Key for DeepSeek
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Jina API Key for Embeddings
JINA_API_KEY=your_jina_api_key_here
```

### 3. Run the Backend & Frontend

Open **two terminal windows**:

#### Terminal 1 — Start FastAPI Server:
```bash
uv run lumos api
```
*The REST API will be available at [http://localhost:8000](http://localhost:8000), and interactive Swagger docs at [http://localhost:8000/docs](http://localhost:8000/docs).*

#### Terminal 2 — Start Streamlit Web UI:
```bash
uv run lumos ui
```
*The Web UI will automatically open at [http://localhost:8501](http://localhost:8501).*

---

## 📖 How to Use the Chatbot

1. **Upload E-Books**:
   - In the Streamlit sidebar, select any `.pdf` or `.epub` English book.
   - Click **📥 Parse & Index E-Book**.
   - The system extracts chapters/pages, generates overlapping semantic chunks, embeds them using `jina-embeddings-v5-omni-small`, and stores them in ChromaDB.
2. **Ask Questions**:
   - In the chat prompt, ask questions in natural language (e.g., *"What does Chapter 3 argue regarding scientific falsification?"* or *"Compare the author's perspective on AI with traditional software"*).
   - DeepSeek streams the answer in real-time.
3. **Inspect Citations**:
   - Click on the **📖 View Citations** expander beneath any answer to view the source book, chapter/page, similarity percentage, and exact passage text.
4. **Manage Library**:
   - In the sidebar, view all indexed books and their total chunk count, or remove any book with the 🗑️ button.

---

## 🛠️ API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Check service status and API key configuration |
| `POST` | `/api/ingest` | Upload and index a `.pdf` or `.epub` file (`multipart/form-data`) |
| `POST` | `/api/chat` | Query the library with streaming SSE or standard JSON response |
| `GET` | `/api/documents` | List all indexed books and chunk statistics |
| `DELETE`| `/api/documents/{filename}` | Delete a book and its vector embeddings from the database |

---

## 🧪 Running Unit Tests

Run the test suite with `uv`:
```bash
uv run pytest
```
All unit tests cover parser integrity, chunking overlap, ChromaDB persistence, and FastAPI endpoint routes.
