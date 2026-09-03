from typing import Iterator, List, Optional
from openai import OpenAI

from lumos.config import Settings, get_settings
from lumos.core.vector_store import SearchResult


SYSTEM_PROMPT = """You are an expert scholarly research assistant answering queries based on the user's e-book library.

Guidelines:
1. Ground your answer strictly in the provided Context passages.
2. If the context does not contain enough information to answer the question accurately, explicitly state: "The provided books do not contain sufficient information to answer this question." Do not fabricate or speculate.
3. Always respond in English to preserve original terminology.
4. Structure your response logically with clear formatting, bullet points, and paragraphs.
5. In your answer, reference the source book and section whenever drawing conclusions (e.g., "[Source: <Book Title>, <Section>]").
"""


class OpenRouterLLM:
    """Interface for DeepSeek via OpenRouter API with context injection and streaming."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.api_key = self.settings.openrouter_api_key
        self.base_url = self.settings.openrouter_base_url
        self.model = self.settings.openrouter_model

    def _get_client(self) -> OpenAI:
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key is not configured. Please set OPENROUTER_API_KEY in your .env file."
            )
        return OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    def format_context(self, search_results: List[SearchResult]) -> str:
        """Format retrieved search results into a clean context prompt block."""
        if not search_results:
            return "No relevant context passages were found in the e-book library."

        blocks = []
        for i, res in enumerate(search_results, 1):
            block = (
                f"--- Passage [{i}] ---\n"
                f"Book: {res.book_title}\n"
                f"Section: {res.section}\n"
                f"Source File: {res.source_file}\n"
                f"Relevance Score: {res.score:.2f}\n\n"
                f"{res.text}\n"
            )
            blocks.append(block)

        return "\n".join(blocks)

    def _build_messages(self, query: str, search_results: List[SearchResult]) -> list:
        context_str = self.format_context(search_results)
        user_message = (
            f"Here is the context retrieved from the e-book library:\n\n"
            f"{context_str}\n\n"
            f"User Question: {query}\n\n"
            f"Please synthesize a comprehensive answer in English based strictly on the above context."
        )

        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

    def generate(self, query: str, search_results: List[SearchResult]) -> str:
        """Generate a complete non-streaming response."""
        client = self._get_client()
        messages = self._build_messages(query, search_results)

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
        )
        return response.choices[0].message.content or ""

    def stream(self, query: str, search_results: List[SearchResult]) -> Iterator[str]:
        """Stream response tokens sequentially."""
        client = self._get_client()
        messages = self._build_messages(query, search_results)

        stream_response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            stream=True,
        )

        for chunk in stream_response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
