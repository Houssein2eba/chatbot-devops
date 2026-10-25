# Kubernetes overview

Kubernetes runs containers as Pods and manages desired state. A Deployment
creates and replaces Pods. A Service gives Pods a stable network endpoint.

# kubectl context and cluster

Check the client version and cluster connection:

```bash
kubectl version
kubectl cluster-info
kubectl config current-context
kubectl config get-contexts
kubectl config use-context <context-name>
```

# Kubernetes resources

List common resources in the current namespace:

```bash
kubectl get pods
kubectl get deployments
kubectl get services
kubectl get all
```

List resources in every namespace:

```bash
kubectl get pods --all-namespaces
```

Show a resource in detail:

```bash
kubectl describe pod <pod-name>
kubectl describe deployment <deployment-name>
kubectl describe service <service-name>
```

Show resource YAML:

```bash
kubectl get deployment <deployment-name> -o yaml
```

# Applying manifests

Create or update resources from a YAML file:

```bash
kubectl apply -f deployment.yaml
kubectl apply -f kubernetes/
```

Delete resources described by a file:

```bash
kubectl delete -f deployment.yaml
```

Validate the YAML without applying it:

```bash
kubectl apply --dry-run=client -f deployment.yaml
```

# Deployments and scaling

Create a Deployment from an image:

```bash
kubectl create deployment chatbot --image=devops-helpdesk:latest
```

Scale a Deployment:

```bash
kubectl scale deployment chatbot --replicas=3
```

Change the image used by a Deployment:

```bash
kubectl set image deployment/chatbot chatbot=devops-helpdesk:1.1.0
```

Check rollout status and history:

```bash
kubectl rollout status deployment/chatbot
kubectl rollout history deployment/chatbot
```

Undo the latest rollout:

```bash
kubectl rollout undo deployment/chatbot
```

# Pods and logs

Read logs from a Pod:

```bash
kubectl logs <pod-name>
kubectl logs -f <pod-name>
kubectl logs deployment/chatbot
```

Run a shell or command inside a Pod:

```bash
kubectl exec -it <pod-name> -- sh
kubectl exec <pod-name> -- env
```

Forward a local port to a Service:

```bash
kubectl port-forward service/chatbot 8000:8000
```

# Services

Expose a Deployment as a Service:

```bash
kubectl expose deployment chatbot --port=8000 --target-port=8000
```

List Service endpoints:

```bash
kubectl get service chatbot
kubectl get endpoints chatbot
```

# Namespaces and configuration

List namespaces and create one:

```bash
kubectl get namespaces
kubectl create namespace dev
```

Use a namespace for a command:

```bash
kubectl get pods --namespace dev
kubectl apply -f deployment.yaml --namespace dev
```

List ConfigMaps and Secrets:

```bash
kubectl get configmaps
kubectl get secrets
```

Create a ConfigMap:

```bash
kubectl create configmap chatbot-config --from-literal=PORT=8000
```

Create a Secret. Do not put real credentials in shell history or Git:

```bash
kubectl create secret generic chatbot-secrets --from-literal=API_KEY=<value>
```

# Kubernetes health and troubleshooting

Configure liveness and readiness probes to call `/health`. Inspect events
when a Pod does not start:

```bash
kubectl get events --sort-by=.lastTimestamp
kubectl get pods -o wide
kubectl describe pod <pod-name>
```

Delete a failed Pod so its Deployment can recreate it:

```bash
kubectl delete pod <pod-name>
```
