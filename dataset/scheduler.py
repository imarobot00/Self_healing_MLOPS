#!/usr/bin/env python3
"""
Scheduler service for automated data pipeline execution.

Runs the incremental data loader at configured intervals using APScheduler.
Supports both interval-based and cron-based scheduling.
"""
import argparse
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
import yaml

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# Import our pipeline components
from incremental_loader import IncrementalLoader
from validator import DataValidator
from monitor import create_pipeline_monitor


class PipelineScheduler:
    """Manages scheduled execution of the data pipeline."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the scheduler with configuration."""
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
        
        self.config = self._load_config(config_path)
        self.scheduler = BlockingScheduler()
        
        # Setup monitoring
        log_config = self.config.get("monitoring", {})
        alert_config = self.config.get("notifications", {})
        
        self.logger, self.metrics, self.alerts = create_pipeline_monitor(
            log_file=log_config.get("log_file", "pipeline.log"),
            log_level=log_config.get("log_level", "INFO"),
            alert_config=alert_config
        )
        
        # Track consecutive failures for alerting
        self.consecutive_failures = 0
        self.max_consecutive_failures = (
            self.config.get("monitoring", {})
            .get("alerts", {})
            .get("max_consecutive_failures", 3)
        )
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _load_config(self, config_path: Path) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except (yaml.YAMLError, IOError) as e:
            print(f"Error loading config: {e}")
            sys.exit(1)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info("Received shutdown signal, stopping scheduler...")
        self.scheduler.shutdown(wait=True)
        sys.exit(0)
    
    def run_pipeline(self):
        """Execute the data pipeline once."""
        run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.logger.info(f"Starting pipeline run: {run_id}")
        
        try:
            # Get locations from config
            locations = self.config.get("locations", [3459])
            
            # Initialize loader
            api_config = self.config.get("api", {})
            data_config = self.config.get("data", {})
            
            # Set data directory (use /app/data in Docker, current dir otherwise)
            data_dir = Path(os.getenv("DATA_DIR", "/app/data")) if os.path.exists("/app/data") else Path(__file__).parent
            loader = IncrementalLoader(data_dir=data_dir)
            
            # Run the pipeline
            start_time = datetime.utcnow()
            summary = loader.process_all_locations(locations)
            end_time = datetime.utcnow()
            
            # Record metrics
            duration = (end_time - start_time).total_seconds()
            self.metrics.record_metric("duration_seconds", duration)
            self.metrics.record_metric("total_records_fetched", summary.get("total_new_records", 0))
            self.metrics.record_metric("total_locations_processed", summary.get("total_locations", 0))
            self.metrics.record_metric("successful_locations", summary.get("successful", 0))
            self.metrics.record_metric("failed_locations", summary.get("failed", 0))
            
            # Check for failures
            if summary.get("failed", 0) > 0:
                self.consecutive_failures += 1
                self.logger.warning(
                    f"Pipeline completed with failures: {summary['failed']}/{summary['total_locations']}",
                    consecutive_failures=self.consecutive_failures
                )
                
                # Send alert if threshold exceeded
                if self.consecutive_failures >= self.max_consecutive_failures:
                    self.alerts.send_alert(
                        level="error",
                        title="Pipeline Consecutive Failures",
                        message=f"Pipeline has failed {self.consecutive_failures} times consecutively",
                        context={"summary": summary}
                    )
            else:
                # Reset failure counter on success
                if self.consecutive_failures > 0:
                    self.logger.info("Pipeline recovered from previous failures")
                    self.consecutive_failures = 0
                
                self.logger.info(
                    f"Pipeline completed successfully in {duration:.2f}s",
                    records_fetched=summary.get("total_new_records", 0),
                    locations_processed=summary.get("total_locations", 0)
                )
            
            # Optional: Run validation
            if self.config.get("validation", {}).get("enabled", False):
                self._validate_data(locations)
            
            # Finalize metrics
            self.metrics.finalize_run()
            
        except Exception as e:
            self.consecutive_failures += 1
            self.logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            self.metrics.record_error(str(e), {"run_id": run_id})
            
            # Send critical alert
            if self.consecutive_failures >= self.max_consecutive_failures:
                self.alerts.send_alert(
                    level="critical",
                    title="Pipeline Critical Failure",
                    message=f"Pipeline has failed {self.consecutive_failures} times: {e}",
                    context={"error": str(e), "run_id": run_id}
                )
    
    def _validate_data(self, locations: list):
        """Validate data for all locations."""
        self.logger.info("Running data validation...")
        
        validator = DataValidator()
        data_dir = Path(__file__).parent
        
        for location_id in locations:
            json_file = data_dir / f"location_{location_id}.json"
            if json_file.exists():
                metrics = validator.validate_file(json_file)
                
                quality_score = metrics.get("quality_score", 0)
                self.logger.info(
                    f"Validation for location {location_id}",
                    quality_score=quality_score,
                    valid_records=metrics.get("valid_records", 0),
                    invalid_records=metrics.get("invalid_records", 0)
                )
                
                # Alert on poor data quality
                if quality_score < 90:
                    self.alerts.send_alert(
                        level="warning",
                        title=f"Low Data Quality: Location {location_id}",
                        message=f"Data quality score: {quality_score:.2f}%",
                        context=metrics
                    )
    
    def start_interval_schedule(self, hours: int = 2):
        """
        Start the scheduler with interval-based triggering.
        
        Args:
            hours: Interval in hours between pipeline runs
        """
        self.logger.info(f"Starting scheduler with {hours}-hour interval")
        
        # Schedule the job
        self.scheduler.add_job(
            self.run_pipeline,
            trigger=IntervalTrigger(hours=hours),
            id="data_pipeline",
            name="OpenAQ Data Pipeline",
            max_instances=1,  # Prevent overlapping runs
            replace_existing=True
        )
        
        # Run immediately on startup
        self.logger.info("Running pipeline immediately on startup...")
        self.run_pipeline()
        
        # Start the scheduler
        self.logger.info("Scheduler started, waiting for next trigger...")
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.logger.info("Scheduler stopped")
    
    def start_cron_schedule(self, cron_expression: str = "0 */2 * * *"):
        """
        Start the scheduler with cron-based triggering.
        
        Args:
            cron_expression: Cron expression (default: every 2 hours at minute 0)
        """
        self.logger.info(f"Starting scheduler with cron: {cron_expression}")
        
        # Parse cron expression
        parts = cron_expression.split()
        if len(parts) != 5:
            self.logger.error("Invalid cron expression format")
            sys.exit(1)
        
        minute, hour, day, month, day_of_week = parts
        
        # Schedule the job
        self.scheduler.add_job(
            self.run_pipeline,
            trigger=CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week
            ),
            id="data_pipeline",
            name="OpenAQ Data Pipeline",
            max_instances=1,
            replace_existing=True
        )
        
        # Run immediately on startup
        self.logger.info("Running pipeline immediately on startup...")
        self.run_pipeline()
        
        # Start the scheduler
        next_run = self.scheduler.get_job("data_pipeline").next_run_time
        self.logger.info(f"Scheduler started, next run at: {next_run}")
        
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.logger.info("Scheduler stopped")
    
    def run_once(self):
        """Run the pipeline once without scheduling."""
        self.logger.info("Running pipeline once (no scheduling)")
        self.run_pipeline()


def main():
    """Command-line interface for the scheduler."""
    parser = argparse.ArgumentParser(
        description="Schedule and run the OpenAQ data pipeline"
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to config.yaml file"
    )
    parser.add_argument(
        "--mode", "-m",
        type=str,
        choices=["interval", "cron", "once"],
        default="interval",
        help="Scheduling mode: interval, cron, or once"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=2,
        help="Interval in hours (for interval mode, default: 2)"
    )
    parser.add_argument(
        "--cron",
        type=str,
        default="0 */2 * * *",
        help="Cron expression (for cron mode, default: '0 */2 * * *')"
    )
    
    args = parser.parse_args()
    
    # Initialize scheduler
    config_path = Path(args.config) if args.config else None
    scheduler = PipelineScheduler(config_path=config_path)
    
    # Start in requested mode
    if args.mode == "interval":
        scheduler.start_interval_schedule(hours=args.interval)
    elif args.mode == "cron":
        scheduler.start_cron_schedule(cron_expression=args.cron)
    elif args.mode == "once":
        scheduler.run_once()


if __name__ == "__main__":
    main()
