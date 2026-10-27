import json
import os
import re
import urllib.request
from urllib.parse import urlencode

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
SOLR_URL = os.getenv("SOLR_URL", "http://localhost:8983/solr/devops").rstrip("/")


def _document_chunks(document: str) -> list[tuple[str, str]]:
    chunks = []
    for section in re.split(r"(?=^#{1,3} )", document, flags=re.MULTILINE):
        lines = section.strip().splitlines()
        if not lines:
            continue
        title = next((line.lstrip("# ").strip() for line in lines if line.startswith("#")), "")
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


def index_knowledge() -> None:
    docs = []
    for filename in sorted(os.listdir(KNOWLEDGE_DIR)):
        if not filename.endswith(".md"):
            continue
        path = os.path.join(KNOWLEDGE_DIR, filename)
        with open(path, encoding="utf-8") as handle:
            document = handle.read()
        for title, chunk in _document_chunks(document):
            docs.append({
                "id": f"{filename}:{title or 'section'}:{len(docs)}",
                "source": f"knowledge/{filename}",
                "title": title,
                "content": chunk,
                "topic": os.path.splitext(filename)[0].lower(),
            })

    payload = {"add": {"doc": docs, "commitWithin": 1000}}
    request = urllib.request.Request(
        f"{SOLR_URL}/update?{urlencode({'commit': 'true'})}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        print(response.read().decode("utf-8"), flush=True)


if __name__ == "__main__":
    index_knowledge()
