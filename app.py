"""Small HTTP service used as the first containerized project component."""

import json
import os
import re
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from typing import Any


HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "8000"))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
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
    (("build", "compose"), ("docker compose build", "docker compose up --build")),
    (("compose", "yaml"), ("docker compose build", "docker compose up --build")),
    (("deploy", "compose"), ("docker compose up --build", "docker compose up -d")),
    (("remove", "unused", "volume"), ("docker volume prune",)),
    (("list", "running", "container"), ("docker ps",)),
    (("view", "container", "logs"), ("docker logs",)),
)


def load_documents() -> dict[str, str]:
    """Load Markdown files from the built-in knowledge base."""
    documents = {}
    try:
        for filename in os.listdir(KNOWLEDGE_DIR):
            if filename.endswith(".md"):
                path = os.path.join(KNOWLEDGE_DIR, filename)
                with open(path, encoding="utf-8") as file:
                    documents[f"knowledge/{filename}"] = file.read()
    except OSError:
        print(f"Knowledge directory not available: {KNOWLEDGE_DIR}", flush=True)
    return documents


def _document_chunks(document: str) -> list[tuple[str, str]]:
    """Create small heading-aware chunks so answers stay focused."""
    chunks = []
    for section in re.split(r"(?=^#{1,3} )", document, flags=re.MULTILINE):
        lines = section.strip().splitlines()
        if not lines:
            continue
        title = next(
            (line.lstrip("# ").strip() for line in lines if line.startswith("#")),
            "",
        )
        body = section.strip()
        blocks = re.split(r"\n\s*\n", body)
        pending = ""
        for block in blocks:
            if block.startswith("```") and pending:
                pending = f"{pending}\n\n{block}"
            else:
                if pending:
                    chunks.append((title, pending.strip()))
                pending = block
        if pending:
            chunks.append((title, pending.strip()))
    return chunks


def _solr_search(question: str, limit: int = 1) -> list[dict[str, Any]]:
    """Query an external Solr collection when configured."""
    if not SOLR_URL:
        return []

    params = {
        "q": question,
        "defType": "edismax",
        "qf": "title^4 content",
        "rows": max(limit, 1),
        "wt": "json",
        "hl": "true",
        "hl.fl": "content",
    }
    url = f"{SOLR_URL}/select?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - defensive for runtime envs
        print(f"Solr query failed for '{question}': {exc}", flush=True)
        return []

    matches = []
    for doc in payload.get("response", {}).get("docs", []):
        text = doc.get("content") or doc.get("text") or ""
        if not text:
            continue
        matches.append({
            "source": doc.get("source", "solr-index"),
            "title": doc.get("title", "Relevant section"),
            "text": text,
            "score": float(doc.get("score", 0.0) or 0.0),
        })
    return matches


def search_documents(question: str, limit: int = 1) -> list[dict[str, Any]]:
    """Retrieve the most relevant small document chunks using Solr when available."""
    solr_matches = _solr_search(question, limit)
    if solr_matches:
        return solr_matches

    keywords = {
        word for word in re.findall(r"[a-z0-9]+", question.lower())
        if word not in STOP_WORDS and len(word) > 2
    }
    if not keywords:
        keywords = {
            word for word in re.findall(r"[a-z0-9]+", question.lower())
            if word in {"docker", "kubernetes", "git"}
        }
    question_words = set(re.findall(r"[a-z0-9]+", question.lower()))
    expected_commands = {
        command
        for phrase, commands in INTENT_PHRASES
        if set(phrase).issubset(question_words)
        for command in commands
    }
    matches = []
    for source, document in load_documents().items():
        for title, chunk in _document_chunks(document):
            chunk_words = re.findall(r"[a-z0-9]+", chunk.lower())
            chunk_word_set = set(chunk_words)
            title_words = set(re.findall(r"[a-z0-9]+", title.lower()))
            overlap = keywords & chunk_word_set
            score = sum(4 if word in title_words else 1 for word in overlap)
            score += sum(12 for command in expected_commands if command in chunk.lower())
            source_topic = os.path.splitext(os.path.basename(source))[0].lower()
            if len(keywords) == 1 and source_topic in keywords:
                score += 3
            if score:
                matches.append({
                    "source": source,
                    "title": title,
                    "text": chunk,
                    "score": score,
                })
    ranked = sorted(
        matches,
        key=lambda match: (match["score"], len(match["text"])),
        reverse=True,
    )
    if expected_commands:
        selected = []
        selected_keys = set()
        for command in expected_commands:
            for match in ranked:
                key = (match["source"], match["text"])
                if command in match["text"].lower() and key not in selected_keys:
                    selected.append(match)
                    selected_keys.add(key)
                    break
        ranked = selected + [
            match for match in ranked
            if (match["source"], match["text"]) not in selected_keys
        ]
        limit = max(limit, len(selected))
    return ranked[:limit]


def _question_parts(question: str) -> list[str]:
    """Split a question containing multiple independent requests."""
    parts = re.split(
        r"\?|;|\s+\band\b\s+(?=(?:how|what|where|which|can|is|to|build|deploy|"
        r"create|clone|run|start|stop|remove|check)\b)",
        question,
        flags=re.IGNORECASE,
    )
    return [part.strip() for part in parts if part.strip()]


def _groq_answer(question: str, matches: list[dict[str, Any]]) -> str | None:
    """Generate a final answer with Groq when configured and the API key is available."""
    if not GROQ_API_KEY:
        return None

    context = "\n\n---\n\n".join(
        f"Source: {match['source']}\nTitle: {match['title']}\n\n{match['text']}"
        for match in matches
    )
    prompt = (
        "Answer the user's question using only the supplied documentation context. "
        "If the answer is not present, say so clearly. Keep the answer concise but useful, "
        "and cite the relevant source file names when you reference the documentation.\n\n"
        f"Question:\n{question}\n\nDocumentation context:\n{context}"
    )

    try:
        from openai import OpenAI
    except ImportError:
        print("Groq integration requires the 'openai' package. Install it with: pip install openai", flush=True)
        return None

    try:
        client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful DevOps documentation assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=500,
        )
    except Exception as exc:  # pragma: no cover - network and credentials can fail at runtime
        print(f"Groq answer generation failed: {exc}", flush=True)
        return None

    answer = response.choices[0].message.content.strip()
    return answer or None


def create_answer(question: str) -> str:
    """Build focused, cited answers for one or more requests."""
    matches = []
    seen = set()
    for part in _question_parts(question):
        for match in search_documents(part):
            key = (match["source"], match["text"])
            if key not in seen:
                matches.append((part, match))
                seen.add(key)
    if not matches:
        return (
            "I could not find an answer in the project documentation. "
            "Try asking about Docker, Kubernetes, CI/CD, health checks, or type help."
        )

    groq_answer = _groq_answer(question, [match for _, match in matches])
    if groq_answer:
        return groq_answer

    answers = []
    for part, match in matches:
        answers.append(f"{match['source']}:\n{match['text']}\n")
    return "\n\n---\n\n".join(answers)


class ChatbotHandler(BaseHTTPRequestHandler):
    """Handle the web UI, health checks, and chat responses."""

    def _send_json(
        self, status_code: int, payload: dict[str, Any], content_type: str = "application/json"
    ) -> None:
        response = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._serve_file("index.html", "text/html; charset=utf-8")
            return
        static_files = {
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/script.js": ("script.js", "text/javascript; charset=utf-8"),
        }
        if path in static_files:
            filename, content_type = static_files[path]
            self._serve_file(filename, content_type)
            return
        if path == "/health":
            self._send_json(200, {"status": "ok"})
            return

        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/chat/stream":
            self._handle_stream()
            return
        if path != "/chat":
            self._send_json(404, {"error": "Not found"})
            return

        payload = self._read_json()
        if payload is None:
            return

        question = payload.get("question") if isinstance(payload, dict) else None
        if not isinstance(question, str) or not question.strip():
            self._send_json(400, {"error": "A non-empty 'question' is required"})
            return

        answer = create_answer(question.strip())
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

    def _handle_stream(self) -> None:
        payload = self._read_json()
        if payload is None:
            return
        question = payload.get("question")
        if not isinstance(question, str) or not question.strip():
            self._send_json(400, {"error": "A non-empty 'question' is required"})
            return

        answer = create_answer(question.strip())
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
            with open(filename, "rb") as file:
                content = file.read()
        except OSError:
            self._send_json(404, {"error": "UI file not found"})
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: Any) -> None:
        """Keep container logs concise and compatible with standard logging tools."""
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
