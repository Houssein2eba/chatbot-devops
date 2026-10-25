"""Small HTTP service used as the first containerized project component."""

import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from typing import Any


HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "8000"))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
STOP_WORDS = {
    "a", "an", "and", "are", "can", "do", "for", "from", "how", "i", "in",
    "is", "it", "me", "of", "on", "please", "the", "to", "what", "with",
    "you", "docker", "command", "commands", "use", "using",
}


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


def search_documents(question: str, limit: int = 1) -> list[dict[str, Any]]:
    """Retrieve the most relevant small document chunks using keyword matching."""
    keywords = {
        word for word in re.findall(r"[a-z0-9]+", question.lower())
        if word not in STOP_WORDS and len(word) > 2
    }
    if not keywords:
        keywords = {
            word for word in re.findall(r"[a-z0-9]+", question.lower())
            if word in {"docker", "kubernetes", "git"}
        }
    matches = []
    for source, document in load_documents().items():
        for title, chunk in _document_chunks(document):
            chunk_words = re.findall(r"[a-z0-9]+", chunk.lower())
            chunk_word_set = set(chunk_words)
            title_words = set(re.findall(r"[a-z0-9]+", title.lower()))
            overlap = keywords & chunk_word_set
            score = sum(4 if word in title_words else 1 for word in overlap)
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
    return sorted(
        matches,
        key=lambda match: (match["score"], len(match["text"])),
        reverse=True,
    )[:limit]


def create_answer(question: str) -> str:
    """Build a cited answer from the highest-scoring document sections."""
    matches = search_documents(question)
    if not matches:
        return (
            "I could not find an answer in the project documentation. "
            "Try asking about Docker, Kubernetes, CI/CD, health checks, or type help."
        )

    match = matches[0]
    return f"{match['text']}\n\nSource: {match['source']}"


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
