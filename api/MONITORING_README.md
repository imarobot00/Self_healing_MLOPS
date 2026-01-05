# Model Performance Monitoring System 📊

> Real-time tracking of prediction accuracy, performance metrics, and automated alerting for the AQI prediction model.

## Overview

This monitoring system tracks every prediction made by the API, compares them with actual values when available, calculates performance metrics, detects degradation, and sends alerts when the model performance drops below acceptable thresholds.

## Features Implemented

### ✅ 1. Prediction Logging
- **Every prediction logged** with:
  - Timestamp
  - Location ID
  - Input features (PM2.5, PM1, temperature, humidity)
  - Predicted AQI
  - Model version used
  - Response time
- Logs saved to daily JSONL files: `logs/predictions/predictions_YYYYMMDD.jsonl`

### ✅ 2. Request Logging
- **All API requests tracked**:
  - Endpoint accessed
  - HTTP method
  - Query parameters
  - Status code
  - Response time
- Logs saved to: `logs/predictions/requests_YYYYMMDD.jsonl`

### ✅ 3. Actual Value Tracking
- Fetches actual AQI values from dataset files
- Matches predictions with actuals by timestamp
- Calculates prediction errors
- Updates prediction logs with actuals

### ✅ 4. Performance Metrics
Calculates rolling metrics from recent predictions:
- **MAE** (Mean Absolute Error) - Average prediction error in AQI points
- **RMSE** (Root Mean Square Error) - Penalizes large errors
- **R² Score** - Coefficient of determination (0-1, higher is better)
- **Coverage Rate** - % of predictions with actual values

### ✅ 5. Performance Degradation Detection
Monitors metrics and triggers alerts when:
- **MAE exceeds 15.0** AQI points (configurable threshold)
- **R² drops below 0.75** (configurable threshold)

### ✅ 6. Alert System
- Automated alerts logged when performance degrades
- Alert types: `MAE_THRESHOLD`, `R2_THRESHOLD`
- Alerts saved to: `logs/metrics/alerts_YYYYMMDD.jsonl`
- Queryable via API

### ✅ 7. Web Dashboard
Beautiful monitoring dashboard at `/monitoring` showing:
- Real-time performance metrics
- Historical metrics chart (MAE & R² over 7 days)
- Recent alerts list
- Total predictions count
- Coverage rate
- Average response time
- Auto-refresh every 30 seconds

## Architecture

```
api/
├── monitoring.py           # PerformanceMonitor class
├── main.py                 # FastAPI app with monitoring integration
└── static/
    └── monitoring.html     # Web dashboard

logs/
├── predictions/
│   ├── predictions_20260105.jsonl    # Daily prediction logs
│   └── requests_20260105.jsonl       # Daily request logs
└── metrics/
    ├── metrics_20260105.jsonl        # Daily metrics calculations
    └── alerts_20260105.jsonl         # Daily alerts
```

## API Endpoints

### Monitoring Endpoints

#### `GET /monitoring/summary`
Get overall monitoring summary with current metrics.

**Response:**
```json
{
  "total_predictions": 150,
  "predictions_with_actuals": 45,
  "coverage_rate": 0.30,
  "recent_metrics": {
    "mae": 8.23,
    "rmse": 12.45,
    "r2": 0.8765,
    "status": "ok"
  },
  "alert_count_24h": 0,
  "avg_response_time_ms": 245.3,
  "monitoring_status": "healthy"
}
```

#### `GET /monitoring/metrics?days=7`
Get historical metrics for the last N days.

**Parameters:**
- `days` (int, default=7): Number of days of history

**Response:**
```json
{
  "metrics": [
    {
      "timestamp": "2026-01-05T12:00:00",
      "mae": 8.23,
      "rmse": 12.45,
      "r2": 0.8765,
      "count": 45,
      "status": "ok"
    }
  ]
}
```

#### `GET /monitoring/predictions?limit=50`
Get recent predictions with their actuals.

**Parameters:**
- `limit` (int, default=50): Number of recent predictions

**Response:**
```json
{
  "predictions": [
    {
      "prediction_id": "6093549_2026-01-05T10:00:00+00:00_1767615882",
      "timestamp": "2026-01-05T18:09:42",
      "location_id": 6093549,
      "forecast_timestamp": "2026-01-05T10:00:00+00:00",
      "predicted_aqi": 185.29,
      "actual_aqi": 178.5,
      "error": 6.79,
      "model_version": "20260105_125547"
    }
  ]
}
```

#### `GET /monitoring/alerts?hours=24`
Get recent alerts.

**Parameters:**
- `hours` (int, default=24): Hours of alert history

**Response:**
```json
{
  "alerts": [
    {
      "timestamp": "2026-01-05T15:30:00",
      "type": "MAE_THRESHOLD",
      "message": "MAE (16.45) exceeds threshold (15.0)",
      "severity": "warning"
    }
  ]
}
```

#### `POST /monitoring/update-actuals`
Trigger update of predictions with actual values from dataset.

**Response:**
```json
{
  "message": "Updating actuals and calculating metrics in background"
}
```

## Usage Workflow

### 1. Normal Operation
The monitoring system runs automatically in the background:
1. Every prediction is logged automatically
2. Request logging via middleware
3. Metrics stored in memory and files

### 2. After Data Collection (Every 2-3 hours)
After pulling new data from git:

```bash
# Pull latest data
git pull origin main

# Update actuals and calculate metrics
curl -X POST http://localhost:8000/monitoring/update-actuals
```

Or use the dashboard button: **"Update Actuals from Dataset"**

### 3. Viewing Monitoring Dashboard
Open in browser:
```
http://localhost:8000/monitoring
```

Features:
- Real-time metrics display
- Performance charts
- Alert notifications
- Auto-refresh every 30 seconds

### 4. Querying Metrics Programmatically

```bash
# Get summary
curl http://localhost:8000/monitoring/summary

# Get last 7 days metrics
curl "http://localhost:8000/monitoring/metrics?days=7"

# Get recent predictions
curl "http://localhost:8000/monitoring/predictions?limit=100"

# Get alerts
curl "http://localhost:8000/monitoring/alerts?hours=48"
```

## Configuration

Thresholds can be configured in `monitoring.py`:

```python
monitor = PerformanceMonitor(
    log_dir="logs/predictions",
    metrics_dir="logs/metrics",
    window_size=100,              # Rolling window for metrics
    alert_threshold_mae=15.0,     # Alert if MAE > 15 AQI points
    alert_threshold_r2=0.75       # Alert if R² < 0.75
)
```

## Monitoring Metrics Explained

### MAE (Mean Absolute Error)
- Average difference between predicted and actual AQI
- **Lower is better**
- Interpretation:
  - < 5: Excellent
  - 5-10: Good
  - 10-15: Acceptable
  - > 15: Poor (triggers alert)

### RMSE (Root Mean Square Error)
- Similar to MAE but penalizes large errors more
- **Lower is better**
- Always ≥ MAE

### R² Score (Coefficient of Determination)
- Measures how well predictions explain variance in actuals
- **Range: 0 to 1, higher is better**
- Interpretation:
  - > 0.9: Excellent
  - 0.75-0.9: Good
  - 0.5-0.75: Moderate
  - < 0.5: Poor

### Coverage Rate
- Percentage of predictions with actual values available
- Shows data freshness and matching success
- **Higher is better** (aim for > 50%)

## Alert Thresholds

### Default Thresholds
- **MAE Threshold**: 15.0 AQI points
  - Reasoning: EPA AQI categories span 50 points, so error > 15 means ~30% category uncertainty
  
- **R² Threshold**: 0.75
  - Reasoning: Below 0.75 means model explains < 75% of variance, indicating poor fit

### When Alerts Trigger
1. **MAE exceeds threshold**:
   - Model predictions drifting from reality
   - Possible causes: Concept drift, seasonal changes, data quality issues
   - Action: Retrain model on recent data

2. **R² below threshold**:
   - Model not capturing underlying patterns
   - Possible causes: New patterns in data, feature drift
   - Action: Review features, retrain model

## Example Monitoring Session

```bash
# 1. Make some predictions
curl "http://localhost:8000/forecast?location_id=6093549&hours=5"

# 2. Check monitoring summary
curl http://localhost:8000/monitoring/summary
# Output:
# {
#   "total_predictions": 5,
#   "predictions_with_actuals": 0,
#   "coverage_rate": 0.0,
#   "monitoring_status": "healthy"
# }

# 3. After data collection (3 hours later), update actuals
curl -X POST http://localhost:8000/monitoring/update-actuals

# 4. Wait a few seconds, then check metrics
curl http://localhost:8000/monitoring/summary
# Output:
# {
#   "total_predictions": 5,
#   "predictions_with_actuals": 3,
#   "coverage_rate": 0.6,
#   "recent_metrics": {
#     "mae": 6.45,
#     "rmse": 9.23,
#     "r2": 0.8832,
#     "status": "ok"
#   },
#   "monitoring_status": "healthy"
# }
```

## Files and Logs

### Prediction Logs
Location: `logs/predictions/predictions_YYYYMMDD.jsonl`

Format (JSONL - one JSON per line):
```json
{
  "prediction_id": "6093549_2026-01-05T10:00:00+00:00_1767615882",
  "timestamp": "2026-01-05T18:09:42.205827",
  "location_id": 6093549,
  "forecast_timestamp": "2026-01-05T10:00:00+00:00",
  "predicted_aqi": 185.29,
  "model_version": "20260105_125547",
  "input_features": {
    "pm25": 38.68,
    "temperature": 25.32,
    "humidity": 28.58
  },
  "response_time_ms": null,
  "actual_aqi": 178.5,
  "error": 6.79
}
```

### Request Logs
Location: `logs/predictions/requests_YYYYMMDD.jsonl`

Format:
```json
{
  "timestamp": "2026-01-05T18:09:42",
  "endpoint": "/forecast",
  "method": "GET",
  "params": {"location_id": "6093549", "hours": "5"},
  "status_code": 200,
  "response_time_ms": 256.3
}
```

### Metrics Logs
Location: `logs/metrics/metrics_YYYYMMDD.jsonl`

Format:
```json
{
  "timestamp": "2026-01-05T18:30:00",
  "mae": 8.23,
  "rmse": 12.45,
  "r2": 0.8765,
  "count": 45,
  "status": "ok"
}
```

### Alert Logs
Location: `logs/metrics/alerts_YYYYMMDD.jsonl`

Format:
```json
{
  "timestamp": "2026-01-05T15:30:00",
  "type": "MAE_THRESHOLD",
  "message": "MAE (16.45) exceeds threshold (15.0)",
  "severity": "warning"
}
```

## Benefits

### 1. Continuous Quality Assurance
- Know exactly how well your model is performing
- Detect degradation before it becomes critical
- Track improvements after retraining

### 2. Data-Driven Decisions
- Metrics show when retraining is needed
- Identify which locations have higher errors
- Understand prediction patterns

### 3. Debugging & Troubleshooting
- Full audit trail of predictions
- Compare predicted vs actual for specific timestamps
- Identify systematic errors

### 4. Compliance & Reporting
- Historical performance records
- SLA monitoring (response times)
- Performance reports for stakeholders

## Integration with Existing Components

### With Forecaster
- Automatically logs every forecast prediction
- Tracks multi-hour predictions individually
- Links predictions to timestamps for later matching

### With Model Retraining
After retraining:
```bash
# 1. Deploy new model
cp training/models/arf_model_*.pkl api/

# 2. Restart API
pkill -f "python3 main.py"
cd api && python3 main.py &

# 3. Monitor new model performance
# Dashboard will show metrics for new model version
```

### With Data Collection Pipeline
Add to scheduler:
```python
# After collecting data
subprocess.run(['curl', '-X', 'POST', 
               'http://localhost:8000/monitoring/update-actuals'])
```

## Future Enhancements

### Planned Features
1. **Email/Slack Alerts**: Send notifications when alerts trigger
2. **A/B Testing**: Compare two model versions side-by-side
3. **Drift Detection**: Automated concept drift detection using ADWIN
4. **Feature Monitoring**: Track feature distributions over time
5. **Model Comparison**: Compare metrics across model versions
6. **Database Backend**: Store logs in PostgreSQL/TimescaleDB
7. **Grafana Integration**: Professional dashboards with Prometheus metrics

### Easy Additions
1. Add more alert thresholds (RMSE, response time, error rate)
2. Export metrics to CSV for analysis
3. Weekly performance reports
4. Per-location performance tracking

## Troubleshooting

### No Predictions With Actuals
**Problem**: `coverage_rate` is 0.0

**Solutions**:
1. Wait for data collection (predictions need to match future data)
2. Check timestamp alignment in dataset
3. Verify location files exist: `dataset/location_*.json`
4. Run manual update: `POST /monitoring/update-actuals`

### Metrics Not Calculating
**Problem**: `recent_metrics` is null

**Solutions**:
1. Need at least 5 predictions with actuals
2. Run: `POST /monitoring/update-actuals`
3. Check logs: `tail -f logs/metrics/metrics_*.jsonl`

### Dashboard Not Loading
**Problem**: Monitoring page shows error

**Solutions**:
1. Check API is running: `curl http://localhost:8000/health`
2. Verify static files: `ls api/static/monitoring.html`
3. Check browser console for errors

## Performance Impact

### Memory Usage
- In-memory buffer: ~100 predictions (configurable via `window_size`)
- Minimal memory footprint: ~1-2 MB

### Disk Usage
- ~1 KB per prediction
- ~500 KB per day with 500 predictions
- Auto-rotation: Daily log files

### CPU Overhead
- Logging: < 1ms per prediction
- Metrics calculation: ~10-50ms (only when requested)
- Request middleware: < 0.5ms per request

### Network Impact
- No external calls
- Local file system only
- Dashboard polling: ~1 KB every 30 seconds

## Summary

The monitoring system provides **complete observability** of your AQI prediction model with:
- ✅ Automatic prediction & request logging
- ✅ Performance metrics tracking (MAE, RMSE, R²)
- ✅ Degradation detection & alerting
- ✅ Beautiful web dashboard
- ✅ Historical trend analysis
- ✅ Zero configuration needed

**Access the dashboard**: http://localhost:8000/monitoring

**Next Steps**: 
- Set up automated data collection schedule
- Configure alert notifications (email/Slack)
- Implement automated retraining triggers based on alerts
