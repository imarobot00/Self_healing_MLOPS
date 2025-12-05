# Data Pipeline - Command Cheat Sheet

## 🚀 Quick Start

```bash
# Option 1: Docker (easiest)
./quickstart.sh docker

# Option 2: Local scheduler
./quickstart.sh local

# Option 3: Run once
./quickstart.sh once
```

## 📦 Docker Commands

```bash
# Start pipeline
docker-compose up -d

# View logs (live)
docker-compose logs -f data-pipeline

# Stop pipeline
docker-compose down

# Restart
docker-compose restart data-pipeline

# Rebuild after code changes
docker-compose up -d --build

# Check status
docker-compose ps

# Shell into container
docker-compose exec data-pipeline bash
```

## 🔄 Pipeline Operations

```bash
cd dataset

# Fetch data once (single location)
python incremental_loader.py --locations 3459

# Fetch data for multiple locations
python incremental_loader.py --locations 3459 6093549 6093550

# Reset state and refetch all data
python incremental_loader.py --locations 3459 --reset-state

# Start scheduler (2-hour interval)
python scheduler.py --mode interval --interval 2

# Start scheduler (cron - every 2 hours at minute 0)
python scheduler.py --mode cron --cron "0 */2 * * *"

# Run pipeline once (no scheduling)
python scheduler.py --mode once

# Custom interval (every 6 hours)
python scheduler.py --mode interval --interval 6
```

## ✅ Validation & Testing

```bash
cd dataset

# Run component tests
python test_pipeline.py

# Validate specific file
python validator.py --file location_3459.json

# Validate with sampling (faster)
python validator.py --file location_3459.json --sample 1000

# Save validation report
python validator.py --file location_3459.json --output report.txt

# Test monitoring
python monitor.py
```

## 📊 Data Inspection

```bash
cd dataset

# View state (last fetch times)
cat .state.json | python -m json.tool

# Check data file sizes
ls -lh location_*.json

# Count records in a file
cat location_3459.json | python -c "import json, sys; print(len(json.load(sys.stdin)))"

# View last 10 records
cat location_3459.json | python -c "import json, sys; print(json.dumps(json.load(sys.stdin)[-10:], indent=2))"

# Check logs
tail -f pipeline.log

# View metrics history
cat metrics.json | python -m json.tool
```

## 🔧 Configuration

```bash
# Edit locations and settings
nano dataset/config.yaml

# Setup environment variables
cp dataset/.env.example dataset/.env
nano dataset/.env

# Set API key for current session
export OPENAQ_API_KEY="your_key_here"

# Set Slack webhook
export SLACK_WEBHOOK_URL="https://hooks.slack.com/..."
```

## 🐛 Troubleshooting

```bash
# Check Python dependencies
cd dataset && pip list | grep -E "requests|APScheduler|PyYAML"

# Test API connectivity
curl -H "X-API-Key: YOUR_KEY" "https://api.openaq.org/v3/locations/3459"

# Check for syntax errors
python -m py_compile dataset/incremental_loader.py

# View recent errors in logs
tail -n 100 dataset/pipeline.log | grep ERROR

# Clear state (fresh start)
rm dataset/.state.json

# Remove all data files (CAUTION)
rm dataset/location_*.json
```

## 📈 GitHub Actions

```bash
# View workflow runs
# Go to: https://github.com/imarobot00/Self_healing_MLOPS/actions

# Trigger manual run
# Actions → "Data Pipeline - Scheduled Run" → Run workflow

# Add API key secret
# Settings → Secrets → Actions → New repository secret
# Name: OPENAQ_API_KEY
# Value: your_key_here

# View workflow logs
gh run list --workflow=data-pipeline.yml
gh run view <run-id> --log
```

## 🛠️ Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
cd dataset
pip install -r requirements.txt

# Add new dependency
pip install <package>
pip freeze | grep <package> >> requirements.txt

# Format code (optional)
pip install black
black dataset/*.py

# Lint code (optional)
pip install pylint
pylint dataset/*.py
```

## 🔑 Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAQ_API_KEY` | No | Built-in key | OpenAQ API key |
| `SLACK_WEBHOOK_URL` | No | None | Slack webhook for alerts |
| `WEBHOOK_URL` | No | None | Custom webhook endpoint |
| `LOG_LEVEL` | No | INFO | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `ENVIRONMENT` | No | production | Environment name |

## 📁 File Locations

```
dataset/
├── config.yaml              # Pipeline configuration
├── .env                     # Environment variables (create from .env.example)
├── .state.json              # State tracking (auto-generated)
├── location_*.json          # Data files (auto-generated)
├── pipeline.log             # Execution logs (auto-generated)
├── metrics.json             # Metrics history (auto-generated)
├── incremental_loader.py    # Main data loader
├── scheduler.py             # Scheduling service
├── validator.py             # Data validation
├── monitor.py               # Logging & metrics
└── test_pipeline.py         # Component tests
```

## 🎯 Common Workflows

### Initial Setup
```bash
# 1. Clone repo
git clone https://github.com/imarobot00/Self_healing_MLOPS.git
cd Self_healing_MLOPS

# 2. Configure
cp dataset/.env.example dataset/.env
nano dataset/.env  # Add API key

# 3. First run
./quickstart.sh once

# 4. Start scheduler
./quickstart.sh docker  # or 'local'
```

### Daily Operations
```bash
# Check pipeline status
docker-compose ps

# View recent logs
docker-compose logs --tail=100 data-pipeline

# Check data updates
ls -lt dataset/location_*.json | head
```

### Debugging Issues
```bash
# 1. Check logs
tail -f dataset/pipeline.log

# 2. Check metrics
cat dataset/metrics.json | python -m json.tool | grep -A 10 '"errors"'

# 3. Test components
./quickstart.sh test

# 4. Run once manually
./quickstart.sh once

# 5. Validate data quality
./quickstart.sh validate
```

### Updating Code
```bash
# 1. Pull changes
git pull origin main

# 2. Rebuild Docker
docker-compose down
docker-compose up -d --build

# 3. Check logs
docker-compose logs -f data-pipeline
```

## 💡 Tips

- **Test before deploying**: Always run `./quickstart.sh test` after changes
- **Monitor logs**: Use `docker-compose logs -f` to watch real-time execution
- **State management**: `.state.json` tracks progress - back it up!
- **Data validation**: Run validation regularly to catch quality issues
- **Alert configuration**: Set up Slack/email for production monitoring
- **Resource limits**: Adjust Docker memory/CPU in `docker-compose.yml`
- **Scheduling**: GitHub Actions is free but Docker gives more control

## 🔗 Useful Links

- OpenAQ API Docs: https://docs.openaq.org/
- OpenAQ Explorer: https://explore.openaq.org/
- APScheduler Docs: https://apscheduler.readthedocs.io/
- Docker Compose Docs: https://docs.docker.com/compose/
- GitHub Actions Docs: https://docs.github.com/en/actions
