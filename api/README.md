# 🚀 Air Quality Prediction API

**Production-ready FastAPI service for real-time AQI predictions using Adaptive Random Forest**

## ✅ Status: FULLY OPERATIONAL

Your API is **successfully deployed** and running! 🎉

---

## 📊 What This API Does

Transforms your trained ML model into a **production web service** that can:

1. **Accept HTTP requests** from any application (web, mobile, IoT)
2. **Load your trained ARF model** automatically on startup
3. **Generate 65+ features** from just 5 basic sensor readings
4. **Return instant predictions** (< 100ms response time)
5. **Monitor performance** with Prometheus metrics
6. **Support online learning** through feedback endpoint

---

## 🏃 Quick Start

### 1. Start the API Server

```bash
cd api
python3 main.py
```

The server will start on `http://localhost:8000`

### 2. Access Interactive Documentation

Open your browser and go to:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 3. Test a Prediction

```bash
# Using curl
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "pm25": 65.3,
    "pm1": 48.2,
    "temperature": 12.5,
    "relativehumidity": 72.8,
    "um003": 2340.5
  }'

# Using Python
python3 test_prediction.py
```

---

## 🔌 API Endpoints

### 🎯 **POST /predict** - Make AQI Prediction

Get AQI prediction from sensor readings.

**Request Body:**
```json
{
  "pm25": 45.2,          // PM2.5 concentration (µg/m³)
  "pm1": 32.1,           // PM1 concentration (µg/m³)
  "temperature": 18.5,   // Temperature (°C)
  "relativehumidity": 65.3,  // Humidity (%)
  "um003": 1250.0        // Particle count
}
```

**Response:**
```json
{
  "predicted_aqi": 112.5,
  "aqi_category": "Unhealthy for Sensitive Groups",
  "model_version": "20251215_233922",
  "timestamp": "2026-01-04T21:45:17.965151"
}
```

**AQI Categories:**
- 0-50: Good
- 51-100: Moderate
- 101-150: Unhealthy for Sensitive Groups
- 151-200: Unhealthy
- 201-300: Very Unhealthy
- 300+: Hazardous

### 💚 **GET /health** - Health Check

Check if API is running and model is loaded.

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "model_version": "20251215_233922",
  "uptime_seconds": 123.45
}
```

### 📊 **GET /model/info** - Model Information

Get details about the currently loaded model.

**Response:**
```json
{
  "metadata": {
    "path": "../training/models/arf_model_20251215_233922.pkl",
    "version": "20251215_233922",
    "loaded_at": "2026-01-04T21:45:10.312623"
  },
  "status": "loaded"
}
```

### 🔄 **POST /feedback** - Submit Feedback (Online Learning)

Update model with actual AQI values for continuous improvement.

**Request Body:**
```json
{
  "features": {
    "pm25": 45.2,
    "pm1": 32.1,
    "temperature": 18.5,
    "relativehumidity": 65.3,
    "um003": 1250.0
  },
  "actual_aqi": 115.3
}
```

### 📈 **GET /metrics** - Prometheus Metrics

Get monitoring metrics (total predictions, latency, etc.)

---

## 🧪 Testing

### Run Complete Test Suite

```bash
python3 test_prediction.py
```

This will test:
- ✅ Health check
- ✅ Prediction endpoint
- ✅ Model info endpoint
- ✅ Multiple prediction scenarios

### Manual Testing with curl

```bash
# Good air quality
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{"pm25": 25.0, "pm1": 18.0, "temperature": 18.0, "relativehumidity": 60.0, "um003": 1000.0}'

# Unhealthy air quality
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{"pm25": 120.0, "pm1": 95.0, "temperature": 15.0, "relativehumidity": 75.0, "um003": 4200.0}'
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Client Application                                     │
│  (Web App / Mobile / IoT Device)                        │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP Request
                     │ {pm25, temperature, ...}
                     ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI Server (main.py)                               │
│  - Request validation (Pydantic)                        │
│  - CORS handling                                        │
│  - Metrics tracking (Prometheus)                        │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Model Manager (model_loader.py)                        │
│  - Loads trained ARF model (.pkl)                       │
│  - Manages model versioning                             │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Feature Engineer (feature_engineer.py)                 │
│  - Loads historical data from location JSON files       │
│  - Calculates lag features (1h, 3h, 6h, 12h, 24h)       │
│  - Computes rolling statistics (mean, std, min, max)    │
│  - Generates time-based features (hour, day, month)     │
│  - Creates interaction features                         │
│  - Total: 65+ features from 5 inputs!                   │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  ARF Model (River)                                      │
│  - Trained on 93.2% R² accuracy                         │
│  - Adaptive drift detection (ADWIN)                     │
│  - Online learning capable                              │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼ Prediction
┌─────────────────────────────────────────────────────────┐
│  Response                                               │
│  {predicted_aqi, category, timestamp}                   │
└─────────────────────────────────────────────────────────┘
```

---

## 📦 Components

### 1. **main.py** - FastAPI Application
- Defines all API endpoints
- Handles CORS for cross-origin requests
- Integrates Prometheus metrics
- Manages startup/shutdown events

### 2. **model_loader.py** - Model Management
- Loads trained models from disk
- Manages model versioning
- Handles model switching
- Coordinates prediction pipeline

### 3. **feature_engineer.py** - Feature Generation
- Transforms 5 basic inputs → 65+ features
- Loads historical data for lag features
- Calculates rolling statistics
- Generates cyclical time encodings
- Creates interaction features

### 4. **schemas.py** - Data Validation
- Pydantic models for request/response
- Input validation (ranges, types)
- Documentation examples

### 5. **test_prediction.py** - Test Suite
- Automated testing script
- Tests all endpoints
- Multiple test scenarios

---

## 🚀 Next Steps

### 1. **Production Deployment**

```bash
# Using Docker
docker build -t aqi-api .
docker run -p 8000:8000 aqi-api

# Using systemd (Linux service)
sudo systemctl enable aqi-api
sudo systemctl start aqi-api
```

### 2. **Add Monitoring**

The API already exposes Prometheus metrics at `/metrics`. Set up:
- Prometheus to scrape metrics
- Grafana for visualization dashboards

### 3. **Implement Drift Detection**

Add automatic retraining when model performance degrades:
```python
# Check prediction accuracy
if accuracy < threshold:
    trigger_retraining()
```

### 4. **Scale Up**

Deploy on Kubernetes with multiple replicas:
```bash
kubectl apply -f k8s/api-deployment.yaml
kubectl scale deployment aqi-api --replicas=3
```

---

## 🎯 Use Cases

### 1. **Web Dashboard**
```javascript
// React/Vue app
fetch('http://your-server.com:8000/predict', {
  method: 'POST',
  body: JSON.stringify(sensorData)
})
.then(res => res.json())
.then(data => displayAQI(data.predicted_aqi))
```

### 2. **Mobile App**
```kotlin
// Android
val retrofit = Retrofit.Builder()
    .baseUrl("http://your-server.com:8000")
    .build()
val prediction = api.predict(sensorData)
```

### 3. **IoT Device**
```python
# Raspberry Pi with air quality sensor
import requests
response = requests.post(
    'http://api-server:8000/predict',
    json=read_sensors()
)
```

### 4. **Automated Alerts**
```python
# Check AQI every hour
aqi = get_prediction()
if aqi > 150:
    send_alert("Air quality unhealthy!")
```

---

## ⚙️ Configuration

### Environment Variables

Create `.env` file:
```bash
MODEL_PATH=../training/models/arf_model_20251215_233922.pkl
API_PORT=8000
LOG_LEVEL=INFO
ENABLE_CORS=true
```

### Change Port

```python
# In main.py
uvicorn.run(app, host="0.0.0.0", port=8080)  # Changed to 8080
```

---

## 🐛 Troubleshooting

### API won't start
```bash
# Check if port 8000 is already in use
lsof -i :8000
kill -9 <PID>

# Check logs
tail -f /tmp/api.log
```

### Model not found
```bash
# Verify model exists
ls -lh ../training/models/

# Update path in model_loader.py if needed
```

### Predictions all the same
- This happens when historical data is missing
- The feature engineer falls back to current values
- Solution: Run data pipeline to collect more historical data

### CORS errors in browser
- Already configured in `main.py`
- Change `allow_origins=["*"]` to specific domains if needed

---

## 📚 Learn More

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Pydantic**: https://docs.pydantic.dev/
- **River (ML)**: https://riverml.xyz/
- **Prometheus Metrics**: https://prometheus.io/

---

## 🎉 Success!

Your ML model is now a production API! You've completed:

✅ Data Pipeline (automated collection)  
✅ Model Training (93.2% R² accuracy)  
✅ **API Deployment** ← **YOU ARE HERE**  

Next: Add drift detection and auto-retraining for full self-healing MLOps! 🚀
