# Running the Python service with Docker

The containerized DevOps Helpdesk provides:

- `GET /health` for container and future orchestration health checks.
- A browser UI at `/` with question input and streamed responses.
- `POST /chat/stream` for Server-Sent Events (SSE) response streaming.
- `POST /chat` as a JSON API fallback.
- Keyword-based RAG search over the built-in `knowledge/` files.

The knowledge base includes practical references for Docker, Docker Compose,
Kubernetes, CI/CD, troubleshooting, and Git. Ask questions such as:

```text
How do I remove unused Docker volumes?
What is the difference between docker compose up and down?
How do I scale a Kubernetes deployment?
How do I create a Git branch?
How can I inspect container logs?
```

## Run locally without Docker

```bash
python app.py
```

Then open `http://localhost:8000/health`.

Open `http://localhost:8000/` to use the interactive chat UI.

The chatbot does not use an AI model. It extracts meaningful keywords from the
question, searches small Markdown sections in `knowledge/`, and returns only
the best matching section with its source filename.

## Build and run the image

```bash
docker build -t chatbot-devops .
docker run --rm -p 8000:8000 chatbot-devops
```

Verify the running container:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"What is Docker?\"}"
```

Kubernetes manifests will be added in a later project step. The `/health`
endpoint and container `HEALTHCHECK` are ready to be reused by those manifests.

## Run tests

```bash
python -m unittest test_app.py
```
