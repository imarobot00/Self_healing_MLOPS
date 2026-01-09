# Week 4: Docker Containerization - COMPLETED ✅

## Summary
Successfully containerized the ML prediction API service with Docker and integrated with the monitoring stack from Week 3.

## Services Running

| Service | Status | Port | Description |
|---------|--------|------|-------------|
| mlops-api | ✅ Healthy | 8000 | FastAPI prediction service |
| mlops-training | ⏸️ One-shot | 8001 | Auto-trainer (runs on schedule) |
| mlops-orchestrator | ⏸️ One-shot | 8002 | Self-healing orchestrator |

## API Endpoints

- **Health Check**: `GET http://localhost:8000/health`
- **Prediction**: `POST http://localhost:8000/predict`
- **Swagger Docs**: `http://localhost:8000/docs`
- **Prometheus Metrics**: `http://localhost:8000/metrics/prometheus`

## Example Prediction Request

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "pm25": 50.5,
    "pm1": 25.0,
    "temperature": 22.5,
    "relativehumidity": 65.0,
    "um003": 1250.0,
    "hour": 14,
    "day_of_week": 2,
    "month": 1
  }'
```

Response:
```json
{
    "predicted_aqi": 177.06,
    "aqi_category": "Unhealthy",
    "model_version": "20260105_125547",
    "timestamp": "2026-01-09T05:32:41.148208"
}
```

## Docker Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose Stack                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │   mlops-api     │    │  mlops-training │                 │
│  │   (FastAPI)     │    │  (Auto-trainer) │                 │
│  │    :8000        │    │     :8001       │                 │
│  └────────┬────────┘    └─────────────────┘                 │
│           │                                                  │
│           │ Shared Volume: ./training/models                │
│           │                                                  │
│  ┌────────▼──────────────────────────────────────────┐      │
│  │           Monitoring Network                       │      │
│  │  (Connected to prometheus, grafana, alertmanager) │      │
│  └───────────────────────────────────────────────────┘      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Files Created

1. **api/Dockerfile** - Multi-stage build for FastAPI service
2. **training/Dockerfile** - Multi-stage build for training pipeline
3. **docker-compose.mlops.yml** - Service orchestration
4. **training/health_server.py** - Health check HTTP server

## Key Features

- ✅ Multi-stage Docker builds for smaller images
- ✅ Shared model volume between API and training
- ✅ Health checks with automatic restart
- ✅ Integration with Prometheus monitoring
- ✅ Cross-directory module sharing (api ↔ training)
- ✅ Environment variable configuration

## Commands

```bash
# Start all services
docker compose -f docker-compose.mlops.yml up -d

# Check status
docker compose -f docker-compose.mlops.yml ps

# View logs
docker compose -f docker-compose.mlops.yml logs -f

# Stop services
docker compose -f docker-compose.mlops.yml down

# Rebuild after changes
docker compose -f docker-compose.mlops.yml build --no-cache
```

## Integration with Monitoring (Week 3)

The containerized services integrate with the monitoring stack:
- Prometheus scrapes metrics from `http://mlops-api:8000/metrics/prometheus`
- Grafana dashboards show prediction counts, latency, and model performance
- AlertManager receives alerts for service issues

## Lessons Learned

1. **Docker build context**: Files must be copied from within the build context
2. **Cross-directory imports**: Services importing from sibling directories need all dependencies copied
3. **WORKDIR placement**: Affects relative path resolution for CMD
4. **Volume mounts**: Use host paths for development, named volumes for production
5. **Requirements synchronization**: API needs all dependencies that imported modules use

## Next Steps (Week 5-6)

- [ ] Kubernetes deployment manifests
- [ ] Helm charts for parameterized deployment
- [ ] Horizontal Pod Autoscaling
- [ ] ServiceMonitor for Prometheus Operator
- [ ] CI/CD pipeline with GitHub Actions

---
*Completed: January 9, 2026*
