# Production Deployment Guide

This guide covers deploying the Federated Learning Platform to production environments with managed databases and cloud infrastructure.

## Table of Contents
- [Managed PostgreSQL Setup](#managed-postgresql-setup)
- [Environment Configuration](#environment-configuration)
- [Docker Image Deployment](#docker-image-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Monitoring and Logging](#monitoring-and-logging)

## Managed PostgreSQL Setup

### AWS RDS

1. **Create RDS PostgreSQL Instance**:
   ```bash
   aws rds create-db-instance \
     --db-instance-identifier federated-learning-db \
     --db-instance-class db.t3.micro \
     --engine postgres \
     --master-username fl_user \
     --master-user-password <SECURE_PASSWORD> \
     --allocated-storage 20 \
     --publicly-accessible false \
     --vpc-security-group-ids <SECURITY_GROUP_ID>
   ```

2. **Connection Details**:
   - Host: `federated-learning-db.<region>.rds.amazonaws.com`
   - Port: `5432`
   - Database: Create using AWS Console or CLI
   - Username: `fl_user`
   - Password: Use AWS Secrets Manager

3. **Environment Variable**:
   ```bash
   DATABASE_URL=postgresql://fl_user:<PASSWORD>@federated-learning-db.xxxxx.rds.amazonaws.com:5432/fl_db
   ```

### Azure Database for PostgreSQL

1. **Create Azure Database**:
   ```bash
   az postgres server create \
     --resource-group <group> \
     --name federated-learning-db \
     --location <region> \
     --admin-user fl_user \
     --admin-password <SECURE_PASSWORD> \
     --sku-name B_Gen5_2 \
     --storage-size 51200
   ```

2. **Connection Details**:
   - Host: `federated-learning-db.postgres.database.azure.com`
   - Port: `5432`
   - Connection string:
   ```
   postgresql://fl_user@federated-learning-db:<PASSWORD>@federated-learning-db.postgres.database.azure.com:5432/fl_db?sslmode=require
   ```

3. **Note**: Azure requires SSL connections. Set `?sslmode=require` in the connection string.

### Google Cloud SQL

1. **Create Cloud SQL Instance**:
   ```bash
   gcloud sql instances create federated-learning-db \
     --database-version=POSTGRES_15 \
     --tier=db-f1-micro \
     --region=<region>
   ```

2. **Create Database and User**:
   ```bash
   gcloud sql databases create fl_db --instance=federated-learning-db
   gcloud sql users create fl_user --instance=federated-learning-db --password=<PASSWORD>
   ```

3. **Enable Public IP** (if needed):
   ```bash
   gcloud sql instances patch federated-learning-db --assign-ip
   ```

4. **Connection Details**:
   - Public IP: Get from console or CLI
   - Cloud SQL Proxy (recommended for Cloud Run):
   ```bash
   cloud_sql_proxy -instances=<PROJECT>:region:federated-learning-db=tcp:5432 &
   DATABASE_URL=postgresql://fl_user:<PASSWORD>@localhost:5432/fl_db
   ```

## Environment Configuration

### Backend .env File

Create `.env` in the `backend/` directory:

```dotenv
# Database (use managed PostgreSQL connection string)
DATABASE_URL=postgresql://user:password@host:5432/database_name

# Server configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# Python environment
PYTHONUNBUFFERED=1

# Optional: Logging level
LOG_LEVEL=INFO
```

### Docker Environment Variables

When running with Docker Compose or Kubernetes:

```yaml
environment:
  DATABASE_URL: $DATABASE_URL  # Set from secrets/CI
  BACKEND_HOST: 0.0.0.0
  BACKEND_PORT: 8000
```

### Secrets Management

**AWS Secrets Manager**:
```bash
aws secretsmanager create-secret \
  --name federated-learning/database-url \
  --secret-string "postgresql://user:password@host:5432/db"
```

**Kubernetes Secrets**:
```bash
kubectl create secret generic database-credentials \
  --from-literal=DATABASE_URL="postgresql://..." \
  -n federated-learning
```

## Docker Image Deployment

### Building Images for Production

1. **Build Backend Image**:
   ```bash
   cd backend
   docker build -t federated-learning-backend:latest .
   ```

2. **Build Frontend Image**:
   ```bash
   cd frontend
   docker build -t federated-learning-frontend:latest .
   ```

3. **Push to Registry** (e.g., ECR, GCR, Docker Hub):
   ```bash
   # AWS ECR
   aws ecr create-repository --repository-name federated-learning-backend
   docker tag federated-learning-backend:latest <ECR_URI>/federated-learning-backend:latest
   docker push <ECR_URI>/federated-learning-backend:latest
   
   # Google Container Registry
   docker tag federated-learning-backend:latest gcr.io/<PROJECT>/federated-learning-backend:latest
   docker push gcr.io/<PROJECT>/federated-learning-backend:latest
   ```

### Docker Compose Deployment

```bash
DATABASE_URL="postgresql://..." docker compose up -d
```

Verify status:
```bash
docker compose ps
docker compose logs backend  # Check for startup errors
```

## Kubernetes Deployment

### Prerequisites
- Configured Kubernetes cluster
- `kubectl` CLI installed
- Image pushed to registry accessible by cluster



```bash
k3d cluster create my-federated-cluster --api-port 6550 -p "8081:80@loadbalancer" --agents 2
```

```bash
k3d kubeconfig get my-federated-cluster > ~/.kube/config
chmod 600 ~/.kube/config
kubectl config use-context k3d-my-federated-cluster
```

```bash
kubectl get nodes
```

### Deploy Namespace and Secrets

```bash
kubectl apply -f k8s/namespace.yaml

# Create database secret
kubectl create secret generic database-credentials \
  --from-literal=DATABASE_URL="postgresql://fl_user:fl_pass@postgres:5440/fl_db" \
  -n fl-platform
```

### Deploy Backend

Update `k8s/backend-deployment.yaml`:
```yaml
env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: database-credentials
        key: DATABASE_URL
```


```bash
docker build -t user/fl-backend:latest .
k3d image import user/fl-backend:latest -c my-federated-cluster
docker build -t user/fl-frontend:latest .
k3d image import user/fl-frontend:latest -c my-federated-cluster
```

Deploy:
```bash
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service.yaml
```

Verify:
```bash
kubectl get pods -n fl-platform
kubectl logs -n fl-platform -l app=fl-backend --tail=50
```

### Deploy PostgreSQL StatefulSet (Optional)

For in-cluster PostgreSQL:
```bash
kubectl apply -f k8s/postgres-statefulset.yaml
```

### Deploy Frontend

```bash
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/frontend-service.yaml
kubectl apply -f k8s/backend-ingress.yaml
```

### Configure Ingress

Update ingress for your domain:
```yaml
spec:
  rules:
  - host: api.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: backend
            port:
              number: 8000
```

## Monitoring and Logging

### Health Checks

```bash
# Forward local port 8000 to the backend service port 80
kubectl port-forward svc/fl-backend 8000:80 -n fl-platform
kubectl port-forward svc/fl-frontend 3000:80 -n fl-platform
```

Backend health endpoint:
```bash
curl http://localhost:8081/health
```

For database connectivity:
```bash
kubectl exec -it fl-postgres-0 -n fl-platform -- psql -U fl_user -d fl_db
```


Stop cluster:
```bash  

k3d cluster stop my-federated-cluster
k3d cluster delete --all
```

Start cluster:
```bash  
k3d cluster start my-federated-cluster
```


### Logging

View application logs:
```bash
# Docker Compose
docker compose logs -f backend

# Kubernetes
kubectl logs -n federated-learning -f -l app=fl-backend

# Google Cloud Logging
gcloud logging read 'resource.type="cloud_run_revision"' --limit 50
```

### Database Monitoring

**AWS RDS**:
- Monitor CPU, storage, connections via CloudWatch
- Enable Enhanced Monitoring for detailed metrics
- Set up alarms for critical thresholds

**Azure**:
- Monitor via Azure Monitor
- Enable Query Performance Insight
- Set up alerts for CPU, storage, connections

**Google Cloud SQL**:
- Monitor via Cloud Console
- Enable Cloud Logging
- Configure alerting policies

### Application Metrics

The backend logs key metrics each round:
- Aggregated accuracy and loss
- Privacy epsilon (if DP enabled)
- Secure aggregation status
- Client participation

### Performance Tuning

1. **Database Connection Pooling** (SQLAlchemy):
   ```python
   # Adjust pool size for your workload
   pool_size=20
   max_overflow=40
   ```

2. **Memory Configuration** (PyTorch):
   - For large models, set environment variables:
   ```bash
   PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
   ```

3. **Async Processing** (Optional):
   - For long-running rounds, consider using Celery + Redis
   - Document in separate guide if needed

## Rollback Procedure

If deployment encounters issues:

```bash
# Docker Compose
docker compose down
docker compose up -d  # Previous working image

# Kubernetes
kubectl set image deployment/backend backend=<PREVIOUS_IMAGE> -n federated-learning
kubectl rollout status deployment/backend -n federated-learning
```

## Security Checklist

- [ ] Database password `*` stored in Secrets Manager, not in code
- [ ] SSL enabled for PostgreSQL connection (`.postgres.database.azure.com?sslmode=require`)
- [ ] Database backups automated (RDS automated backups, Azure backup, GCloud SQL backups)
- [ ] Network policies restrict access to database (security groups, network policies)
- [ ] Container images scanned for vulnerabilities
- [ ] API endpoints authenticated (add auth layer if needed)
- [ ] HTTPS enforced for frontend (via Ingress/Load Balancer SSL certificates)
- [ ] Rate limiting enabled for API
- [ ] Secrets rotated periodically

---

**Questions?** Contact your DevOps/Infrastructure team or refer to the platform's GitHub Issues.

