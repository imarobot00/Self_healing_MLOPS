# ☁️ Self-Healing MLOps: Cloud Deployment Learning Path

**Date**: January 6, 2026  
**Goal**: Learn Docker, Kubernetes, and Cloud by deploying your self-healing ML system  
**Duration**: 6-8 weeks  
**Cloud Platform**: Azure (can adapt to AWS/GCP)

---

## 🎯 Learning Philosophy

**"Learn by Building, Not by Watching"**

Instead of taking courses first, you'll:
1. ✅ Build a feature locally (e.g., drift detection)
2. ✅ Containerize it with Docker (learn Docker concepts)
3. ✅ Deploy to Kubernetes (learn K8s concepts)
4. ✅ Move to cloud (learn cloud services)
5. 🔁 Repeat for next feature

By the end, you'll have:
- ✅ A production-ready self-healing ML system
- ✅ Hands-on Docker experience
- ✅ Real Kubernetes deployment skills
- ✅ Cloud platform expertise
- ✅ A portfolio project to show employers

---

## 📚 Week-by-Week Breakdown

### **Week 1: Docker Basics + Drift Detection**
**What You'll Learn**:
- Dockerfile syntax
- Docker images & containers
- Docker volumes
- Multi-stage builds
- Docker networking

**What You'll Build**:
1. Drift detection module (Python)
2. Containerize it with Docker
3. Run drift detector in a container

**Learning Resources** (spend 3-4 hours):
- [Docker Official Tutorial](https://docs.docker.com/get-started/) - Parts 1-3
- [Docker for Beginners](https://docker-curriculum.com/) - First 4 sections
- YouTube: "Docker in 2 Hours" by TechWorld with Nana

**Implementation Tasks**:

#### Day 1-2: Learn Docker Basics
```bash
# Install Docker
sudo apt-get update
sudo apt-get install docker.io docker-compose
sudo usermod -aG docker $USER  # Add yourself to docker group
# Logout and login again

# Test Docker
docker --version
docker run hello-world

# Try basic commands
docker images
docker ps
docker ps -a
docker logs <container-id>
docker exec -it <container-id> bash
```

**Practice Exercises**:
```bash
# Exercise 1: Run Python in container
docker run -it python:3.11 python -c "print('Hello from Docker!')"

# Exercise 2: Run with volume
echo "print('Hello from file!')" > test.py
docker run -v $(pwd):/app python:3.11 python /app/test.py

# Exercise 3: Interactive mode
docker run -it -v $(pwd):/app python:3.11 bash
```

#### Day 3-5: Build Drift Detector + Containerize

**Step 1**: Create the drift detector
```bash
mkdir -p monitoring
```

Create `monitoring/drift_detector.py`:
```python
import json
import pandas as pd
import numpy as np
from scipy.stats import ks_2samp
from datetime import datetime
from pathlib import Path
from typing import Dict, List

class DriftDetector:
    """Detects distribution drift between training and production data"""
    
    def __init__(self, baseline_path: str = "monitoring/baseline_stats.json"):
        self.baseline_path = Path(baseline_path)
        self.baseline_stats = self._load_baseline()
        print(f"✅ Baseline loaded: {len(self.baseline_stats)} features")
    
    def _load_baseline(self) -> Dict:
        """Load baseline statistics from training data"""
        if not self.baseline_path.exists():
            print("⚠️  Baseline not found. Generate with: python monitoring/generate_baseline.py")
            return {}
        
        with open(self.baseline_path, 'r') as f:
            return json.load(f)
    
    def calculate_drift_score(self, recent_data: pd.DataFrame) -> Dict:
        """
        Calculate drift score using Kolmogorov-Smirnov test
        
        Args:
            recent_data: DataFrame with recent predictions
        
        Returns:
            {
                'timestamp': str,
                'overall_drift_score': float,
                'features': {
                    'pm25': {'ks_stat': float, 'p_value': float, 'drift': bool},
                    ...
                },
                'recommendation': str
            }
        """
        if not self.baseline_stats:
            return {'error': 'No baseline statistics available'}
        
        features_to_check = ['pm25', 'pm1', 'temperature', 'relativehumidity']
        feature_results = {}
        drift_scores = []
        
        for feature in features_to_check:
            if feature not in recent_data.columns:
                continue
            
            # Get recent data for this feature
            recent_values = recent_data[feature].dropna().values
            
            if len(recent_values) < 30:
                continue
            
            # Simulate baseline distribution from stats
            baseline = self.baseline_stats.get(feature, {})
            if not baseline:
                continue
            
            # Generate synthetic baseline from saved statistics
            baseline_mean = baseline['mean']
            baseline_std = baseline['std']
            baseline_values = np.random.normal(
                baseline_mean, 
                baseline_std, 
                size=len(recent_values)
            )
            
            # Kolmogorov-Smirnov test
            ks_stat, p_value = ks_2samp(recent_values, baseline_values)
            
            # Drift detected if KS stat > 0.3 or p_value < 0.05
            is_drifted = ks_stat > 0.3 or p_value < 0.05
            
            feature_results[feature] = {
                'ks_statistic': float(ks_stat),
                'p_value': float(p_value),
                'drifted': is_drifted,
                'severity': 'high' if ks_stat > 0.5 else 'medium' if ks_stat > 0.3 else 'low'
            }
            
            drift_scores.append(ks_stat)
        
        # Calculate overall drift score
        overall_score = np.mean(drift_scores) if drift_scores else 0.0
        
        # Determine recommendation
        if overall_score > 0.5:
            recommendation = "CRITICAL: Immediate retraining required"
        elif overall_score > 0.3:
            recommendation = "WARNING: Monitor closely, consider retraining"
        else:
            recommendation = "OK: No significant drift detected"
        
        return {
            'timestamp': datetime.now().isoformat(),
            'overall_drift_score': float(overall_score),
            'features': feature_results,
            'recommendation': recommendation,
            'num_samples_analyzed': len(recent_data)
        }
    
    def load_recent_predictions(self, days: int = 1) -> pd.DataFrame:
        """Load recent predictions from API logs"""
        predictions_dir = Path("api/logs/predictions")
        
        if not predictions_dir.exists():
            print("⚠️  No predictions directory found")
            return pd.DataFrame()
        
        # Find recent prediction files
        all_files = sorted(predictions_dir.glob("predictions_*.jsonl"))
        
        if not all_files:
            print("⚠️  No prediction files found")
            return pd.DataFrame()
        
        # Read last N files
        recent_files = all_files[-days:]
        
        all_predictions = []
        for file in recent_files:
            with open(file, 'r') as f:
                for line in f:
                    try:
                        pred = json.loads(line)
                        if 'features' in pred:
                            all_predictions.append(pred['features'])
                    except json.JSONDecodeError:
                        continue
        
        if not all_predictions:
            print("⚠️  No valid predictions found")
            return pd.DataFrame()
        
        df = pd.DataFrame(all_predictions)
        print(f"✅ Loaded {len(df)} predictions from {len(recent_files)} files")
        return df
    
    def run_drift_check(self) -> Dict:
        """
        Main method: Load recent data and check for drift
        """
        print("\n" + "="*60)
        print("🔍 DRIFT DETECTION ANALYSIS")
        print("="*60)
        
        # Load recent predictions
        recent_data = self.load_recent_predictions(days=1)
        
        if recent_data.empty:
            return {
                'error': 'No recent data available',
                'recommendation': 'Make some predictions first'
            }
        
        # Calculate drift
        drift_report = self.calculate_drift_score(recent_data)
        
        # Print results
        print(f"\n📊 Analysis Summary:")
        print(f"   Samples Analyzed: {drift_report['num_samples_analyzed']}")
        print(f"   Overall Drift Score: {drift_report['overall_drift_score']:.3f}")
        print(f"   Recommendation: {drift_report['recommendation']}")
        
        print(f"\n📈 Feature-Level Results:")
        for feature, result in drift_report['features'].items():
            emoji = "🔴" if result['drifted'] else "🟢"
            print(f"   {emoji} {feature:20s} KS={result['ks_statistic']:.3f}  p={result['p_value']:.4f}  [{result['severity']}]")
        
        print("\n" + "="*60)
        
        return drift_report


if __name__ == "__main__":
    # Run drift detection
    detector = DriftDetector()
    report = detector.run_drift_check()
    
    # Save report
    output_dir = Path("monitoring/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"drift_report_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n💾 Report saved to: {output_file}")
```

Create `monitoring/generate_baseline.py`:
```python
import pandas as pd
import json
from pathlib import Path

def generate_baseline():
    """Generate baseline statistics from training data"""
    
    # Load training data
    train_data_path = Path("dataset/preprocessed/train_data.csv")
    
    if not train_data_path.exists():
        print("❌ Training data not found!")
        return
    
    print("📊 Loading training data...")
    df = pd.read_csv(train_data_path)
    
    # Calculate statistics for key features
    features = ['pm25', 'pm1', 'temperature', 'relativehumidity']
    baseline = {}
    
    for col in features:
        if col not in df.columns:
            continue
        
        baseline[col] = {
            'mean': float(df[col].mean()),
            'std': float(df[col].std()),
            'min': float(df[col].min()),
            'max': float(df[col].max()),
            'q25': float(df[col].quantile(0.25)),
            'q50': float(df[col].quantile(0.50)),
            'q75': float(df[col].quantile(0.75)),
            'count': int(df[col].count())
        }
        
        print(f"✅ {col}: mean={baseline[col]['mean']:.2f}, std={baseline[col]['std']:.2f}")
    
    # Save baseline
    output_path = Path("monitoring/baseline_stats.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(baseline, f, indent=2)
    
    print(f"\n💾 Baseline saved to: {output_path}")
    print(f"📊 Features tracked: {len(baseline)}")

if __name__ == "__main__":
    generate_baseline()
```

**Step 2**: Test locally
```bash
# Generate baseline
python monitoring/generate_baseline.py

# Run drift detection (make sure API has made some predictions)
python monitoring/drift_detector.py
```

**Step 3**: Create Dockerfile for drift detector

Create `Dockerfile.drift`:
```dockerfile
# Use official Python runtime
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY monitoring/ ./monitoring/
COPY api/logs/ ./api/logs/
COPY dataset/preprocessed/ ./dataset/preprocessed/

# Set environment
ENV PYTHONUNBUFFERED=1

# Run drift detection
CMD ["python", "monitoring/drift_detector.py"]
```

Create `requirements.txt` (drift detector specific):
```txt
scipy==1.11.4
pandas==2.1.4
numpy==1.26.2
```

**Step 4**: Build and run Docker container
```bash
# Build image
docker build -f Dockerfile.drift -t drift-detector:v1 .

# Run container
docker run --rm \
  -v $(pwd)/monitoring:/app/monitoring \
  -v $(pwd)/api/logs:/app/api/logs \
  drift-detector:v1

# Check container logs
docker ps -a
docker logs <container-id>
```

**🎓 Learning Checkpoint**:
- [ ] Understand what Docker images are
- [ ] Know how to build an image from Dockerfile
- [ ] Understand volumes (mounting host directories)
- [ ] Can run containers and view logs
- [ ] Understand the difference between images and containers

---

### **Week 2: Docker Compose + Auto-Retraining**
**What You'll Learn**:
- Docker Compose syntax
- Multi-container orchestration
- Service dependencies
- Environment variables
- Docker networks

**Learning Resources** (2-3 hours):
- [Docker Compose Tutorial](https://docs.docker.com/compose/gettingstarted/)
- YouTube: "Docker Compose in 12 Minutes"

**What You'll Build**:
1. Auto-retraining module
2. Docker Compose setup for all services
3. Inter-container communication

**Implementation**:

Create `retraining/auto_trainer.py` (~400 lines - I'll provide full code)

Create `docker-compose.full.yml`:
```yaml
version: '3.8'

services:
  # Data Pipeline (existing)
  data-pipeline:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: openaq-pipeline
    volumes:
      - ./dataset:/app/data
      - ./logs:/app/logs
    networks:
      - mlops-network
    restart: unless-stopped

  # Prediction API
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    container_name: aqi-api
    ports:
      - "8000:8000"
    volumes:
      - ./api:/app/api
      - ./training/models:/app/models
      - ./api/logs:/app/logs
    networks:
      - mlops-network
    depends_on:
      - data-pipeline
    environment:
      - MODEL_PATH=/app/models
      - LOG_LEVEL=INFO
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Drift Detector (runs every 6 hours)
  drift-detector:
    build:
      context: .
      dockerfile: Dockerfile.drift
    container_name: drift-detector
    volumes:
      - ./monitoring:/app/monitoring
      - ./api/logs:/app/api/logs
      - ./dataset/preprocessed:/app/dataset/preprocessed
    networks:
      - mlops-network
    depends_on:
      - api
    environment:
      - CHECK_INTERVAL_HOURS=6
      - DRIFT_THRESHOLD=0.5

  # Auto-Retraining Service
  auto-retrainer:
    build:
      context: .
      dockerfile: Dockerfile.retrainer
    container_name: auto-retrainer
    volumes:
      - ./training:/app/training
      - ./dataset:/app/dataset
      - ./monitoring:/app/monitoring
    networks:
      - mlops-network
    depends_on:
      - drift-detector
      - api
    environment:
      - RETRAINING_ENABLED=true
      - MIN_IMPROVEMENT_PCT=5

  # PostgreSQL for metrics storage
  postgres:
    image: postgres:15
    container_name: mlops-postgres
    environment:
      POSTGRES_DB: mlops_metrics
      POSTGRES_USER: mlops_user
      POSTGRES_PASSWORD: mlops_pass
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - mlops-network
    ports:
      - "5432:5432"

  # Redis for caching
  redis:
    image: redis:7-alpine
    container_name: mlops-redis
    networks:
      - mlops-network
    ports:
      - "6379:6379"

networks:
  mlops-network:
    driver: bridge

volumes:
  postgres-data:
```

**Test it**:
```bash
# Start all services
docker-compose -f docker-compose.full.yml up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api
docker-compose logs -f drift-detector

# Stop everything
docker-compose down
```

**🎓 Learning Checkpoint**:
- [ ] Understand service definitions in docker-compose.yml
- [ ] Know how to define service dependencies
- [ ] Understand Docker networks and how containers communicate
- [ ] Can manage multi-container applications
- [ ] Understand volumes vs bind mounts

---

### **Week 3: Kubernetes Basics + Local Cluster**
**What You'll Learn**:
- Kubernetes architecture (pods, nodes, control plane)
- kubectl commands
- Deployments, Services, ConfigMaps
- Local Kubernetes (minikube or kind)

**Learning Resources** (4-5 hours):
- [Kubernetes Official Tutorial](https://kubernetes.io/docs/tutorials/kubernetes-basics/)
- YouTube: "Kubernetes Course for Beginners" by freeCodeCamp (first 2 hours)
- [Kubernetes Crash Course](https://www.youtube.com/watch?v=X48VuDVv0do)

**What You'll Build**:
1. Local Kubernetes cluster
2. Deploy your containers to K8s
3. Expose API via K8s Service

**Implementation**:

#### Day 1-2: Setup Local Kubernetes
```bash
# Option 1: Install minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# Start cluster
minikube start --cpus 4 --memory 8192

# Verify
kubectl get nodes
kubectl cluster-info

# Option 2: Install kind (Kubernetes in Docker)
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

# Create cluster
kind create cluster --name mlops-cluster

# Verify
kubectl get nodes
```

#### Day 3-5: Deploy to Kubernetes

Create `kubernetes/` directory structure:
```bash
mkdir -p kubernetes/{deployments,services,configmaps,jobs}
```

Create `kubernetes/namespace.yaml`:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: mlops
  labels:
    name: mlops
```

Create `kubernetes/deployments/api-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-deployment
  namespace: mlops
  labels:
    app: aqi-api
spec:
  replicas: 3  # 3 instances for high availability
  selector:
    matchLabels:
      app: aqi-api
  template:
    metadata:
      labels:
        app: aqi-api
    spec:
      containers:
      - name: api
        image: aqi-api:v1  # Your Docker image
        ports:
        - containerPort: 8000
        env:
        - name: MODEL_PATH
          value: "/app/models"
        - name: LOG_LEVEL
          value: "INFO"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: model-storage
          mountPath: /app/models
        - name: logs-storage
          mountPath: /app/logs
      volumes:
      - name: model-storage
        hostPath:
          path: /data/models
          type: DirectoryOrCreate
      - name: logs-storage
        hostPath:
          path: /data/logs
          type: DirectoryOrCreate
```

Create `kubernetes/services/api-service.yaml`:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-service
  namespace: mlops
spec:
  type: LoadBalancer  # Change to NodePort for minikube
  selector:
    app: aqi-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
    nodePort: 30080  # For NodePort type
```

Create `kubernetes/jobs/retrain-cronjob.yaml`:
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: model-retraining
  namespace: mlops
spec:
  schedule: "0 */6 * * *"  # Every 6 hours
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: retrainer
            image: auto-retrainer:v1
            env:
            - name: RETRAINING_ENABLED
              value: "true"
            volumeMounts:
            - name: training-data
              mountPath: /app/training
          restartPolicy: OnFailure
          volumes:
          - name: training-data
            hostPath:
              path: /data/training
```

**Deploy to Kubernetes**:
```bash
# Build and load images to minikube
docker build -f Dockerfile.api -t aqi-api:v1 .
minikube image load aqi-api:v1

docker build -f Dockerfile.retrainer -t auto-retrainer:v1 .
minikube image load auto-retrainer:v1

# Apply configurations
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -f kubernetes/deployments/
kubectl apply -f kubernetes/services/
kubectl apply -f kubernetes/jobs/

# Check status
kubectl get all -n mlops

# Get API URL (for minikube)
minikube service api-service -n mlops --url

# View logs
kubectl logs -f deployment/api-deployment -n mlops

# Execute into pod
kubectl exec -it <pod-name> -n mlops -- /bin/bash
```

**🎓 Learning Checkpoint**:
- [ ] Understand Kubernetes architecture
- [ ] Know the difference between Pods, Deployments, Services
- [ ] Can write basic K8s YAML manifests
- [ ] Understand kubectl commands
- [ ] Know how to debug pods (logs, exec)
- [ ] Understand health checks (liveness/readiness probes)

---

### **Week 4: Cloud Setup (Azure AKS)**
**What You'll Learn**:
- Azure fundamentals
- Azure Container Registry (ACR)
- Azure Kubernetes Service (AKS)
- Azure CLI

**Learning Resources** (3-4 hours):
- [Azure Free Account](https://azure.microsoft.com/free/) - $200 free credit
- [Azure CLI Quickstart](https://learn.microsoft.com/en-us/cli/azure/get-started-with-azure-cli)
- [AKS Tutorial](https://learn.microsoft.com/en-us/azure/aks/tutorial-kubernetes-prepare-app)

**What You'll Build**:
1. Azure account and resource group
2. Azure Container Registry
3. AKS cluster
4. Deploy your system to cloud

**Implementation**:

#### Day 1: Setup Azure Account
```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login
az login

# Set subscription (if multiple)
az account list --output table
az account set --subscription "<your-subscription-id>"

# Create resource group
az group create \
  --name mlops-rg \
  --location eastus

# Verify
az group list --output table
```

#### Day 2: Setup Container Registry
```bash
# Create Azure Container Registry
az acr create \
  --resource-group mlops-rg \
  --name mlopsacr123 \
  --sku Basic

# Login to ACR
az acr login --name mlopsacr123

# Tag and push images
docker tag aqi-api:v1 mlopsacr123.azurecr.io/aqi-api:v1
docker push mlopsacr123.azurecr.io/aqi-api:v1

docker tag auto-retrainer:v1 mlopsacr123.azurecr.io/auto-retrainer:v1
docker push mlopsacr123.azurecr.io/auto-retrainer:v1

# Verify images
az acr repository list --name mlopsacr123 --output table
```

#### Day 3-5: Create AKS Cluster and Deploy
```bash
# Create AKS cluster (this takes 10-15 minutes)
az aks create \
  --resource-group mlops-rg \
  --name mlops-cluster \
  --node-count 3 \
  --node-vm-size Standard_B2s \
  --enable-addons monitoring \
  --generate-ssh-keys

# Get credentials
az aks get-credentials \
  --resource-group mlops-rg \
  --name mlops-cluster

# Verify connection
kubectl get nodes

# Attach ACR to AKS
az aks update \
  --resource-group mlops-rg \
  --name mlops-cluster \
  --attach-acr mlopsacr123

# Update Kubernetes manifests to use ACR images
# Edit kubernetes/deployments/api-deployment.yaml
# Change: image: aqi-api:v1
# To: image: mlopsacr123.azurecr.io/aqi-api:v1

# Deploy to AKS
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -f kubernetes/deployments/
kubectl apply -f kubernetes/services/

# Get external IP (takes a few minutes)
kubectl get services -n mlops --watch

# Test API
EXTERNAL_IP=$(kubectl get service api-service -n mlops -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
curl http://$EXTERNAL_IP/health
```

**🎓 Learning Checkpoint**:
- [ ] Understand Azure resource groups
- [ ] Know how to use Azure CLI
- [ ] Understand container registries
- [ ] Can create and manage AKS clusters
- [ ] Know how to connect kubectl to AKS
- [ ] Understand cloud costs and resource management

---

### **Week 5: Monitoring & Observability**
**What You'll Learn**:
- Prometheus for metrics
- Grafana for dashboards
- Azure Monitor integration
- Logging with Fluent Bit

**What You'll Build**:
1. Prometheus + Grafana stack in K8s
2. Custom dashboards for ML metrics
3. Alerting rules

**Implementation**:

Install monitoring stack:
```bash
# Add Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install Prometheus + Grafana
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace

# Port-forward Grafana
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80

# Access Grafana at http://localhost:3000
# Default: admin / prom-operator
```

Create custom Prometheus metrics in your API:
```python
from prometheus_client import Counter, Histogram, Gauge

# Add to api/main.py
prediction_counter = Counter('predictions_total', 'Total predictions made')
drift_score_gauge = Gauge('drift_score', 'Current drift score')
mae_gauge = Gauge('model_mae', 'Current model MAE')
```

---

### **Week 6: CI/CD Pipeline**
**What You'll Learn**:
- GitHub Actions
- Automated testing
- Continuous deployment
- GitOps principles

**What You'll Build**:
1. GitHub Actions workflow
2. Automated Docker builds
3. Auto-deploy to AKS on git push

Create `.github/workflows/deploy.yml`:
```yaml
name: Build and Deploy to AKS

on:
  push:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Login to Azure
      uses: azure/login@v1
      with:
        creds: ${{ secrets.AZURE_CREDENTIALS }}
    
    - name: Login to ACR
      run: az acr login --name mlopsacr123
    
    - name: Build and push Docker images
      run: |
        docker build -f Dockerfile.api -t mlopsacr123.azurecr.io/aqi-api:${{ github.sha }} .
        docker push mlopsacr123.azurecr.io/aqi-api:${{ github.sha }}
    
    - name: Deploy to AKS
      uses: azure/k8s-deploy@v1
      with:
        manifests: |
          kubernetes/deployments/api-deployment.yaml
        images: |
          mlopsacr123.azurecr.io/aqi-api:${{ github.sha }}
        kubectl-version: 'latest'
```

**🎓 Learning Checkpoint**:
- [ ] Understand CI/CD concepts
- [ ] Can write GitHub Actions workflows
- [ ] Know how to automate deployments
- [ ] Understand GitOps principles

---

## 📊 Learning Progress Tracker

Track your progress:

```
Week 1: Docker Basics
  [x] Installed Docker
  [ ] Built first Dockerfile
  [ ] Run containers with volumes
  [ ] Understand Docker networking
  [ ] Drift detector containerized

Week 2: Docker Compose
  [ ] Multi-container setup
  [ ] Service dependencies
  [ ] Environment configuration
  [ ] All services running locally

Week 3: Kubernetes
  [ ] Local K8s cluster running
  [ ] Deployed first pod
  [ ] Created service
  [ ] Understand kubectl

Week 4: Cloud (Azure)
  [ ] Azure account created
  [ ] ACR setup and images pushed
  [ ] AKS cluster running
  [ ] System deployed to cloud

Week 5: Monitoring
  [ ] Prometheus installed
  [ ] Grafana dashboards created
  [ ] Custom metrics exposed

Week 6: CI/CD
  [ ] GitHub Actions workflow
  [ ] Automated deployments
  [ ] Full GitOps pipeline
```

---

## 💰 Cost Management

**Azure Free Tier**:
- $200 free credit for 30 days
- 12 months of free services (limited)

**Estimated Monthly Costs** (after free tier):
- AKS cluster (3 B2s nodes): ~$60/month
- Azure Container Registry: ~$5/month
- Storage: ~$5/month
- **Total**: ~$70/month

**Cost Optimization**:
- Use smallest node size (B2s)
- Stop cluster when not using: `az aks stop`
- Delete resources when done learning
- Use Azure Cost Management to monitor

**Start/Stop Cluster**:
```bash
# Stop (saves ~80% of costs)
az aks stop --resource-group mlops-rg --name mlops-cluster

# Start when needed
az aks start --resource-group mlops-rg --name mlops-cluster
```

---

## 🎯 Final Project State

After 6 weeks, you'll have:

```
✅ Self-healing ML system with:
   - Drift detection
   - Auto-retraining
   - Performance monitoring

✅ Fully containerized with Docker

✅ Deployed to Kubernetes (local + cloud)

✅ Running on Azure AKS

✅ Monitored with Prometheus/Grafana

✅ CI/CD pipeline with GitHub Actions

✅ Portfolio-ready project!
```

---

## 📚 Additional Resources

### Books:
- "Docker Deep Dive" by Nigel Poulton
- "Kubernetes Up & Running" by Kelsey Hightower
- "The Kubernetes Book" by Nigel Poulton

### Interactive Learning:
- [Play with Docker](https://labs.play-with-docker.com/)
- [Play with Kubernetes](https://labs.play-with-k8s.com/)
- [KodeKloud](https://kodekloud.com/) - Hands-on labs

### Certifications (Optional):
- Docker Certified Associate
- Certified Kubernetes Administrator (CKA)
- Azure Administrator Associate (AZ-104)

---

## 🚀 Getting Started Tomorrow

**Day 1 Action Items**:
1. [ ] Install Docker and Docker Compose
2. [ ] Run `docker run hello-world`
3. [ ] Complete first 3 Docker tutorials
4. [ ] Create `monitoring/drift_detector.py`
5. [ ] Write your first Dockerfile
6. [ ] Build and run drift detector container

**Pro Tip**: Don't try to learn everything at once. Build one feature, containerize it, deploy it, then move to the next. Learning by doing is 10x more effective than watching tutorials!

Ready to start? Let me know and I'll help you with Day 1 tasks! 💪
