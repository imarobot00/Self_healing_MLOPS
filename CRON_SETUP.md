# Automated Pipeline Setup with Cron

## Overview

This guide configures automated execution of:
1. **Data Pipeline**: Fetches latest AQI data every 2 hours
2. **Prediction Matching**: Matches old predictions with new actual data
3. **Forecast Generation**: Makes new predictions for next 5 hours

## Cron Configuration

### 1. Edit Crontab

```bash
crontab -e
```

### 2. Add Cron Job

```cron
# Run every 2 hours: Fetch data + match predictions + generate forecasts
0 */2 * * * cd "/home/bipul/Bipul/Self Healing MLOps" && \
            cd dataset && python scheduler.py && \
            cd .. && python api/post_pipeline_predict.py >> logs/post_pipeline.log 2>&1
```

**Explanation**:
- `0 */2 * * *`: Run at minute 0 of every 2nd hour (00:00, 02:00, 04:00, etc.)
- `cd dataset && python scheduler.py`: Fetch latest data from OpenAQ API
- `cd .. && python api/post_pipeline_predict.py`: Match old predictions + make new predictions
- `>> logs/post_pipeline.log 2>&1`: Log all output to file

### 3. Alternative: Run Only on Specific Hours

```cron
# Run at 00:00, 06:00, 12:00, 18:00 daily
0 0,6,12,18 * * * cd "/home/bipul/Bipul/Self Healing MLOps" && \
                  cd dataset && python scheduler.py && \
                  cd .. && python api/post_pipeline_predict.py >> logs/post_pipeline.log 2>&1
```

### 4. Create Log Directory

```bash
mkdir -p "/home/bipul/Bipul/Self Healing MLOps/logs"
```

## Verification

### Check Cron is Running

```bash
# View cron jobs
crontab -l

# Check cron service status
sudo systemctl status cron

# Check logs (Ubuntu/Debian)
grep CRON /var/log/syslog | tail -20

# Check logs (CentOS/RHEL)
grep CRON /var/log/cron | tail -20
```

### Monitor Execution

```bash
# Watch the log file in real-time
tail -f "/home/bipul/Bipul/Self Healing MLOps/logs/post_pipeline.log"

# Check recent predictions
ls -lt "/home/bipul/Bipul/Self Healing MLOps/api/logs/predictions/"

# Count today's predictions
cat "/home/bipul/Bipul/Self Healing MLOps/api/logs/predictions/predictions_$(date +%Y%m%d).jsonl" | wc -l
```

## Manual Execution

### Run Complete Pipeline Manually

```bash
cd "/home/bipul/Bipul/Self Healing MLOps"

# Step 1: Fetch latest data
cd dataset && python scheduler.py

# Step 2: Match old predictions + generate new forecasts
cd .. && python api/post_pipeline_predict.py
```

### Run Specific Operations

```bash
# Only match old predictions (no new forecasts)
python api/post_pipeline_predict.py --match-only

# Only specific locations
python api/post_pipeline_predict.py --locations 5509787 6093549

# Custom number of hours to forecast
python api/post_pipeline_predict.py --hours 10
```

## Troubleshooting

### Issue: Cron Job Not Running

**Solution 1: Check Python Environment**
```bash
# Cron may not have same PATH as your shell
# Add Python path explicitly to crontab:
PATH=/usr/local/bin:/usr/bin:/bin

0 */2 * * * cd "/home/bipul/Bipul/Self Healing MLOps" && \
            /usr/bin/python3 dataset/scheduler.py && \
            /usr/bin/python3 api/post_pipeline_predict.py >> logs/post_pipeline.log 2>&1
```

**Solution 2: Use Full Python Path**
```bash
# Find Python path
which python3  # e.g., /usr/bin/python3

# Update crontab with full path
0 */2 * * * cd "/home/bipul/Bipul/Self Healing MLOps" && \
            /usr/bin/python3 dataset/scheduler.py && \
            /usr/bin/python3 api/post_pipeline_predict.py >> logs/post_pipeline.log 2>&1
```

### Issue: API Not Running

Predictions require the FastAPI server to be running:

```bash
# Check if API is running
curl http://localhost:8000/health

# Start API if needed
cd "/home/bipul/Bipul/Self Healing MLOps"
python api/main.py
```

**Better: Run API as System Service**

Create `/etc/systemd/system/aqi-api.service`:
```ini
[Unit]
Description=AQI Prediction API
After=network.target

[Service]
Type=simple
User=bipul
WorkingDirectory=/home/bipul/Bipul/Self Healing MLOps
ExecStart=/usr/bin/python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable aqi-api
sudo systemctl start aqi-api
sudo systemctl status aqi-api
```

### Issue: Permission Denied

```bash
# Make scripts executable
chmod +x dataset/scheduler.py
chmod +x api/post_pipeline_predict.py

# Check log directory permissions
mkdir -p logs
chmod 755 logs
```

### Issue: No Predictions Matched

This is normal for brand new predictions - they'll be matched once actual data arrives (2 hours later).

**Example Timeline**:
```
12:00 PM - Data pipeline runs, fetches data up to 10:00 AM
          - Prediction matcher matches 8:00 AM prediction with 10:00 AM actual
          - Forecaster generates predictions for 11:00 AM - 3:00 PM

2:00 PM  - Data pipeline runs, fetches data up to 12:00 PM
          - Prediction matcher matches 10:00 AM and 12:00 PM predictions
          - Forecaster generates predictions for 1:00 PM - 5:00 PM
```

## Expected Behavior

### Every 2 Hours

1. **Data Pipeline Executes**
   - Fetches latest data from OpenAQ API
   - Updates location JSON files
   - Typically completes in 10-30 seconds

2. **Prediction Matcher Runs**
   - Scans last 7 days of predictions
   - Matches unmatched predictions with newly available actual data
   - Updates prediction logs with actual_aqi and error values
   - Match rate: 30-70% (depends on data availability)

3. **Forecaster Generates New Predictions**
   - Makes predictions for next 5 hours
   - Uses latest available data timestamp (not current time)
   - Logs predictions to daily JSONL files
   - Predictions per run: 50 (10 locations × 5 hours)

### Log Files

Check these files to verify execution:

1. **Post-Pipeline Log**: `logs/post_pipeline.log`
   - Shows complete execution flow
   - Matching statistics
   - Prediction counts

2. **Prediction Logs**: `api/logs/predictions/predictions_YYYYMMDD.jsonl`
   - Each prediction with metadata
   - Matched predictions have actual_aqi filled

3. **Request Logs**: `api/logs/predictions/requests_YYYYMMDD.jsonl`
   - API request details
   - Response times

## Performance Metrics

### Resource Usage
- Memory: ~200-300 MB per execution
- CPU: <10% during execution (30-60 seconds)
- Disk: ~1-2 MB per day (prediction logs)

### Timing
- Data fetch: 10-30 seconds
- Prediction matching: 1-3 seconds
- Forecast generation: 2-5 seconds
- **Total**: 15-40 seconds per execution

### Data Volume
- Predictions per day: ~600 (50 predictions × 12 runs)
- Matched predictions: 200-400 per day (30-70% match rate)
- Log file size: ~1-2 MB per day

## Next Steps

Once automated pipeline is running:

1. **Week 2: Monitor drift and trigger retraining**
   - Check drift scores daily
   - Automatically retrain if drift > 0.15
   - Validate new models before deployment

2. **Week 3: Self-healing loop**
   - Tie drift detection + retraining together
   - Automatic model rollback on validation failure
   - Notification system for model updates

3. **Week 4-6: Containerization**
   - Dockerize all components
   - Deploy to Kubernetes
   - Run on cloud (Azure AKS)

---

**Status**: Ready for automated execution
**Setup Time**: 5 minutes
**Maintenance**: Zero after initial setup
