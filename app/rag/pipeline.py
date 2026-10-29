"""Retrieval-augmented generation pipeline.

Retrieves the most relevant chunks from Qdrant and asks Groq to answer using
*only* those chunks. Documents are included in the context, and the system is
configured to provide answers based on the retrieved content.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator, Dict, List, Optional, Tuple

from groq import Groq

from app.config import get_settings
from app.models import Citation, RetrievedChunk
from app.rag import vectorstore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a precise enterprise knowledge assistant. Answer the user's "
    "question using only facts explicitly supported by the provided document "
    "context. If the question is unrelated to that context, or the context "
    "does not contain enough information to answer, say that the knowledge "
    "base does not contain the answer. Do not answer from general knowledge, "
    "prior conversation, or assumptions. Be concise. Cite supporting files "
    "using [Source: filename]."
)

_client: Optional[Groq] = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        settings = get_settings()
        # Resolves GROQ_API_KEY from the environment.
        _client = Groq(api_key=settings.groq_api_key or None)
    return _client


def _build_context(chunks: List[dict]) -> str:
    """Turn retrieved chunks into a context string for the LLM."""
    context_parts = []
    for chunk in chunks:
        context_parts.append(
            f"Source: {chunk['source']} (chunk {chunk['chunk_index']})\n"
            f"Content: {chunk['text']}\n"
        )
    return "\n---\n".join(context_parts)


def _build_messages(
    question: str, history: List[dict], context: str
) -> List[dict]:
    messages: List[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    # Add context and question in the final user turn.
    user_message = (
        "Use only the document context below to answer the question. "
        "If it does not support an answer, say the knowledge base does not "
        "contain the answer.\n\n"
        f"Document context:\n{context}\n\nQuestion: {question}"
    )
    messages.append({"role": "user", "content": user_message})
    return messages


def _retrieve(
    question: str, top_k: Optional[int], sources: Optional[List[str]]
) -> List[dict]:
    settings = get_settings()
    k = top_k or settings.top_k
    return vectorstore.search(question, top_k=k, sources=sources)


def _request_kwargs(messages: List[dict]) -> dict:
    settings = get_settings()
    kwargs: dict = {
        "model": settings.groq_model,
        "max_tokens": settings.max_tokens,
        "messages": messages,
    }
    return kwargs


def _usage_dict(usage) -> dict:
    """Return token counts when the provider includes usage metadata."""
    if usage is None:
        return {}
    prompt_tokens = getattr(usage, "prompt_tokens", None)
    completion_tokens = getattr(usage, "completion_tokens", None)
    if prompt_tokens is None and completion_tokens is None:
        return {}
    return {
        "input_tokens": prompt_tokens or 0,
        "output_tokens": completion_tokens or 0,
    }


def _parse_answer(response_text: str, chunks: List[dict]) -> Tuple[str, List[Citation]]:
    """Parse the answer and extract simple citations based on source mentions."""
    citations: List[Citation] = []
    # Try to extract source mentions from the response
    for i, chunk in enumerate(chunks):
        source = chunk.get("source", "")
        if source in response_text:
            citations.append(
                Citation(
                    cited_text=chunk["text"][:200],
                    source=source,
                    chunk_index=chunk.get("chunk_index"),
                    start_char=None,
                    end_char=None,
                )
            )
    return response_text, citations


def answer(
    question: str,
    history: Optional[List[dict]] = None,
    top_k: Optional[int] = None,
    sources: Optional[List[str]] = None,
) -> dict:
    """Synchronous RAG answer with grounded citations."""
    chunks = _retrieve(question, top_k, sources)
    settings = get_settings()

    if not chunks:
        return {
            "answer": "I couldn't find anything relevant in the knowledge base to answer that.",
            "citations": [],
            "sources": [],
            "model": settings.groq_model,
            "usage": {},
        }

    context = _build_context(chunks)
    messages = _build_messages(question, history or [], context)
    response = _get_client().chat.completions.create(
        **_request_kwargs(messages)
    )

    answer_text = response.choices[0].message.content
    answer_text, citations = _parse_answer(answer_text, chunks)
    return {
        "answer": answer_text,
        "citations": [c.model_dump() for c in citations],
        "sources": [RetrievedChunk(**chunk).model_dump() for chunk in chunks],
        "model": response.model,
        "usage": _usage_dict(getattr(response, "usage", None)),
    }


async def answer_stream(
    question: str,
    history: Optional[List[dict]] = None,
    top_k: Optional[int] = None,
    sources: Optional[List[str]] = None,
) -> AsyncIterator[Dict]:
    """Stream tokens, then emit a final event with citations + sources.

    Yields dicts shaped as {"type": "...", ...} for SSE serialization.
    """
    chunks = _retrieve(question, top_k, sources)

    # Always tell the client what was retrieved up front.
    yield {
        "type": "sources",
        "sources": [RetrievedChunk(**chunk).model_dump() for chunk in chunks],
    }

    if not chunks:
        yield {
            "type": "text",
            "text": "I couldn't find anything relevant in the knowledge base to answer that.",
        }
        yield {"type": "done", "citations": [], "usage": {}}
        return

    context = _build_context(chunks)
    messages = _build_messages(question, history or [], context)

    stream = _get_client().chat.completions.create(
        **_request_kwargs(messages),
        stream=True
    )

    full_answer = ""
    for chunk in stream:
        if chunk.choices[0].delta.content:
            text = chunk.choices[0].delta.content
            full_answer += text
            yield {"type": "text", "text": text}

    # Get final usage info
    final_usage = getattr(getattr(stream, "response", None), "usage", None)

    _, citations = _parse_answer(full_answer, chunks)
    yield {
        "type": "done",
        "citations": [c.model_dump() for c in citations],
        "usage": _usage_dict(final_usage),
    }
