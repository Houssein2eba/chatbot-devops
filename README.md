# DocuBot

A chatbot that answers questions using our own documents (for example
the course syllabus and school rules) and shows which document each
answer came from.

Built for the [module name] course to practice a complete DevOps
workflow: Git, Docker, Docker Compose, Kubernetes, Terraform and CI/CD.

## Features
- Ask questions in a web chat
- Answers based only on our documents, with the source shown
- Documents loaded from the `data/` folder by an ingestion script
- Health endpoint at `/health`
- Runs locally with Docker Compose or on a Kubernetes cluster
- Infrastructure created with Terraform
- Automated test, build and push with GitHub Actions

## How It Works

1. The ingestion script splits our documents into small chunks and
   stores them in a vector database.
2. When a user asks a question, the API finds the most relevant chunks.
3. The chunks and the question are sent to an AI model, which writes
   the answer.
4. The answer is shown with its sources.

## Architecture

```
[ Web UI ] --> [ API: Python FastAPI ] --> [ Vector DB: Qdrant ]
                        |
                        +--> [ AI model: [API name or local model] ]
```

DevOps flow:

```
git push -> GitHub Actions (test, build, scan, push image)
         -> Terraform creates the cluster and deploys the app
         -> Kubernetes runs the app and restarts failed pods
```

[Insert architecture diagram image here]

## Tools Used

| Tool | Role in this project |
|---|---|
| Git / GitHub | Version control, branches, pull requests |
| Docker | Packages the API and UI into images |
| Docker Compose | Runs API, UI and database together locally |
| Kubernetes | Runs the services, ConfigMap, Secret, health probes |
| Terraform | Creates the cluster and deploys resources as code |
| GitHub Actions | CI/CD: test, build, [scan], push |

## Project Structure

```
docubot/
├── app/                 API code and Dockerfile
├── ui/                  web chat interface
├── scripts/             ingestion script
├── data/                our documents
├── tests/               unit tests
├── k8s/                 Kubernetes manifests
├── terraform/           main.tf, variables.tf, outputs.tf
├── .github/workflows/   ci.yml
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## Requirements
- Git, Docker Desktop, kubectl, kind, Terraform
- 8 GB RAM recommended
- [API key for the AI model, if used]

## Configuration
Copy `.env.example` to `.env` and fill in your values:
```
[API_KEY_NAME]=your-key-here
```
Never commit the real `.env` file.

## Run Locally with Docker Compose

1. Clone the repository:
   ```
   git clone [your repository link]
   cd docubot
   ```
2. Start everything:
   ```
   docker compose up -d --build
   ```
3. Load the documents:
   ```
   docker compose exec api python scripts/ingest.py
   ```
4. Open http://localhost:[port] and ask a question.
5. Stop:
   ```
   docker compose down
   ```

## Deploy on Kubernetes with Terraform

1. Create a local cluster:
   ```
   kind create cluster --name docubot
   ```
2. Deploy:
   ```
   cd terraform
   terraform init
   terraform plan
   terraform apply
   ```
3. Check the pods:
   ```
   kubectl get pods -n [namespace]
   ```
4. Open the app with the URL from the Terraform output
   (or `kubectl port-forward svc/[service] 8080:80 -n [namespace]`).

## CI/CD Pipeline

`.github/workflows/ci.yml` runs on every push to `main`:
1. Checks out the code
2. Runs the tests
3. [Scans the code or image for vulnerabilities]
4. Builds the Docker image
5. Pushes it to Docker Hub

Required GitHub secrets: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`

[Insert screenshot of a successful run]

## Demo

Scaling:
```
kubectl scale deployment [api-deployment] --replicas=3 -n [namespace]
```

Self-healing:
```
kubectl delete pod [pod-name] -n [namespace]
kubectl get pods -n [namespace] -w
```

[Insert screenshots: chat answering, pods running, pipeline run]

## Cleanup
```
cd terraform && terraform destroy
kind delete cluster --name docubot
```

## Git Workflow
- `main` is the stable branch
- Work happens in `feature/...` branches, merged by pull request
  after review by the other team member
- Commit messages: `feat:`, `fix:`, `docs:`


## Limitations and What We Learned
[Be honest: what doesn't work well, what was hard, what you solved.]

## References
[List only what you really used, for example:]
- Docker, Kubernetes, Terraform and GitHub Actions documentation
- Documentation of the vector database and AI model you chose
- [Any tutorial or repository you took code or ideas from]
