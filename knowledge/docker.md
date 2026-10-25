# Docker overview

Docker packages an application and its dependencies into an image. A
container is a running instance of an image.

# Docker version and help

Check the installed Docker client and server:

```bash
docker version
docker info
```

Show all available commands or help for one command:

```bash
docker help
docker <command> --help
```

# Docker images

List local images:

```bash
docker images
docker image ls
```

Build an image from the Dockerfile in the current directory:

```bash
docker build -t <container-name> .
```

Build with a specific version tag:

```bash
docker build -t <container-name>:1.0.0 .
```

Build without using the cache:

```bash
docker build --no-cache -t <container-name> .
```

Tag an existing image:

```bash
docker tag <container-name>:latest username/<container-name>:latest
```

Remove one image or unused images:

```bash
docker image rm <container-name>:latest
docker image prune
docker image prune -a
```

Inspect image metadata and view its layer history:

```bash
docker image inspect <container-name>
docker history <container-name>
```

# Docker Hub and registries

Sign in to a container registry:

```bash
docker login
```

Pull an image from a registry:

```bash
docker pull python:3.12-slim
```

Push a tagged image:

```bash
docker push username/<container-name>:latest
```

Log out:

```bash
docker logout
```

# Running containers

Start a container in the foreground:

```bash
docker run --rm -p 8000:8000 <container-name>
```

Start it in the background with a name:

```bash
docker run -d --name <container-name> -p 8000:8000 <container-name>
```

Publish a host port to a container port:

```bash
docker run -p 8080:8000 <container-name>
```

Set an environment variable:

```bash
docker run -e PORT=8000 <container-name>
```

Load environment variables from a file:

```bash
docker run --env-file .env <container-name>
```

Give a container a CPU or memory limit:

```bash
docker run --memory=512m --cpus=1 <container-name>
```

Automatically restart a container after a failure:

```bash
docker run --restart unless-stopped -d --name <container-name> -p 8000:8000 <container-name>
```

# Container status and lifecycle

List running containers or all containers:

```bash
docker ps
docker ps -a
```

Show container details:

```bash
docker inspect <container-name>
```

Start, stop, restart, pause, or unpause a container:

```bash
docker start <container-name>
docker stop <container-name>
docker restart <container-name>
docker pause <container-name>
docker unpause <container-name>
```

Rename a container:

```bash
docker rename old-name new-name
```

Remove a stopped container:

```bash
docker rm <container-name>
```

Stop and remove a running container:

```bash
docker rm --force <container-name>
```

Remove stopped containers that are no longer needed:

```bash
docker container prune
```

# Logs and debugging

Show container logs:

```bash
docker logs <container-name>
```

Follow logs in real time or show only recent lines:

```bash
docker logs -f <container-name>
docker logs --tail 100 <container-name>
docker logs --since 10m <container-name>
```

Show live CPU, memory, and network usage:

```bash
docker stats
docker stats <container-name>
```

Run a command inside a running container:

```bash
docker exec <container-name> ls
docker exec -it <container-name> sh
```

Copy files between the host and a container:

```bash
docker cp <container-name>:/app/app.py .
docker cp ./config.json <container-name>:/app/config.json
```

# Volumes and persistent data

List, inspect, create, and remove named volumes:

```bash
docker volume ls
docker volume inspect project-data
docker volume create project-data
docker volume rm project-data
```

Mount a named volume into a container:

```bash
docker run --mount source=project-data,target=/app/data <container-name>
```

Remove unused volumes:

```bash
docker volume prune
```

# Networks

List, inspect, create, and remove Docker networks:

```bash
docker network ls
docker network inspect bridge
docker network create devops-network
docker network rm devops-network
```

Connect a container to a network:

```bash
docker run --network devops-network --name chatbot <container-name>
docker network connect devops-network chatbot
docker network disconnect devops-network chatbot
```

Containers on the same user-defined network can reach each other by
container name.

# Docker Compose

Docker Compose starts multiple related services from `compose.yaml` or
`docker-compose.yml`.

Build services and start them in the foreground:

```bash
docker compose up --build
```

Start services in the background:

```bash
docker compose up -d
```

Stop and remove Compose containers and networks:

```bash
docker compose down
```

Stop and remove containers, networks, and named volumes:

```bash
docker compose down --volumes
```

List Compose services and their status:

```bash
docker compose ps
```

Show Compose logs, or follow one service:

```bash
docker compose logs
docker compose logs -f chatbot
```

Build or rebuild services:

```bash
docker compose build
docker compose build --no-cache
```

Pull images defined by the Compose file:

```bash
docker compose pull
```

Run one command or one service:

```bash
docker compose run --rm chatbot python -m unittest
docker compose up chatbot
```

Restart services:

```bash
docker compose restart
```

Validate the Compose configuration:

```bash
docker compose config
```

# Docker cleanup

Remove stopped containers, unused networks, dangling images, and build cache:

```bash
docker system prune
```

Also remove unused images and volumes. Use this carefully:

```bash
docker system prune -a --volumes
```

Inspect disk usage before cleanup:

```bash
docker system df
```
