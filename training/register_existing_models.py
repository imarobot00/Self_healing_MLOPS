"""
Register existing models in the Model Registry.

This script scans the models/ directory and registers all found models.
"""

import os
import json
from pathlib import Path
from model_registry import ModelRegistry


def register_existing_models():
    """Register all existing models in the models/ directory."""
    registry = ModelRegistry()
    
    models_dir = Path(registry.models_dir)
    if not models_dir.exists():
        print(f"⚠️  Models directory not found: {models_dir}")
        return
    
    # Find all model directories
    model_dirs = [d for d in models_dir.iterdir() if d.is_dir() and d.name.startswith('model_')]
    
    print(f"\n🔍 Found {len(model_dirs)} model directories\n")
    
    for model_dir in sorted(model_dirs):
        model_id = model_dir.name
        
        # Check if model files exist
        model_pkl = model_dir / 'model.pkl'
        metadata_json = model_dir / 'metadata.json'
        
        if not model_pkl.exists():
            print(f"⚠️  Skipping {model_id}: model.pkl not found")
            continue
        
        # Load metadata if available
        metadata = {}
        metrics = {}
        
        if metadata_json.exists():
            with open(metadata_json, 'r') as f:
                data = json.load(f)
                metadata = data.get('metadata', {})
                metrics = data.get('metrics', {})
        
        # Register model
        try:
            registry.register_model(
                model_id=model_id,
                model_path=str(model_dir),
                metrics=metrics,
                metadata=metadata,
                status='candidate'
            )
            print(f"✅ Registered: {model_id}")
            if metrics:
                print(f"   Metrics: MAE={metrics.get('mae', 'N/A')}, R²={metrics.get('r2', 'N/A')}")
        except Exception as e:
            print(f"❌ Failed to register {model_id}: {e}")
    
    # Show summary
    print(f"\n📊 Registry Summary:")
    stats = registry.get_stats()
    print(f"   Total Models: {stats['total_models']}")
    print(f"   Production: {stats['production'] or 'None'}")
    print(f"   Staging: {stats['staging'] or 'None'}")
    
    print(f"\n💡 Next steps:")
    print(f"   1. Review models: python model_registry.py list")
    print(f"   2. Promote to staging: (use ModelValidator first)")
    print(f"   3. Promote to production: (after testing in staging)")


if __name__ == '__main__':
    register_existing_models()
