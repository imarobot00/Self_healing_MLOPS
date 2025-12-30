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
