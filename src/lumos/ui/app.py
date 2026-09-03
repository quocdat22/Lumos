import json
import os
from pathlib import Path
import httpx
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Lumos - Native E-Book RAG Chatbot",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Backend URL configuration
BACKEND_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")


def check_backend_health():
    try:
        res = httpx.get(f"{BACKEND_URL}/api/health", timeout=3.0)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


def fetch_documents():
    try:
        res = httpx.get(f"{BACKEND_URL}/api/documents", timeout=5.0)
        if res.status_code == 200:
            return res.json().get("books", [])
    except Exception as e:
        st.sidebar.error(f"Error fetching books: {e}")
    return []


def delete_document(source_file: str):
    try:
        res = httpx.delete(f"{BACKEND_URL}/api/documents/{source_file}", timeout=10.0)
        if res.status_code == 200:
            st.toast(f"Deleted '{source_file}' successfully!", icon="🗑️")
            return True
        else:
            st.sidebar.error(f"Delete failed: {res.text}")
    except Exception as e:
        st.sidebar.error(f"Error deleting: {e}")
    return False


def upload_document(uploaded_file):
    try:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        res = httpx.post(f"{BACKEND_URL}/api/ingest", files=files, timeout=300.0)
        if res.status_code == 200:
            return res.json()
        else:
            st.sidebar.error(f"Ingest failed: {res.json().get('detail', res.text)}")
    except Exception as e:
        st.sidebar.error(f"Network error during upload: {e}")
    return None


# Sidebar layout
with st.sidebar:
    st.title("📚 E-Book Library")
    st.caption("Native RAG with DeepSeek & Jina")

    # Backend Status
    health = check_backend_health()
    if health:
        st.success("🟢 Backend Connected", icon="✅")
        if not health.get("openrouter_configured"):
            st.warning("⚠️ OPENROUTER_API_KEY not set in .env")
        if not health.get("jina_configured"):
            st.warning("⚠️ JINA_API_KEY not set in .env")
    else:
        st.error(f"🔴 Backend unreachable at {BACKEND_URL}. Start FastAPI first!")

    st.divider()

    # Document Upload Section
    st.subheader("Upload E-Book")
    uploaded_file = st.file_uploader(
        "Choose a PDF or EPUB file",
        type=["pdf", "epub"],
        help="Upload English e-books in .pdf or .epub format",
    )

    if uploaded_file is not None:
        if st.button("📥 Parse & Index E-Book", use_container_width=True):
            with st.spinner(f"Parsing, chunking, and embedding '{uploaded_file.name}'..."):
                result = upload_document(uploaded_file)
                if result:
                    st.success(
                        f"**{result['book_title']}** indexed!\n\n"
                        f"- Sections: {result['sections_count']}\n"
                        f"- Chunks: {result['chunks_count']}"
                    )
                    st.rerun()

    st.divider()

    # Document Library Management
    st.subheader("Indexed Books")
    books = fetch_documents() if health else []
    if books:
        for b in books:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**📖 {b['book_title']}**")
                st.caption(f"`{b['source_file']}` • {b['chunk_count']} chunks")
            with col2:
                if st.button("🗑️", key=f"del_{b['source_file']}", help=f"Delete {b['source_file']}"):
                    if delete_document(b["source_file"]):
                        st.rerun()
    else:
        st.info("No e-books indexed yet. Upload a book above to start querying.")

    st.divider()

    # Search Configuration
    st.subheader("Retrieval Settings")
    top_k = st.slider("Top-K Context Chunks", min_value=1, max_value=15, value=5, step=1)

    if st.button("🧹 Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


# Main Chat Interface
st.title("Lumos — E-Book Scholar")
st.markdown(
    "Ask any scholarly or thematic questions across your indexed e-book library. "
    "Answers are synthesized strictly in **English** with exact source citations."
)

# Initialize chat messages
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous conversation messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("citations"):
            with st.expander(f"📖 View Citations ({len(msg['citations'])} sources)"):
                for idx, cite in enumerate(msg["citations"], 1):
                    st.markdown(
                        f"**[{idx}] {cite['book_title']}** — *{cite['section']}* (Relevance: `{cite['score'] * 100:.1f}%`)"
                    )
                    st.caption(f"Source file: `{cite['source_file']}`")
                    st.code(cite["text"], language="text")

# Chat input
if user_prompt := st.chat_input("Ask a question about your books (e.g. 'What are the main arguments in chapter 2?')..."):
    # Append user message
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    # Generate assistant response
    with st.chat_message("assistant"):
        citations_holder = []

        def stream_sse():
            try:
                with httpx.Client(timeout=120.0) as client:
                    with client.stream(
                        "POST",
                        f"{BACKEND_URL}/api/chat",
                        json={"query": user_prompt, "top_k": top_k, "stream": True},
                    ) as response:
                        if response.status_code != 200:
                            yield f"⚠️ API Error ({response.status_code}): {response.read().decode('utf-8')}"
                            return

                        current_event = None
                        for line in response.iter_lines():
                            if not line:
                                continue
                            if line.startswith("event: "):
                                current_event = line[7:].strip()
                            elif line.startswith("data: "):
                                data_str = line[6:].strip()
                                if current_event == "citations":
                                    citations_holder.extend(json.loads(data_str))
                                elif current_event == "token":
                                    payload = json.loads(data_str)
                                    yield payload.get("token", "")
                                elif current_event == "done":
                                    break
            except Exception as e:
                yield f"⚠️ Error communicating with backend: {str(e)}"

        # Stream response tokens
        response_text = st.write_stream(stream_sse())

        # Render citations accordion
        if citations_holder:
            with st.expander(f"📖 View Citations ({len(citations_holder)} sources)"):
                for idx, cite in enumerate(citations_holder, 1):
                    st.markdown(
                        f"**[{idx}] {cite['book_title']}** — *{cite['section']}* (Relevance: `{cite['score'] * 100:.1f}%`)"
                    )
                    st.caption(f"Source file: `{cite['source_file']}`")
                    st.code(cite["text"], language="text")

        # Save assistant message into session state
        st.session_state.messages.append({
            "role": "assistant",
            "content": response_text,
            "citations": citations_holder,
        })
