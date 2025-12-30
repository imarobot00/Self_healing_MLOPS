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
