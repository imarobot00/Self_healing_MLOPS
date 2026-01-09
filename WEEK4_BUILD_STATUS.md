# 🐳 Week 4: Docker Containerization - In Progress

**Status**: Building Docker images...  
**Date**: January 9, 2026

---

## ✅ Completed So Far

### 1. API Service Dockerfile (`api/Dockerfile`)
- **Base Image**: Python 3.11-slim (multi-stage build)
- **Stage 1 (Builder)**: Install build dependencies (gcc, g++)
- **Stage 2 (Runtime)**: Copy compiled packages, application code
- **Exposed Port**: 8000
- **Health Check**: `curl -f http://localhost:8000/health`
- **Entry Point**: `uvicorn main:app --host 0.0.0.0 --port 8000`
- **Volumes**: 
  - `/app/models` - Shared model storage
  - `/app/logs` - API logs
- **Features**:
  - Static files for UI
  - Metrics endpoint for Prometheus
  - Auto-reload on code changes (dev mode)

### 2. Training Service Dockerfile (`training/Dockerfile`)
- **Base Image**: Python 3.11-slim (multi-stage build)
- **Components Included**:
  - training.py - Core training logic
  - auto_trainer.py - Automated retraining
  - model_validator.py - Model validation
  - model_registry.py - Registry management
  - self_healing_orchestrator.py - Self-healing logic
  - metrics_collector.py - Metrics
  - alert_manager.py - Alerts
  - health_checks.py - Health monitoring
- **Exposed Port**: 8001
- **Health Check**: `curl -f http://localhost:8001/health`
- **Volumes**:
  - `/app/models` - Shared model storage
  - `/data` - Training data (read-only)
  - `/app/logs`, `/app/charts`, `/app/evaluations` - Outputs
  - `/app/registry.json` - Model registry

### 3. ML Services Docker Compose (`docker-compose.mlops.yml`)
- **Services**: 3 containers
  1. **mlops-api** (port 8000)
     - Depends on: mlops-training
     - Networks: mlops-network, monitoring_monitoring
     - Health check: 30s interval
     
  2. **mlops-training** (port 8001)
     - Networks: mlops-network, monitoring_monitoring
     - Health check: 60s interval
     - Volumes: models, data, logs, charts, evaluations
     
  3. **mlops-orchestrator** (port 8002)
     - Command: `python self_healing_orchestrator.py`
     - Depends on: mlops-api, mlops-training
     - Shares volumes with training
     - Networks: mlops-network, monitoring_monitoring

- **Networks**:
  - `mlops-network` (172.21.0.0/16) - Internal ML services
  - `monitoring_monitoring` (external) - Connect to monitoring stack

- **Volumes**:
  - `mlops-models` - Persistent model storage (shared)

### 4. Deployment Script (`start-mlops.sh`)
- **Pre-flight Checks**:
  - Docker installed and running
  - Monitoring stack running (starts if needed)
  - Required files present
- **Build Process**:
  - Builds all images with --no-cache
  - Multi-stage optimization
- **Startup**:
  - Starts services with docker compose up -d
  - Waits for health checks
  - Verifies Prometheus integration
- **Output**:
  - Service URLs
  - Quick action commands
  - Testing instructions

### 5. Supporting Files
- `api/.dockerignore` - Excludes test files, logs, models from build
- `training/.dockerignore` - Excludes docs, tests, generated outputs
- `training/health_server.py` - HTTP server for health checks
- `training/requirements.txt` - Training service dependencies

---

## 🔄 Current Status: Building Images

The Docker images are currently building. This process includes:

1. **Downloading base images** (Python 3.11-slim)
2. **Installing system dependencies** (gcc, g++, curl)
3. **Installing Python packages**:
   - API: fastapi, uvicorn, river, pandas, numpy, prometheus-client
   - Training: river, pandas, numpy, scikit-learn, matplotlib, seaborn, dill
4. **Copying application code**
5. **Creating directory structure**
6. **Setting up health checks**

Expected build time: **3-5 minutes** (first build)

---

## 📦 What's Being Built

### Image Sizes (Estimated)
- **API Image**: ~400-500 MB
  - Base: Python 3.11-slim (~150 MB)
  - Dependencies: ~200-250 MB
  - Application code: ~50 MB

- **Training Image**: ~500-600 MB
  - Base: Python 3.11-slim (~150 MB)
  - Dependencies: ~250-350 MB (includes matplotlib, seaborn)
  - Application code: ~100 MB

- **Orchestrator**: Uses same image as training

### Multi-Stage Build Benefits
- ✅ Smaller final images (no build tools in runtime)
- ✅ Faster deployments
- ✅ Better security (fewer attack surfaces)
- ✅ Optimized layers (better caching)

---

## 🚀 What Happens Next

Once the build completes:

1. **Services Start**:
   ```
   mlops-training (8001) → mlops-api (8000) → mlops-orchestrator (8002)
   ```

2. **Health Checks Run**:
   - Training: 60s interval, 60s start period
   - API: 30s interval, 40s start period
   - Orchestrator: 60s interval, 60s start period

3. **Prometheus Starts Scraping**:
   - mlops-api: /metrics/prometheus (10s interval)
   - mlops-training: /metrics (30s interval)
   - mlops-orchestrator: /metrics (30s interval)

4. **Grafana Dashboards Populate**:
   - ML System Overview fills with data
   - Training Pipeline shows metrics
   - Real-time graphs appear

5. **Self-Healing Activates**:
   - Drift detection starts
   - Auto-retraining triggers
   - Model validation pipeline active

---

## 🎯 Next Steps (After Build)

### 1. Verify Services Are Running
```bash
docker compose -f docker-compose.mlops.yml ps
```

Expected output:
```
NAME                  STATUS                PORTS
mlops-api             Up (healthy)          0.0.0.0:8000->8000/tcp
mlops-training        Up (healthy)          0.0.0.0:8001->8001/tcp
mlops-orchestrator    Up (healthy)          0.0.0.0:8002->8002/tcp
```

### 2. Check Prometheus Targets
Open: http://localhost:9090/targets

Should see:
- ✅ mlops-api (UP)
- ✅ mlops-training (UP)
- ✅ mlops-orchestrator (UP)

### 3. View Grafana Dashboards
Open: http://localhost:3000 (admin/admin)

Navigate to: Dashboards → MLOps
- ML System Overview - Now showing live data!
- ML Training Pipeline - Real metrics!

### 4. Test API
```bash
# Health check
curl http://localhost:8000/health

# Metrics
curl http://localhost:8000/metrics/prometheus

# API docs
Open: http://localhost:8000/docs

# Make a prediction
curl -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"features": {...}}'
```

### 5. View Logs
```bash
# All services
docker compose -f docker-compose.mlops.yml logs -f

# Specific service
docker compose -f docker-compose.mlops.yml logs -f mlops-api
docker compose -f docker-compose.mlops.yml logs -f mlops-training
docker compose -f docker-compose.mlops.yml logs -f mlops-orchestrator
```

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Monitoring Stack                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐              │
│  │Prometheus│  │ Grafana  │  │Alert Manager │              │
│  │  :9090   │  │  :3000   │  │    :9093     │              │
│  └────┬─────┘  └──────────┘  └──────────────┘              │
│       │                                                       │
│       │ Scrapes metrics every 10-30s                         │
└───────┼───────────────────────────────────────────────────────┘
        │
        │ monitoring_monitoring network
        │
┌───────┼───────────────────────────────────────────────────────┐
│       │              ML Services Stack                         │
│       │                                                        │
│   ┌───▼─────────┐    ┌──────────────┐    ┌─────────────────┐│
│   │   mlops-api  │◄───│ mlops-train  │◄───│mlops-orchestrator││
│   │   :8000      │    │   :8001      │    │     :8002        ││
│   │              │    │              │    │                  ││
│   │ • Predictions│    │ • Training   │    │ • Drift detect   ││
│   │ • Health     │    │ • Validation │    │ • Auto-retrain   ││
│   │ • Metrics    │    │ • Registry   │    │ • Deployment     ││
│   └──────┬───────┘    └──────┬───────┘    └────────┬─────────┘│
│          │                   │                     │          │
│          └───────────────────┼─────────────────────┘          │
│                              │                                │
│                         mlops-models                          │
│                      (shared volume)                          │
└───────────────────────────────────────────────────────────────┘
```

---

## 📊 Resource Usage (Expected)

### CPU
- API: ~5-10% (idle), up to 50% (during predictions)
- Training: ~10-20% (idle), up to 80% (during training)
- Orchestrator: ~5% (monitoring)

### Memory
- API: ~200-300 MB
- Training: ~400-600 MB
- Orchestrator: ~200-300 MB

### Disk
- Images: ~1.5 GB total
- Models: ~50-100 MB per model
- Logs: ~10-50 MB/day

### Network
- Internal (mlops-network): High throughput
- External (monitoring): Low (metrics scraping)
- API: Variable (depends on traffic)

---

## 🎉 What's New vs Week 3

### Week 3 (Monitoring)
- ✅ Monitoring infrastructure deployed
- ✅ Prometheus scraping system metrics
- ✅ Grafana dashboards (empty)
- ✅ Alert rules configured
- ❌ ML services not running

### Week 4 (Containerization)
- ✅ All ML services containerized
- ✅ Unified deployment with Docker Compose
- ✅ Prometheus scraping ML metrics
- ✅ Grafana dashboards showing live data
- ✅ End-to-end observability
- ✅ Self-healing workflows active

---

## 🔍 Troubleshooting (Common Issues)

### Build Fails
```bash
# Clear Docker cache
docker system prune -a
docker volume prune

# Rebuild without cache
docker compose -f docker-compose.mlops.yml build --no-cache
```

### Services Not Starting
```bash
# Check logs
docker compose -f docker-compose.mlops.yml logs

# Check specific service
docker compose -f docker-compose.mlops.yml logs mlops-api
```

### Health Checks Failing
```bash
# Check health status
docker compose -f docker-compose.mlops.yml ps

# Inspect container
docker inspect mlops-api

# Check port binding
netstat -tuln | grep 8000
```

### Can't Connect to Monitoring
```bash
# Check if monitoring network exists
docker network ls | grep monitoring

# Restart monitoring stack
cd monitoring && ./start-monitoring.sh
```

---

**Status**: ⏳ Building... (Check back in a few minutes)

Once complete, run:
```bash
docker compose -f docker-compose.mlops.yml ps
```

Expected result: All 3 services showing "(healthy)"
