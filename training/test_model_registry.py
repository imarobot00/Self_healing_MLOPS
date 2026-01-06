"""
Tests for Model Registry

Tests version tracking, promotion workflow, rollback, and lifecycle management.
"""

import os
import json
import pytest
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

from model_registry import ModelRegistry


@pytest.fixture
def temp_registry():
    """Create temporary registry for testing."""
    temp_dir = tempfile.mkdtemp()
    registry_path = os.path.join(temp_dir, 'registry.json')
    models_dir = os.path.join(temp_dir, 'models')
    
    registry = ModelRegistry(
        registry_path=registry_path,
        models_dir=models_dir
    )
    
    yield registry, temp_dir
    
    # Cleanup
    shutil.rmtree(temp_dir)


def test_registry_initialization(temp_registry):
    """Test registry initialization."""
    registry, temp_dir = temp_registry
    
    # Check registry structure
    assert 'production' in registry.registry
    assert 'staging' in registry.registry
    assert 'models' in registry.registry
    assert 'history' in registry.registry
    
    # Should start empty
    assert registry.registry['production'] is None
    assert registry.registry['staging'] is None
    assert len(registry.registry['models']) == 0
    
    print("✅ Registry initialization test passed")


def test_model_registration(temp_registry):
    """Test registering new models."""
    registry, temp_dir = temp_registry
    
    # Register first model
    model_id = 'model_20260106_180235'
    metrics = {'mae': 15.2, 'r2': 0.85}
    metadata = {'training_duration': 120, 'samples': 10000}
    
    entry = registry.register_model(
        model_id=model_id,
        metrics=metrics,
        metadata=metadata
    )
    
    # Verify registration
    assert entry['model_id'] == model_id
    assert entry['status'] == 'candidate'
    assert entry['metrics'] == metrics
    assert entry['metadata'] == metadata
    assert 'registered_at' in entry
    
    # Verify in registry
    assert model_id in registry.registry['models']
    stored = registry.get_model(model_id)
    assert stored['model_id'] == model_id
    
    print(f"✅ Registered model: {model_id}")
    
    # Register second model
    model_id_2 = 'model_20260106_180648'
    entry_2 = registry.register_model(
        model_id=model_id_2,
        metrics={'mae': 14.1, 'r2': 0.88}
    )
    
    assert len(registry.registry['models']) == 2
    
    print("✅ Model registration test passed")


def test_list_models(temp_registry):
    """Test listing models with filters."""
    registry, temp_dir = temp_registry
    
    # Register multiple models
    registry.register_model('model_001', status='candidate')
    registry.register_model('model_002', status='candidate')
    registry.register_model('model_003', status='staging')
    registry.register_model('model_004', status='production')
    registry.register_model('model_005', status='archived')
    
    # List all
    all_models = registry.list_models()
    assert len(all_models) == 5
    
    # Filter by status
    candidates = registry.list_models(status='candidate')
    assert len(candidates) == 2
    
    staging = registry.list_models(status='staging')
    assert len(staging) == 1
    assert staging[0]['model_id'] == 'model_003'
    
    production = registry.list_models(status='production')
    assert len(production) == 1
    assert production[0]['model_id'] == 'model_004'
    
    archived = registry.list_models(status='archived')
    assert len(archived) == 1
    
    print("✅ List models test passed")


def test_promote_to_staging(temp_registry):
    """Test promoting model to staging."""
    registry, temp_dir = temp_registry
    
    # Register two models
    model_1 = 'model_001'
    model_2 = 'model_002'
    
    registry.register_model(model_1)
    registry.register_model(model_2)
    
    # Promote first to staging
    result = registry.promote_to_staging(
        model_1,
        validation_result={'decision': 'APPROVE', 'mae': 15.0}
    )
    
    assert result['status'] == 'staging'
    assert 'promoted_to_staging_at' in result
    assert result['validation']['decision'] == 'APPROVE'
    
    # Check registry state
    assert registry.registry['staging']['model_id'] == model_1
    
    print(f"✅ Promoted {model_1} to staging")
    
    # Promote second to staging (should demote first)
    result_2 = registry.promote_to_staging(model_2)
    
    assert result_2['status'] == 'staging'
    assert registry.registry['staging']['model_id'] == model_2
    
    # First model should be demoted to candidate
    model_1_entry = registry.get_model(model_1)
    assert model_1_entry['status'] == 'candidate'
    
    print("✅ Staging promotion test passed")


def test_promote_to_production(temp_registry):
    """Test promoting model to production."""
    registry, temp_dir = temp_registry
    
    # Register and promote to staging first
    model_id = 'model_prod_001'
    registry.register_model(model_id, metrics={'mae': 15.0})
    registry.promote_to_staging(model_id)
    
    # Promote to production
    result = registry.promote_to_production(model_id, promoted_by='test_system')
    
    assert result['status'] == 'production'
    assert 'promoted_to_production_at' in result
    assert result['promoted_by'] == 'test_system'
    
    # Check registry state
    assert registry.registry['production']['model_id'] == model_id
    assert registry.registry['production']['promoted_by'] == 'test_system'
    
    # Staging should be cleared
    assert registry.registry['staging'] is None
    
    # Verify get_production
    prod = registry.get_production()
    assert prod['model_id'] == model_id
    
    print("✅ Production promotion test passed")


def test_production_replacement(temp_registry):
    """Test replacing production model archives the old one."""
    registry, temp_dir = temp_registry
    
    # Register and promote first model
    model_1 = 'model_v1'
    registry.register_model(model_1, metrics={'mae': 20.0})
    registry.promote_to_production(model_1)
    
    assert registry.get_production()['model_id'] == model_1
    
    # Register and promote second model
    model_2 = 'model_v2'
    registry.register_model(model_2, metrics={'mae': 15.0})
    registry.promote_to_production(model_2)
    
    # New model should be in production
    assert registry.get_production()['model_id'] == model_2
    
    # Old model should be archived
    model_1_entry = registry.get_model(model_1)
    assert model_1_entry['status'] == 'archived'
    assert 'archived_at' in model_1_entry
    assert model_1_entry['archive_reason'] == 'Replaced by new model'
    
    # Should be in history
    history = registry.get_history()
    assert len(history) > 0
    assert history[0]['model_id'] == model_1
    
    print("✅ Production replacement test passed")


def test_archive_model(temp_registry):
    """Test manual archival."""
    registry, temp_dir = temp_registry
    
    model_id = 'model_archive_test'
    registry.register_model(model_id)
    
    # Archive it
    result = registry.archive_model(
        model_id,
        reason='Testing archival',
        archived_by='test_script'
    )
    
    assert result['status'] == 'archived'
    assert result['archive_reason'] == 'Testing archival'
    assert result['archived_by'] == 'test_script'
    assert 'archived_at' in result
    
    # Should be in history
    history = registry.get_history()
    assert any(h['model_id'] == model_id for h in history)
    
    print("✅ Archive model test passed")


def test_rollback_to_previous(temp_registry):
    """Test rollback to previous production model."""
    registry, temp_dir = temp_registry
    
    # Deploy model v1
    model_v1 = 'model_v1'
    registry.register_model(model_v1, metrics={'mae': 15.0})
    registry.promote_to_production(model_v1)
    
    # Deploy model v2 (will archive v1)
    model_v2 = 'model_v2'
    registry.register_model(model_v2, metrics={'mae': 14.0})
    registry.promote_to_production(model_v2)
    
    # Verify v2 is in production
    assert registry.get_production()['model_id'] == model_v2
    
    # Rollback to v1
    result = registry.rollback_to_previous()
    
    # Should be back to v1
    assert result['model_id'] == model_v1
    assert registry.get_production()['model_id'] == model_v1
    
    # v2 should be marked as failed
    model_v2_entry = registry.get_model(model_v2)
    assert model_v2_entry['status'] == 'failed'
    assert 'failure_reason' in model_v2_entry
    
    print("✅ Rollback to previous test passed")


def test_rollback_to_specific_version(temp_registry):
    """Test rollback to specific version."""
    registry, temp_dir = temp_registry
    
    # Deploy 3 models sequentially
    models = ['model_v1', 'model_v2', 'model_v3']
    for model in models:
        registry.register_model(model)
        registry.promote_to_production(model)
    
    # Current production is v3
    assert registry.get_production()['model_id'] == 'model_v3'
    
    # Rollback to v1 (skip v2)
    result = registry.rollback_to_version('model_v1')
    
    assert result['model_id'] == 'model_v1'
    assert registry.get_production()['model_id'] == 'model_v1'
    
    # v3 should be failed
    model_v3 = registry.get_model('model_v3')
    assert model_v3['status'] == 'failed'
    
    print("✅ Rollback to specific version test passed")


def test_mark_failed(temp_registry):
    """Test marking model as failed."""
    registry, temp_dir = temp_registry
    
    model_id = 'model_failing'
    registry.register_model(model_id)
    
    # Mark as failed
    registry.mark_failed(
        model_id,
        reason='High error rate in production',
        details='MAE increased from 15 to 45'
    )
    
    model = registry.get_model(model_id)
    assert model['status'] == 'failed'
    assert model['failure_reason'] == 'High error rate in production'
    assert model['failure_details'] == 'MAE increased from 15 to 45'
    assert 'failed_at' in model
    
    print("✅ Mark failed test passed")


def test_get_history(temp_registry):
    """Test history retrieval."""
    registry, temp_dir = temp_registry
    
    # Deploy and archive several models
    for i in range(5):
        model_id = f'model_v{i}'
        registry.register_model(model_id)
        registry.promote_to_production(model_id)
    
    # Should have 4 archived models in history (v0-v3, v4 is current)
    history = registry.get_history(limit=10)
    assert len(history) >= 4
    
    # History should be sorted (newest first)
    assert history[0]['model_id'] == 'model_v3'  # Most recently archived
    
    # Limited history
    history_limited = registry.get_history(limit=2)
    assert len(history_limited) == 2
    
    print("✅ Get history test passed")


def test_prune_old_models(temp_registry):
    """Test pruning old archived models."""
    registry, temp_dir = temp_registry
    
    # Create 15 archived models
    for i in range(15):
        model_id = f'model_archive_{i:02d}'
        registry.register_model(model_id)
        registry.archive_model(model_id, reason='Testing')
    
    # Should have 15 archived models
    archived = registry.list_models(status='archived')
    assert len(archived) == 15
    
    # Prune, keeping only last 5
    pruned = registry.prune_old_models(keep_last_n=5)
    
    # Should have pruned 10 models
    assert len(pruned) == 10
    
    # Should have only 5 archived models left
    archived_after = registry.list_models(status='archived')
    assert len(archived_after) == 5
    
    print("✅ Prune old models test passed")


def test_get_previous_production(temp_registry):
    """Test getting previous production model."""
    registry, temp_dir = temp_registry
    
    # No previous production yet
    assert registry.get_previous_production() is None
    
    # Deploy v1
    registry.register_model('model_v1')
    registry.promote_to_production('model_v1')
    
    # Still no previous (v1 is current)
    assert registry.get_previous_production() is None
    
    # Deploy v2 (archives v1)
    registry.register_model('model_v2')
    registry.promote_to_production('model_v2')
    
    # Now v1 should be previous production
    prev = registry.get_previous_production()
    assert prev is not None
    assert prev['model_id'] == 'model_v1'
    
    print("✅ Get previous production test passed")


def test_registry_persistence(temp_registry):
    """Test registry saves and loads correctly."""
    registry, temp_dir = temp_registry
    
    # Register models and promote
    registry.register_model('model_001', metrics={'mae': 15.0})
    registry.register_model('model_002', metrics={'mae': 14.0})
    registry.promote_to_production('model_001')
    
    # Create new registry instance (load from file)
    registry_path = registry.registry_path
    models_dir = registry.models_dir
    
    new_registry = ModelRegistry(
        registry_path=str(registry_path),
        models_dir=str(models_dir)
    )
    
    # Should have same data
    assert len(new_registry.registry['models']) == 2
    assert new_registry.get_production()['model_id'] == 'model_001'
    
    prod = new_registry.get_model('model_001')
    assert prod['metrics']['mae'] == 15.0
    
    print("✅ Registry persistence test passed")


def test_get_stats(temp_registry):
    """Test registry statistics."""
    registry, temp_dir = temp_registry
    
    # Register models with different statuses
    registry.register_model('model_001', status='candidate')
    registry.register_model('model_002', status='candidate')
    registry.register_model('model_003', status='staging')
    registry.register_model('model_004', status='production')
    registry.register_model('model_005', status='archived')
    registry.register_model('model_006', status='failed')
    
    stats = registry.get_stats()
    
    assert stats['total_models'] == 6
    assert stats['by_status']['candidate'] == 2
    assert stats['by_status']['staging'] == 1
    assert stats['by_status']['production'] == 1
    assert stats['by_status']['archived'] == 1
    assert stats['by_status']['failed'] == 1
    
    print("✅ Get stats test passed")


def run_all_tests():
    """Run all tests manually."""
    print("\n" + "="*60)
    print("Running Model Registry Tests")
    print("="*60 + "\n")
    
    tests = [
        ("Registry Initialization", test_registry_initialization),
        ("Model Registration", test_model_registration),
        ("List Models", test_list_models),
        ("Promote to Staging", test_promote_to_staging),
        ("Promote to Production", test_promote_to_production),
        ("Production Replacement", test_production_replacement),
        ("Archive Model", test_archive_model),
        ("Rollback to Previous", test_rollback_to_previous),
        ("Rollback to Specific Version", test_rollback_to_specific_version),
        ("Mark Failed", test_mark_failed),
        ("Get History", test_get_history),
        ("Prune Old Models", test_prune_old_models),
        ("Get Previous Production", test_get_previous_production),
        ("Registry Persistence", test_registry_persistence),
        ("Get Stats", test_get_stats),
    ]
    
    num_passed = 0
    num_failed = 0
    
    for test_name, test_func in tests:
        print(f"\n▶️  Running: {test_name}")
        print("-" * 60)
        try:
            # Create temp registry for each test
            temp_dir = tempfile.mkdtemp()
            registry_path = os.path.join(temp_dir, 'registry.json')
            models_dir = os.path.join(temp_dir, 'models')
            
            registry = ModelRegistry(
                registry_path=registry_path,
                models_dir=models_dir
            )
            
            # Run test
            test_func((registry, temp_dir))
            
            # Cleanup
            shutil.rmtree(temp_dir)
            
            num_passed += 1
            print(f"✅ {test_name} PASSED")
        except Exception as e:
            num_failed += 1
            print(f"❌ {test_name} FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print(f"Test Summary: {num_passed} passed, {num_failed} failed")
    print("="*60 + "\n")
    
    return num_failed == 0


if __name__ == '__main__':
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
