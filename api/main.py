from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import logging
import time
from datetime import datetime
from typing import Dict
from pathlib import Path

from schemas import (
    PredictionRequest, 
    PredictionResponse, 
    HealthResponse,
    FeedbackRequest
)
from model_loader import ModelManager
from forecaster import AQIForecaster

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

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Prometheus metrics
prediction_counter = Counter('predictions_total', 'Total number of predictions')
prediction_latency = Histogram('prediction_latency_seconds', 'Prediction latency')
feedback_counter = Counter('feedback_total', 'Total feedback received')

# Global state
model_manager = ModelManager()
forecaster = None
startup_time = time.time()

@app.on_event("startup")
async def startup_event():
    """Load model on startup"""
    global forecaster
    try:
        model_manager.load_latest_model()
        logger.info("Model loaded successfully on startup")
        
        # Initialize forecaster
        forecaster = AQIForecaster(
            model=model_manager.current_model,
            feature_engineer=model_manager.feature_engineer
        )
        logger.info("Forecaster initialized successfully")
    except Exception as e:
        logger.error(f"Failed to load model on startup: {e}")
        raise

@app.get("/", tags=["Root"])
async def root():
    """Serve the web interface"""
    static_file = Path(__file__).parent / "static" / "index.html"
    if static_file.exists():
        return FileResponse(static_file)
    return {
        "message": "Air Quality Prediction API",
        "version": "1.0.0",
        "docs": "/docs",
        "web_interface": "/static/index.html"
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

@app.get("/forecast", tags=["Forecast"])
async def get_forecast(location_id: int = 6142174, hours: int = 5):
    """
    Get AQI forecast for the next N hours based on historical data.
    
    Parameters:
    - location_id: Location ID to forecast (default: 6142174 - Ranibari)
    - hours: Number of hours to forecast ahead (default: 5)
    """
    try:
        if forecaster is None:
            raise HTTPException(status_code=503, detail="Forecaster not initialized")
        
        forecasts = forecaster.forecast_next_hours(location_id, hours)
        current = forecaster.get_current_conditions(location_id)
        
        return {
            "location_id": location_id,
            "current_conditions": current,
            "forecasts": forecasts,
            "model_version": model_manager.model_metadata.get('version', 'unknown'),
            "generated_at": datetime.now().isoformat()
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Forecast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history", tags=["Forecast"])
async def get_history(location_id: int = 6142174, hours: int = 24):
    """
    Get historical AQI trend for charting.
    
    Parameters:
    - location_id: Location ID (default: 6142174 - Ranibari)
    - hours: Number of hours of history (default: 24)
    """
    try:
        if forecaster is None:
            raise HTTPException(status_code=503, detail="Forecaster not initialized")
        
        trend = forecaster.get_historical_trend(location_id, hours)
        
        return {
            "location_id": location_id,
            "hours": hours,
            "data": trend
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"History error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/locations", tags=["Forecast"])
async def get_locations():
    """Get list of available locations"""
    data_dir = Path(__file__).parent.parent / "dataset"
    location_files = list(data_dir.glob("location_*.json"))
    
    locations = []
    for file in location_files:
        location_id = int(file.stem.replace('location_', ''))
        locations.append({
            "id": location_id,
            "name": f"Location {location_id}"
        })
    
    return {"locations": locations}

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
