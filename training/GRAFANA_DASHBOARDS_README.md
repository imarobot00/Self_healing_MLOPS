# Grafana Dashboard Configuration Guide

This directory contains Grafana dashboard configurations for monitoring the ML system.

## Dashboards

### 1. ML System Overview (`grafana_dashboard_overview.json`)

**Purpose**: High-level view of system health and performance

**Panels**:
- **System Health**: Overall health status (healthy/unhealthy)
- **Prediction Rate**: Requests per second by model
- **Prediction Latency**: P50 and P95 latency
- **Model Performance**: MAE and R² score trends
- **Model Drift**: PSI score with threshold indicators
- **Error Rate**: Percentage of failed predictions
- **Active Health Checks**: Status of all health probes

**Refresh Rate**: 30 seconds

**Use Case**: Executive dashboard, at-a-glance status

---

### 2. ML Training Pipeline (`grafana_dashboard_training.json`)

**Purpose**: Monitor training, validation, and deployment pipeline

**Panels**:
- **Total Trainings**: Count of training runs
- **Success Rate**: Training success percentage
- **Failed Trainings**: Count of failures
- **Training Duration**: Time to complete training
- **Drift Checks**: Rate of drift detection checks
- **Total Validations**: Validation runs
- **Approved/Rejected**: Validation outcomes
- **Models in Registry**: Total models tracked
- **Models by Status**: Breakdown (candidate/staging/production)
- **Total Deployments**: Model deployment count
- **Rollbacks**: Emergency rollback count
- **Healing Workflows**: Self-healing triggers

**Refresh Rate**: 1 minute

**Use Case**: ML operations team, troubleshooting

---

## Setup Instructions

### 1. Install Grafana

**Docker**:
```bash
docker run -d -p 3000:3000 --name=grafana grafana/grafana-oss
```

**Linux**:
```bash
sudo apt-get install -y grafana
sudo systemctl start grafana-server
sudo systemctl enable grafana-server
```

Access: http://localhost:3000 (default user:admin pass:admin)

---

### 2. Add Prometheus Data Source

1. Go to **Configuration → Data Sources**
2. Click **Add data source**
3. Select **Prometheus**
4. Configure:
   - Name: `Prometheus`
   - URL: `http://localhost:9090` (or your Prometheus server)
   - Access: `Server` (or `Browser` if running locally)
5. Click **Save & Test**

---

### 3. Import Dashboards

#### Option A: Via UI

1. Go to **Create → Import**
2. Upload JSON file or paste contents
3. Select Prometheus data source
4. Click **Import**

#### Option B: Via API

```bash
# Import overview dashboard
curl -X POST http://admin:admin@localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @grafana_dashboard_overview.json

# Import training dashboard
curl -X POST http://admin:admin@localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @grafana_dashboard_training.json
```

---

### 4. Configure Alerts (Optional)

Add alerts to panels:

1. Edit panel
2. Go to **Alert** tab
3. Click **Create Alert**
4. Configure condition (e.g., `model_drift_psi > 0.3`)
5. Set notification channel
6. Save

---

## Prometheus Setup

### 1. Install Prometheus

**Docker**:
```bash
docker run -d -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

### 2. Configure Prometheus (`prometheus.yml`)

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'mlops-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics/prometheus'
    
  - job_name: 'mlops-training'
    static_configs:
      - targets: ['localhost:8001']
    metrics_path: '/metrics'
```

### 3. Verify Metrics

Visit http://localhost:9090/targets to see scrape status

Query examples:
- `predictions_total`
- `model_mae`
- `training_duration_seconds`

---

## Customization

### Adding New Panels

```json
{
  "id": 14,
  "gridPos": {"h": 8, "w": 12, "x": 0, "y": 34},
  "type": "graph",
  "title": "Your Custom Metric",
  "targets": [
    {
      "expr": "your_metric_name",
      "legendFormat": "{{label}}",
      "refId": "A"
    }
  ]
}
```

### Panel Types

- **stat**: Single value with thresholds
- **graph**: Time series line chart
- **table**: Tabular data
- **gauge**: Progress/percentage gauge
- **heatmap**: Distribution heatmap

### Common Prometheus Queries

```promql
# Rate of change
rate(predictions_total[5m])

# Percentiles
histogram_quantile(0.95, rate(prediction_duration_seconds_bucket[5m]))

# Ratio
trainings_success_total / trainings_total

# Aggregation
sum by (model) (predictions_total)
```

---

## Best Practices

1. **Layer Dashboards**:
   - L1: Executive (high-level)
   - L2: Service owner (per-service)
   - L3: Debug (deep dive)

2. **Use Time Variables**:
   - Add time range selector
   - Support zooming

3. **Set Thresholds**:
   - Green: Healthy
   - Yellow: Warning
   - Red: Critical

4. **Add Annotations**:
   - Mark deployments
   - Note incidents
   - Track changes

5. **Keep It Simple**:
   - Max 6-8 panels per view
   - Clear titles
   - Consistent colors

---

## Troubleshooting

### No Data Showing

1. Check Prometheus is scraping:
   ```bash
   curl http://localhost:9090/api/v1/targets
   ```

2. Verify metrics endpoint:
   ```bash
   curl http://localhost:8000/metrics/prometheus
   ```

3. Check dashboard time range (top-right)

### Slow Queries

- Reduce time range
- Increase scrape interval
- Use recording rules in Prometheus

### Missing Metrics

- Check metric names match exactly
- Verify labels are correct
- Ensure service is exporting metrics

---

## Next Steps

1. **Set up Alert Manager** for notifications
2. **Create recording rules** for complex queries
3. **Add business metrics** (predictions per customer, revenue impact)
4. **Configure retention** for historical data
5. **Export dashboards** for version control

---

## Resources

- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Best Practices](https://grafana.com/docs/grafana/latest/best-practices/)
- [Dashboard Examples](https://grafana.com/grafana/dashboards/)
