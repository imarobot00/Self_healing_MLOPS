# Advanced Monitoring & Alerting - Comprehensive Learning Guide

## What is Observability in MLOps?

**Observability** is your ability to understand what's happening inside your ML system by examining its outputs. Unlike traditional software, ML systems have unique monitoring needs:

- **Model performance** changes over time (drift)
- **Data quality** affects predictions
- **Training processes** are long-running and resource-intensive
- **Multiple versions** of models exist simultaneously
- **Business metrics** tied directly to model accuracy

Think of it as having **X-ray vision** into your ML system—seeing not just if it's running, but *how well* it's performing and *why* it might be failing.

---

## The Three Pillars of Observability

### 1. Metrics (Numbers over time)

**What:** Quantitative measurements collected at regular intervals

**Examples:**
- Request rate: 1000 req/s
- Model MAE: 6.5 µg/m³
- Training duration: 15 minutes
- P95 latency: 45ms

**When to use:** Understanding trends, setting alerts, capacity planning

### 2. Logs (Event records)

**What:** Timestamped text records of discrete events

**Examples:**
- "2026-01-08 10:30:00 - Model validation started"
- "2026-01-08 10:32:15 - ERROR: Training failed due to insufficient data"
- "2026-01-08 10:35:00 - Rollback completed to model_20260107_180235"

**When to use:** Debugging, audit trails, understanding causality

### 3. Traces (Request paths)

**What:** End-to-end journey of a request through your system

**Example:**
```
API request → Feature engineering (10ms) → Model inference (25ms) 
          → Post-processing (5ms) → Response (40ms total)
```

**When to use:** Finding bottlenecks, understanding dependencies

---

## ML-Specific Monitoring Challenges

### Traditional Software Monitoring

```
✅ Is service up?
✅ Response time acceptable?
✅ Error rate low?
```

**Goal:** Keep system running

### ML System Monitoring

```
✅ Is service up?
✅ Response time acceptable?
✅ Error rate low?
🤔 Are predictions accurate?
🤔 Has data distribution changed?
🤔 Is model degrading?
🤔 Are business metrics improving?
```

**Goal:** Keep system running *AND* performing well

### The Silent Failure Problem

```python
# Traditional software
def divide(a, b):
    return a / b  # Fails loudly on b=0

# ML model
def predict(input_data):
    return model.predict(input_data)  # Returns garbage silently on drift
```

**ML systems can fail silently** - they keep running but produce bad predictions. This is why ML-specific monitoring is critical.

---

## What to Monitor

### 1. System Health Metrics

**Infrastructure:**
- CPU usage (%)
- Memory usage (MB)
- Disk I/O (ops/s)
- Network throughput (Mbps)

**Application:**
- Request rate (req/s)
- Response time (ms) - P50, P95, P99
- Error rate (%)
- Availability (%)

**Why:** Ensure system can handle load

### 2. Model Performance Metrics

**Prediction Quality:**
- MAE (Mean Absolute Error)
- RMSE (Root Mean Squared Error)
- R² (coefficient of determination)
- MAPE (Mean Absolute Percentage Error)

**Distribution:**
- Prediction distribution (histogram)
- Ground truth vs predictions (scatter)
- Residuals distribution

**Why:** Detect model degradation

### 3. Data Quality Metrics

**Input Data:**
- Missing value rate (%)
- Out-of-range values (%)
- Data freshness (minutes since last update)
- Feature distributions (mean, std, min, max)

**Drift Detection:**
- PSI (Population Stability Index)
- KL Divergence
- Wasserstein Distance

**Why:** Catch data issues before they affect predictions

### 4. Training Metrics

**Process:**
- Training duration (minutes)
- Training frequency (per day)
- Success rate (%)
- Resource usage during training

**Model Quality:**
- Training loss
- Validation loss
- Overfitting indicators (train vs val gap)

**Why:** Optimize training process, catch training failures

### 5. Business Metrics

**Impact:**
- Prediction accuracy on recent data
- False positive/negative rates
- User satisfaction scores
- Revenue impact

**Why:** Tie technical metrics to business value

---

## Monitoring Architecture

### Centralized Monitoring System

```
┌─────────────────────────────────────────────────────────┐
│                    MONITORING STACK                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐     ┌──────────────┐                │
│  │  Prometheus  │ ◄── │   Exporters  │                │
│  │   (Metrics)  │     │  (Components)│                │
│  └──────┬───────┘     └──────────────┘                │
│         │                                               │
│         ▼                                               │
│  ┌──────────────┐     ┌──────────────┐                │
│  │   Grafana    │     │ Alert Manager│                │
│  │ (Dashboards) │     │ (Notifications)               │
│  └──────────────┘     └──────────────┘                │
│                                                         │
└─────────────────────────────────────────────────────────┘
         │                        │
         ▼                        ▼
    Visualize                  Alert
    
    
┌─────────────────────────────────────────────────────────┐
│                   YOUR ML SYSTEM                        │
├─────────────────────────────────────────────────────────┤
│  API ──▶ Orchestrator ──▶ Trainer ──▶ Validator       │
│   │          │               │            │             │
│   ├─metrics──┼──metrics──────┼──metrics───┤             │
│   ├─logs─────┼──logs─────────┼──logs──────┤             │
│   └─health───┴──health───────┴──health────┘             │
└─────────────────────────────────────────────────────────┘
```

### Components

**1. Metrics Collection (Prometheus)**
- Pull metrics from exporters every 15s
- Store time-series data
- Query with PromQL

**2. Visualization (Grafana)**
- Connect to Prometheus
- Build dashboards
- Real-time graphs

**3. Alerting (Alert Manager)**
- Evaluate alert rules
- Route notifications
- Deduplication & grouping

**4. Exporters (Your Code)**
- Expose metrics endpoints
- Prometheus format
- `/metrics` endpoint

---

## Prometheus Metrics Format

### Four Metric Types

**1. Counter (Only goes up)**
```python
# Example: Total predictions made
predictions_total{model="model_v1"} 15234

# Use for: Cumulative counts
# Examples: requests, errors, training runs
```

**2. Gauge (Can go up or down)**
```python
# Example: Current MAE
model_mae{model="model_v1"} 6.5

# Use for: Current values
# Examples: CPU usage, MAE, active users
```

**3. Histogram (Distribution of values)**
```python
# Example: Request duration buckets
request_duration_bucket{le="0.01"} 245
request_duration_bucket{le="0.05"} 612
request_duration_bucket{le="0.1"} 987

# Use for: Latency, request sizes
# Enables: Percentile calculations
```

**4. Summary (Pre-computed percentiles)**
```python
# Example: Request duration quantiles
request_duration{quantile="0.5"} 0.025
request_duration{quantile="0.95"} 0.087
request_duration{quantile="0.99"} 0.145

# Use for: When histograms too expensive
```

### Example Metrics Endpoint

```python
# GET /metrics
# HELP predictions_total Total number of predictions made
# TYPE predictions_total counter
predictions_total{model="model_20260107"} 15234

# HELP model_mae Current model MAE
# TYPE model_mae gauge
model_mae{model="model_20260107"} 6.5

# HELP drift_psi Current PSI drift score
# TYPE drift_psi gauge
drift_psi 0.18

# HELP training_duration_seconds Time to train model
# TYPE training_duration_seconds histogram
training_duration_seconds_bucket{le="300"} 0
training_duration_seconds_bucket{le="600"} 3
training_duration_seconds_bucket{le="1200"} 8
training_duration_seconds_sum 8456
training_duration_seconds_count 8
```

---

## Alert Design

### Alert Severity Levels

**🔴 P1 - Critical (Page immediately)**
- Production API down
- Model predictions failing (100% error rate)
- Automatic rollback triggered
- Data pipeline completely broken

**🟡 P2 - High (Alert within 15 min)**
- Model MAE degraded >20%
- Training failures (3+ in a row)
- High error rate (>5%)
- Disk space <10%

**🟢 P3 - Medium (Alert within 1 hour)**
- Drift detected above threshold
- Validation rejected new model
- Slower than usual response time
- Minor resource constraints

**🔵 P4 - Low (Daily digest)**
- New model deployed
- Routine maintenance completed
- Non-critical warnings

### Alert Rules Examples

**Model Performance Degradation**
```yaml
alert: ModelPerformanceDegraded
expr: model_mae > 15
for: 10m
labels:
  severity: high
annotations:
  summary: "Model MAE above threshold"
  description: "MAE is {{ $value }}, threshold is 15"
```

**High Error Rate**
```yaml
alert: HighErrorRate
expr: rate(errors_total[5m]) > 0.05
for: 5m
labels:
  severity: critical
annotations:
  summary: "Error rate above 5%"
```

**Training Failure**
```yaml
alert: TrainingFailed
expr: training_failures_total > 3
for: 1h
labels:
  severity: high
annotations:
  summary: "Multiple training failures detected"
```

### Alert Fatigue Prevention

**❌ Bad Alert (Too noisy)**
```yaml
# Fires on every small fluctuation
alert: MAEIncreased
expr: model_mae > 6.0
```

**✅ Good Alert (Meaningful)**
```yaml
# Only fires on sustained degradation
alert: MAEDegraded
expr: avg_over_time(model_mae[30m]) > 15
for: 10m
```

**Strategies:**
1. **Thresholds** - Set meaningful limits
2. **Duration** - Require sustained issue (`for: 10m`)
3. **Grouping** - Combine related alerts
4. **Routing** - Different severities to different channels

---

## Notification Channels

### Slack Integration

```python
import requests

def send_slack_alert(webhook_url, alert):
    payload = {
        "text": f"🚨 {alert['severity'].upper()}: {alert['title']}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{alert['title']}*\n{alert['description']}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Severity:*\n{alert['severity']}"},
                    {"type": "mrkdwn", "text": f"*Component:*\n{alert['component']}"}
                ]
            }
        ]
    }
    
    requests.post(webhook_url, json=payload)
```

**Example Alert:**
```
🚨 HIGH: Model Performance Degraded
────────────────────────────────
MAE increased from 6.5 to 18.2 (+180%)
Current model: model_20260107_180235
Threshold: 15.0

Severity: high
Component: model_validator
Time: 2026-01-08 10:30:00
────────────────────────────────
Actions:
• View dashboard: http://grafana/d/model-health
• Trigger rollback: POST /orchestrator/rollback
• Check logs: tail -f orchestrator.log
```

### Email Integration

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email_alert(to_emails, alert):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"[{alert['severity'].upper()}] {alert['title']}"
    msg['From'] = 'mlops-alerts@company.com'
    msg['To'] = ', '.join(to_emails)
    
    html = f"""
    <html>
      <body>
        <h2 style="color: {'red' if alert['severity'] == 'critical' else 'orange'}">
          {alert['title']}
        </h2>
        <p>{alert['description']}</p>
        <table>
          <tr><td><b>Severity:</b></td><td>{alert['severity']}</td></tr>
          <tr><td><b>Component:</b></td><td>{alert['component']}</td></tr>
          <tr><td><b>Time:</b></td><td>{alert['timestamp']}</td></tr>
        </table>
        <p><a href="{alert['dashboard_url']}">View Dashboard</a></p>
      </body>
    </html>
    """
    
    msg.attach(MIMEText(html, 'html'))
    
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login('user', 'password')
        server.send_message(msg)
```

---

## SLOs and SLAs

### What's the Difference?

**SLO (Service Level Objective)** - Internal goal
- "We aim for 99.9% uptime"
- "Target P95 latency <100ms"
- Set by engineering team

**SLA (Service Level Agreement)** - Contract with customers
- "We guarantee 99% uptime or you get a refund"
- Legal commitment
- Based on SLOs with buffer

### Defining ML System SLOs

**Availability SLO**
```
Target: 99.9% uptime (monthly)
Error budget: 43 minutes downtime per month

Measurement:
uptime = (total_time - downtime) / total_time
```

**Latency SLO**
```
Target: P95 latency < 100ms
Error budget: 5% of requests can be >100ms

Measurement:
histogram_quantile(0.95, request_duration_bucket)
```

**Accuracy SLO**
```
Target: MAE < 10 µg/m³
Error budget: Can exceed for max 1% of time

Measurement:
avg_over_time(model_mae[30d]) < 10
```

**Data Freshness SLO**
```
Target: Predictions based on data <1 hour old
Error budget: 0.1% can use older data

Measurement:
(now() - data_timestamp) < 3600
```

### Error Budget

**Concept:** How much failure we can tolerate

**99.9% uptime = 0.1% downtime allowed**
- Per month: 43 minutes
- Per week: 10 minutes
- Per day: 86 seconds

**If error budget exhausted:**
- Freeze feature development
- Focus on reliability
- No risky deployments

**Example:**
```python
# Month starts: 100% error budget remaining
# Jan 5: 10 min outage → 23% budget used
# Jan 12: 15 min outage → 58% budget used
# Jan 20: 5 min outage → 69% budget used
# Jan 25: 30 min outage → Budget exceeded! 🚨

# Action: Stop all deployments until next month
```

---

## Health Checks

### Three Types

**1. Liveness Probe** - "Is service alive?"
```python
@app.get("/health/live")
def liveness():
    # Simple: Am I running?
    return {"status": "alive"}
```

**2. Readiness Probe** - "Can service handle traffic?"
```python
@app.get("/health/ready")
def readiness():
    # Check: Can I serve requests?
    if model_loaded and database_connected:
        return {"status": "ready"}
    else:
        raise HTTPException(503, "not ready")
```

**3. Startup Probe** - "Has service finished starting?"
```python
@app.get("/health/startup")
def startup():
    # Check: Has initialization completed?
    if initialization_complete:
        return {"status": "started"}
    else:
        raise HTTPException(503, "still starting")
```

### Comprehensive Health Check

```python
@app.get("/health")
def health_check():
    checks = {
        "model": check_model_loaded(),
        "database": check_database(),
        "disk_space": check_disk_space(),
        "memory": check_memory(),
        "dependencies": check_external_services()
    }
    
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if all_healthy else "unhealthy",
            "checks": checks,
            "timestamp": datetime.now().isoformat()
        }
    )
```

---

## Monitoring Best Practices

### 1. The Four Golden Signals (Google SRE)

**Latency** - Time to serve request
```python
request_duration_seconds{quantile="0.95"} < 0.1
```

**Traffic** - Demand on system
```python
rate(requests_total[5m])
```

**Errors** - Failed requests
```python
rate(errors_total[5m]) / rate(requests_total[5m])
```

**Saturation** - How "full" the system is
```python
memory_usage_percent > 80
```

### 2. USE Method (Brendan Gregg)

**Utilization** - % time resource busy
**Saturation** - Queue depth
**Errors** - Error count

**For every resource:** CPU, Memory, Disk, Network

### 3. RED Method (Tom Wilkie)

**Rate** - Requests per second
**Errors** - Failed requests per second
**Duration** - Latency distribution

**For every service endpoint**

### 4. ML-Specific: MSED Method

**Model Performance** - MAE, R², accuracy
**System Health** - Latency, errors, availability
**Events** - Deployments, rollbacks, training
**Data Quality** - Drift, missing values, freshness

---

## Dashboard Design

### Anti-Patterns

**❌ Dashboard Overload**
- 50+ metrics on one screen
- No clear hierarchy
- Everything is equally important (nothing is)

**❌ Vanity Metrics**
- Total predictions ever: 1,234,567 (so what?)
- Uptime: 100% (for 5 minutes)
- Metrics that don't drive actions

**❌ Missing Context**
- Graph with no units
- Alert with no threshold line
- Current value with no historical baseline

### Best Practices

**✅ At-a-Glance Status**
- Green/Yellow/Red status indicators
- Current vs target clearly shown
- Trends visible

**✅ Actionable Metrics**
- Every metric ties to an action
- Clear "healthy" vs "unhealthy" ranges
- Links to runbooks

**✅ Layered Dashboards**
- **L1:** Executive summary (is everything okay?)
- **L2:** Service-level details (which service has issues?)
- **L3:** Deep dive (what exactly is wrong?)

### Example Dashboard Layout

```
┌─────────────────────────────────────────────────────┐
│  ML System Health Dashboard                         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Overall Status: 🟢 Healthy                         │
│  SLO Compliance: 99.95% (Target: 99.9%)            │
│  Error Budget: 78% remaining                       │
│                                                     │
├─────────────────────────────────────────────────────┤
│  API Health           │  Model Performance          │
│  ──────────           │  ──────────────            │
│  🟢 Latency: 45ms     │  🟢 MAE: 6.5 µg/m³         │
│  🟢 Error Rate: 0.1%  │  🟢 R²: 0.93               │
│  🟢 Requests: 1.2k/s  │  🟢 Drift: 0.18            │
├─────────────────────────────────────────────────────┤
│  Training Pipeline    │  Data Quality               │
│  ────────────────     │  ───────────               │
│  🟡 Last: 2h ago      │  🟢 Freshness: 15min       │
│  🟢 Success: 100%     │  🟢 Missing: 0.01%         │
│  🟢 Duration: 12min   │  🟢 Outliers: 0.02%        │
└─────────────────────────────────────────────────────┘
```

---

## Testing Monitoring

### Verify Alerts Fire

```python
def test_mae_alert():
    # Inject bad MAE
    metrics.set_mae(20.0)  # Above threshold
    
    # Wait for alert evaluation
    time.sleep(65)  # Alert fires after 1 min
    
    # Check alert fired
    alerts = get_active_alerts()
    assert any(a['name'] == 'ModelPerformanceDegraded' for a in alerts)
```

### Load Testing

```bash
# Generate load to test monitoring
hey -n 10000 -c 100 http://localhost:8000/predict

# Verify metrics captured
curl http://localhost:8000/metrics | grep request_duration

# Check dashboard updates
```

---

## Summary

Comprehensive monitoring for ML systems requires:

✅ **Three Pillars** - Metrics, Logs, Traces  
✅ **ML-Specific Metrics** - Model performance, drift, data quality  
✅ **Smart Alerting** - Meaningful thresholds, proper routing  
✅ **SLOs** - Clear targets for reliability  
✅ **Health Checks** - Liveness, readiness, startup  
✅ **Great Dashboards** - At-a-glance status, actionable insights  

**Next:** Implement monitoring system for our self-healing platform!
