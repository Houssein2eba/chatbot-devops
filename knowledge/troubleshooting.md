# Troubleshooting workflow

Start by checking whether the process, container, or Pod is running. Then
inspect logs, health checks, configuration, and network connectivity.

# Docker container status

List running and stopped containers:

```bash
docker ps
docker ps -a
```

Inspect the container configuration:

```bash
docker inspect <container-name>
```

Check whether the image exists locally:

```bash
docker images
```

# Docker logs

Read logs or follow new log lines:

```bash
docker logs <container-name>
docker logs -f <container-name>
docker logs --tail 100 <container-name>
```

# Docker health checks

Show the health state:

```bash
docker inspect --format "{{json .State.Health}}" <container-name>
```

Test the application from the host:

```bash
curl --fail http://localhost:8000/health
```

# Common Docker problems

If port 8000 is already in use, publish a different host port:

```bash
docker run --rm -p 8080:8000 devops-helpdesk
```

If the container exits immediately, inspect its logs:

```bash
docker logs <container-name>
```

If code changes are not visible, rebuild the image:

```bash
docker build --no-cache -t devops-helpdesk .
```

If Docker has no disk space, inspect and clean unused resources:

```bash
docker system df
docker system prune
```

# Kubernetes troubleshooting

Check Pods, events, and detailed resource information:

```bash
kubectl get pods
kubectl get events --sort-by=.lastTimestamp
kubectl describe pod <pod-name>
```

Read application logs:

```bash
kubectl logs <pod-name>
kubectl logs deployment/<deployment-name>
```

Check the rollout:

```bash
kubectl rollout status deployment/<deployment-name>
kubectl rollout history deployment/<deployment-name>
```

Check whether a Service has endpoints:

```bash
kubectl get service <service-name>
kubectl get endpoints <service-name>
```
