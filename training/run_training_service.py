#!/usr/bin/env python3
"""
Training Service - Long-Running Daemon

Runs the auto-trainer in a continuous loop with health checks.
Designed for Docker containerization.
"""
import os
import sys
import time
import logging
import threading
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import health server
from health_server import start_health_server

# Service state for health checks
service_state = {
    'status': 'starting',
    'last_check': None,
    'last_check_result': None,
    'check_count': 0,
    'retrain_count': 0,
    'error_count': 0,
    'started_at': datetime.now().isoformat()
}


def update_health_state(status: str, result: dict = None):
    """Update service state for health checks"""
    service_state['status'] = status
    service_state['last_check'] = datetime.now().isoformat()
    if result:
        service_state['last_check_result'] = result


def run_training_loop():
    """Main training loop"""
    from auto_trainer import AutoTrainer
    
    # Configuration from environment
    check_interval = int(os.environ.get('TRAINING_CHECK_INTERVAL', 3600))  # 1 hour default
    drift_threshold = float(os.environ.get('DRIFT_THRESHOLD', 0.15))
    data_dir = os.environ.get('DATA_PATH', 'dataset')
    models_dir = os.environ.get('MODEL_PATH', 'training/models')
    
    logger.info("=" * 80)
    logger.info("🚀 TRAINING SERVICE STARTING")
    logger.info("=" * 80)
    logger.info(f"  Check Interval: {check_interval}s ({check_interval/60:.1f} min)")
    logger.info(f"  Drift Threshold: {drift_threshold}")
    logger.info(f"  Data Directory: {data_dir}")
    logger.info(f"  Models Directory: {models_dir}")
    logger.info("=" * 80)
    
    # Initialize trainer
    trainer = AutoTrainer(
        data_dir=data_dir,
        models_dir=models_dir,
        drift_threshold=drift_threshold
    )
    
    service_state['status'] = 'running'
    
    while True:
        try:
            logger.info("")
            logger.info("=" * 60)
            logger.info(f"🔄 Training Check #{service_state['check_count'] + 1}")
            logger.info("=" * 60)
            
            update_health_state('checking')
            service_state['check_count'] += 1
            
            # Run the trainer
            retrained, model_path, info = trainer.run(force=False)
            
            if retrained:
                service_state['retrain_count'] += 1
                logger.info(f"✅ Model retrained: {model_path}")
                update_health_state('running', {
                    'action': 'retrained',
                    'model_path': str(model_path),
                    'metrics': info.get('metrics', {})
                })
            else:
                reason = info.get('decision', 'unknown') if info else 'unknown'
                logger.info(f"⏸️  No retraining needed: {reason}")
                update_health_state('running', {
                    'action': 'skipped',
                    'reason': reason
                })
            
        except Exception as e:
            service_state['error_count'] += 1
            logger.error(f"❌ Error in training check: {e}")
            import traceback
            logger.error(traceback.format_exc())
            update_health_state('error', {'error': str(e)})
        
        # Sleep until next check
        logger.info(f"💤 Sleeping for {check_interval}s until next check...")
        time.sleep(check_interval)


def main():
    """Main entry point"""
    # Start health server
    port = int(os.environ.get('TRAINING_PORT', 8001))
    logger.info(f"Starting health server on port {port}")
    start_health_server(port=port)
    
    # Give health server time to start
    time.sleep(1)
    
    # Run training loop (blocks forever)
    try:
        run_training_loop()
    except KeyboardInterrupt:
        logger.info("\n🛑 Training service stopped by user")
        sys.exit(0)


if __name__ == '__main__':
    main()
