"""
Model Registry - Central Version Tracking for Self-Healing MLOps

This module provides a centralized registry for tracking all model versions,
their states, deployment history, and enabling safe rollbacks.

Key Features:
- Version tracking with unique IDs
- State management (candidate, staging, production, archived)
- Promotion workflow
- Rollback capability
- Deployment history
- Metadata storage

Usage:
    from model_registry import ModelRegistry
    
    registry = ModelRegistry()
    
    # Register new model
    registry.register_model('model_20260106_180235', metadata={...})
    
    # Promote to production
    registry.promote_to_production('model_20260106_180235')
    
    # Rollback if needed
    registry.rollback_to_previous()
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from copy import deepcopy

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelRegistry:
    """
    Centralized registry for ML model version tracking and lifecycle management.
    """
    
    def __init__(self, registry_path: str = None, models_dir: str = None):
        """
        Initialize Model Registry.
        
        Args:
            registry_path: Path to registry.json file
            models_dir: Directory containing model folders
        """
        if registry_path is None:
            registry_path = os.path.join(
                os.path.dirname(__file__),
                'registry.json'
            )
        self.registry_path = Path(registry_path)
        
        if models_dir is None:
            models_dir = os.path.join(
                os.path.dirname(__file__),
                'models'
            )
        self.models_dir = Path(models_dir)
        
        # Load or initialize registry
        self.registry = self.load_registry()
        
        logger.info(f"Initialized ModelRegistry")
        logger.info(f"Registry: {self.registry_path}")
        logger.info(f"Models directory: {self.models_dir}")
    
    def load_registry(self) -> Dict:
        """Load registry from file or create new."""
        if self.registry_path.exists():
            with open(self.registry_path, 'r') as f:
                registry = json.load(f)
            logger.info(f"Loaded registry with {len(registry.get('models', {}))} models")
            return registry
        else:
            logger.info("Creating new registry")
            return {
                'production': None,
                'staging': None,
                'models': {},
                'history': []
            }
    
    def save_registry(self):
        """Save registry to file."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_path, 'w') as f:
            json.dump(self.registry, f, indent=2)
        logger.info(f"Registry saved to {self.registry_path}")
    
    def register_model(
        self, 
        model_id: str, 
        model_path: str = None,
        metrics: Dict = None,
        metadata: Dict = None,
        status: str = 'candidate'
    ) -> Dict:
        """
        Register a new model in the registry.
        
        Args:
            model_id: Unique model identifier (e.g., model_20260106_180235)
            model_path: Path to model directory
            metrics: Performance metrics dict
            metadata: Additional metadata
            status: Initial status (default: 'candidate')
            
        Returns:
            Registered model entry
        """
        if model_id in self.registry['models']:
            logger.warning(f"Model {model_id} already registered, updating...")
        
        if model_path is None:
            model_path = str(self.models_dir / model_id)
        
        entry = {
            'model_id': model_id,
            'model_path': model_path,
            'status': status,
            'registered_at': datetime.now().isoformat(),
            'metrics': metrics or {},
            'metadata': metadata or {}
        }
        
        self.registry['models'][model_id] = entry
        self.save_registry()
        
        logger.info(f"Registered model: {model_id} (status: {status})")
        return entry
    
    def get_model(self, model_id: str) -> Optional[Dict]:
        """Get model entry by ID."""
        return self.registry['models'].get(model_id)
    
    def list_models(self, status: str = None) -> List[Dict]:
        """
        List all models, optionally filtered by status.
        
        Args:
            status: Filter by status (candidate, staging, production, archived, failed)
            
        Returns:
            List of model entries
        """
        models = list(self.registry['models'].values())
        
        if status:
            models = [m for m in models if m.get('status') == status]
        
        # Sort by registered_at (newest first)
        models.sort(key=lambda x: x.get('registered_at', ''), reverse=True)
        
        return models
    
    def promote_to_staging(self, model_id: str, validation_result: Dict = None) -> Dict:
        """
        Promote model to staging.
        
        Args:
            model_id: Model to promote
            validation_result: Validation results from ModelValidator
            
        Returns:
            Updated model entry
        """
        model = self.get_model(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found in registry")
        
        # Update current staging model status if exists
        if self.registry['staging']:
            old_staging = self.registry['staging']['model_id']
            if old_staging in self.registry['models']:
                self.registry['models'][old_staging]['status'] = 'candidate'
                logger.info(f"Demoted {old_staging} from staging to candidate")
        
        # Promote to staging
        model['status'] = 'staging'
        model['promoted_to_staging_at'] = datetime.now().isoformat()
        if validation_result:
            model['validation'] = validation_result
        
        self.registry['staging'] = {
            'model_id': model_id,
            'promoted_at': datetime.now().isoformat()
        }
        
        self.save_registry()
        logger.info(f"Promoted {model_id} to staging")
        
        return model
    
    def promote_to_production(
        self, 
        model_id: str, 
        promoted_by: str = 'manual'
    ) -> Dict:
        """
        Promote model to production.
        Archives current production model.
        
        Args:
            model_id: Model to promote
            promoted_by: Who/what triggered promotion
            
        Returns:
            Updated model entry
        """
        model = self.get_model(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found in registry")
        
        # Archive current production model
        if self.registry['production']:
            current_prod_id = self.registry['production']['model_id']
            self.archive_model(
                current_prod_id,
                reason='Replaced by new model',
                archived_by=promoted_by
            )
        
        # Promote to production
        model['status'] = 'production'
        model['promoted_to_production_at'] = datetime.now().isoformat()
        model['promoted_by'] = promoted_by
        
        self.registry['production'] = {
            'model_id': model_id,
            'promoted_at': datetime.now().isoformat(),
            'promoted_by': promoted_by
        }
        
        # Clear staging if this model was in staging
        if self.registry['staging'] and self.registry['staging']['model_id'] == model_id:
            self.registry['staging'] = None
        
        self.save_registry()
        logger.info(f"✅ Promoted {model_id} to PRODUCTION (by: {promoted_by})")
        
        return model
    
    def archive_model(
        self, 
        model_id: str, 
        reason: str = None,
        archived_by: str = None
    ) -> Dict:
        """
        Archive a model (mark as no longer active).
        
        Args:
            model_id: Model to archive
            reason: Reason for archival
            archived_by: Who/what triggered archival
            
        Returns:
            Updated model entry
        """
        model = self.get_model(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found in registry")
        
        was_production = model.get('status') == 'production'
        
        # Update model status
        model['status'] = 'archived'
        model['archived_at'] = datetime.now().isoformat()
        model['archive_reason'] = reason
        model['archived_by'] = archived_by
        
        # Calculate uptime if was production
        if was_production and 'promoted_to_production_at' in model:
            promoted_at = datetime.fromisoformat(model['promoted_to_production_at'])
            archived_at = datetime.now()
            uptime_seconds = (archived_at - promoted_at).total_seconds()
            model['production_uptime_seconds'] = uptime_seconds
        
        # Add to history
        history_entry = deepcopy(model)
        self.registry['history'].insert(0, history_entry)
        
        # Keep only last 50 in history
        self.registry['history'] = self.registry['history'][:50]
        
        self.save_registry()
        logger.info(f"Archived {model_id} (reason: {reason})")
        
        return model
    
    def get_production(self) -> Optional[Dict]:
        """Get current production model."""
        if not self.registry['production']:
            return None
        
        model_id = self.registry['production']['model_id']
        return self.get_model(model_id)
    
    def get_staging(self) -> Optional[Dict]:
        """Get current staging model."""
        if not self.registry['staging']:
            return None
        
        model_id = self.registry['staging']['model_id']
        return self.get_model(model_id)
    
    def get_previous_production(self) -> Optional[Dict]:
        """Get the most recent archived production model."""
        for entry in self.registry['history']:
            if entry.get('status') == 'archived' and 'promoted_to_production_at' in entry:
                return entry
        return None
    
    def get_history(self, limit: int = 10) -> List[Dict]:
        """
        Get deployment history.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of historical model entries
        """
        return self.registry['history'][:limit]
    
    def rollback_to_previous(self) -> Dict:
        """
        Rollback to previous production model.
        
        Returns:
            The model that is now in production
        """
        previous = self.get_previous_production()
        if not previous:
            raise ValueError("No previous production model found for rollback")
        
        logger.warning(f"🔄 Rolling back to {previous['model_id']}")
        
        # Mark current production as failed (but don't archive)
        current = self.get_production()
        current_id = None
        if current:
            current_id = current['model_id']
            self.mark_failed(
                current_id,
                reason='Rolled back due to production issues'
            )
        
        # Re-register previous model as candidate
        previous_id = previous['model_id']
        if previous_id not in self.registry['models']:
            # Re-add from history
            self.registry['models'][previous_id] = previous
        
        # Manually promote to production (bypass archive logic)
        model = self.registry['models'][previous_id]
        model['status'] = 'production'
        model['promoted_to_production_at'] = datetime.now().isoformat()
        model['promoted_by'] = 'rollback'
        
        self.registry['production'] = {
            'model_id': previous_id,
            'promoted_at': datetime.now().isoformat(),
            'promoted_by': 'rollback'
        }
        
        self.save_registry()
        
        logger.info(f"✅ Rollback complete: {previous_id} is now in production")
        
        return self.get_production()
    
    def rollback_to_version(self, model_id: str) -> Dict:
        """
        Rollback to specific model version.
        
        Args:
            model_id: Model ID to rollback to
            
        Returns:
            The model that is now in production
        """
        # Check if model exists
        model = self.get_model(model_id)
        if not model:
            # Check in history
            for entry in self.registry['history']:
                if entry['model_id'] == model_id:
                    model = entry
                    # Re-add to active models
                    self.registry['models'][model_id] = model
                    break
        
        if not model:
            raise ValueError(f"Model {model_id} not found in registry or history")
        
        logger.warning(f"🔄 Rolling back to specific version: {model_id}")
        
        # Mark current production as failed (but don't archive)
        current = self.get_production()
        current_id = None
        if current:
            current_id = current['model_id']
            self.mark_failed(
                current_id,
                reason=f'Rolled back to {model_id}'
            )
        
        # Manually promote specified version to production (bypass archive logic)
        model = self.registry['models'][model_id]
        model['status'] = 'production'
        model['promoted_to_production_at'] = datetime.now().isoformat()
        model['promoted_by'] = 'manual_rollback'
        
        self.registry['production'] = {
            'model_id': model_id,
            'promoted_at': datetime.now().isoformat(),
            'promoted_by': 'manual_rollback'
        }
        
        self.save_registry()
        
        logger.info(f"✅ Rollback complete: {model_id} is now in production")
        
        return self.get_production()
    
    def mark_failed(self, model_id: str, reason: str, details: str = None):
        """
        Mark a model as failed.
        
        Args:
            model_id: Model that failed
            reason: Failure reason
            details: Additional details
        """
        model = self.get_model(model_id)
        if not model:
            logger.warning(f"Model {model_id} not found, cannot mark as failed")
            return
        
        model['status'] = 'failed'
        model['failed_at'] = datetime.now().isoformat()
        model['failure_reason'] = reason
        if details:
            model['failure_details'] = details
        
        self.save_registry()
        logger.error(f"❌ Marked {model_id} as FAILED: {reason}")
    
    def prune_old_models(self, keep_last_n: int = 10) -> List[str]:
        """
        Prune old archived models, keeping only the most recent N.
        
        Args:
            keep_last_n: Number of archived models to keep
            
        Returns:
            List of pruned model IDs
        """
        archived = self.list_models(status='archived')
        
        if len(archived) <= keep_last_n:
            logger.info(f"Only {len(archived)} archived models, no pruning needed")
            return []
        
        # Sort by archived_at
        archived.sort(key=lambda x: x.get('archived_at', ''), reverse=True)
        
        # Models to prune (beyond keep_last_n)
        to_prune = archived[keep_last_n:]
        
        pruned_ids = []
        for model in to_prune:
            model_id = model['model_id']
            
            # Remove from registry
            if model_id in self.registry['models']:
                del self.registry['models'][model_id]
                pruned_ids.append(model_id)
                logger.info(f"Pruned {model_id} from registry")
        
        if pruned_ids:
            self.save_registry()
            logger.info(f"Pruned {len(pruned_ids)} old models")
        
        return pruned_ids
    
    def get_stats(self) -> Dict:
        """Get registry statistics."""
        models = self.registry['models']
        
        stats = {
            'total_models': len(models),
            'by_status': {},
            'production': self.registry['production'],
            'staging': self.registry['staging'],
            'history_entries': len(self.registry['history'])
        }
        
        # Count by status
        for model in models.values():
            status = model.get('status', 'unknown')
            stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
        
        return stats


def main():
    """CLI for model registry operations."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Model Registry CLI")
    parser.add_argument('action', choices=[
        'list', 'production', 'staging', 'history', 
        'rollback', 'stats', 'prune'
    ])
    parser.add_argument('--status', help='Filter by status')
    parser.add_argument('--limit', type=int, default=10, help='Limit results')
    parser.add_argument('--to', help='Model ID for rollback')
    
    args = parser.parse_args()
    
    registry = ModelRegistry()
    
    if args.action == 'list':
        models = registry.list_models(status=args.status)
        print(f"\n📋 Models (count: {len(models)}):")
        for model in models[:args.limit]:
            print(f"  • {model['model_id']} - {model['status']}")
            if 'metrics' in model and model['metrics']:
                metrics = model['metrics']
                print(f"    MAE: {metrics.get('mae', 'N/A')}, R²: {metrics.get('r2', 'N/A')}")
    
    elif args.action == 'production':
        prod = registry.get_production()
        if prod:
            print(f"\n🎯 Production Model: {prod['model_id']}")
            print(f"   Status: {prod['status']}")
            if 'metrics' in prod:
                print(f"   Metrics: {prod['metrics']}")
        else:
            print("\n⚠️  No production model set")
    
    elif args.action == 'staging':
        stag = registry.get_staging()
        if stag:
            print(f"\n🔬 Staging Model: {stag['model_id']}")
            print(f"   Status: {stag['status']}")
            if 'metrics' in stag:
                print(f"   Metrics: {stag['metrics']}")
        else:
            print("\n⚠️  No staging model set")
    
    elif args.action == 'history':
        history = registry.get_history(limit=args.limit)
        print(f"\n📜 History (last {len(history)}):")
        for entry in history:
            print(f"  • {entry['model_id']} - {entry['status']}")
            if 'archived_at' in entry:
                print(f"    Archived: {entry['archived_at']}")
    
    elif args.action == 'rollback':
        if args.to:
            result = registry.rollback_to_version(args.to)
        else:
            result = registry.rollback_to_previous()
        print(f"\n✅ Rolled back to: {result['model_id']}")
    
    elif args.action == 'stats':
        stats = registry.get_stats()
        print(f"\n📊 Registry Statistics:")
        print(f"   Total Models: {stats['total_models']}")
        print(f"   By Status:")
        for status, count in stats['by_status'].items():
            print(f"     {status}: {count}")
        print(f"   History Entries: {stats['history_entries']}")
    
    elif args.action == 'prune':
        pruned = registry.prune_old_models(keep_last_n=args.limit)
        print(f"\n🧹 Pruned {len(pruned)} models")


if __name__ == '__main__':
    main()
