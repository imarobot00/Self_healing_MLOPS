# Data Pipeline

Automated 2-hour interval data loading pipeline for OpenAQ air quality measurements.

## Overview

This pipeline automatically fetches air quality measurements from the OpenAQ API every 2 hours, performs incremental loading with deduplication, validates data quality, and stores results in JSON files. It includes comprehensive monitoring, alerting, and multiple deployment options.

## Features

- ✅ **Incremental Loading**: Fetches only new data since last run using state tracking
- ✅ **Deduplication**: Automatically removes duplicate measurements
- ✅ **Data Validation**: Schema validation and value range checking
- ✅ **Monitoring**: Structured logging and metrics collection
- ✅ **Alerting**: Slack/webhook notifications for failures
- ✅ **Multiple Deployment Options**: Docker, GitHub Actions, or local scheduling
- ✅ **Automatic Recovery**: Tracks consecutive failures and sends alerts

## Quick Start

### Option 1: Docker (Recommended for Production)

1. **Setup environment**:
```bash
cp dataset/.env.example dataset/.env
# Edit dataset/.env and add your OPENAQ_API_KEY
```

2. **Run with Docker Compose**:
```bash
docker-compose up -d
```

3. **View logs**:
```bash
docker-compose logs -f data-pipeline
```

### Option 2: GitHub Actions (Cloud-Native)

1. **Add repository secrets**:
   - Go to Settings → Secrets → Actions
   - Add `OPENAQ_API_KEY` (required)
   - Add `SLACK_WEBHOOK_URL` (optional for alerts)

2. **Enable workflow**:
   - The workflow runs automatically every 2 hours
   - Manual trigger: Actions → "Data Pipeline - Scheduled Run" → Run workflow

### Option 3: Local Scheduling

1. **Install dependencies**:
```bash
cd dataset
pip install -r requirements.txt
```

2. **Configure**:
```bash
# Edit config.yaml to set location IDs
nano config.yaml

# Set API key (optional)
export OPENAQ_API_KEY="your_api_key_here"
```

3. **Run scheduler**:
```bash
# Start 2-hour interval scheduler
python scheduler.py --mode interval --interval 2

# Or use cron scheduling
python scheduler.py --mode cron --cron "0 */2 * * *"

# Or run once
python scheduler.py --mode once
```

## Components

### Core Modules

- **`incremental_loader.py`**: Fetches new measurements with state tracking
- **`scheduler.py`**: APScheduler-based task scheduling
- **`validator.py`**: Data quality validation
- **`monitor.py`**: Logging, metrics, and alerting
- **`config.yaml`**: Pipeline configuration
- **`.state.json`**: Tracks last fetch timestamps (auto-generated)

### Manual Usage

```bash
# Incremental loading for multiple locations
python incremental_loader.py --locations 3459 6093549 6093550

# Reset state and fetch all data
python incremental_loader.py --locations 3459 --reset-state

# Validate data quality
python validator.py --file location_3459.json --sample 1000

# Test monitoring components
python monitor.py
```

## Configuration

Edit `dataset/config.yaml`:

```yaml
# Locations to monitor
locations:
  - 3459
  - 6093549
  # ... add more

# Schedule interval
schedule:
  interval_hours: 2

# Validation rules
validation:
  enabled: true
  parameter_ranges:
    pm25: [0, 1000]
    # ... configure ranges

# Monitoring
monitoring:
  log_level: INFO
  alerts:
    max_consecutive_failures: 3

# Notifications
notifications:
  enabled: true
  slack:
    enabled: true
```

## Data Flow

```
┌─────────────┐
│  Scheduler  │ (Every 2 hours)
└──────┬──────┘
       │
       v
┌──────────────────┐
│ Incremental      │
│ Loader           │──→ Check .state.json for last fetch time
│                  │──→ Fetch new data from OpenAQ API
│                  │──→ Deduplicate against existing data
│                  │──→ Append to location_*.json files
│                  │──→ Update .state.json
└──────┬───────────┘
       │
       v
┌──────────────────┐
│ Validator        │──→ Schema validation
│                  │──→ Value range checks
│                  │──→ Generate quality metrics
└──────┬───────────┘
       │
       v
┌──────────────────┐
│ Monitor          │──→ Log events
│                  │──→ Track metrics
│                  │──→ Send alerts on failure
└──────────────────┘
```

## Output Files

- `location_{id}.json` - Measurement data for each location
- `.state.json` - Last fetch timestamps and run metadata
- `pipeline.log` - Execution logs
- `metrics.json` - Historical metrics (last 100 runs)

## Monitoring & Alerts

### Metrics Tracked
- Records fetched per run
- Duplicate records removed
- Data quality scores
- API response times
- Pipeline duration
- Consecutive failures

### Alert Triggers
- 3+ consecutive failures
- Data quality < 90%
- API response time > 60s

### Alert Channels
- Slack (webhook)
- Email (SMTP)
- Custom webhook

## Deployment Options Comparison

| Feature | Docker | GitHub Actions | Local Scheduler |
|---------|--------|----------------|-----------------|
| Always-on | ✅ | ✅ | ⚠️ Requires running machine |
| Resource usage | Medium | Free (GitHub) | Low |
| Setup complexity | Low | Very Low | Medium |
| Customization | High | Medium | High |
| Best for | VMs, servers | Small datasets | Development |

## Troubleshooting

### Pipeline not running
```bash
# Check scheduler status
docker-compose logs data-pipeline

# Check GitHub Actions workflow runs
# Go to Actions tab in GitHub repository
```

### No new data fetched
```bash
# Check state file
cat dataset/.state.json

# Reset state to refetch all data
python incremental_loader.py --reset-state --locations 3459
```

### Data quality issues
```bash
# Run validation with detailed report
python validator.py --file location_3459.json --output validation_report.txt

# Check for API issues
curl -H "X-API-Key: YOUR_KEY" "https://api.openaq.org/v3/locations/3459"
```

### High memory usage
```bash
# Reduce locations in config.yaml
# Process locations sequentially instead of parallel
# Increase Docker memory limit in docker-compose.yml
```

## Development

### Running Tests
```bash
cd dataset

# Test incremental loader
python incremental_loader.py --locations 3459 --data-dir ./test_data

# Test validator
python validator.py --file location_3459.json --sample 100

# Test scheduler (once)
python scheduler.py --mode once
```

### Adding New Locations

1. Find location ID from OpenAQ: https://explore.openaq.org/
2. Add to `config.yaml`:
```yaml
locations:
  - 3459
  - YOUR_NEW_LOCATION_ID
```
3. Run pipeline to fetch initial data

### Custom Alert Handlers

Edit `monitor.py` to add custom alert methods:
```python
def _send_custom_alert(self, alert: Dict):
    # Your custom alert logic
    pass
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAQ_API_KEY` | Optional | OpenAQ API key (uses fallback if not set) |
| `SLACK_WEBHOOK_URL` | Optional | Slack incoming webhook URL |
| `WEBHOOK_URL` | Optional | Custom webhook endpoint |
| `LOG_LEVEL` | Optional | Logging level (default: INFO) |
| `ENVIRONMENT` | Optional | Environment name (development/production) |

## Performance

- **Memory**: ~200-500MB depending on data volume
- **CPU**: Minimal, spikes during data processing
- **Network**: ~1-10MB per location per run (varies)
- **Storage**: ~1-5MB per location per month

## License

This project is part of the Self Healing MLOps system.

## Support

For issues or questions:
1. Check logs: `docker-compose logs data-pipeline` or `cat dataset/pipeline.log`
2. Review metrics: `cat dataset/metrics.json`
3. Open an issue in the GitHub repository
