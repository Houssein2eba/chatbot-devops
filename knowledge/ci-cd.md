# CI/CD overview

Continuous Integration (CI) runs automated checks whenever code changes.
Continuous Delivery or Deployment (CD) packages and releases validated code.

# GitHub Actions basics

GitHub Actions workflows are YAML files stored in:

```text
.github/workflows/
```

A workflow normally checks out code, installs dependencies, runs tests, and
builds the Docker image.

# Python validation

Run the project tests:

```bash
python -m unittest discover -v
```

Check Python syntax:

```bash
python -m compileall .
```

# Docker validation in CI

Build the same image used for deployment:

```bash
docker build -t devops-helpdesk:${GITHUB_SHA} .
```

Start a temporary container for a smoke test:

```bash
docker run -d --name chatbot-ci -p 8000:8000 devops-helpdesk:${GITHUB_SHA}
curl --fail http://localhost:8000/health
docker rm --force chatbot-ci
```

# Release tags

Use immutable version tags for releases:

```bash
docker tag devops-helpdesk:latest registry.example.com/devops-helpdesk:1.0.0
docker push registry.example.com/devops-helpdesk:1.0.0
```

Avoid using `latest` as the only production tag because it does not identify
which exact version is deployed.

# Deployment pipeline

A safe pipeline usually follows this order:

```text
commit -> tests -> image build -> image scan -> registry push -> deployment
```

If tests fail, the pipeline should stop before publishing or deploying the
image.
