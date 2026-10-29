"""HTTP service for the DevOps documentation chatbot."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse


HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "8000"))
BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
SOLR_URL = os.getenv("SOLR_URL", "").rstrip("/")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

STOP_WORDS = {
    "a", "an", "and", "are", "can", "do", "for", "from", "how", "i", "in",
    "is", "it", "me", "of", "on", "please", "the", "to", "what", "with",
    "you", "docker", "command", "commands", "use", "using",
}
INTENT_PHRASES = (
    (("create", "repository"), ("git init",)),
    (("initialize", "repository"), ("git init",)),
    (("clone", "repository"), ("git clone",)),
    (("run", "container", "background"), ("docker run -d",)),
    (("run", "container", "detached"), ("docker run -d",)),
    (("build", "compose"), ("docker compose build", "docker compose up --build")),
    (("compose", "yaml"), ("docker compose build", "docker compose up --build")),
    (("deploy", "compose"), ("docker compose up --build", "docker compose up -d")),
    (("remove", "unused", "volume"), ("docker volume prune",)),
    (("list", "running", "container"), ("docker ps",)),
    (("view", "container", "logs"), ("docker logs",)),
)


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration for the chatbot service."""

    knowledge_dir: Path = KNOWLEDGE_DIR
    solr_url: str = SOLR_URL
    groq_api_key: str = GROQ_API_KEY
    groq_model: str = GROQ_MODEL
    base_dir: Path = BASE_DIR


@dataclass(frozen=True)
class SearchMatch:
    """A documentation result returned by a search provider."""

    source: str
    title: str
    text: str
    score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "title": self.title,
            "text": self.text,
            "score": self.score,
        }


class SearchProvider(Protocol):
    """Interface implemented by documentation search providers."""

    def search(self, question: str, limit: int) -> list[SearchMatch]:
        ...


class DocumentRepository:
    """Loads documentation files from a configured directory."""

    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = knowledge_dir

    def load(self) -> dict[str, str]:
        documents: dict[str, str] = {}
        try:
            for path in self.knowledge_dir.iterdir():
                if path.suffix == ".md":
                    documents[f"knowledge/{path.name}"] = path.read_text(
                        encoding="utf-8"
                    )
        except OSError:
            print(
                f"Knowledge directory not available: {self.knowledge_dir}",
                flush=True,
            )
        return documents


class DocumentChunker:
    """Creates focused, heading-aware chunks from Markdown documents."""

    def chunk(self, document: str) -> list[tuple[str, str]]:
        chunks: list[tuple[str, str]] = []
        sections = re.split(r"(?=^#{1,3} )", document, flags=re.MULTILINE)
        for section in sections:
            lines = section.strip().splitlines()
            if not lines:
                continue
            title = next(
                (line.lstrip("# ").strip() for line in lines if line.startswith("#")),
                "",
            )
            pending = ""
            for block in re.split(r"\n\s*\n", section.strip()):
                if block.startswith("```") and pending:
                    pending = f"{pending}\n\n{block}"
                else:
                    if pending:
                        chunks.append((title, pending.strip()))
                    pending = block
            if pending:
                chunks.append((title, pending.strip()))
        return chunks


class IntentMatcher:
    """Identifies commands that should be prioritized for a question."""

    def expected_commands(self, question: str) -> set[str]:
        words = set(re.findall(r"[a-z0-9]+", question.lower()))
        return {
            command
            for phrase, commands in INTENT_PHRASES
            if set(phrase).issubset(words)
            for command in commands
        }


class SolrSearchProvider:
    """Retrieves documentation from Solr when it is configured."""

    def __init__(self, solr_url: str, intent_matcher: IntentMatcher) -> None:
        self.solr_url = solr_url
        self.intent_matcher = intent_matcher

    def search(self, question: str, limit: int) -> list[SearchMatch]:
        if not self.solr_url:
            return []
        params = {
            "q": question,
            "defType": "edismax",
            "qf": "title^4 content",
            "rows": max(limit, 3),
            "wt": "json",
            "hl": "true",
            "hl.fl": "content",
        }
        url = f"{self.solr_url}/select?{urllib.parse.urlencode(params)}"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError) as exc:  # pragma: no cover - runtime failure
            print(f"Solr query failed for '{question}': {exc}", flush=True)
            return []

        matches = []
        for document in payload.get("response", {}).get("docs", []):
            text = document.get("content") or document.get("text") or ""
            if text:
                matches.append(
                    SearchMatch(
                        source=document.get("source", "solr-index"),
                        title=document.get("title", "Relevant section"),
                        text=text,
                        score=float(document.get("score", 0.0) or 0.0),
                    )
                )
        return self._prioritize_commands(question, matches)[:limit]

    def _prioritize_commands(
        self, question: str, matches: list[SearchMatch]
    ) -> list[SearchMatch]:
        expected = self.intent_matcher.expected_commands(question)
        prioritized = [
            match
            for command in expected
            for match in matches
            if command in match.text.lower()
        ]
        if not prioritized:
            return matches
        selected = {(match.source, match.text) for match in prioritized}
        return prioritized + [
            match for match in matches
            if (match.source, match.text) not in selected
        ]


class LocalSearchProvider:
    """Searches local Markdown chunks using keyword relevance."""

    def __init__(
        self,
        repository: DocumentRepository,
        chunker: DocumentChunker,
        intent_matcher: IntentMatcher,
    ) -> None:
        self.repository = repository
        self.chunker = chunker
        self.intent_matcher = intent_matcher

    def search(self, question: str, limit: int) -> list[SearchMatch]:
        keywords = {
            word for word in re.findall(r"[a-z0-9]+", question.lower())
            if word not in STOP_WORDS and len(word) > 2
        }
        if not keywords:
            keywords = {
                word for word in re.findall(r"[a-z0-9]+", question.lower())
                if word in {"docker", "kubernetes", "git"}
            }
        expected_commands = self.intent_matcher.expected_commands(question)
        matches: list[SearchMatch] = []
        for source, document in self.repository.load().items():
            for title, chunk in self.chunker.chunk(document):
                score = self._score(
                    source, title, chunk, keywords, expected_commands
                )
                if score:
                    matches.append(SearchMatch(source, title, chunk, score))

        ranked = sorted(
            matches,
            key=lambda match: (match.score, len(match.text)),
            reverse=True,
        )
        return self._prioritize_commands(ranked, expected_commands, limit)

    @staticmethod
    def _score(
        source: str,
        title: str,
        chunk: str,
        keywords: set[str],
        expected_commands: set[str],
    ) -> int:
        chunk_words = set(re.findall(r"[a-z0-9]+", chunk.lower()))
        title_words = set(re.findall(r"[a-z0-9]+", title.lower()))
        overlap = keywords & chunk_words
        score = sum(4 if word in title_words else 1 for word in overlap)
        score += sum(12 for command in expected_commands if command in chunk.lower())
        source_topic = Path(source).stem.lower()
        if len(keywords) == 1 and source_topic in keywords:
            score += 3
        return score

    @staticmethod
    def _prioritize_commands(
        ranked: list[SearchMatch],
        expected_commands: set[str],
        limit: int,
    ) -> list[SearchMatch]:
        selected: list[SearchMatch] = []
        selected_keys: set[tuple[str, str]] = set()
        for command in expected_commands:
            for match in ranked:
                key = (match.source, match.text)
                if command in match.text.lower() and key not in selected_keys:
                    selected.append(match)
                    selected_keys.add(key)
                    break
        remaining = [
            match for match in ranked
            if (match.source, match.text) not in selected_keys
        ]
        return (selected + remaining)[:max(limit, len(selected))]


class DocumentSearchService:
    """Coordinates remote and local documentation search."""

    def __init__(
        self, providers: list[SearchProvider]
    ) -> None:
        self.providers = providers

    def search(self, question: str, limit: int = 1) -> list[SearchMatch]:
        for provider in self.providers:
            matches = provider.search(question, limit)
            if matches:
                return matches
        return []


class AnswerGenerator:
    """Generates an answer using Groq or the retrieved documentation."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def generate(self, question: str, matches: list[SearchMatch]) -> str | None:
        if not self.config.groq_api_key:
            return None
        context = "\n\n".join(
            f"[{match.source}]\n{match.text}" for match in matches
        )
        prompt = (
            "Answer the user's question using only the supplied documentation context. "
            "If the answer is not present, say so clearly. Keep the answer concise but "
            "useful, and cite the relevant source file names when you reference the "
            "documentation.\n\n"
            f"Question:\n{question}\n\nDocumentation context:\n{context}"
        )
        try:
            from openai import OpenAI
        except ImportError:
            print(
                "Groq integration requires the 'openai' package. "
                "Install it with: pip install openai",
                flush=True,
            )
            return None
        try:
            client = OpenAI(
                api_key=self.config.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
            )
            response = client.chat.completions.create(
                model=self.config.groq_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful DevOps documentation assistant.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=500,
            )
        except Exception as exc:  # pragma: no cover - network and credentials
            print(f"Groq answer generation failed: {exc}", flush=True)
            return None
        answer = response.choices[0].message.content
        return answer.strip() if answer else None


class ChatbotService:
    """Application service for question splitting, search, and answer creation."""

    def __init__(
        self,
        search_service: DocumentSearchService,
        answer_generator: AnswerGenerator,
    ) -> None:
        self.search_service = search_service
        self.answer_generator = answer_generator

    def create_answer(self, question: str) -> str:
        matches: list[tuple[str, SearchMatch]] = []
        seen: set[tuple[str, str]] = set()
        for part in self._question_parts(question):
            for match in self.search_service.search(part):
                key = (match.source, match.text)
                if key not in seen:
                    matches.append((part, match))
                    seen.add(key)
        if not matches:
            return (
                "I could not find an answer in the project documentation. "
                "Try asking about Docker, Kubernetes, CI/CD, health checks, or type help."
            )
        generated = self.answer_generator.generate(
            question, [match for _, match in matches]
        )
        if generated:
            return generated
        return "\n\n---\n\n".join(
            f"{match.source}:\n{match.text}\n" for _, match in matches
        )

    @staticmethod
    def _question_parts(question: str) -> list[str]:
        parts = re.split(
            r"\?|;|\s+\band\b\s+(?=(?:how|what|where|which|can|is|to|build|deploy|"
            r"create|clone|run|start|stop|remove|check)\b)",
            question,
            flags=re.IGNORECASE,
        )
        return [part.strip() for part in parts if part.strip()]


def _create_chatbot_service() -> ChatbotService:
    config = AppConfig()
    matcher = IntentMatcher()
    repository = DocumentRepository(config.knowledge_dir)
    providers: list[SearchProvider] = [
        SolrSearchProvider(config.solr_url, matcher),
        LocalSearchProvider(repository, DocumentChunker(), matcher),
    ]
    return ChatbotService(
        DocumentSearchService(providers),
        AnswerGenerator(config),
    )


_CHATBOT_SERVICE = _create_chatbot_service()


def load_documents() -> dict[str, str]:
    """Backward-compatible access to the configured documentation repository."""
    return DocumentRepository(KNOWLEDGE_DIR).load()


def _document_chunks(document: str) -> list[tuple[str, str]]:
    """Backward-compatible access to Markdown chunking."""
    return DocumentChunker().chunk(document)


def _expected_commands(question: str) -> set[str]:
    """Backward-compatible access to intent matching."""
    return IntentMatcher().expected_commands(question)


def search_documents(question: str, limit: int = 1) -> list[dict[str, Any]]:
    """Retrieve relevant documentation chunks."""
    return [
        match.as_dict()
        for match in _CHATBOT_SERVICE.search_service.search(question, limit)
    ]


def create_answer(question: str) -> str:
    """Build a focused, cited answer for one or more requests."""
    return _CHATBOT_SERVICE.create_answer(question)


class ChatbotHandler(BaseHTTPRequestHandler):
    """HTTP adapter for the chatbot application service."""

    service = _CHATBOT_SERVICE

    def _send_json(
        self,
        status_code: int,
        payload: dict[str, Any],
        content_type: str = "application/json",
    ) -> None:
        response = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        static_files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/script.js": ("script.js", "text/javascript; charset=utf-8"),
        }
        if path in static_files:
            self._serve_file(*static_files[path])
        elif path == "/health":
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in {"/chat", "/chat/stream"}:
            self._send_json(404, {"error": "Not found"})
            return
        payload = self._read_json()
        if payload is None:
            return
        question = payload.get("question")
        if not isinstance(question, str) or not question.strip():
            self._send_json(400, {"error": "A non-empty 'question' is required"})
            return
        answer = self.service.create_answer(question.strip())
        if path == "/chat/stream":
            self._stream_answer(answer)
        else:
            self._send_json(200, {"answer": answer})

    def _read_json(self) -> dict[str, Any] | None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length))
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "Request body must be valid JSON"})
            return None
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "JSON body must be an object"})
            return None
        return payload

    def _stream_answer(self, answer: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        for chunk in re.findall(r"\s+|\S+", answer):
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
            self.wfile.flush()
            time.sleep(0.03)
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        self.close_connection = True

    def _serve_file(self, filename: str, content_type: str) -> None:
        try:
            content = (BASE_DIR / filename).read_bytes()
        except OSError:
            self._send_json(404, {"error": "UI file not found"})
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}", flush=True)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), ChatbotHandler)
    print(f"Chatbot service listening on {HOST}:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
