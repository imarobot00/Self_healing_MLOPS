"""
Self-Healing Orchestrator - Autonomous MLOps Workflow Manager

This module orchestrates the complete self-healing workflow:
1. Monitor for drift
2. Trigger retraining when needed
3. Validate new models
4. Promote approved models
5. Deploy to production
6. Monitor and rollback if needed

Usage:
    from self_healing_orchestrator import SelfHealingOrchestrator
    
    orchestrator = SelfHealingOrchestrator()
    
    # Start autonomous mode (runs forever)
    orchestrator.run_daemon()
    
    # Or trigger manually
    orchestrator.check_and_heal()
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any
import traceback

# Import from same directory
from auto_trainer import AutoTrainer
from model_validator import ModelValidator
from model_registry import ModelRegistry

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SelfHealingOrchestrator:
    """
    Autonomous orchestrator for self-healing ML system.
    
    Coordinates drift detection, retraining, validation, and deployment.
    """
    
    # State constants
    IDLE = 'IDLE'
    CHECKING = 'CHECKING'
    TRAINING = 'TRAINING'
    VALIDATING = 'VALIDATING'
    PROMOTING = 'PROMOTING'
    DEPLOYED = 'DEPLOYED'
    ERROR = 'ERROR'
    ROLLING_BACK = 'ROLLING_BACK'
    
    def __init__(
        self,
        config: Dict = None,
        auto_promote_marginal: bool = False
    ):
        """
        Initialize Self-Healing Orchestrator.
        
        Args:
            config: Configuration dict
            auto_promote_marginal: Whether to auto-promote MARGINAL models
        """
        self.config = config or self.default_config()
        self.auto_promote_marginal = auto_promote_marginal
        
        # Initialize components
        self.trainer = AutoTrainer()
        self.validator = ModelValidator()
        self.registry = ModelRegistry()
        
        # State tracking
        self.state = self.IDLE
        self.current_workflow = None
        self.last_check_time = None
        self.last_training_time = None
        
        # Metrics
        self.metrics = {
            'drift_checks': 0,
            'trainings_triggered': 0,
            'trainings_successful': 0,
            'trainings_failed': 0,
            'validations_approved': 0,
            'validations_rejected': 0,
            'deployments_successful': 0,
            'deployments_failed': 0,
            'rollbacks': 0
        }
        
        # Workflow log
        self.workflow_log_path = Path(__file__).parent / 'orchestrator_logs'
        self.workflow_log_path.mkdir(exist_ok=True)
        
        logger.info("🤖 Self-Healing Orchestrator initialized")
        logger.info(f"   Auto-promote marginal: {self.auto_promote_marginal}")
        logger.info(f"   Drift threshold: {self.config['drift_threshold']}")
    
    @staticmethod
    def default_config() -> Dict:
        """Get default configuration."""
        return {
            # Drift detection
            'drift_threshold': 0.25,
            'drift_check_interval': 3600,  # 1 hour
            
            # Training controls
            'min_retrain_interval': 86400,  # 24 hours
            'training_timeout': 3600,
            
            # Validation thresholds
            'mae_improvement_threshold': 0.05,  # 5%
            'r2_improvement_threshold': 0.02,
            
            # Deployment
            'deployment_health_check': True,
            'health_check_retries': 3,
            
            # Rollback
            'auto_rollback': True,
            'error_rate_threshold': 1.2,  # 20% increase
            'mae_degradation_threshold': 1.1,  # 10% degradation
        }
    
    def set_state(self, new_state: str, workflow_id: str = None):
        """Update orchestrator state."""
        old_state = self.state
        self.state = new_state
        logger.info(f"🔄 State: {old_state} → {new_state}")
        
        if workflow_id:
            self.log_workflow_event(workflow_id, f"state_change: {old_state} → {new_state}")
    
    def log_workflow_event(self, workflow_id: str, event: str, data: Dict = None):
        """Log workflow event."""
        log_file = self.workflow_log_path / f"{workflow_id}.json"
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'event': event,
            'state': self.state,
            'data': data or {}
        }
        
        # Append to log file
        if log_file.exists():
            with open(log_file, 'r') as f:
                log_data = json.load(f)
        else:
            log_data = {'workflow_id': workflow_id, 'events': []}
        
        log_data['events'].append(entry)
        
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2)
    
    def check_drift(self) -> Optional[Dict]:
        """
        Check for data drift.
        
        Returns:
            Drift info if drift detected, None otherwise
        """
        self.metrics['drift_checks'] += 1
        self.last_check_time = datetime.now()
        
        try:
            # For now, simulate drift detection
            # In production, integrate with dataset/monitor.py
            
            # Check if we have drift detection results
            drift_log_path = Path(__file__).parent.parent / 'dataset' / 'drift_log.json'
            
            if drift_log_path.exists():
                with open(drift_log_path, 'r') as f:
                    drift_data = json.load(f)
                
                # Check most recent entry
                if drift_data:
                    latest = drift_data[-1] if isinstance(drift_data, list) else drift_data
                    psi_score = latest.get('psi_score', 0)
                    
                    if psi_score > self.config['drift_threshold']:
                        logger.warning(f"🚨 Drift detected: PSI={psi_score:.3f} (threshold={self.config['drift_threshold']})")
                        return {
                            'psi_score': psi_score,
                            'threshold': self.config['drift_threshold'],
                            'detected_at': datetime.now().isoformat(),
                            'source': 'drift_log'
                        }
            
            logger.info(f"✅ No drift detected")
            return None
            
        except Exception as e:
            logger.error(f"Error checking drift: {e}")
            return None
    
    def should_retrain(self, drift_info: Dict = None) -> bool:
        """
        Decide if we should retrain.
        
        Args:
            drift_info: Drift detection info
            
        Returns:
            True if should retrain
        """
        # Check if currently training
        if self.state in [self.TRAINING, self.VALIDATING, self.PROMOTING]:
            logger.info("⏸️  Already processing, skip retrain")
            return False
        
        # Check cooldown period
        if self.last_training_time:
            time_since_training = datetime.now() - self.last_training_time
            min_interval = timedelta(seconds=self.config['min_retrain_interval'])
            
            if time_since_training < min_interval:
                logger.info(f"⏸️  Too soon since last training ({time_since_training}), skip")
                return False
        
        # If drift provided, check threshold
        if drift_info:
            if drift_info['psi_score'] > self.config['drift_threshold']:
                logger.info("✅ Retrain conditions met")
                return True
        
        return False
    
    def handle_drift(self, drift_info: Dict):
        """
        Handle drift detection event.
        
        Args:
            drift_info: Drift detection results
        """
        workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_workflow = workflow_id
        
        logger.info(f"🔍 Handling drift (workflow: {workflow_id})")
        self.log_workflow_event(workflow_id, 'drift_detected', drift_info)
        
        if not self.should_retrain(drift_info):
            logger.info("⏭️  Skipping retrain")
            self.current_workflow = None
            return
        
        # Trigger training
        self.trigger_training(workflow_id)
    
    def trigger_training(self, workflow_id: str):
        """
        Trigger model retraining.
        
        Args:
            workflow_id: Workflow identifier
        """
        self.set_state(self.TRAINING, workflow_id)
        self.log_workflow_event(workflow_id, 'training_started')
        self.metrics['trainings_triggered'] += 1
        
        try:
            logger.info("🔨 Starting model training...")
            
            # Train new model
            model_id = self.trainer.train_model(reason='drift_detected')
            self.last_training_time = datetime.now()
            
            logger.info(f"✅ Training complete: {model_id}")
            self.log_workflow_event(workflow_id, 'training_complete', {'model_id': model_id})
            self.metrics['trainings_successful'] += 1
            
            # Register in registry
            metadata = self.trainer.load_metadata(model_id)
            self.registry.register_model(
                model_id=model_id,
                metrics=metadata.get('metrics', {}),
                metadata=metadata.get('metadata', {})
            )
            
            # Proceed to validation
            self.trigger_validation(workflow_id, model_id)
            
        except Exception as e:
            logger.error(f"❌ Training failed: {e}")
            logger.error(traceback.format_exc())
            self.log_workflow_event(workflow_id, 'training_failed', {'error': str(e)})
            self.metrics['trainings_failed'] += 1
            self.handle_failure(workflow_id, 'training', e)
    
    def trigger_validation(self, workflow_id: str, new_model_id: str):
        """
        Trigger model validation.
        
        Args:
            workflow_id: Workflow identifier
            new_model_id: New model to validate
        """
        self.set_state(self.VALIDATING, workflow_id)
        self.log_workflow_event(workflow_id, 'validation_started', {'model_id': new_model_id})
        
        try:
            logger.info(f"🔍 Validating model: {new_model_id}")
            
            # Get current production model
            current_prod = self.registry.get_production()
            current_model_id = current_prod['model_id'] if current_prod else None
            
            if not current_model_id:
                logger.warning("⚠️  No production model, auto-approving first model")
                result = {
                    'decision': 'APPROVE',
                    'reasons': ['First model, auto-approved'],
                    'new_metrics': {}
                }
            else:
                # Validate against current production
                result = self.validator.validate(new_model_id, current_model_id)
            
            logger.info(f"📊 Validation result: {result['decision']}")
            self.log_workflow_event(workflow_id, 'validation_complete', result)
            
            # Handle result
            self.handle_validation_result(workflow_id, new_model_id, result)
            
        except Exception as e:
            logger.error(f"❌ Validation failed: {e}")
            logger.error(traceback.format_exc())
            self.log_workflow_event(workflow_id, 'validation_failed', {'error': str(e)})
            self.handle_failure(workflow_id, 'validation', e)
    
    def handle_validation_result(self, workflow_id: str, model_id: str, result: Dict):
        """
        Handle validation result.
        
        Args:
            workflow_id: Workflow identifier
            model_id: Model that was validated
            result: Validation result
        """
        decision = result['decision']
        
        if decision == 'APPROVE':
            logger.info("✅ Model APPROVED, promoting to production")
            self.metrics['validations_approved'] += 1
            self.trigger_promotion(workflow_id, model_id, result)
        
        elif decision == 'MARGINAL':
            logger.warning("⚠️  Model MARGINAL")
            
            if self.auto_promote_marginal:
                logger.info("📤 Auto-promoting marginal model")
                self.metrics['validations_approved'] += 1
                self.trigger_promotion(workflow_id, model_id, result)
            else:
                logger.info("📧 Marginal model requires human approval")
                self.log_workflow_event(workflow_id, 'requires_human_approval', result)
                self.metrics['validations_rejected'] += 1
                self.set_state(self.IDLE, workflow_id)
                self.current_workflow = None
        
        elif decision == 'REJECT':
            logger.error("❌ Model REJECTED, not promoting")
            self.metrics['validations_rejected'] += 1
            
            # Mark as failed in registry
            self.registry.mark_failed(
                model_id,
                reason='Validation rejected',
                details=str(result.get('reasons', []))
            )
            
            self.log_workflow_event(workflow_id, 'model_rejected', result)
            self.set_state(self.IDLE, workflow_id)
            self.current_workflow = None
    
    def trigger_promotion(self, workflow_id: str, model_id: str, validation_result: Dict):
        """
        Trigger model promotion.
        
        Args:
            workflow_id: Workflow identifier
            model_id: Model to promote
            validation_result: Validation result
        """
        self.set_state(self.PROMOTING, workflow_id)
        self.log_workflow_event(workflow_id, 'promotion_started', {'model_id': model_id})
        
        try:
            logger.info(f"📤 Promoting model to production: {model_id}")
            
            # Promote to staging first
            self.registry.promote_to_staging(model_id, validation_result=validation_result)
            
            # Then to production
            self.registry.promote_to_production(model_id, promoted_by='orchestrator_automated')
            
            logger.info(f"✅ Promotion complete: {model_id}")
            self.log_workflow_event(workflow_id, 'promotion_complete', {'model_id': model_id})
            self.metrics['deployments_successful'] += 1
            
            # Transition to deployed state
            self.set_state(self.DEPLOYED, workflow_id)
            
            # Post-deployment monitoring (in background)
            self.monitor_deployment(workflow_id, model_id)
            
            # Return to idle
            self.set_state(self.IDLE, workflow_id)
            self.current_workflow = None
            
        except Exception as e:
            logger.error(f"❌ Promotion failed: {e}")
            logger.error(traceback.format_exc())
            self.log_workflow_event(workflow_id, 'promotion_failed', {'error': str(e)})
            self.metrics['deployments_failed'] += 1
            self.handle_failure(workflow_id, 'promotion', e)
    
    def monitor_deployment(self, workflow_id: str, model_id: str):
        """
        Monitor newly deployed model.
        
        Args:
            workflow_id: Workflow identifier
            model_id: Deployed model
        """
        logger.info(f"👀 Monitoring deployment: {model_id}")
        self.log_workflow_event(workflow_id, 'monitoring_started', {'model_id': model_id})
        
        # In production, this would:
        # 1. Watch error rates
        # 2. Monitor prediction metrics
        # 3. Compare against baseline
        # 4. Trigger rollback if issues detected
        
        # For now, just log
        logger.info(f"✅ Deployment monitoring complete (simulated)")
    
    def rollback(self, workflow_id: str, reason: str):
        """
        Rollback to previous production model.
        
        Args:
            workflow_id: Workflow identifier
            reason: Reason for rollback
        """
        self.set_state(self.ROLLING_BACK, workflow_id)
        self.log_workflow_event(workflow_id, 'rollback_started', {'reason': reason})
        self.metrics['rollbacks'] += 1
        
        try:
            logger.warning(f"🔙 Rolling back: {reason}")
            
            # Rollback in registry
            previous = self.registry.rollback_to_previous()
            
            logger.info(f"✅ Rolled back to: {previous['model_id']}")
            self.log_workflow_event(workflow_id, 'rollback_complete', {
                'model_id': previous['model_id']
            })
            
            # In production, would also reload model in API
            
            self.set_state(self.IDLE, workflow_id)
            
        except Exception as e:
            logger.error(f"❌ Rollback failed: {e}")
            logger.error(traceback.format_exc())
            self.log_workflow_event(workflow_id, 'rollback_failed', {'error': str(e)})
    
    def handle_failure(self, workflow_id: str, stage: str, error: Exception):
        """
        Handle workflow failure.
        
        Args:
            workflow_id: Workflow identifier
            stage: Stage where failure occurred
            error: Exception that occurred
        """
        self.set_state(self.ERROR, workflow_id)
        self.log_workflow_event(workflow_id, 'workflow_failed', {
            'stage': stage,
            'error': str(error),
            'traceback': traceback.format_exc()
        })
        
        logger.error(f"❌ Workflow failed at stage: {stage}")
        logger.error(f"   Error: {error}")
        
        # Reset to idle
        self.set_state(self.IDLE, workflow_id)
        self.current_workflow = None
    
    def check_and_heal(self) -> Dict:
        """
        Check for drift and trigger healing if needed.
        
        Returns:
            Status dict
        """
        logger.info("🔍 Running drift check...")
        
        self.set_state(self.CHECKING)
        
        # Check for drift
        drift_info = self.check_drift()
        
        if drift_info:
            # Handle drift
            self.handle_drift(drift_info)
            return {
                'status': 'healing_triggered',
                'drift_info': drift_info,
                'workflow_id': self.current_workflow
            }
        else:
            self.set_state(self.IDLE)
            return {
                'status': 'healthy',
                'drift_info': None
            }
    
    def get_status(self) -> Dict:
        """Get orchestrator status."""
        return {
            'state': self.state,
            'current_workflow': self.current_workflow,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'last_training_time': self.last_training_time.isoformat() if self.last_training_time else None,
            'metrics': self.metrics,
            'production_model': self.registry.get_production()
        }
    
    def get_metrics(self) -> Dict:
        """Get orchestrator metrics."""
        metrics = self.metrics.copy()
        
        # Calculate success rates
        total_trainings = metrics['trainings_successful'] + metrics['trainings_failed']
        if total_trainings > 0:
            metrics['training_success_rate'] = metrics['trainings_successful'] / total_trainings
        else:
            metrics['training_success_rate'] = 0
        
        total_deployments = metrics['deployments_successful'] + metrics['deployments_failed']
        if total_deployments > 0:
            metrics['deployment_success_rate'] = metrics['deployments_successful'] / total_deployments
        else:
            metrics['deployment_success_rate'] = 0
        
        return metrics
    
    def run_daemon(self, check_interval: int = None):
        """
        Run orchestrator in daemon mode.
        
        Args:
            check_interval: Seconds between checks (default from config)
        """
        interval = check_interval or self.config['drift_check_interval']
        
        logger.info(f"🤖 Starting daemon mode (check every {interval}s)")
        logger.info(f"   Press Ctrl+C to stop")
        
        try:
            while True:
                try:
                    self.check_and_heal()
                except Exception as e:
                    logger.error(f"Error in check cycle: {e}")
                    logger.error(traceback.format_exc())
                
                logger.info(f"💤 Sleeping for {interval}s...")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("\n🛑 Daemon stopped by user")


def main():
    """CLI for orchestrator."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Self-Healing Orchestrator")
    parser.add_argument('action', nargs='?', choices=[
        'check', 'status', 'metrics', 'daemon', 'rollback'
    ], default='check')
    parser.add_argument('--interval', type=int, default=3600, 
                       help='Check interval for daemon mode (seconds)')
    parser.add_argument('--auto-promote-marginal', action='store_true',
                       help='Auto-promote marginal models')
    
    args = parser.parse_args()
    
    orchestrator = SelfHealingOrchestrator(
        auto_promote_marginal=args.auto_promote_marginal
    )
    
    if args.action == 'check':
        result = orchestrator.check_and_heal()
        print(f"\n📊 Result: {result['status']}")
        if result.get('drift_info'):
            print(f"   Drift PSI: {result['drift_info']['psi_score']:.3f}")
            print(f"   Workflow: {result['workflow_id']}")
    
    elif args.action == 'status':
        status = orchestrator.get_status()
        print(f"\n📊 Orchestrator Status:")
        print(f"   State: {status['state']}")
        print(f"   Workflow: {status['current_workflow'] or 'None'}")
        print(f"   Last check: {status['last_check_time'] or 'Never'}")
        if status['production_model']:
            print(f"   Production: {status['production_model']['model_id']}")
    
    elif args.action == 'metrics':
        metrics = orchestrator.get_metrics()
        print(f"\n📊 Orchestrator Metrics:")
        print(f"   Drift checks: {metrics['drift_checks']}")
        print(f"   Trainings: {metrics['trainings_successful']}/{metrics['trainings_triggered']}")
        print(f"   Training success rate: {metrics['training_success_rate']:.1%}")
        print(f"   Validations approved: {metrics['validations_approved']}")
        print(f"   Validations rejected: {metrics['validations_rejected']}")
        print(f"   Deployments: {metrics['deployments_successful']}/{metrics['deployments_successful'] + metrics['deployments_failed']}")
        print(f"   Rollbacks: {metrics['rollbacks']}")
    
    elif args.action == 'daemon':
        orchestrator.run_daemon(check_interval=args.interval)
    
    elif args.action == 'rollback':
        workflow_id = f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        orchestrator.rollback(workflow_id, "Manual rollback via CLI")
        print(f"\n✅ Rollback complete")


if __name__ == '__main__':
    main()
