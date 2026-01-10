#!/usr/bin/env python3
"""
Orchestrator Service - Long-Running Daemon

Runs the self-healing orchestrator in a continuous loop with health checks.
Designed for Docker containerization.

Features:
- Drift detection
- Prediction accuracy monitoring  
- Automatic retraining trigger
"""
import os
import sys
import time
import logging
import threading
import subprocess
import requests
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
    'last_workflow': None,
    'check_count': 0,
    'heal_count': 0,
    'retrain_count': 0,
    'error_count': 0,
    'started_at': datetime.now().isoformat()
}


def check_retraining_needed(api_url: str) -> dict:
    """Check if retraining is needed by calling the API"""
    try:
        response = requests.get(f"{api_url}/retraining-status", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Failed to get retraining status: {response.status_code}")
            return None
    except Exception as e:
        logger.warning(f"Could not reach API for retraining status: {e}")
        return None


def trigger_retraining(api_url: str) -> bool:
    """Trigger retraining via API and run the actual retraining"""
    try:
        # Record the trigger in API (for Prometheus)
        requests.post(f"{api_url}/trigger-retraining", timeout=10)
        
        # Run the actual retraining
        logger.info("🔧 Starting model retraining...")
        
        result = subprocess.run(
            ["python", "/training/retrain_model.py"],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        if result.returncode == 0:
            logger.info("✅ Retraining completed successfully")
            logger.info(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
            return True
        else:
            logger.error(f"❌ Retraining failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("❌ Retraining timed out after 10 minutes")
        return False
    except Exception as e:
        logger.error(f"❌ Retraining error: {e}")
        return False


def update_health_state(status: str, workflow_id: str = None, result: dict = None):
    """Update service state for health checks"""
    service_state['status'] = status
    service_state['last_check'] = datetime.now().isoformat()
    if workflow_id:
        service_state['last_workflow'] = workflow_id
    if result:
        service_state['last_result'] = result


def run_orchestrator_loop():
    """Main orchestrator loop"""
    from self_healing_orchestrator import SelfHealingOrchestrator
    
    # Configuration from environment
    check_interval = int(os.environ.get('ORCHESTRATOR_CHECK_INTERVAL', 1800))  # 30 min default
    auto_promote = os.environ.get('AUTO_PROMOTE_MARGINAL', 'false').lower() == 'true'
    api_url = os.environ.get('API_URL', 'http://localhost:8000')
    
    logger.info("=" * 80)
    logger.info("🤖 ORCHESTRATOR SERVICE STARTING")
    logger.info("=" * 80)
    logger.info(f"  Check Interval: {check_interval}s ({check_interval/60:.1f} min)")
    logger.info(f"  Auto-Promote Marginal: {auto_promote}")
    logger.info(f"  API URL: {api_url}")
    logger.info("=" * 80)
    
    # Initialize orchestrator
    orchestrator = SelfHealingOrchestrator(
        auto_promote_marginal=auto_promote
    )
    
    service_state['status'] = 'running'
    
    while True:
        try:
            logger.info("")
            logger.info("=" * 60)
            logger.info(f"🔍 Orchestrator Check #{service_state['check_count'] + 1}")
            logger.info("=" * 60)
            
            update_health_state('checking')
            service_state['check_count'] += 1
            
            # Run the orchestrator check
            result = orchestrator.check_and_heal()
            
            workflow_id = result.get('workflow_id', 'unknown')
            status = result.get('status', 'unknown')
            
            if status == 'HEALED':
                service_state['heal_count'] += 1
                logger.info(f"✅ Self-healing completed: {workflow_id}")
                update_health_state('running', workflow_id, {
                    'action': 'healed',
                    'status': status,
                    'drift_info': result.get('drift_info', {})
                })
            elif status == 'NO_DRIFT':
                logger.info(f"✅ No drift detected")
                update_health_state('running', workflow_id, {
                    'action': 'healthy',
                    'status': status
                })
            else:
                logger.info(f"📊 Drift check result: {status}")
                update_health_state('running', workflow_id, {
                    'action': 'checked',
                    'status': status
                })
            
            # ============================================
            # CHECK PREDICTION ACCURACY & AUTO-RETRAIN
            # ============================================
            logger.info("")
            logger.info("📊 Checking prediction accuracy from API...")
            
            retrain_status = check_retraining_needed(api_url)
            
            if retrain_status:
                retrain_required = retrain_status.get('retraining_required', 'NO')
                severity = retrain_status.get('severity', 'OK')
                overall_mae = retrain_status.get('overall_mae', 0)
                
                logger.info(f"   Retraining Required: {retrain_required}")
                logger.info(f"   Severity: {severity}")
                logger.info(f"   Overall MAE: {overall_mae:.2f}")
                
                if retrain_required in ['YES', 'RECOMMENDED']:
                    logger.info("")
                    logger.info("🚨 " + "=" * 50)
                    logger.info(f"🚨 RETRAINING TRIGGERED - {severity}")
                    logger.info(f"🚨 Reason: {retrain_status.get('reason', 'Unknown')}")
                    logger.info("🚨 " + "=" * 50)
                    
                    # Trigger retraining
                    success = trigger_retraining(api_url)
                    
                    if success:
                        service_state['retrain_count'] += 1
                        logger.info("✅ Retraining completed successfully!")
                    else:
                        logger.error("❌ Retraining failed!")
                else:
                    logger.info("✅ Model accuracy is acceptable, no retraining needed")
            else:
                logger.info("⚠️ Could not check retraining status (API unavailable)")
            
        except Exception as e:
            service_state['error_count'] += 1
            logger.error(f"❌ Error in orchestrator check: {e}")
            import traceback
            logger.error(traceback.format_exc())
            update_health_state('error', result={'error': str(e)})
        
        # Sleep until next check
        logger.info("")
        logger.info(f"💤 Sleeping for {check_interval}s until next check...")
        time.sleep(check_interval)


def main():
    """Main entry point"""
    # Start health server
    port = int(os.environ.get('ORCHESTRATOR_PORT', 8002))
    logger.info(f"Starting health server on port {port}")
    start_health_server(port=port)
    
    # Give health server time to start
    time.sleep(1)
    
    # Run orchestrator loop (blocks forever)
    try:
        run_orchestrator_loop()
    except KeyboardInterrupt:
        logger.info("\n🛑 Orchestrator service stopped by user")
        sys.exit(0)


if __name__ == '__main__':
    main()
