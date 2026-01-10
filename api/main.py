from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import logging
import time
import os
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
from monitoring import PerformanceMonitor
from prediction_tracker import PredictionTracker

# Import drift detector using importlib to avoid naming conflicts
import importlib.util
import sys
from pathlib import Path

# Import monitoring components from training
def _import_training_module(module_name, file_name):
    """Import module from training directory."""
    spec = importlib.util.spec_from_file_location(
        module_name,
        Path(__file__).parent.parent / "training" / file_name
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

metrics_module = _import_training_module("metrics_collector", "metrics_collector.py")
alert_module = _import_training_module("alert_manager", "alert_manager.py")
health_module = _import_training_module("health_checks", "health_checks.py")

MetricsCollector = metrics_module.MetricsCollector
AlertManager = alert_module.AlertManager
HealthChecker = health_module.HealthChecker

def _import_drift_detector():
    """Import DriftDetector from monitoring package outside api/"""
    spec = importlib.util.spec_from_file_location(
        "drift_detection",
        Path(__file__).parent.parent / "monitoring" / "drift_detector.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DriftDetector

DriftDetector = _import_drift_detector()

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

# Middleware to log all requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all API requests for monitoring"""
    start_time = time.time()
    
    response = await call_next(request)
    
    response_time = (time.time() - start_time) * 1000  # ms
    
    # Log request
    monitor.log_request(
        endpoint=request.url.path,
        method=request.method,
        params=dict(request.query_params),
        status_code=response.status_code,
        response_time_ms=response_time
    )
    
    return response

# Prometheus metrics
prediction_counter = Counter('predictions_total', 'Total number of predictions')
prediction_latency = Histogram('prediction_latency_seconds', 'Prediction latency')
feedback_counter = Counter('feedback_total', 'Total feedback received')

# Retraining metrics
from prometheus_client import Gauge, Info
retraining_required_gauge = Gauge('retraining_required', 'Whether retraining is required (1=yes, 0=no)')
retraining_severity_gauge = Gauge('retraining_severity', 'Retraining severity level (0=ok, 1=warning, 2=high, 3=critical)')
model_overall_mae_gauge = Gauge('model_overall_mae', 'Overall Mean Absolute Error of predictions')
retraining_triggered_counter = Counter('retraining_triggered_total', 'Total number of times retraining was triggered')
last_retraining_timestamp = Gauge('last_retraining_timestamp', 'Unix timestamp of last retraining trigger')

# Global state
model_manager = ModelManager(models_dir=os.environ.get('MODEL_PATH'))
forecaster = None
monitor = PerformanceMonitor()
drift_detector = None  # Lazy loaded
startup_time = time.time()
prediction_tracker = PredictionTracker(storage_dir=os.environ.get('PREDICTIONS_DIR', '/logs/predictions'))

# Initialize monitoring components
metrics_collector = MetricsCollector(app_name="aqi_api")
alert_manager = AlertManager()
health_checker = HealthChecker(service_name="aqi_api")

def get_drift_detector():
    """Lazy load drift detector"""
    global drift_detector
    if drift_detector is None:
        config_path = Path(__file__).parent.parent / "monitoring" / "drift_config.yaml"
        drift_detector = DriftDetector(config_path=str(config_path))
    return drift_detector

@app.on_event("startup")
async def startup_event():
    """Load model on startup"""
    global forecaster
    try:
        model_manager.load_latest_model()
        logger.info("Model loaded successfully on startup")
        
        # Initialize forecaster with data directory from env
        data_dir = os.environ.get('DATA_DIR', '../dataset')
        forecaster = AQIForecaster(
            model=model_manager.current_model,
            feature_engineer=model_manager.feature_engineer,
            data_dir=data_dir
        )
        logger.info(f"Forecaster initialized successfully with data_dir={data_dir}")
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

@app.get("/forecast-ui", tags=["Root"])
async def forecast_ui():
    """Serve the forecast dashboard - shows predictions from real data"""
    static_file = Path(__file__).parent / "static" / "forecast.html"
    if static_file.exists():
        return FileResponse(static_file)
    return {"error": "Forecast UI not found"}

@app.get("/monitoring", tags=["Root"])
async def monitoring_dashboard():
    """Serve the monitoring dashboard"""
    static_file = Path(__file__).parent / "static" / "monitoring.html"
    if static_file.exists():
        return FileResponse(static_file)
    return {"message": "Monitoring dashboard not found"}

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy" if model_manager.current_model else "unhealthy",
        model_loaded=model_manager.current_model is not None,
        model_version=model_manager.model_metadata.get('version', 'unknown'),
        uptime_seconds=time.time() - startup_time
    )

@app.post("/reload-model", tags=["Health"])
async def reload_model():
    """
    Manually reload the latest model.
    Use this after retraining to immediately load the new model.
    """
    try:
        old_version = model_manager.model_metadata.get('version', 'none')
        model_manager.load_latest_model()
        new_version = model_manager.model_metadata.get('version', 'none')
        
        return {
            "status": "success",
            "old_version": old_version,
            "new_version": new_version,
            "changed": old_version != new_version,
            "message": f"Model updated from {old_version} to {new_version}" if old_version != new_version else "Already on latest model"
        }
    except Exception as e:
        logger.error(f"Error reloading model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health/liveness", tags=["Health"])
async def liveness_probe():
    """Kubernetes liveness probe"""
    return {"status": "alive" if health_checker.is_alive() else "dead"}

@app.get("/health/readiness", tags=["Health"])
async def readiness_probe():
    """Kubernetes readiness probe"""
    return {"status": "ready" if health_checker.is_ready() else "not_ready"}

@app.get("/health/startup", tags=["Health"])
async def startup_probe():
    """Kubernetes startup probe"""
    return {"status": "started" if health_checker.is_started() else "starting"}

@app.get("/health/detailed", tags=["Health"])
async def detailed_health():
    """Detailed health status with all checks"""
    return health_checker.get_status()

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
        
        # Log prediction for monitoring
        response_time = (time.time() - start_time) * 1000  # ms
        monitor.log_prediction(
            location_id=features.get('location_id', 0),
            timestamp=datetime.now().isoformat(),
            predicted_aqi=predicted_aqi,
            input_features=features,
            model_version=model_manager.model_metadata.get('version', 'unknown'),
            response_time_ms=response_time
        )
        
        # Record metrics (both old and new)
        prediction_counter.inc()
        prediction_latency.observe(time.time() - start_time)
        
        # New metrics collector
        duration = time.time() - start_time
        metrics_collector.increment('predictions_total', labels={'model': model_manager.model_metadata.get('version', 'unknown')})
        metrics_collector.observe('prediction_duration_seconds', duration)
        mae_value = monitor.calculate_metrics().get('mae')
        if mae_value is not None:
            metrics_collector.set_gauge('model_mae', mae_value)
        
        # Check for alerts
        alert_manager.check_and_alert(metrics_collector.get_summary())
        
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
    """Prometheus metrics endpoint (legacy)"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/metrics/prometheus", tags=["Monitoring"])
async def prometheus_metrics():
    """New Prometheus metrics from MetricsCollector"""
    combined = generate_latest().decode('utf-8')
    combined += "\n" + metrics_collector.export()
    combined += "\n" + health_checker.export_prometheus_format()
    return Response(content=combined, media_type=CONTENT_TYPE_LATEST)

@app.get("/metrics/summary", tags=["Monitoring"])
async def metrics_summary():
    """Human-readable metrics summary"""
    return metrics_collector.get_summary()

@app.get("/alerts/active", tags=["Monitoring"])
async def active_alerts():
    """Get currently active alerts"""
    alerts = alert_manager.get_active_alerts()
    return {
        "count": len(alerts),
        "alerts": [{
            "rule_name": a.rule_name,
            "severity": a.severity,
            "message": a.message,
            "timestamp": a.timestamp
        } for a in alerts]
    }

@app.get("/alerts/history", tags=["Monitoring"])
async def alert_history(hours: int = 24):
    """Get alert history"""
    alerts = alert_manager.get_alert_history(hours=hours)
    return {
        "count": len(alerts),
        "hours": hours,
        "alerts": [{
            "rule_name": a.rule_name,
            "severity": a.severity,
            "message": a.message,
            "timestamp": a.timestamp
        } for a in alerts]
    }

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
        
        # Log and save each forecast prediction
        for forecast in forecasts:
            monitor.log_prediction(
                location_id=location_id,
                timestamp=forecast['timestamp'],
                predicted_aqi=forecast['predicted_aqi'],
                input_features={'pm25': forecast['pm25'], 'temperature': forecast['temperature'], 
                               'relativehumidity': forecast['humidity']},
                model_version=model_manager.model_metadata.get('version', 'unknown')
            )
            # Save prediction for later evaluation against actuals
            prediction_tracker.save_prediction(
                location_id=location_id,
                forecast_timestamp=forecast['timestamp'],
                predicted_aqi=forecast['predicted_aqi'],
                predicted_pm25=forecast['pm25'],
                model_version=model_manager.model_metadata.get('version', 'unknown')
            )
            # Increment prediction counter
            prediction_counter.inc()
            metrics_collector.increment('predictions_total', labels={'model': model_manager.model_metadata.get('version', 'unknown')})
        
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
    data_dir = Path(os.environ.get('DATA_DIR', '../dataset'))
    location_files = list(data_dir.glob("location_*.json"))
    
    # Location name mapping
    location_names = {
        3459: "Ratna Park",
        5506835: "US Embassy",
        5509787: "Pulchowk",
        6093549: "Bhaisepati",
        6093550: "Kirtipur",
        6093551: "Lalitpur",
        6133623: "Boudha",
        6142022: "Thamel",
        6142174: "Ranibari",
        6142175: "Chabahil"
    }
    
    locations = []
    for file in location_files:
        location_id = int(file.stem.replace('location_', ''))
        locations.append({
            "id": location_id,
            "name": location_names.get(location_id, f"Location {location_id}")
        })
    
    return {"locations": locations}

@app.post("/evaluate-predictions", tags=["Monitoring"])
async def evaluate_predictions():
    """
    Evaluate saved predictions against actual data.
    Call this after git pull to compare predictions with new actual values.
    """
    try:
        data_dir = os.environ.get('DATA_DIR', '../dataset')
        result = prediction_tracker.evaluate_predictions(data_dir)
        return result
    except Exception as e:
        logger.error(f"Error evaluating predictions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/prediction-accuracy", tags=["Monitoring"])
async def get_prediction_accuracy():
    """
    Get summary of prediction accuracy - shows how well model predicted vs actual values.
    """
    try:
        summary = prediction_tracker.get_evaluation_summary()
        return summary
    except Exception as e:
        logger.error(f"Error getting prediction accuracy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/retraining-status", tags=["Monitoring"])
async def get_retraining_status():
    """
    Check if model retraining is required based on prediction accuracy.
    
    Returns:
    - retraining_required: YES/NO
    - reason: Why retraining is/isn't needed
    - metrics: Current accuracy metrics
    - thresholds: The thresholds used for decision
    """
    # Thresholds
    MAE_WARNING = 25.0    # Warning if MAE > 25
    MAE_CRITICAL = 35.0   # Critical if MAE > 35
    ACCURACY_MIN = 70.0   # Minimum acceptable accuracy %
    MIN_SAMPLES = 10      # Minimum samples needed for reliable decision
    
    try:
        summary = prediction_tracker.get_evaluation_summary()
        
        if summary["total"] < MIN_SAMPLES:
            # Update Prometheus metrics
            retraining_required_gauge.set(0)
            retraining_severity_gauge.set(0)
            return {
                "retraining_required": "UNKNOWN",
                "confidence": "low",
                "reason": f"Not enough data. Need {MIN_SAMPLES} evaluations, have {summary['total']}",
                "recommendation": "Make more predictions and evaluate them",
                "metrics": summary,
                "thresholds": {
                    "mae_warning": MAE_WARNING,
                    "mae_critical": MAE_CRITICAL,
                    "min_accuracy": ACCURACY_MIN,
                    "min_samples": MIN_SAMPLES
                }
            }
        
        overall_mae = summary.get("overall_mae", 0)
        
        # Update MAE gauge
        model_overall_mae_gauge.set(overall_mae)
        
        # Check locations with poor performance
        poor_locations = []
        for loc_id, data in summary.get("by_location", {}).items():
            if data["mae"] > MAE_CRITICAL:
                poor_locations.append({
                    "location": loc_id,
                    "mae": data["mae"],
                    "samples": data["count"]
                })
        
        # Decision logic
        if overall_mae > MAE_CRITICAL:
            status = "YES"
            severity = "CRITICAL"
            severity_num = 3
            reason = f"Overall MAE ({overall_mae:.1f}) exceeds critical threshold ({MAE_CRITICAL})"
        elif len(poor_locations) >= 2:
            status = "YES"
            severity = "HIGH"
            severity_num = 2
            reason = f"{len(poor_locations)} locations have MAE > {MAE_CRITICAL}: {[p['location'] for p in poor_locations]}"
        elif overall_mae > MAE_WARNING:
            status = "RECOMMENDED"
            severity = "WARNING"
            severity_num = 1
            reason = f"Overall MAE ({overall_mae:.1f}) exceeds warning threshold ({MAE_WARNING})"
        else:
            status = "NO"
            severity = "OK"
            severity_num = 0
            reason = f"Model performing well. MAE ({overall_mae:.1f}) is within acceptable range"
        
        # Update Prometheus metrics
        retraining_required_gauge.set(1 if status in ["YES", "RECOMMENDED"] else 0)
        retraining_severity_gauge.set(severity_num)
        
        return {
            "retraining_required": status,
            "severity": severity,
            "reason": reason,
            "overall_mae": overall_mae,
            "poor_locations": poor_locations,
            "total_evaluations": summary["total"],
            "recommendation": "Run: docker exec mlops-training python /training/retrain_model.py" if status in ["YES", "RECOMMENDED"] else "No action needed",
            "thresholds": {
                "mae_warning": MAE_WARNING,
                "mae_critical": MAE_CRITICAL,
                "min_samples": MIN_SAMPLES
            }
        }
    except Exception as e:
        logger.error(f"Error checking retraining status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/trigger-retraining", tags=["Monitoring"])
async def trigger_retraining():
    """
    Trigger model retraining and record the event in Prometheus.
    This endpoint is called when retraining is initiated.
    """
    try:
        # Increment retraining counter
        retraining_triggered_counter.inc()
        
        # Set last retraining timestamp
        last_retraining_timestamp.set(time.time())
        
        logger.info("Retraining triggered and recorded in Prometheus")
        
        return {
            "status": "triggered",
            "timestamp": datetime.now().isoformat(),
            "message": "Retraining event recorded. Run: docker exec mlops-training python /training/retrain_model.py"
        }
    except Exception as e:
        logger.error(f"Error triggering retraining: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/monitoring/summary", tags=["Monitoring"])
async def monitoring_summary():
    """Get monitoring summary with current performance metrics"""
    try:
        summary = monitor.get_summary()
        return summary
    except Exception as e:
        logger.error(f"Error getting monitoring summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/monitoring/metrics", tags=["Monitoring"])
async def monitoring_metrics(days: int = 7):
    """Get metrics history for the last N days"""
    try:
        history = monitor.get_metrics_history(days=days)
        return {"metrics": history}
    except Exception as e:
        logger.error(f"Error getting metrics history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/monitoring/predictions", tags=["Monitoring"])
async def monitoring_predictions(limit: int = 50):
    """Get recent predictions with their actuals"""
    try:
        predictions = monitor.get_recent_predictions(limit=limit)
        return {"predictions": predictions}
    except Exception as e:
        logger.error(f"Error getting predictions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/monitoring/locations", tags=["Monitoring"])
async def monitoring_locations():
    """Get detailed metrics for each location"""
    try:
        location_metrics = monitor.calculate_metrics_by_location()
        return {"location_metrics": location_metrics}
    except Exception as e:
        logger.error(f"Error getting location metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/monitoring/alerts", tags=["Monitoring"])
async def monitoring_alerts(hours: int = 24):
    """Get recent alerts"""
    try:
        alerts = monitor.get_alerts(hours=hours)
        return {"alerts": alerts}
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/monitoring/drift", tags=["Monitoring"])
async def get_drift_status(days: int = 1):
    """
    Get current drift detection status
    
    Args:
        days: Number of days to analyze (default: 1)
    
    Returns:
        Drift analysis report with recommendations
    """
    try:
        detector = get_drift_detector()
        report = detector.run_drift_check(days=days)
        
        # Add status code based on drift severity
        if 'error' in report:
            return {
                "status": "error",
                "report": report
            }
        
        drift_score = report.get('overall_drift_score', 0)
        
        if drift_score > 0.5:
            status = "critical"
        elif drift_score > 0.3:
            status = "warning"
        elif drift_score > 0.2:
            status = "minor"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "report": report
        }
    
    except Exception as e:
        logger.error(f"Error in drift detection: {e}")
        raise HTTPException(status_code=500, detail=f"Drift detection failed: {str(e)}")

@app.get("/monitoring/drift/history", tags=["Monitoring"])
async def get_drift_history(limit: int = 10):
    """
    Get historical drift reports
    
    Args:
        limit: Maximum number of reports to return
    
    Returns:
        List of past drift reports
    """
    try:
        reports_dir = Path("../monitoring/reports")
        
        if not reports_dir.exists():
            return {"reports": []}
        
        # Get all drift report files
        report_files = sorted(reports_dir.glob("drift_report_*.json"), reverse=True)
        
        reports = []
        for report_file in report_files[:limit]:
            try:
                with open(report_file, 'r') as f:
                    report = json.load(f)
                    reports.append({
                        "file": report_file.name,
                        "timestamp": report.get('timestamp'),
                        "drift_score": report.get('overall_drift_score'),
                        "recommendation": report.get('recommendation'),
                        "num_samples": report.get('num_samples_analyzed')
                    })
            except Exception as e:
                logger.warning(f"Could not read {report_file}: {e}")
                continue
        
        return {"reports": reports}
    
    except Exception as e:
        logger.error(f"Error getting drift history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/monitoring/drift/reset-baseline", tags=["Monitoring"])
async def reset_baseline():
    """
    Regenerate baseline statistics from current training data
    
    This should be called after model retraining to update the drift detection baseline
    """
    try:
        import subprocess
        
        # Run baseline generation script
        result = subprocess.run(
            ["python", "../monitoring/generate_baseline.py"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            # Reload drift detector with new baseline
            global drift_detector
            drift_detector = None
            
            return {
                "status": "success",
                "message": "Baseline statistics regenerated",
                "output": result.stdout
            }
        else:
            return {
                "status": "error",
                "message": "Failed to regenerate baseline",
                "error": result.stderr
            }
    
    except Exception as e:
        logger.error(f"Error resetting baseline: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/monitoring/update-actuals", tags=["Monitoring"])
async def update_actuals(background_tasks: BackgroundTasks):
    """
    Update predictions with actual values from dataset.
    Run this after pulling new data to calculate performance metrics.
    """
    try:
        background_tasks.add_task(monitor.update_actuals)
        background_tasks.add_task(monitor.calculate_metrics)
        return {"message": "Updating actuals and calculating metrics in background"}
    except Exception as e:
        logger.error(f"Error updating actuals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/monitoring/backfill-predictions", tags=["Monitoring"])
async def backfill_predictions(hours_back: int = 12):
    """
    Generate predictions for past hours (where we have actual data).
    This populates the monitoring dashboard immediately.
    
    Parameters:
    - hours_back: How many hours back to generate predictions for (default: 12)
    """
    try:
        if forecaster is None:
            raise HTTPException(status_code=503, detail="Forecaster not initialized")
        
        # Get all available locations
        data_dir = Path(__file__).parent.parent / "dataset"
        location_files = list(data_dir.glob("location_*.json"))
        
        backfilled_count = 0
        for loc_file in location_files:
            location_id = int(loc_file.stem.replace('location_', ''))
            
            try:
                # Generate backfill predictions for this location
                backfill_forecasts = forecaster.backfill_predictions(location_id, hours_back=hours_back)
                
                # Log each prediction
                for forecast in backfill_forecasts:
                    monitor.log_prediction(
                        location_id=location_id,
                        timestamp=forecast['timestamp'],
                        predicted_aqi=forecast['predicted_aqi'],
                        input_features={'pm25': forecast['pm25'], 'temperature': forecast.get('temperature', 0)},
                        model_version=model_manager.model_metadata.get('version', 'unknown')
                    )
                    backfilled_count += 1
            except Exception as e:
                logger.warning(f"Could not backfill location {location_id}: {e}")
                continue
        
        # Now update actuals to match predictions with data
        updated_count = monitor.update_actuals()
        monitor.calculate_metrics()
        
        return {
            "message": "Backfill complete",
            "predictions_generated": backfilled_count,
            "predictions_matched": updated_count
        }
    except Exception as e:
        logger.error(f"Error in backfill: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
