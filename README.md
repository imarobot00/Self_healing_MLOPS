# 🌍 Self-Healing MLOps Pipeline

A production-ready, self-healing machine learning system for **Air Quality Index (AQI) forecasting** in Kathmandu Valley. The system automatically monitors model performance, detects degradation, and triggers retraining when needed.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Docker](https://img.shields.io/badge/Docker-Containerized-blue)
![Prometheus](https://img.shields.io/badge/Prometheus-Monitoring-orange)
![Grafana](https://img.shields.io/badge/Grafana-Dashboards-green)
![River ML](https://img.shields.io/badge/River_ML-ARF-purple)
![OpenAQ](https://img.shields.io/badge/OpenAQ-Data_Source-teal)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-CI/CD-black)

## 🎯 Features

- **Real-time AQI Forecasting** - 5-hour ahead predictions using Adaptive Random Forest
- **Self-Healing Pipeline** - Automatic retraining when model accuracy degrades
- **Multi-Location Support** - 10 monitoring stations across Kathmandu Valley
- **Live Data Integration** - Fetches real-time data from OpenAQ API
- **Production Monitoring** - Prometheus metrics + Grafana dashboards
- **Containerized Deployment** - Docker Compose orchestration

## 📍 Monitored Locations

| ID | Location | Status |
|----|----------|--------|
| 5509787 | Baluwatar | ✅ Active |
| 6142022 | Mid Baneshwor | ✅ Active |
| 6133623 | Jadibuti | ✅ Active |
| 6093549 | Golfutar | ✅ Active |
| 6093550 | Tankeshwor | ✅ Active |
| 6093551 | Teku | ✅ Active |
| 6142174 | Ranibari | ✅ Active |
| 6142175 | Sorakhutte | ✅ Active |
| 5506835 | Gaushala Chowk | ✅ Active |
| 3459 | Ratna Park | ✅ Active |

## 🤖 The Model - Adaptive Random Forest (ARF)

| Attribute | Details |
|-----------|---------|
| **Algorithm** | Adaptive Random Forest (ARF) |
| **Library** | River ML |
| **Type** | Online/Incremental Learning |
| **Training Data** | 32,000+ samples |
| **Features** | 62 engineered features |
| **Target** | AQI (Air Quality Index) |

### Why Adaptive Random Forest?

- **Handles Concept Drift**: Automatically adapts to changing data patterns in air quality
- **Online Learning**: Learns incrementally from streaming data without full retraining
- **Memory Efficient**: Doesn't need to store entire dataset in memory
- **Robust**: Ensemble method provides stable predictions

### Feature Engineering (62 Features)

| Category | Features |
|----------|----------|
| **Lag Features** | 1h, 2h, 3h, 6h, 12h, 24h previous values |
| **Rolling Statistics** | Mean, Std, Min, Max over various windows |
| **Cyclical Time** | Hour (sin/cos), Day (sin/cos), Month (sin/cos) |
| **Interaction Features** | Cross-feature combinations |
| **Location Encoding** | Station-specific identifiers |

## 📡 Data Pipeline

### Data Source: OpenAQ API

- **Source**: [OpenAQ](https://openaq.org/) - Open Air Quality Data
- **Coverage**: 10 monitoring stations in Kathmandu Valley
- **Parameters**: PM2.5, PM1, Temperature, Humidity
- **Update Frequency**: Hourly measurements

### Automated Data Collection with GitHub Actions

```yaml
# .github/workflows/fetch_data.yml
# Runs on schedule to fetch latest air quality data from OpenAQ
```

- **Scheduled Workflow**: Automatically fetches new data from OpenAQ API
- **Storage**: Data stored in repository as JSON files
- **Usage**: Pull latest data before prediction evaluation

### Data Flow

```
OpenAQ API → GitHub Actions (scheduled fetch) → Repository → 
Git Pull → Preprocessing → Model Training/Evaluation
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Self-Healing MLOps                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐ │
│  │   OpenAQ    │───▶│   Dataset   │───▶│    Preprocessing        │ │
│  │    API      │    │   Fetcher   │    │    Pipeline             │ │
│  └─────────────┘    └─────────────┘    └───────────┬─────────────┘ │
│                                                     │               │
│                                                     ▼               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Docker Containers                         │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│  │  │  mlops-api  │  │  mlops-     │  │  mlops-orchestrator │  │   │
│  │  │   :8000     │  │  training   │  │       :8002         │  │   │
│  │  │             │  │   :8001     │  │                     │  │   │
│  │  │ • Forecast  │  │ • Auto      │  │ • Monitor MAE       │  │   │
│  │  │ • Predict   │  │   Trainer   │  │ • Trigger Retrain   │  │   │
│  │  │ • Evaluate  │  │ • Retrain   │  │ • Health Checks     │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │   │
│  │         │                │                     │             │   │
│  │         └────────────────┴─────────────────────┘             │   │
│  │                          │                                   │   │
│  │                   Shared /models Volume                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Monitoring Stack                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│  │  │ Prometheus  │  │   Grafana   │  │    Alertmanager     │  │   │
│  │  │   :9090     │  │   :3001     │  │       :9093         │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Git
- 4GB+ RAM recommended

### 1. Clone the Repository

```bash
git clone https://github.com/imarobot00/Self_healing_MLOPS.git
cd Self_healing_MLOPS
```

### 2. Start the Monitoring Stack

```bash
cd monitoring
docker compose up -d
cd ..
```

### 3. Start the MLOps Services

```bash
docker compose -f docker-compose.mlops.yml up -d
```

### 4. Verify All Services

```bash
# Check container status
docker ps

# Verify API health
curl http://localhost:8000/health
```

### 5. Access the UI

- **Forecast UI**: http://localhost:8000/forecast
- **Grafana Dashboard**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9090

## 📡 API Endpoints

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health check |
| `/predict` | POST | Single prediction |
| `/forecast/{location_id}` | GET | 5-hour forecast |
| `/locations` | GET | List all locations |

### Monitoring Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/prediction-accuracy` | GET | Accuracy metrics by location |
| `/retraining-status` | GET | Check if retraining needed |
| `/evaluate-predictions` | POST | Compare predictions vs actuals |
| `/reload-model` | POST | Manually reload latest model |
| `/trigger-retraining` | POST | Manually trigger retraining |
| `/metrics` | GET | Prometheus metrics |

### Example: Get Forecast

```bash
# Get 5-hour forecast for Baluwatar
curl "http://localhost:8000/forecast/5509787?hours=5"
```

### Example: Check Retraining Status

```bash
curl http://localhost:8000/retraining-status
```

Response:
```json
{
  "retraining_required": "YES",
  "severity": "HIGH",
  "overall_mae": 26.79,
  "poor_locations": [
    {"location": "6093549", "mae": 52.27, "samples": 8}
  ],
  "thresholds": {
    "mae_warning": 25.0,
    "mae_critical": 35.0
  }
}
```

## 🔄 Self-Healing Workflow

```
1. Make Predictions
       │
       ▼
2. Save to forecast_predictions.jsonl
       │
       ▼
3. GitHub Actions fetches new data from OpenAQ (scheduled)
       │
       ▼
4. Git Pull (new actual data arrives)
       │
       ▼
5. POST /evaluate-predictions
       │
       ▼
6. Calculate MAE per location
       │
       ▼
7. Orchestrator checks /retraining-status (every 3 min)
       │
       ▼
8. If MAE > threshold → Trigger Retraining (ARF model)
       │
       ▼
9. New model saved to /models
       │
       ▼
10. API auto-reloads new model (every 60 sec)
       │
       ▼
11. Back to step 1
```

## 📊 Prometheus Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `prediction_requests_total` | Counter | Total predictions made |
| `prediction_latency_seconds` | Histogram | Prediction response time |
| `model_overall_mae` | Gauge | Current model MAE |
| `retraining_required` | Gauge | 1 if retraining needed |
| `retraining_severity` | Gauge | 0=none, 1=medium, 2=high |
| `prediction_error_aqi` | Gauge | Per-location error |

## 📁 Project Structure

```
Self Healing MLOps/
├── api/                          # Prediction API service
│   ├── main.py                   # FastAPI application
│   ├── model_loader.py           # Model loading with auto-reload
│   ├── forecaster.py             # Forecasting logic
│   ├── prediction_tracker.py     # Save & evaluate predictions
│   ├── Dockerfile
│   ├── static/                   # Web UI files
│   │   ├── forecast.html         # Main forecast UI
│   │   └── monitoring.html       # Monitoring dashboard
│   └── logs/predictions/         # Prediction logs
│
├── training/                     # Training service
│   ├── training.py               # Model training logic
│   ├── retrain_model.py          # Retraining script
│   ├── run_training_service.py   # Long-running daemon
│   ├── run_orchestrator_service.py # Orchestrator daemon
│   ├── Dockerfile
│   └── models/                   # Trained models
│
├── dataset/                      # Data collection
│   ├── fetch_openaq_location.py  # OpenAQ data fetcher
│   ├── merge_data.py             # Data merging
│   ├── data_preprocessor.py      # Preprocessing pipeline
│   ├── location_*.json           # Raw data files (from OpenAQ)
│   └── preprocessed/             # Processed datasets
│       ├── train_data.csv
│       └── test_data.csv
│
├── .github/workflows/            # GitHub Actions
│   └── fetch_data.yml            # Scheduled data collection
│
├── monitoring/                   # Monitoring stack
│   ├── docker-compose.yml
│   ├── prometheus/
│   └── grafana/
│
├── docker-compose.mlops.yml      # MLOps services
└── README.md                     # This file
```

## 🛠️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_PATH` | `/models` | Path to model files |
| `DATA_PATH` | `/data` | Path to training data |
| `API_PORT` | `8000` | API service port |
| `TRAINING_CHECK_INTERVAL` | `300` | Training check interval (sec) |
| `DRIFT_THRESHOLD` | `0.15` | Data drift threshold |

### Retraining Thresholds

| Threshold | Value | Description |
|-----------|-------|-------------|
| `MAE_WARNING` | 25.0 | Triggers MEDIUM severity |
| `MAE_CRITICAL` | 35.0 | Triggers HIGH severity |
| `MIN_SAMPLES` | 10 | Min samples before evaluation |

## 🔧 Common Operations

### View Logs

```bash
# API logs
docker logs -f mlops-api

# Training logs
docker logs -f mlops-training

# Orchestrator logs
docker logs -f mlops-orchestrator
```

### Manual Retraining

```bash
docker exec mlops-training python /training/retrain_model.py
```

### Force Model Reload

```bash
curl -X POST http://localhost:8000/reload-model
```

### Pull New Data & Evaluate

```bash
git pull origin main
curl -X POST http://localhost:8000/evaluate-predictions
```

### Stop All Services

```bash
docker compose -f docker-compose.mlops.yml down
cd monitoring && docker compose down
```

## 📈 Model Information

- **Algorithm**: Adaptive Random Forest (River ML)
- **Features**: 62 engineered features
- **Target**: AQI (Air Quality Index)
- **Training**: Incremental online learning
- **Data**: ~32K+ samples from OpenAQ

### Feature Engineering

- Lag features (1h, 2h, 3h, 6h, 12h, 24h)
- Rolling statistics (mean, std, min, max)
- Time-based features (hour, day, month, cyclical)
- Interaction features
- Location encoding

## 🐛 Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs mlops-api

# Rebuild image
docker compose -f docker-compose.mlops.yml build mlops-api
docker compose -f docker-compose.mlops.yml up -d mlops-api
```

### Model Not Loading

```bash
# List available models
ls -lh training/models/*.pkl

# Force reload
curl -X POST http://localhost:8000/reload-model
```

### High Prediction Errors

```bash
# Check accuracy
curl http://localhost:8000/prediction-accuracy

# Check retraining status
curl http://localhost:8000/retraining-status

# Manual retrain
docker exec mlops-training python /training/retrain_model.py
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 🙏 Acknowledgments

- **[OpenAQ](https://openaq.org/)** - For providing open air quality data
- **[River ML](https://riverml.xyz/)** - For the Adaptive Random Forest implementation
- **[FastAPI](https://fastapi.tiangolo.com/)** - For the excellent API framework

## 👤 Author

**Bipul**

- GitHub: [@imarobot00](https://github.com/imarobot00)

---

Built with ❤️ for cleaner air in Kathmandu Valley 🏔️

Built with ❤️ for cleaner air in Kathmandu Metrpolitian city 🏔️
