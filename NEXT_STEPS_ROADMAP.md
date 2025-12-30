# 🚀 Self-Healing MLOps: Complete Implementation Roadmap

**Current Date**: December 30, 2025  
**Project Status**: Data Pipeline ✅ | ML Training ✅ | **Production Deployment** 🔨

---

## 📍 Where You Are Now

### ✅ Completed Components

1. **Automated Data Pipeline** (100% Complete)
   - ✅ Fetches OpenAQ data every 2 hours
   - ✅ Incremental loading with state tracking
   - ✅ Data validation and quality checks
   - ✅ Monitoring and alerting
   - ✅ Docker + GitHub Actions deployment
   - **Location**: `dataset/`

2. **ML Model Training** (100% Complete)
   - ✅ Adaptive Random Forest with ADWIN drift detection
   - ✅ **93.2% R² score** on test set (Excellent!)
   - ✅ MAE: 4.31 AQI points (Very Good!)
   - ✅ 12 drift events detected during training
   - ✅ Online learning capability (`learn_one()`)
   - ✅ Model serialization with dill
   - **Location**: `training/models/`

### 🎯 What's Missing

You have **data collection** and **model training**, but no way to:
- Actually USE the model for predictions
- Monitor model performance in production
- Auto-retrain when things break
- Serve predictions to users/applications

**The self-healing part doesn't exist yet!**

---

## 🎯 Phase 1: Model Deployment (START HERE)

### Goal: Make Your Model Accessible

Build a REST API that serves predictions from your trained ARF model.

### 1.1 Create Prediction API

**What to Build:**

```
api/
├── main.py                 # FastAPI application
├── model_loader.py         # Load and manage models
├── schemas.py              # Request/response models
├── config.py               # API configuration
├── utils.py                # Helper functions
├── requirements.txt        # API dependencies
├── Dockerfile              # Container for API
└── test_api.py            # API tests
```

**Implementation Steps:**

#### Step 1: Create API Directory Structure

```bash
mkdir -p api
cd api
```

#### Step 2: Create `api/requirements.txt`

```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
dill==0.3.7
river==0.20.0
pandas==2.1.4
numpy==1.26.2
python-dotenv==1.0.0
prometheus-client==0.19.0
```

#### Step 3: Create `api/schemas.py`

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class PredictionRequest(BaseModel):
    """Input features for AQI prediction"""
    pm25: float = Field(..., ge=0, le=1000, description="PM2.5 in µg/m³")
    pm1: float = Field(..., ge=0, le=1000, description="PM1 in µg/m³")
    temperature: float = Field(..., ge=-50, le=60, description="Temperature in °C")
    relativehumidity: float = Field(..., ge=0, le=100, description="Humidity in %")
    um003: Optional[float] = Field(None, description="Particle count")
    
    # Time-based features (if your model uses them)
    hour: Optional[int] = Field(None, ge=0, le=23)
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    month: Optional[int] = Field(None, ge=1, le=12)
    
    class Config:
        json_schema_extra = {
            "example": {
                "pm25": 45.2,
                "pm1": 32.1,
                "temperature": 18.5,
                "relativehumidity": 65.3,
                "um003": 1250.0,
                "hour": 14,
                "day_of_week": 1,
                "month": 12
            }
        }

class PredictionResponse(BaseModel):
    """AQI prediction output"""
    predicted_aqi: float
    aqi_category: str
    confidence: Optional[float] = None
    model_version: str
    timestamp: datetime
    
class HealthResponse(BaseModel):
    """API health check"""
    status: str
    model_loaded: bool
    model_version: str
    uptime_seconds: float

class FeedbackRequest(BaseModel):
    """Feedback for online learning"""
    features: PredictionRequest
    actual_aqi: float
    prediction_id: Optional[str] = None
```

#### Step 4: Create `api/model_loader.py`

```python
import dill
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ModelManager:
    """Manages loading, versioning, and switching of ML models"""
    
    def __init__(self, models_dir: str = "../training/models"):
        self.models_dir = Path(models_dir)
        self.current_model = None
        self.model_metadata = {}
        
    def load_latest_model(self):
        """Load the most recent model"""
        model_files = sorted(self.models_dir.glob("arf_model_*.pkl"))
        
        if not model_files:
            raise FileNotFoundError(f"No models found in {self.models_dir}")
        
        latest_model_path = model_files[-1]
        return self.load_model(latest_model_path)
    
    def load_model(self, model_path: Path):
        """Load a specific model"""
        logger.info(f"Loading model from {model_path}")
        
        with open(model_path, 'rb') as f:
            model = dill.load(f)
        
        # Extract metadata from filename
        # Format: arf_model_20251214_213238.pkl
        timestamp_str = model_path.stem.replace('arf_model_', '')
        
        self.current_model = model
        self.model_metadata = {
            'path': str(model_path),
            'version': timestamp_str,
            'loaded_at': datetime.now().isoformat()
        }
        
        logger.info(f"Model loaded successfully: {self.model_metadata}")
        return model
    
    def predict(self, features: dict) -> float:
        """Make a prediction"""
        if self.current_model is None:
            raise RuntimeError("No model loaded")
        
        return self.current_model.predict_one(features)
    
    def update_model(self, features: dict, target: float):
        """Update model with new data (online learning)"""
        if self.current_model is None:
            raise RuntimeError("No model loaded")
        
        self.current_model.learn_one(features, target)
        logger.info(f"Model updated with new sample: target={target}")
    
    def get_metadata(self) -> dict:
        """Get current model metadata"""
        return self.model_metadata
```

#### Step 5: Create `api/main.py`

```python
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import logging
import time
from datetime import datetime
from typing import Dict

from schemas import (
    PredictionRequest, 
    PredictionResponse, 
    HealthResponse,
    FeedbackRequest
)
from model_loader import ModelManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Air Quality Prediction API",
    description="Real-time AQI predictions using Adaptive Random Forest",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
prediction_counter = Counter('predictions_total', 'Total number of predictions')
prediction_latency = Histogram('prediction_latency_seconds', 'Prediction latency')
feedback_counter = Counter('feedback_total', 'Total feedback received')

# Global state
model_manager = ModelManager()
startup_time = time.time()

@app.on_event("startup")
async def startup_event():
    """Load model on startup"""
    try:
        model_manager.load_latest_model()
        logger.info("Model loaded successfully on startup")
    except Exception as e:
        logger.error(f"Failed to load model on startup: {e}")
        raise

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "message": "Air Quality Prediction API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy" if model_manager.current_model else "unhealthy",
        model_loaded=model_manager.current_model is not None,
        model_version=model_manager.model_metadata.get('version', 'unknown'),
        uptime_seconds=time.time() - startup_time
    )

@app.post("/predict", response_model=PredictionResponse, tags=["Prediction"])
async def predict(request: PredictionRequest):
    """
    Make AQI prediction
    
    Returns predicted AQI and category based on input features.
    """
    start_time = time.time()
    
    try:
        # Convert request to features dict
        features = request.model_dump(exclude_none=True)
        
        # Make prediction
        predicted_aqi = model_manager.predict(features)
        
        # Determine AQI category
        aqi_category = get_aqi_category(predicted_aqi)
        
        # Record metrics
        prediction_counter.inc()
        prediction_latency.observe(time.time() - start_time)
        
        return PredictionResponse(
            predicted_aqi=round(predicted_aqi, 2),
            aqi_category=aqi_category,
            model_version=model_manager.model_metadata.get('version', 'unknown'),
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/feedback", tags=["Feedback"])
async def submit_feedback(request: FeedbackRequest, background_tasks: BackgroundTasks):
    """
    Submit feedback for online learning
    
    Accepts actual AQI values to update the model continuously.
    """
    try:
        features = request.features.model_dump(exclude_none=True)
        
        # Update model in background
        background_tasks.add_task(
            model_manager.update_model,
            features,
            request.actual_aqi
        )
        
        feedback_counter.inc()
        
        return {
            "status": "success",
            "message": "Feedback received and model will be updated"
        }
        
    except Exception as e:
        logger.error(f"Feedback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/model/info", tags=["Model"])
async def model_info():
    """Get current model information"""
    return {
        "metadata": model_manager.get_metadata(),
        "status": "loaded" if model_manager.current_model else "not_loaded"
    }

def get_aqi_category(aqi: float) -> str:
    """Convert AQI value to EPA category"""
    if aqi <= 50:
        return "Good"
    elif aqi <= 100:
        return "Moderate"
    elif aqi <= 150:
        return "Unhealthy for Sensitive Groups"
    elif aqi <= 200:
        return "Unhealthy"
    elif aqi <= 300:
        return "Very Unhealthy"
    else:
        return "Hazardous"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

#### Step 6: Create `api/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy API code
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Step 7: Create `api/.env.example`

```env
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
MODEL_PATH=../training/models
LOG_LEVEL=INFO

# Model Settings
AUTO_RETRAIN_THRESHOLD=0.85
DRIFT_CHECK_INTERVAL=3600
```

#### Step 8: Test Locally

```bash
cd api

# Install dependencies
pip install -r requirements.txt

# Run the API
python main.py

# In another terminal, test it
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "pm25": 45.2,
    "pm1": 32.1,
    "temperature": 18.5,
    "relativehumidity": 65.3,
    "um003": 1250.0,
    "hour": 14,
    "day_of_week": 1,
    "month": 12
  }'
```

Expected output:
```json
{
  "predicted_aqi": 89.45,
  "aqi_category": "Moderate",
  "model_version": "20251214_213238",
  "timestamp": "2025-12-30T10:30:00"
}
```

---

## 🎯 Phase 2: Integration with Data Pipeline

### Goal: Automatic Predictions on New Data

### 2.1 Create Inference Pipeline

**What to Build:**

```
inference/
├── inference_pipeline.py   # Connects data pipeline → API → storage
├── config.yaml             # Inference configuration
└── requirements.txt
```

#### Step 1: Create `inference/inference_pipeline.py`

```python
import requests
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class InferencePipeline:
    """Automatically make predictions on new data"""
    
    def __init__(self, api_url="http://localhost:8000"):
        self.api_url = api_url
        self.predictions_dir = Path("inference/predictions")
        self.predictions_dir.mkdir(parents=True, exist_ok=True)
    
    def process_new_data(self, data_file: Path):
        """Process a data file and make predictions"""
        logger.info(f"Processing {data_file}")
        
        # Load data
        df = pd.read_csv(data_file)
        
        predictions = []
        
        for idx, row in df.iterrows():
            # Prepare features
            features = {
                'pm25': row.get('pm25', 0),
                'pm1': row.get('pm1', 0),
                'temperature': row.get('temperature', 0),
                'relativehumidity': row.get('relativehumidity', 0),
                'um003': row.get('um003', 0)
            }
            
            # Make prediction
            response = requests.post(
                f"{self.api_url}/predict",
                json=features
            )
            
            if response.status_code == 200:
                pred = response.json()
                predictions.append({
                    'timestamp': row.get('timestamp'),
                    'actual_aqi': row.get('aqi', None),
                    'predicted_aqi': pred['predicted_aqi'],
                    'aqi_category': pred['aqi_category'],
                    **features
                })
        
        # Save predictions
        pred_df = pd.DataFrame(predictions)
        output_file = self.predictions_dir / f"predictions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        pred_df.to_csv(output_file, index=False)
        
        logger.info(f"Saved {len(predictions)} predictions to {output_file}")
        return pred_df
    
    def submit_feedback(self, predictions_df):
        """Submit actual values as feedback"""
        for idx, row in predictions_df.iterrows():
            if pd.notna(row['actual_aqi']):
                feedback = {
                    'features': {
                        'pm25': row['pm25'],
                        'pm1': row['pm1'],
                        'temperature': row['temperature'],
                        'relativehumidity': row['relativehumidity'],
                        'um003': row['um003']
                    },
                    'actual_aqi': row['actual_aqi']
                }
                
                requests.post(f"{self.api_url}/feedback", json=feedback)
        
        logger.info(f"Submitted feedback for {len(predictions_df)} samples")

if __name__ == "__main__":
    pipeline = InferencePipeline()
    
    # Process latest data
    latest_data = Path("../dataset/preprocessed/test_data.csv")
    predictions = pipeline.process_new_data(latest_data)
    
    # Submit feedback if actuals available
    pipeline.submit_feedback(predictions)
```

### 2.2 Update docker-compose.yml

Add the API service:

```yaml
services:
  # Existing data-pipeline service...
  
  prediction-api:
    build: ./api
    ports:
      - "8000:8000"
    volumes:
      - ./training/models:/app/models:ro
      - ./api/logs:/app/logs
    environment:
      - MODEL_PATH=/app/models
    depends_on:
      - data-pipeline
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## 🎯 Phase 3: Monitoring & Self-Healing

### Goal: Detect Issues and Auto-Fix

### 3.1 Model Performance Monitor

**What to Build:**

```
monitoring/
├── performance_monitor.py  # Track model accuracy
├── drift_detector.py       # Detect data/concept drift
├── alert_manager.py        # Send alerts
└── dashboard.py            # Optional: Streamlit dashboard
```

#### Step 1: Create `monitoring/performance_monitor.py`

```python
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Monitor model performance in production"""
    
    def __init__(self, threshold_mae=10.0, threshold_r2=0.80):
        self.threshold_mae = threshold_mae
        self.threshold_r2 = threshold_r2
        self.metrics_file = Path("monitoring/metrics_history.json")
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
    
    def evaluate_predictions(self, predictions_df):
        """Calculate performance metrics"""
        if 'actual_aqi' not in predictions_df.columns:
            logger.warning("No actual values available for evaluation")
            return None
        
        # Remove rows with missing actuals
        df = predictions_df.dropna(subset=['actual_aqi'])
        
        if len(df) == 0:
            return None
        
        # Calculate metrics
        mae = np.mean(np.abs(df['predicted_aqi'] - df['actual_aqi']))
        rmse = np.sqrt(np.mean((df['predicted_aqi'] - df['actual_aqi'])**2))
        
        # R² score
        ss_res = np.sum((df['actual_aqi'] - df['predicted_aqi'])**2)
        ss_tot = np.sum((df['actual_aqi'] - df['actual_aqi'].mean())**2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'mae': float(mae),
            'rmse': float(rmse),
            'r2': float(r2),
            'n_samples': len(df),
            'alert': mae > self.threshold_mae or r2 < self.threshold_r2
        }
        
        # Save metrics
        self._save_metrics(metrics)
        
        # Check for degradation
        if metrics['alert']:
            logger.warning(f"⚠️  Model performance degraded! MAE: {mae:.2f}, R²: {r2:.3f}")
            return {'status': 'degraded', 'metrics': metrics}
        
        logger.info(f"✅ Model performing well. MAE: {mae:.2f}, R²: {r2:.3f}")
        return {'status': 'healthy', 'metrics': metrics}
    
    def _save_metrics(self, metrics):
        """Append metrics to history"""
        history = []
        if self.metrics_file.exists():
            with open(self.metrics_file, 'r') as f:
                history = json.load(f)
        
        history.append(metrics)
        
        # Keep last 1000 entries
        history = history[-1000:]
        
        with open(self.metrics_file, 'w') as f:
            json.dump(history, f, indent=2)
    
    def check_trend(self, window_days=7):
        """Check if performance is degrading over time"""
        if not self.metrics_file.exists():
            return None
        
        with open(self.metrics_file, 'r') as f:
            history = json.load(f)
        
        if len(history) < 2:
            return None
        
        # Filter last N days
        cutoff = datetime.now() - timedelta(days=window_days)
        recent = [
            m for m in history 
            if datetime.fromisoformat(m['timestamp']) > cutoff
        ]
        
        if len(recent) < 2:
            return None
        
        # Calculate trend
        maes = [m['mae'] for m in recent]
        r2s = [m['r2'] for m in recent]
        
        # Simple linear regression on MAE
        x = np.arange(len(maes))
        mae_slope = np.polyfit(x, maes, 1)[0]
        r2_slope = np.polyfit(x, r2s, 1)[0]
        
        return {
            'mae_trend': 'increasing' if mae_slope > 0.5 else 'stable',
            'r2_trend': 'decreasing' if r2_slope < -0.01 else 'stable',
            'needs_retraining': mae_slope > 0.5 or r2_slope < -0.01
        }
```

#### Step 2: Create `monitoring/drift_detector.py`

```python
from river import drift
import numpy as np
import logging

logger = logging.getLogger(__name__)

class DriftDetector:
    """Detect data and concept drift"""
    
    def __init__(self):
        # ADWIN for drift detection
        self.drift_detector = drift.ADWIN(delta=0.002)
        self.drift_count = 0
        
    def check_drift(self, predictions_df):
        """Check for concept drift using prediction errors"""
        if 'actual_aqi' not in predictions_df.columns:
            return None
        
        df = predictions_df.dropna(subset=['actual_aqi'])
        
        if len(df) == 0:
            return None
        
        # Calculate errors
        errors = np.abs(df['predicted_aqi'] - df['actual_aqi'])
        
        # Check each error
        drift_detected = False
        for error in errors:
            self.drift_detector.update(error)
            if self.drift_detector.drift_detected:
                drift_detected = True
                self.drift_count += 1
        
        if drift_detected:
            logger.warning(f"🚨 DRIFT DETECTED! Total drift events: {self.drift_count}")
            return {
                'drift_detected': True,
                'drift_count': self.drift_count,
                'action': 'retrain_recommended'
            }
        
        return {'drift_detected': False, 'drift_count': self.drift_count}
```

#### Step 3: Create `monitoring/auto_retrainer.py`

```python
import subprocess
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class AutoRetrainer:
    """Automatically retrain model when needed"""
    
    def __init__(self, training_script="../training/training.py"):
        self.training_script = Path(training_script)
        self.retrain_log = Path("monitoring/retrain_history.json")
        self.retrain_log.parent.mkdir(parents=True, exist_ok=True)
    
    def trigger_retraining(self, reason="manual"):
        """Trigger model retraining"""
        logger.info(f"🔄 Starting automatic retraining. Reason: {reason}")
        
        try:
            # Run training script
            result = subprocess.run(
                ["python", str(self.training_script)],
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes timeout
            )
            
            if result.returncode == 0:
                logger.info("✅ Retraining completed successfully")
                self._log_retrain(reason, "success")
                return {'status': 'success', 'reason': reason}
            else:
                logger.error(f"❌ Retraining failed: {result.stderr}")
                self._log_retrain(reason, "failed", result.stderr)
                return {'status': 'failed', 'reason': reason, 'error': result.stderr}
                
        except Exception as e:
            logger.error(f"❌ Retraining error: {e}")
            self._log_retrain(reason, "error", str(e))
            return {'status': 'error', 'reason': reason, 'error': str(e)}
    
    def _log_retrain(self, reason, status, error=None):
        """Log retraining event"""
        import json
        
        event = {
            'timestamp': datetime.now().isoformat(),
            'reason': reason,
            'status': status,
            'error': error
        }
        
        history = []
        if self.retrain_log.exists():
            with open(self.retrain_log, 'r') as f:
                history = json.load(f)
        
        history.append(event)
        
        with open(self.retrain_log, 'w') as f:
            json.dump(history, f, indent=2)
```

---

## 🎯 Phase 4: Orchestration (Self-Healing Loop)

### Goal: Connect Everything Together

#### Create `orchestrator.py` (Main Controller)

```python
import schedule
import time
import logging
from pathlib import Path
from inference.inference_pipeline import InferencePipeline
from monitoring.performance_monitor import PerformanceMonitor
from monitoring.drift_detector import DriftDetector
from monitoring.auto_retrainer import AutoRetrainer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SelfHealingOrchestrator:
    """
    Main orchestrator for self-healing MLOps
    
    Flow:
    1. Data Pipeline fetches new data (every 2 hours)
    2. Make predictions on new data
    3. Monitor performance when actuals arrive
    4. Detect drift
    5. Auto-retrain if needed
    6. Reload model
    """
    
    def __init__(self):
        self.inference = InferencePipeline()
        self.monitor = PerformanceMonitor()
        self.drift_detector = DriftDetector()
        self.retrainer = AutoRetrainer()
        
        self.consecutive_degradations = 0
        self.retrain_threshold = 3  # Retrain after 3 consecutive degradations
    
    def run_inference_cycle(self):
        """Run one inference cycle"""
        logger.info("="*60)
        logger.info("🚀 Starting inference cycle")
        logger.info("="*60)
        
        try:
            # 1. Find latest data
            latest_data = self._find_latest_data()
            if not latest_data:
                logger.info("No new data to process")
                return
            
            # 2. Make predictions
            logger.info(f"📊 Processing {latest_data}")
            predictions = self.inference.process_new_data(latest_data)
            
            # 3. Evaluate performance
            logger.info("📈 Evaluating model performance")
            performance = self.monitor.evaluate_predictions(predictions)
            
            if performance:
                if performance['status'] == 'degraded':
                    self.consecutive_degradations += 1
                    logger.warning(f"⚠️  Consecutive degradations: {self.consecutive_degradations}/{self.retrain_threshold}")
                else:
                    self.consecutive_degradations = 0
            
            # 4. Check drift
            logger.info("🔍 Checking for drift")
            drift_result = self.drift_detector.check_drift(predictions)
            
            # 5. Decide if retraining needed
            should_retrain = False
            retrain_reason = None
            
            if self.consecutive_degradations >= self.retrain_threshold:
                should_retrain = True
                retrain_reason = "consecutive_degradation"
            
            if drift_result and drift_result.get('drift_detected'):
                should_retrain = True
                retrain_reason = "drift_detected"
            
            # 6. Trigger retraining if needed
            if should_retrain:
                logger.info(f"🔄 Triggering retraining. Reason: {retrain_reason}")
                result = self.retrainer.trigger_retraining(reason=retrain_reason)
                
                if result['status'] == 'success':
                    logger.info("✅ Model retrained successfully")
                    self.consecutive_degradations = 0
                    # TODO: Reload model in API
            
            # 7. Submit feedback for online learning
            logger.info("📤 Submitting feedback for online learning")
            self.inference.submit_feedback(predictions)
            
            logger.info("✅ Inference cycle completed")
            
        except Exception as e:
            logger.error(f"❌ Error in inference cycle: {e}", exc_info=True)
    
    def _find_latest_data(self):
        """Find latest preprocessed data"""
        data_dir = Path("dataset/preprocessed")
        
        # Look for today's data or latest test data
        csv_files = sorted(data_dir.glob("*.csv"))
        
        if csv_files:
            return csv_files[-1]
        
        return None
    
    def start(self):
        """Start the orchestrator"""
        logger.info("🎯 Self-Healing MLOps Orchestrator Started")
        logger.info("Monitoring mode: Check every 2 hours")
        
        # Run immediately
        self.run_inference_cycle()
        
        # Schedule every 2 hours
        schedule.every(2).hours.do(self.run_inference_cycle)
        
        # Keep running
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

if __name__ == "__main__":
    orchestrator = SelfHealingOrchestrator()
    orchestrator.start()
```

---

## 📅 Implementation Timeline

### Week 1: API Development (Days 1-7)
- [ ] Day 1-2: Setup API structure, schemas, model loader
- [ ] Day 3-4: Implement main.py with all endpoints
- [ ] Day 5: Dockerize API
- [ ] Day 6-7: Test API thoroughly, write tests

### Week 2: Integration (Days 8-14)
- [ ] Day 8-9: Create inference pipeline
- [ ] Day 10-11: Update docker-compose with API service
- [ ] Day 12-13: Test end-to-end flow
- [ ] Day 14: Documentation

### Week 3: Monitoring (Days 15-21)
- [ ] Day 15-16: Performance monitor
- [ ] Day 17-18: Drift detector
- [ ] Day 19-20: Auto-retrainer
- [ ] Day 21: Alert integration

### Week 4: Orchestration (Days 22-28)
- [ ] Day 22-24: Build orchestrator
- [ ] Day 25-26: Integration testing
- [ ] Day 27-28: Load testing, optimization

### Week 5: Production (Days 29-35)
- [ ] Day 29-30: Deploy to production
- [ ] Day 31-32: Monitor and tune
- [ ] Day 33-34: Documentation
- [ ] Day 35: Demo and presentation

---

## 🧪 Testing Strategy

### Unit Tests
```bash
# API tests
pytest api/test_api.py

# Model loader tests
pytest api/test_model_loader.py

# Monitor tests
pytest monitoring/test_monitor.py
```

### Integration Tests
```bash
# End-to-end test
python tests/test_e2e.py

# Load test
locust -f tests/load_test.py
```

### Manual Testing Checklist
- [ ] API returns predictions
- [ ] Predictions are reasonable (MAE < 10)
- [ ] Online learning works (feedback endpoint)
- [ ] Drift detection triggers
- [ ] Auto-retraining completes
- [ ] Model reloads after retraining
- [ ] Alerts are sent
- [ ] System recovers from failures

---

## 📊 Success Metrics

### Technical Metrics
- **API Latency**: < 100ms per prediction
- **Uptime**: > 99.5%
- **Model MAE**: < 10 AQI points in production
- **Drift Detection**: < 24 hour delay
- **Retraining Time**: < 5 minutes
- **Auto-Recovery**: < 1 hour from detection to fix

### Business Metrics
- **Prediction Accuracy**: > 90% category accuracy
- **Data Freshness**: < 2 hours old
- **System Reliability**: Zero manual interventions per month
- **Cost**: < $10/month (if using cloud)

---

## 🚀 Quick Start Commands

```bash
# 1. Start the entire system
docker-compose up -d

# 2. Check if everything is running
docker-compose ps

# 3. Test prediction API
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{"pm25": 45.2, "pm1": 32.1, "temperature": 18.5, "relativehumidity": 65.3}'

# 4. Check API health
curl http://localhost:8000/health

# 5. View logs
docker-compose logs -f prediction-api

# 6. Start orchestrator
python orchestrator.py
```

---

## 📚 Additional Resources

### Documentation to Create
1. **API_DOCUMENTATION.md** - Full API reference
2. **DEPLOYMENT_GUIDE.md** - Production deployment
3. **TROUBLESHOOTING.md** - Common issues and fixes
4. **ARCHITECTURE_DIAGRAM.pdf** - System architecture

### Tools to Consider
- **Monitoring**: Prometheus + Grafana
- **Logging**: ELK Stack or Loki
- **Alerting**: PagerDuty, Slack
- **Database**: PostgreSQL for prediction storage
- **Cache**: Redis for model caching
- **Load Balancer**: Nginx

---

## ⚠️ Important Notes

1. **Start Simple**: Build API first, then add complexity
2. **Test Thoroughly**: Each component should work independently
3. **Monitor Everything**: Logs, metrics, alerts are critical
4. **Document as You Go**: Future you will thank you
5. **Version Everything**: Models, data, code
6. **Backup Regularly**: Models, data, configs

---

## 🎯 Next Immediate Actions

**TODAY (Priority 1):**
1. Create `api/` directory
2. Copy the `api/main.py`, `api/schemas.py`, `api/model_loader.py` code
3. Install dependencies: `pip install -r api/requirements.txt`
4. Test locally: `python api/main.py`
5. Make your first prediction!

**THIS WEEK (Priority 2):**
6. Dockerize the API
7. Update docker-compose.yml
8. Test with Docker
9. Create inference pipeline
10. Connect to your data pipeline

**NEXT WEEK (Priority 3):**
11. Add monitoring
12. Implement drift detection
13. Build orchestrator
14. Test self-healing

---

## 🏆 Vision: What You'll Have

A fully automated system where:
- ✅ Data flows in automatically every 2 hours
- ✅ Model makes predictions in real-time
- ✅ Performance is monitored continuously
- ✅ Drift is detected automatically
- ✅ Model retrains itself when needed
- ✅ No manual intervention required
- ✅ Alerts you only when human decision needed

**That's TRUE Self-Healing MLOps!** 🚀

---

Ready to start? Begin with Phase 1, Step 1: Create the API directory and start coding! 💪
