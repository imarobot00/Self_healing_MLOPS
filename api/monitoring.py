"""
Model Performance Monitoring System
====================================

Tracks predictions, compares with actuals, monitors degradation, and alerts.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
from collections import deque

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """
    Monitors model predictions and performance over time.
    
    Features:
    - Logs all predictions with metadata
    - Fetches actual values from data files
    - Calculates rolling performance metrics
    - Detects performance degradation
    - Triggers alerts when metrics degrade
    """
    
    def __init__(self, 
                 log_dir: str = "logs/predictions",
                 metrics_dir: str = "logs/metrics",
                 window_size: int = 100,
                 alert_threshold_mae: float = 15.0,
                 alert_threshold_r2: float = 0.75):
        """
        Initialize the performance monitor.
        
        Parameters:
        -----------
        log_dir : str
            Directory to store prediction logs
        metrics_dir : str
            Directory to store metrics history
        window_size : int
            Number of recent predictions to use for rolling metrics
        alert_threshold_mae : float
            MAE threshold - alert if exceeded
        alert_threshold_r2 : float
            R² threshold - alert if below this value
        """
        self.log_dir = Path(log_dir)
        self.metrics_dir = Path(metrics_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        
        self.window_size = window_size
        self.alert_threshold_mae = alert_threshold_mae
        self.alert_threshold_r2 = alert_threshold_r2
        
        # In-memory storage for recent predictions
        self.recent_predictions = deque(maxlen=window_size)
        self.recent_errors = deque(maxlen=window_size)
        
        # Metrics history
        self.metrics_history = []
        
        # Alert log
        self.alerts = []
        
        # Load sample predictions on startup
        self._load_sample_predictions()
        
        logger.info(f"PerformanceMonitor initialized - MAE threshold: {alert_threshold_mae}, R² threshold: {alert_threshold_r2}")
    
    def _load_sample_predictions(self):
        """Load sample predictions from JSON file for demo purposes."""
        sample_file = Path(__file__).parent / "sample_predictions.json"
        if sample_file.exists():
            try:
                with open(sample_file, 'r') as f:
                    data = json.load(f)
                    predictions = data.get('predictions', [])
                    for pred in predictions:
                        self.recent_predictions.append(pred)
                    logger.info(f"Loaded {len(predictions)} sample predictions")
            except Exception as e:
                logger.error(f"Error loading sample predictions: {e}")
    
    def log_prediction(self, 
                      location_id: int,
                      timestamp: str,
                      predicted_aqi: float,
                      input_features: Dict,
                      model_version: str,
                      response_time_ms: float = None) -> str:
        """
        Log a prediction for future monitoring.
        
        Returns:
        --------
        str : Prediction ID for tracking
        """
        prediction_id = f"{location_id}_{timestamp}_{datetime.now().timestamp()}"
        
        log_entry = {
            'prediction_id': prediction_id,
            'timestamp': datetime.now().isoformat(),
            'location_id': location_id,
            'forecast_timestamp': timestamp,
            'predicted_aqi': predicted_aqi,
            'model_version': model_version,
            'input_features': {
                'pm25': input_features.get('pm25'),
                'pm1': input_features.get('pm1'),
                'temperature': input_features.get('temperature'),
                'humidity': input_features.get('relativehumidity')
            },
            'response_time_ms': response_time_ms,
            'actual_aqi': None,  # Will be filled later
            'error': None
        }
        
        # Save to daily log file
        log_file = self.log_dir / f"predictions_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        # Store in memory for quick access
        self.recent_predictions.append(log_entry)
        
        return prediction_id
    
    def log_request(self, 
                   endpoint: str,
                   method: str,
                   params: Dict,
                   status_code: int,
                   response_time_ms: float):
        """Log API request for monitoring."""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'endpoint': endpoint,
            'method': method,
            'params': params,
            'status_code': status_code,
            'response_time_ms': response_time_ms
        }
        
        # Save to daily request log
        log_file = self.log_dir / f"requests_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def update_actuals(self, dataset_dir: str = "../dataset") -> int:
        """
        Fetch actual AQI values from data files and update prediction logs.
        
        Returns:
        --------
        int : Number of predictions updated with actual values
        """
        dataset_path = Path(dataset_dir)
        updated_count = 0
        
        # Load recent prediction logs (last 7 days) and store ALL entries
        all_entries_by_date = {}
        for days_back in range(7):
            date = datetime.now() - timedelta(days=days_back)
            date_str = date.strftime('%Y%m%d')
            log_file = self.log_dir / f"predictions_{date_str}.jsonl"
            if log_file.exists():
                with open(log_file, 'r') as f:
                    all_entries = [json.loads(line.strip()) for line in f]
                    all_entries_by_date[date_str] = {
                        'file': log_file,
                        'entries': all_entries
                    }
        
        if not all_entries_by_date:
            logger.info("No predictions to update with actuals")
            return 0
        
        # Group predictions needing update by location
        by_location = {}
        for date_str, data in all_entries_by_date.items():
            for entry in data['entries']:
                if entry.get('actual_aqi') is None:  # Not yet updated
                    loc_id = entry['location_id']
                    if loc_id not in by_location:
                        by_location[loc_id] = []
                    by_location[loc_id].append((entry, date_str))
        
        # For each location, load data and match timestamps
        for loc_id, predictions in by_location.items():
            location_file = dataset_path / f"location_{loc_id}.json"
            if not location_file.exists():
                continue
            
            try:
                with open(location_file, 'r') as f:
                    data = json.load(f)
                
                # Handle both list and dict formats
                results = data if isinstance(data, list) else data.get('results', [])
                
                # Build a lookup dict: timestamp -> pm25 value
                # Normalize timestamps to compare properly
                actual_data = {}
                for item in results:
                    try:
                        ts = item['period']['datetimeFrom']['utc']
                        # Normalize timestamp: convert to datetime then back to ISO without microseconds
                        ts_normalized = pd.to_datetime(ts).replace(microsecond=0, tzinfo=None).isoformat() + 'Z'
                        
                        # Handle both string and dict parameter formats
                        param = item['parameter']
                        if isinstance(param, dict):
                            param = param.get('name', '')
                        value = item['value']
                        
                        if param == 'pm25':
                            actual_data[ts_normalized] = value
                            # Also store with +00:00 suffix for compatibility
                            actual_data[ts_normalized.replace('Z', '+00:00')] = value
                    except (KeyError, TypeError):
                        continue
                
                # Match predictions with actuals
                for pred, date_str in predictions:
                    forecast_ts = pred['forecast_timestamp']
                    # Normalize prediction timestamp too
                    try:
                        pred_ts_normalized = pd.to_datetime(forecast_ts).replace(microsecond=0, tzinfo=None).isoformat() + 'Z'
                    except:
                        pred_ts_normalized = forecast_ts
                    
                    # Try both formats
                    if pred_ts_normalized in actual_data:
                        actual_pm25 = actual_data[pred_ts_normalized]
                        actual_aqi = self._calculate_aqi(actual_pm25)
                        error = abs(pred['predicted_aqi'] - actual_aqi)
                        
                        pred['actual_aqi'] = actual_aqi
                        pred['error'] = error
                        
                        # Update in memory
                        self.recent_errors.append(error)
                        
                        updated_count += 1
                    elif forecast_ts in actual_data:
                        actual_pm25 = actual_data[forecast_ts]
                        actual_aqi = self._calculate_aqi(actual_pm25)
                        error = abs(pred['predicted_aqi'] - actual_aqi)
                        
                        pred['actual_aqi'] = actual_aqi
                        pred['error'] = error
                        
                        # Update in memory
                        self.recent_errors.append(error)
                        
                        updated_count += 1
                
            except Exception as e:
                logger.error(f"Error updating actuals for location {loc_id}: {e}")
        
        # Write all updated entries back to files
        for date_str, data in all_entries_by_date.items():
            log_file = data['file']
            entries = data['entries']
            with open(log_file, 'w') as f:
                for entry in entries:
                    f.write(json.dumps(entry) + '\n')
        
        logger.info(f"Updated {updated_count} predictions with actual values")
        
        # Reload predictions from log files into memory for metrics calculation
        self._reload_predictions_from_logs()
        
        return updated_count
    
    def _reload_predictions_from_logs(self, days: int = 1):
        """Reload predictions from log files into memory."""
        self.recent_predictions.clear()
        
        for days_back in range(days):
            date = datetime.now() - timedelta(days=days_back)
            log_file = self.log_dir / f"predictions_{date.strftime('%Y%m%d')}.jsonl"
            if log_file.exists():
                with open(log_file, 'r') as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            self.recent_predictions.append(entry)
                        except json.JSONDecodeError:
                            continue
        
        logger.info(f"Reloaded {len(self.recent_predictions)} predictions from logs")
    
    def calculate_metrics_by_location(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculate metrics grouped by location.
        Returns dict with location_id as key and metrics as value.
        """
        location_metrics = {}
        
        # Group ALL predictions by location (not just those with actuals)
        all_predictions_by_loc = {}
        predictions_with_actuals_by_loc = {}
        
        for p in self.recent_predictions:
            loc_id = str(p.get('location_id', 'unknown'))
            if loc_id not in all_predictions_by_loc:
                all_predictions_by_loc[loc_id] = []
            all_predictions_by_loc[loc_id].append(p)
            
            if p.get('actual_aqi') is not None:
                if loc_id not in predictions_with_actuals_by_loc:
                    predictions_with_actuals_by_loc[loc_id] = []
                predictions_with_actuals_by_loc[loc_id].append(p)
        
        # Calculate metrics for each location
        for location_id, all_preds in all_predictions_by_loc.items():
            total_count = len(all_preds)
            predictions_with_actuals = predictions_with_actuals_by_loc.get(location_id, [])
            actuals_count = len(predictions_with_actuals)
            
            if actuals_count < 3:  # Need at least 3 for meaningful metrics
                location_metrics[location_id] = {
                    'mae': None,
                    'rmse': None,
                    'r2': None,
                    'count': total_count,
                    'actuals_count': actuals_count,
                    'coverage': round(actuals_count / total_count, 3) if total_count > 0 else 0,
                    'status': 'insufficient_data'
                }
                continue
            
            predictions = predictions_with_actuals
            
            predicted = np.array([p['predicted_aqi'] for p in predictions])
            actual = np.array([p['actual_aqi'] for p in predictions])
            
            mae = float(np.mean(np.abs(predicted - actual)))
            rmse = float(np.sqrt(np.mean((predicted - actual) ** 2)))
            
            ss_res = np.sum((actual - predicted) ** 2)
            ss_tot = np.sum((actual - np.mean(actual)) ** 2)
            r2 = float(1 - (ss_res / ss_tot)) if ss_tot != 0 else 0.0
            
            # Determine status
            status = 'good'
            if mae > self.alert_threshold_mae or r2 < self.alert_threshold_r2:
                status = 'degraded'
            
            location_metrics[location_id] = {
                'mae': round(mae, 2),
                'rmse': round(rmse, 2),
                'r2': round(r2, 3),
                'count': total_count,
                'actuals_count': actuals_count,
                'coverage': round(actuals_count / total_count, 3) if total_count > 0 else 0,
                'status': status,
                'avg_error': round(float(np.mean(predicted - actual)), 2),
                'max_error': round(float(np.max(np.abs(predicted - actual))), 2)
            }
        
        return location_metrics
    
    def calculate_metrics(self) -> Dict:
        """
        Calculate current performance metrics from recent predictions.
        
        Returns:
        --------
        Dict : Current metrics (MAE, RMSE, R², count)
        """
        predictions_with_actuals = [
            p for p in self.recent_predictions 
            if p.get('actual_aqi') is not None
        ]
        
        if len(predictions_with_actuals) < 5:
            logger.warning("Not enough predictions with actuals to calculate metrics")
            return {
                'mae': None,
                'rmse': None,
                'r2': None,
                'count': len(predictions_with_actuals),
                'status': 'insufficient_data'
            }
        
        # Extract predictions and actuals
        y_pred = np.array([p['predicted_aqi'] for p in predictions_with_actuals])
        y_true = np.array([p['actual_aqi'] for p in predictions_with_actuals])
        
        # Calculate metrics
        mae = np.mean(np.abs(y_pred - y_true))
        rmse = np.sqrt(np.mean((y_pred - y_true) ** 2))
        
        # R² score
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'mae': float(mae),
            'rmse': float(rmse),
            'r2': float(r2),
            'count': len(predictions_with_actuals),
            'status': 'ok'
        }
        
        # Check for degradation
        if mae > self.alert_threshold_mae:
            metrics['status'] = 'degraded'
            self._trigger_alert('MAE_THRESHOLD', f"MAE ({mae:.2f}) exceeds threshold ({self.alert_threshold_mae})")
        
        if r2 < self.alert_threshold_r2:
            metrics['status'] = 'degraded'
            self._trigger_alert('R2_THRESHOLD', f"R² ({r2:.4f}) below threshold ({self.alert_threshold_r2})")
        
        # Save to history
        self.metrics_history.append(metrics)
        
        # Save to file
        metrics_file = self.metrics_dir / f"metrics_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(metrics_file, 'a') as f:
            f.write(json.dumps(metrics) + '\n')
        
        logger.info(f"Metrics calculated - MAE: {mae:.2f}, RMSE: {rmse:.2f}, R²: {r2:.4f}, Status: {metrics['status']}")
        
        return metrics
    
    def get_metrics_history(self, days: int = 7) -> List[Dict]:
        """Get metrics history for the last N days."""
        history = []
        
        for days_back in range(days):
            date = datetime.now() - timedelta(days=days_back)
            metrics_file = self.metrics_dir / f"metrics_{date.strftime('%Y%m%d')}.jsonl"
            if metrics_file.exists():
                with open(metrics_file, 'r') as f:
                    for line in f:
                        history.append(json.loads(line.strip()))
        
        return sorted(history, key=lambda x: x['timestamp'])
    
    def get_recent_predictions(self, limit: int = 50) -> List[Dict]:
        """Get recent predictions with their actuals."""
        return list(self.recent_predictions)[-limit:]
    
    def get_alerts(self, hours: int = 24) -> List[Dict]:
        """Get recent alerts."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            alert for alert in self.alerts
            if datetime.fromisoformat(alert['timestamp']) > cutoff
        ]
    
    def get_summary(self) -> Dict:
        """Get overall monitoring summary."""
        total_predictions = len(self.recent_predictions)
        predictions_with_actuals = sum(
            1 for p in self.recent_predictions 
            if p.get('actual_aqi') is not None
        )
        
        recent_metrics = self.metrics_history[-1] if self.metrics_history else None
        location_metrics = self.calculate_metrics_by_location()
        
        return {
            'total_predictions': total_predictions,
            'predictions_with_actuals': predictions_with_actuals,
            'coverage_rate': predictions_with_actuals / total_predictions if total_predictions > 0 else 0,
            'recent_metrics': recent_metrics,
            'alert_count_24h': len(self.get_alerts(hours=24)),
            'monitoring_status': 'healthy' if recent_metrics and recent_metrics.get('status') == 'ok' else 'attention_needed',
            'location_metrics': location_metrics
        }
    
    def get_recent_alerts(self, hours: int = 24) -> List[Dict]:
        """Alias for get_alerts for backward compatibility."""
        return self.get_alerts(hours=hours)
        recent_alerts = self.get_alerts(hours=24)
        
        # Calculate average response time
        response_times = [
            p['response_time_ms'] for p in self.recent_predictions
            if p.get('response_time_ms') is not None
        ]
        avg_response_time = np.mean(response_times) if response_times else None
        
        return {
            'total_predictions': total_predictions,
            'predictions_with_actuals': predictions_with_actuals,
            'coverage_rate': predictions_with_actuals / total_predictions if total_predictions > 0 else 0,
            'recent_metrics': recent_metrics,
            'alert_count_24h': len(recent_alerts),
            'avg_response_time_ms': float(avg_response_time) if avg_response_time else None,
            'monitoring_status': 'healthy' if not recent_alerts else 'attention_needed'
        }
    
    def _trigger_alert(self, alert_type: str, message: str):
        """Trigger a performance alert."""
        alert = {
            'timestamp': datetime.now().isoformat(),
            'type': alert_type,
            'message': message,
            'severity': 'warning'
        }
        
        self.alerts.append(alert)
        
        # Save to alert log
        alert_file = self.metrics_dir / f"alerts_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(alert_file, 'a') as f:
            f.write(json.dumps(alert) + '\n')
        
        logger.warning(f"🚨 ALERT: {alert_type} - {message}")
    
    @staticmethod
    def _calculate_aqi(pm25: float) -> float:
        """Calculate AQI from PM2.5 using EPA formula."""
        if pm25 <= 12.0:
            return ((50 - 0) / (12.0 - 0.0)) * (pm25 - 0.0) + 0
        elif pm25 <= 35.4:
            return ((100 - 51) / (35.4 - 12.1)) * (pm25 - 12.1) + 51
        elif pm25 <= 55.4:
            return ((150 - 101) / (55.4 - 35.5)) * (pm25 - 35.5) + 101
        elif pm25 <= 150.4:
            return ((200 - 151) / (150.4 - 55.5)) * (pm25 - 55.5) + 151
        elif pm25 <= 250.4:
            return ((300 - 201) / (250.4 - 150.5)) * (pm25 - 150.5) + 201
        elif pm25 <= 350.4:
            return ((400 - 301) / (350.4 - 250.5)) * (pm25 - 250.5) + 301
        else:
            return ((500 - 401) / (500.4 - 350.5)) * (pm25 - 350.5) + 401
