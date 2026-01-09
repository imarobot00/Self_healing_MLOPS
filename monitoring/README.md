# 🎯 MLOps Monitoring Stack

Complete production-ready monitoring solution for the ML system with Prometheus, Grafana, and Alert Manager.

## 📦 What's Included

### Services

1. **Prometheus** (`:9090`) - Time-series metrics collection
2. **Grafana** (`:3000`) - Beautiful dashboards and visualization
3. **Alert Manager** (`:9093`) - Intelligent alert routing
4. **Node Exporter** (`:9100`) - System metrics (CPU, memory, disk)
5. **cAdvisor** (`:8080`) - Container metrics

### Configuration Files

- `prometheus.yml` - Prometheus scrape configs and targets
- `alert_rules.yml` - 25+ ML-specific alert rules
- `alertmanager.yml` - Alert routing and notification channels
- `docker-compose.yml` - Complete monitoring stack
- `grafana/` - Auto-provisioned datasources and dashboards

---

## 🚀 Quick Start

### 1. Start Monitoring Stack

```bash
cd monitoring
./start-monitoring.sh
```

This will:
- ✅ Check Docker installation
- ✅ Create necessary directories
- ✅ Start all services
- ✅ Wait for health checks
- ✅ Display access URLs

### 2. Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| **Grafana** | http://localhost:3000 | admin/admin |
| **Prometheus** | http://localhost:9090 | - |
| **Alert Manager** | http://localhost:9093 | - |
| **Node Exporter** | http://localhost:9100 | - |
| **cAdvisor** | http://localhost:8080 | - |

### 3. View Dashboards

1. Open **Grafana**: http://localhost:3000
2. Login: `admin` / `admin`
3. Navigate: **Dashboards → MLOps**
4. Select:
   - **ML System Overview** - Executive dashboard
   - **ML Training Pipeline** - Ops dashboard

---

## 📊 Metrics Being Collected

### API Metrics
```promql
predictions_total                  # Total predictions by model
predictions_errors_total           # Failed predictions
prediction_duration_seconds        # Latency histogram
```

### Model Metrics
```promql
model_mae                          # Mean Absolute Error
model_r2                           # R² score
model_drift_psi                    # PSI drift score
```

### Training Metrics
```promql
trainings_total                    # Total training runs
trainings_success_total            # Successful trainings
trainings_failed_total             # Failed trainings
training_duration_seconds          # Training time
```

### Validation & Registry
```promql
validations_total                  # Total validations
validations_approved_total         # Approved models
validations_rejected_total         # Rejected models
models_total                       # Models in registry
deployments_total                  # Deployments
rollbacks_total                    # Rollbacks
```

### Health Checks
```promql
service_health                     # Overall service health (0/1)
health_check_status                # Individual check status
service_uptime_seconds             # Service uptime
```

---

## 🔔 Alert Rules (25+ Rules)

### Critical (P1) - Immediate Action
- **APIDown** - API unreachable
- **NoPredictions** - No predictions for 10+ minutes
- **SevereModelDrift** - PSI > 0.3
- **ServiceUnhealthy** - Health check failed
- **FrequentRollbacks** - 3+ rollbacks in 6 hours

### High (P2) - Quick Response
- **ModelPerformanceDegraded** - MAE > 10.0
- **HighPredictionLatency** - P95 > 1 second
- **HighErrorRate** - Error rate > 5%
- **TrainingFailed** - Training run failed
- **HighMemoryUsage** - Memory > 90%

### Medium (P3) - Normal Priority
- **ModelR2TooLow** - R² < 0.7
- **ModerateModelDrift** - PSI 0.1-0.3
- **TrainingTooSlow** - Training > 1 hour
- **HighCPUUsage** - CPU > 80%
- **HighMissingDataRate** - Missing data > 10%

### Low (P4) - Informational
- **LowPredictionVolume** - Low traffic
- **NoRecentTraining** - No training in 7 days

---

## ⚙️ Configuration

### Configure Slack Notifications

1. Create Slack webhook: https://api.slack.com/messaging/webhooks
2. Edit `alertmanager.yml`:
   ```yaml
   global:
     slack_api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
   ```
3. Restart Alert Manager:
   ```bash
   docker compose restart alertmanager
   ```

### Configure Email Notifications

Edit `alertmanager.yml`:
```yaml
global:
  smtp_from: 'mlops-alerts@example.com'
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_auth_username: 'your-email@gmail.com'
  smtp_auth_password: 'your-app-password'
```

**Gmail**: Use [App Password](https://support.google.com/accounts/answer/185833)

Restart:
```bash
docker compose restart alertmanager
```

### Add Custom Metrics

1. Expose metrics in your service:
   ```python
   from training.metrics_collector import MetricsCollector
   
   metrics = MetricsCollector()
   metrics.increment('my_custom_metric')
   
   # Expose at /metrics endpoint
   @app.get("/metrics")
   def get_metrics():
       return Response(metrics.export(), media_type="text/plain")
   ```

2. Add scrape config to `prometheus.yml`:
   ```yaml
   scrape_configs:
     - job_name: 'my-service'
       static_configs:
         - targets: ['host.docker.internal:PORT']
   ```

3. Reload Prometheus:
   ```bash
   curl -X POST http://localhost:9090/-/reload
   ```

---

## 🎛️ Common Operations

### Start Stack
```bash
./start-monitoring.sh
```

### Stop Stack
```bash
docker compose down
```

### View Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f prometheus
docker compose logs -f grafana
docker compose logs -f alertmanager
```

### Restart Service
```bash
docker compose restart prometheus
docker compose restart grafana
docker compose restart alertmanager
```

### Check Status
```bash
docker compose ps
```

### Update Configuration
```bash
# After editing prometheus.yml or alert_rules.yml
curl -X POST http://localhost:9090/-/reload

# After editing alertmanager.yml
docker compose restart alertmanager

# After editing Grafana dashboards
# They auto-reload every 30 seconds
```

### Clean Up Everything
```bash
docker compose down -v  # Remove volumes too
```

---

## 🔍 Verify Setup

### 1. Check Prometheus Targets
1. Open http://localhost:9090/targets
2. Verify all targets are **UP**
3. Expected targets:
   - prometheus
   - mlops-api (if API running)
   - node-exporter
   - cadvisor
   - grafana

### 2. Test Metrics
```bash
# Check API metrics
curl http://localhost:8000/metrics/prometheus

# Check if Prometheus sees them
curl http://localhost:9090/api/v1/query?query=predictions_total
```

### 3. Check Grafana Dashboards
1. Open http://localhost:3000
2. Go to **Dashboards**
3. Should see **MLOps** folder with 2 dashboards

### 4. Test Alerts
```bash
# View active alerts
curl http://localhost:9090/api/v1/alerts

# View Alert Manager
open http://localhost:9093
```

---

## 🐛 Troubleshooting

### Prometheus Can't Scrape API

**Problem**: Targets showing as DOWN

**Solutions**:
1. Check if API is running: `curl http://localhost:8000/health`
2. Verify metrics endpoint: `curl http://localhost:8000/metrics/prometheus`
3. Check Docker network: Use `host.docker.internal` instead of `localhost`
4. View Prometheus logs: `docker compose logs prometheus`

### Grafana Dashboards Not Showing Data

**Problem**: Empty panels in dashboards

**Solutions**:
1. Check Prometheus datasource: **Configuration → Data Sources**
2. Test datasource connection
3. Verify time range (top-right corner)
4. Check if metrics exist: Go to Prometheus → Graph → Query `predictions_total`

### Alert Manager Not Sending Notifications

**Problem**: Alerts firing but no notifications

**Solutions**:
1. Check Alert Manager config: `docker compose logs alertmanager`
2. Verify Slack webhook URL is correct
3. Test Slack webhook manually:
   ```bash
   curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
     -H 'Content-Type: application/json' \
     -d '{"text":"Test from MLOps"}'
   ```
4. Check Alert Manager UI: http://localhost:9093

### Services Not Starting

**Problem**: Docker compose fails

**Solutions**:
1. Check Docker is running: `docker info`
2. Check port conflicts:
   ```bash
   lsof -i :9090  # Prometheus
   lsof -i :3000  # Grafana
   lsof -i :9093  # Alert Manager
   ```
3. View specific service logs: `docker compose logs SERVICE_NAME`
4. Check disk space: `df -h`

---

## 📈 Prometheus Queries

### Useful Queries

```promql
# Prediction rate (requests/sec)
rate(predictions_total[5m])

# Error rate
rate(predictions_errors_total[5m]) / rate(predictions_total[5m])

# P95 latency
histogram_quantile(0.95, rate(prediction_duration_seconds_bucket[5m]))

# Model MAE trend
model_mae

# Training success rate
trainings_success_total / trainings_total

# Active alerts
ALERTS{alertstate="firing"}

# Service uptime
service_uptime_seconds / 3600  # In hours
```

---

## 🔐 Security

### Change Default Passwords

Grafana:
1. Login with `admin/admin`
2. You'll be prompted to change password
3. Or set via environment variable:
   ```yaml
   environment:
     - GF_SECURITY_ADMIN_PASSWORD=your_secure_password
   ```

### Restrict Access

Add authentication to Prometheus/Alert Manager (use reverse proxy):

```nginx
location /prometheus/ {
    auth_basic "Prometheus";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://localhost:9090/;
}
```

---

## 📊 Dashboard Customization

### Edit Existing Dashboards

1. Open dashboard in Grafana
2. Click **Dashboard settings** (gear icon)
3. Edit panels
4. **Save**
5. Export JSON: **Share → Export → Save to file**
6. Copy to `monitoring/grafana/dashboards/`

### Create New Dashboard

1. **Create → Dashboard**
2. **Add panel**
3. Select Prometheus datasource
4. Enter query (e.g., `predictions_total`)
5. Configure visualization
6. **Save dashboard**
7. Export and save to `monitoring/grafana/dashboards/`

---

## 🎯 Next Steps

### Week 4: Docker Containerization
- Containerize ML services
- Multi-stage builds
- Docker networks
- Service orchestration

### Week 5-6: Kubernetes
- Deploy to K8s cluster
- Helm charts
- Auto-scaling
- Rolling updates

### Week 7+: Cloud Production
- Azure AKS deployment
- CI/CD pipelines
- Infrastructure as Code
- Production hardening

---

## 📚 Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Alert Manager](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [PromQL Tutorial](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Best Practices](https://grafana.com/docs/grafana/latest/best-practices/)

---

## ✅ Checklist

Before proceeding to Week 4:

- [ ] All monitoring services running
- [ ] Prometheus scraping API metrics
- [ ] Grafana dashboards visible
- [ ] Alerts configured
- [ ] Notifications tested (Slack/Email)
- [ ] Node Exporter collecting system metrics
- [ ] cAdvisor collecting container metrics
- [ ] Custom metrics integrated

---

**Status**: ✅ Production-Ready Monitoring Stack  
**Services**: 5 containers  
**Alert Rules**: 25+  
**Dashboards**: 2 (auto-provisioned)  
**Retention**: 30 days

🎉 **Your ML system is now fully observable!**
