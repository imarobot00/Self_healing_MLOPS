"""
Prediction Tracker - Saves predictions and compares with actuals
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from prometheus_client import Gauge, Counter
import logging

logger = logging.getLogger(__name__)

# Prometheus metrics for prediction accuracy
prediction_error_gauge = Gauge('prediction_error_aqi', 'Prediction error (predicted - actual)', ['location_id'])
prediction_mae_gauge = Gauge('prediction_mae', 'Mean Absolute Error of predictions', ['location_id'])
prediction_accuracy_gauge = Gauge('prediction_accuracy_percent', 'Prediction accuracy percentage', ['location_id'])
predictions_evaluated = Counter('predictions_evaluated_total', 'Total predictions evaluated against actuals')

class PredictionTracker:
    def __init__(self, storage_dir: str = "/logs/predictions"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.predictions_file = self.storage_dir / "forecast_predictions.jsonl"
        self.evaluation_file = self.storage_dir / "prediction_evaluations.jsonl"
        
    def save_prediction(self, location_id: int, forecast_timestamp: str, predicted_aqi: float, 
                        predicted_pm25: float, model_version: str):
        """Save a prediction when user clicks forecast"""
        prediction = {
            "saved_at": datetime.utcnow().isoformat(),
            "location_id": location_id,
            "forecast_timestamp": forecast_timestamp,
            "predicted_aqi": predicted_aqi,
            "predicted_pm25": predicted_pm25,
            "model_version": model_version,
            "evaluated": False
        }
        
        with open(self.predictions_file, "a") as f:
            f.write(json.dumps(prediction) + "\n")
        
        logger.info(f"Saved prediction: location={location_id}, time={forecast_timestamp}, aqi={predicted_aqi}")
        
    def load_pending_predictions(self):
        """Load predictions that haven't been evaluated yet"""
        if not self.predictions_file.exists():
            return []
        
        pending = []
        with open(self.predictions_file, "r") as f:
            for line in f:
                try:
                    pred = json.loads(line.strip())
                    if not pred.get("evaluated", False):
                        pending.append(pred)
                except:
                    continue
        return pending
    
    def evaluate_predictions(self, data_dir: str):
        """Compare saved predictions with actual data and update Prometheus metrics"""
        pending = self.load_pending_predictions()
        if not pending:
            logger.info("No pending predictions to evaluate")
            return {"evaluated": 0, "errors": []}
        
        # Load actual data from dataset
        actuals = self._load_actuals(data_dir)
        if not actuals:
            return {"evaluated": 0, "errors": []}
        
        evaluated = []
        errors_by_location = {}
        
        for pred in pending:
            location_id = pred["location_id"]
            forecast_time = datetime.fromisoformat(pred["forecast_timestamp"].replace("Z", "+00:00").replace("+00:00", ""))
            
            # Find actual value for this location and time
            actual = self._find_actual(actuals, location_id, forecast_time)
            
            if actual:
                error = pred["predicted_aqi"] - actual["aqi"]
                abs_error = abs(error)
                
                evaluation = {
                    "evaluated_at": datetime.utcnow().isoformat(),
                    "location_id": location_id,
                    "forecast_timestamp": pred["forecast_timestamp"],
                    "predicted_aqi": pred["predicted_aqi"],
                    "actual_aqi": actual["aqi"],
                    "error": round(error, 2),
                    "abs_error": round(abs_error, 2),
                    "model_version": pred["model_version"]
                }
                
                # Save evaluation
                with open(self.evaluation_file, "a") as f:
                    f.write(json.dumps(evaluation) + "\n")
                
                # Update Prometheus metrics
                prediction_error_gauge.labels(location_id=str(location_id)).set(error)
                predictions_evaluated.inc()
                
                # Track for MAE calculation
                if location_id not in errors_by_location:
                    errors_by_location[location_id] = []
                errors_by_location[location_id].append(abs_error)
                
                evaluated.append(evaluation)
                pred["evaluated"] = True
        
        # Update MAE and accuracy by location
        for loc_id, errors in errors_by_location.items():
            mae = sum(errors) / len(errors)
            accuracy = max(0, 100 - mae)  # Simple accuracy metric
            prediction_mae_gauge.labels(location_id=str(loc_id)).set(mae)
            prediction_accuracy_gauge.labels(location_id=str(loc_id)).set(accuracy)
        
        # Rewrite predictions file with evaluated status
        self._update_predictions_file(pending)
        
        logger.info(f"Evaluated {len(evaluated)} predictions")
        return {"evaluated": len(evaluated), "evaluations": evaluated}
    
    def _load_actuals(self, data_dir: str):
        """Load actual AQI values from dataset JSON files"""
        actuals = []
        data_path = Path(data_dir)
        
        for json_file in data_path.glob("location_*.json"):
            try:
                location_id = int(json_file.stem.split("_")[1])
                with open(json_file) as f:
                    data = json.load(f)
                
                for record in data:
                    # Handle both string and dict parameter formats
                    param = record.get('parameter')
                    if isinstance(param, dict):
                        param_name = param.get('name', '')
                    else:
                        param_name = param
                    
                    if param_name == 'pm25':
                        timestamp = record['period']['datetimeTo']['utc']
                        pm25 = record['value']
                        aqi = self._pm25_to_aqi(pm25)
                        actuals.append({
                            "location_id": location_id,
                            "timestamp": datetime.fromisoformat(timestamp.replace("Z", "")),
                            "pm25": pm25,
                            "aqi": aqi
                        })
            except Exception as e:
                logger.error(f"Error loading {json_file}: {e}")
                
        return actuals
    
    def _find_actual(self, actuals, location_id, forecast_time, tolerance_minutes=30):
        """Find actual value matching location and time within tolerance"""
        for actual in actuals:
            if actual["location_id"] == location_id:
                time_diff = abs((actual["timestamp"] - forecast_time).total_seconds())
                if time_diff <= tolerance_minutes * 60:
                    return actual
        return None
    
    def _pm25_to_aqi(self, pm25):
        """Convert PM2.5 to AQI using EPA formula"""
        if pm25 <= 12:
            return round((50/12) * pm25, 2)
        elif pm25 <= 35.4:
            return round(50 + (50/23.4) * (pm25 - 12), 2)
        elif pm25 <= 55.4:
            return round(100 + (50/20) * (pm25 - 35.4), 2)
        elif pm25 <= 150.4:
            return round(150 + (50/95) * (pm25 - 55.4), 2)
        elif pm25 <= 250.4:
            return round(200 + (100/100) * (pm25 - 150.4), 2)
        else:
            return round(300 + (100/150) * (pm25 - 250.4), 2)
    
    def _update_predictions_file(self, predictions):
        """Rewrite predictions file with updated evaluated status"""
        # Read all predictions
        all_preds = []
        if self.predictions_file.exists():
            with open(self.predictions_file, "r") as f:
                for line in f:
                    try:
                        all_preds.append(json.loads(line.strip()))
                    except:
                        continue
        
        # Update evaluated status
        pred_map = {(p["location_id"], p["forecast_timestamp"]): p for p in predictions}
        for pred in all_preds:
            key = (pred["location_id"], pred["forecast_timestamp"])
            if key in pred_map:
                pred["evaluated"] = pred_map[key].get("evaluated", False)
        
        # Rewrite file
        with open(self.predictions_file, "w") as f:
            for pred in all_preds:
                f.write(json.dumps(pred) + "\n")
    
    def get_evaluation_summary(self):
        """Get summary of all evaluations for dashboard"""
        if not self.evaluation_file.exists():
            return {"total": 0, "by_location": {}}
        
        evaluations = []
        with open(self.evaluation_file, "r") as f:
            for line in f:
                try:
                    evaluations.append(json.loads(line.strip()))
                except:
                    continue
        
        if not evaluations:
            return {"total": 0, "by_location": {}}
        
        # Calculate summary stats
        by_location = {}
        for ev in evaluations:
            loc = str(ev["location_id"])
            if loc not in by_location:
                by_location[loc] = {"errors": [], "count": 0}
            by_location[loc]["errors"].append(ev["abs_error"])
            by_location[loc]["count"] += 1
        
        # Calculate MAE per location
        for loc, data in by_location.items():
            data["mae"] = round(sum(data["errors"]) / len(data["errors"]), 2)
            data["max_error"] = round(max(data["errors"]), 2)
            data["min_error"] = round(min(data["errors"]), 2)
            del data["errors"]
        
        total_errors = [ev["abs_error"] for ev in evaluations]
        
        return {
            "total": len(evaluations),
            "overall_mae": round(sum(total_errors) / len(total_errors), 2),
            "by_location": by_location,
            "recent": evaluations[-10:]  # Last 10 evaluations
        }
