"""
End-to-End Integration Example - Self-Healing MLOps System

This script demonstrates the complete workflow from drift detection
to automatic model deployment.
"""

import sys
import time
import logging
from pathlib import Path

# Add training directory to path
sys.path.insert(0, str(Path(__file__).parent))

from self_healing_orchestrator import SelfHealingOrchestrator
from model_registry import ModelRegistry

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demo_complete_workflow():
    """
    Demonstrate complete self-healing workflow.
    """
    print("\n" + "="*70)
    print("🤖 SELF-HEALING MLOPS - END-TO-END DEMONSTRATION")
    print("="*70 + "\n")
    
    # Initialize orchestrator
    logger.info("Step 1: Initializing orchestrator...")
    orchestrator = SelfHealingOrchestrator(auto_promote_marginal=False)
    
    time.sleep(1)
    
    # Check initial status
    logger.info("\nStep 2: Checking initial status...")
    status = orchestrator.get_status()
    print(f"\n📊 Initial Status:")
    print(f"   State: {status['state']}")
    print(f"   Production model: {status['production_model']['model_id'] if status['production_model'] else 'None'}")
    
    time.sleep(1)
    
    # Check for drift
    logger.info("\nStep 3: Checking for drift...")
    result = orchestrator.check_and_heal()
    print(f"\n🔍 Drift Check Result: {result['status']}")
    
    if result['status'] == 'healing_triggered':
        print(f"   🚨 Drift detected! PSI: {result['drift_info']['psi_score']:.3f}")
        print(f"   🔨 Workflow started: {result['workflow_id']}")
        
        # Wait for workflow to complete (in real system, this would be async)
        logger.info("\n   Workflow would proceed through:")
        print(f"   1. Training new model...")
        print(f"   2. Validating against current production...")
        print(f"   3. Promoting if approved...")
        print(f"   4. Deploying to production...")
        print(f"   5. Monitoring post-deployment...")
    else:
        print("   ✅ No drift detected, system is healthy")
    
    time.sleep(1)
    
    # Show metrics
    logger.info("\nStep 4: Reviewing metrics...")
    metrics = orchestrator.get_metrics()
    print(f"\n📊 System Metrics:")
    print(f"   Drift checks: {metrics['drift_checks']}")
    print(f"   Training success rate: {metrics['training_success_rate']:.1%}")
    print(f"   Validations approved: {metrics['validations_approved']}")
    print(f"   Validations rejected: {metrics['validations_rejected']}")
    print(f"   Rollbacks: {metrics['rollbacks']}")
    
    time.sleep(1)
    
    # Show registry status
    logger.info("\nStep 5: Checking model registry...")
    registry = ModelRegistry()
    stats = registry.get_stats()
    print(f"\n📦 Registry Status:")
    print(f"   Total models: {stats['total_models']}")
    print(f"   By status: {stats['by_status']}")
    print(f"   Production: {stats['production']}")
    print(f"   History entries: {stats['history_entries']}")
    
    print("\n" + "="*70)
    print("✅ DEMONSTRATION COMPLETE")
    print("="*70 + "\n")


def demo_manual_workflow():
    """
    Demonstrate manual triggering of workflow steps.
    """
    print("\n" + "="*70)
    print("🔧 MANUAL WORKFLOW DEMONSTRATION")
    print("="*70 + "\n")
    
    orchestrator = SelfHealingOrchestrator()
    
    print("This demonstrates manual control of the orchestrator:")
    print("\n1. Manual drift injection:")
    print("   orchestrator.handle_drift({'psi_score': 0.30})")
    
    print("\n2. Manual training trigger:")
    print("   orchestrator.trigger_training('workflow_manual')")
    
    print("\n3. Manual validation:")
    print("   orchestrator.trigger_validation('workflow_id', 'model_id')")
    
    print("\n4. Manual promotion:")
    print("   orchestrator.trigger_promotion('workflow_id', 'model_id', result)")
    
    print("\n5. Manual rollback:")
    print("   orchestrator.rollback('workflow_id', 'manual_rollback')")
    
    print("\n💡 For automated operation, use:")
    print("   orchestrator.run_daemon()  # Runs continuously")
    
    print("\n" + "="*70)


def demo_integration_with_api():
    """
    Show how to integrate with FastAPI.
    """
    print("\n" + "="*70)
    print("🌐 API INTEGRATION EXAMPLE")
    print("="*70 + "\n")
    
    print("Add to your FastAPI application:\n")
    
    api_code = '''
from fastapi import FastAPI, BackgroundTasks
from self_healing_orchestrator import SelfHealingOrchestrator

app = FastAPI()
orchestrator = SelfHealingOrchestrator()

@app.get("/health/check-drift")
def check_drift():
    """Check for drift and trigger healing if needed."""
    result = orchestrator.check_and_heal()
    return result

@app.get("/orchestrator/status")
def get_orchestrator_status():
    """Get current orchestrator status."""
    return orchestrator.get_status()

@app.get("/orchestrator/metrics")
def get_orchestrator_metrics():
    """Get orchestrator metrics."""
    return orchestrator.get_metrics()

@app.post("/orchestrator/rollback")
def emergency_rollback():
    """Emergency rollback to previous model."""
    workflow_id = f"emergency_{datetime.now():%Y%m%d_%H%M%S}"
    orchestrator.rollback(workflow_id, "Emergency rollback via API")
    return {"status": "rolled back", "workflow_id": workflow_id}

@app.on_event("startup")
async def start_orchestrator():
    """Start orchestrator in background."""
    import threading
    thread = threading.Thread(
        target=orchestrator.run_daemon,
        args=(3600,),  # Check every hour
        daemon=True
    )
    thread.start()
'''
    
    print(api_code)
    print("="*70 + "\n")


def demo_deployment_scenarios():
    """
    Show different deployment scenarios.
    """
    print("\n" + "="*70)
    print("🚀 DEPLOYMENT SCENARIOS")
    print("="*70 + "\n")
    
    scenarios = [
        {
            'name': 'Scenario 1: Drift Detected → Auto-Heal',
            'description': 'System detects drift, trains new model, validates, and deploys automatically',
            'steps': [
                '1. Drift monitor detects PSI > 0.25',
                '2. Orchestrator triggers training',
                '3. New model trained (10-20 min)',
                '4. Validator compares with production',
                '5. Decision: APPROVE',
                '6. Registry promotes to production',
                '7. System healed automatically'
            ],
            'outcome': '✅ System recovered without human intervention'
        },
        {
            'name': 'Scenario 2: Model Rejected',
            'description': 'New model performs worse than current production',
            'steps': [
                '1. Drift detected, training triggered',
                '2. New model trained',
                '3. Validator compares: New MAE worse',
                '4. Decision: REJECT',
                '5. Model marked as failed in registry',
                '6. Current production remains active'
            ],
            'outcome': '⚠️  Human notified, system protected from bad model'
        },
        {
            'name': 'Scenario 3: Marginal Improvement',
            'description': 'New model slightly better but below approval threshold',
            'steps': [
                '1. Drift detected, training triggered',
                '2. New model trained',
                '3. Validator: MAE 3% better (need 5%)',
                '4. Decision: MARGINAL',
                '5. Requires human approval',
                '6. Email/Slack notification sent'
            ],
            'outcome': '📧 Human reviews and approves/rejects'
        },
        {
            'name': 'Scenario 4: Production Failure → Rollback',
            'description': 'New model deployed but causes issues',
            'steps': [
                '1. New model deployed to production',
                '2. Post-deployment monitoring detects errors',
                '3. Error rate exceeds threshold',
                '4. Automatic rollback triggered',
                '5. Previous model restored',
                '6. Failed model marked in registry'
            ],
            'outcome': '🔙 System recovered, bad model isolated'
        }
    ]
    
    for scenario in scenarios:
        print(f"\n{scenario['name']}")
        print(f"   {scenario['description']}\n")
        for step in scenario['steps']:
            print(f"   {step}")
        print(f"\n   {scenario['outcome']}\n")
        print("-" * 70)
    
    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description="Self-Healing MLOps Integration Examples")
    parser.add_argument('demo', nargs='?', choices=[
        'complete', 'manual', 'api', 'scenarios', 'all'
    ], default='complete')
    
    args = parser.parse_args()
    
    if args.demo == 'complete' or args.demo == 'all':
        demo_complete_workflow()
    
    if args.demo == 'manual' or args.demo == 'all':
        demo_manual_workflow()
    
    if args.demo == 'api' or args.demo == 'all':
        demo_integration_with_api()
    
    if args.demo == 'scenarios' or args.demo == 'all':
        demo_deployment_scenarios()
