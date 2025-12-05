#!/usr/bin/env python3
"""
Monitoring and logging utilities for the data pipeline.

Provides structured logging, metrics collection, and alerting capabilities.
"""
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
import traceback


class PipelineLogger:
    """Structured logger for the data pipeline."""
    
    def __init__(
        self,
        name: str = "data_pipeline",
        log_file: Optional[Path] = None,
        log_level: str = "INFO"
    ):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler with formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler if log_file specified
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(getattr(logging, log_level.upper()))
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
    
    def info(self, message: str, **kwargs):
        """Log info message with optional structured data."""
        if kwargs:
            message = f"{message} | {json.dumps(kwargs)}"
        self.logger.info(message)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with optional structured data."""
        if kwargs:
            message = f"{message} | {json.dumps(kwargs)}"
        self.logger.warning(message)
    
    def error(self, message: str, exc_info: bool = False, **kwargs):
        """Log error message with optional structured data and exception info."""
        if kwargs:
            message = f"{message} | {json.dumps(kwargs)}"
        self.logger.error(message, exc_info=exc_info)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with optional structured data."""
        if kwargs:
            message = f"{message} | {json.dumps(kwargs)}"
        self.logger.debug(message)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with optional structured data."""
        if kwargs:
            message = f"{message} | {json.dumps(kwargs)}"
        self.logger.critical(message)


class MetricsCollector:
    """Collects and tracks pipeline metrics."""
    
    def __init__(self, metrics_file: Optional[Path] = None):
        self.metrics_file = metrics_file
        self.current_run = {
            "start_time": datetime.utcnow().isoformat() + "Z",
            "metrics": {},
            "errors": []
        }
    
    def record_metric(self, name: str, value: Any):
        """Record a metric value."""
        self.current_run["metrics"][name] = value
    
    def increment_metric(self, name: str, amount: int = 1):
        """Increment a counter metric."""
        current = self.current_run["metrics"].get(name, 0)
        self.current_run["metrics"][name] = current + amount
    
    def record_error(self, error: str, context: Optional[Dict] = None):
        """Record an error occurrence."""
        error_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "error": error,
            "context": context or {}
        }
        self.current_run["errors"].append(error_entry)
    
    def finalize_run(self):
        """Finalize the current run and save metrics."""
        self.current_run["end_time"] = datetime.utcnow().isoformat() + "Z"
        
        if self.metrics_file:
            self._save_metrics()
        
        return self.current_run
    
    def _save_metrics(self):
        """Append current run metrics to metrics file."""
        try:
            # Load existing metrics
            if self.metrics_file.exists():
                with open(self.metrics_file, "r", encoding="utf-8") as f:
                    all_metrics = json.load(f)
            else:
                all_metrics = {"runs": []}
            
            # Append current run
            all_metrics["runs"].append(self.current_run)
            
            # Keep only last 100 runs
            if len(all_metrics["runs"]) > 100:
                all_metrics["runs"] = all_metrics["runs"][-100:]
            
            # Save back
            with open(self.metrics_file, "w", encoding="utf-8") as f:
                json.dump(all_metrics, f, ensure_ascii=False, indent=2)
                
        except (IOError, json.JSONDecodeError) as e:
            print(f"Warning: Could not save metrics: {e}")
    
    def get_summary(self) -> Dict:
        """Get a summary of current metrics."""
        metrics = self.current_run["metrics"]
        return {
            "total_records_fetched": metrics.get("total_records_fetched", 0),
            "total_records_deduplicated": metrics.get("total_records_deduplicated", 0),
            "total_locations_processed": metrics.get("total_locations_processed", 0),
            "successful_locations": metrics.get("successful_locations", 0),
            "failed_locations": metrics.get("failed_locations", 0),
            "total_errors": len(self.current_run["errors"]),
            "duration_seconds": metrics.get("duration_seconds", 0)
        }


class AlertManager:
    """Manages alerts and notifications for pipeline events."""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.notifications_enabled = self.config.get("enabled", False)
    
    def send_alert(
        self,
        level: str,
        title: str,
        message: str,
        context: Optional[Dict] = None
    ):
        """
        Send an alert notification.
        
        Args:
            level: Alert level (info, warning, error, critical)
            title: Alert title
            message: Alert message
            context: Additional context data
        """
        if not self.notifications_enabled:
            return
        
        alert = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "title": title,
            "message": message,
            "context": context or {}
        }
        
        # Email alerts
        if self.config.get("email", {}).get("enabled"):
            self._send_email_alert(alert)
        
        # Slack alerts
        if self.config.get("slack", {}).get("enabled"):
            self._send_slack_alert(alert)
        
        # Webhook alerts
        if self.config.get("webhook", {}).get("enabled"):
            self._send_webhook_alert(alert)
    
    def _send_email_alert(self, alert: Dict):
        """Send email notification."""
        # Placeholder for email implementation
        print(f"[EMAIL ALERT] {alert['title']}: {alert['message']}")
    
    def _send_slack_alert(self, alert: Dict):
        """Send Slack notification."""
        webhook_url = os.getenv("SLACK_WEBHOOK_URL") or self.config.get("slack", {}).get("webhook_url")
        
        if not webhook_url:
            return
        
        try:
            import requests
            
            # Format Slack message
            color = {
                "info": "#36a64f",
                "warning": "#ff9900",
                "error": "#ff0000",
                "critical": "#8b0000"
            }.get(alert["level"], "#808080")
            
            payload = {
                "attachments": [{
                    "color": color,
                    "title": alert["title"],
                    "text": alert["message"],
                    "footer": "Data Pipeline Monitor",
                    "ts": int(datetime.utcnow().timestamp())
                }]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
        except Exception as e:
            print(f"Failed to send Slack alert: {e}")
    
    def _send_webhook_alert(self, alert: Dict):
        """Send webhook notification."""
        webhook_url = os.getenv("WEBHOOK_URL") or self.config.get("webhook", {}).get("url")
        
        if not webhook_url:
            return
        
        try:
            import requests
            
            response = requests.post(webhook_url, json=alert, timeout=10)
            response.raise_for_status()
            
        except Exception as e:
            print(f"Failed to send webhook alert: {e}")


def create_pipeline_monitor(
    log_file: Optional[str] = None,
    metrics_file: Optional[str] = None,
    log_level: str = "INFO",
    alert_config: Optional[Dict] = None
) -> tuple:
    """
    Factory function to create logger, metrics collector, and alert manager.
    
    Returns:
        (logger, metrics_collector, alert_manager)
    """
    log_path = Path(log_file) if log_file else Path(__file__).parent / "pipeline.log"
    metrics_path = Path(metrics_file) if metrics_file else Path(__file__).parent / "metrics.json"
    
    logger = PipelineLogger(log_file=log_path, log_level=log_level)
    metrics = MetricsCollector(metrics_file=metrics_path)
    alerts = AlertManager(config=alert_config)
    
    return logger, metrics, alerts


def main():
    """Test the monitoring utilities."""
    logger, metrics, alerts = create_pipeline_monitor(log_level="DEBUG")
    
    logger.info("Pipeline started", location_count=5)
    logger.debug("Fetching data", location_id=3459)
    
    metrics.record_metric("total_records_fetched", 1500)
    metrics.increment_metric("successful_locations")
    metrics.record_error("API timeout", {"location_id": 3459})
    
    summary = metrics.get_summary()
    logger.info("Metrics summary", **summary)
    
    alerts.send_alert(
        level="warning",
        title="High Error Rate",
        message="Pipeline experienced 3 consecutive failures",
        context={"location_id": 3459}
    )
    
    final_metrics = metrics.finalize_run()
    logger.info("Pipeline completed", total_errors=len(final_metrics["errors"]))


if __name__ == "__main__":
    main()
