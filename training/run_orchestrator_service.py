#!/usr/bin/env python3
"""
Orchestrator Service - Long-Running Daemon

Runs the self-healing orchestrator in a continuous loop with health checks.
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
    'last_workflow': None,
    'check_count': 0,
    'heal_count': 0,
    'error_count': 0,
    'started_at': datetime.now().isoformat()
}


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
                logger.info(f"✅ System healthy, no drift detected")
                update_health_state('running', workflow_id, {
                    'action': 'healthy',
                    'status': status
                })
            else:
                logger.info(f"📊 Check result: {status}")
                update_health_state('running', workflow_id, {
                    'action': 'checked',
                    'status': status
                })
            
        except Exception as e:
            service_state['error_count'] += 1
            logger.error(f"❌ Error in orchestrator check: {e}")
            import traceback
            logger.error(traceback.format_exc())
            update_health_state('error', result={'error': str(e)})
        
        # Sleep until next check
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
