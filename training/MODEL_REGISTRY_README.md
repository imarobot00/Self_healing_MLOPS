# Model Registry - Quick Reference

## Overview

The Model Registry is a centralized system for tracking ML model versions, managing their lifecycle, and enabling safe rollbacks. It provides version tracking, state management, and deployment history.

## Key Features

✅ **Version Tracking** - Unique IDs with timestamps (model_YYYYMMDD_HHMMSS)  
✅ **State Management** - Candidate → Staging → Production → Archived/Failed  
✅ **Promotion Workflow** - Controlled deployment pipeline  
✅ **Rollback Capability** - Quick recovery from production issues  
✅ **Deployment History** - Complete audit trail  
✅ **Metadata Storage** - Metrics, training info, validation results  

---

## Model States

| State | Description | Next Action |
|-------|-------------|-------------|
| **candidate** | Newly trained, not yet validated | Run ModelValidator |
| **staging** | Passed validation, ready for testing | Test in staging environment |
| **production** | Currently serving predictions | Monitor performance |
| **archived** | Previously in production, now replaced | Kept for rollback |
| **failed** | Marked as problematic | Investigate, don't promote |

---

## Quick Start

### 1. Register Existing Models

```bash
# Register all models in models/ directory
python register_existing_models.py
```

### 2. View Registry

```bash
# List all models
python model_registry.py list

# Filter by status
python model_registry.py list --status candidate

# Show production model
python model_registry.py production

# View history
python model_registry.py history --limit 5

# Get statistics
python model_registry.py stats
```

---

## Python API Usage

### Initialize Registry

```python
from model_registry import ModelRegistry

registry = ModelRegistry()
```

### Register New Model

```python
registry.register_model(
    model_id='model_20260106_180235',
    model_path='/path/to/model',
    metrics={'mae': 15.2, 'r2': 0.85},
    metadata={'training_duration': 120, 'samples': 10000}
)
```

### Promotion Workflow

```python
# Step 1: Promote to staging (after validation)
registry.promote_to_staging(
    'model_20260106_180235',
    validation_result={'decision': 'APPROVE', 'mae': 15.0}
)

# Step 2: Test in staging environment
# ... run integration tests ...

# Step 3: Promote to production
registry.promote_to_production(
    'model_20260106_180235',
    promoted_by='automated_pipeline'
)
```

### Get Current Models

```python
# Get production model
prod = registry.get_production()
print(f"Production: {prod['model_id']}")

# Get staging model
staging = registry.get_staging()

# Get previous production (for comparison)
prev = registry.get_previous_production()
```

### Rollback

```python
# Rollback to previous production model
registry.rollback_to_previous()

# Rollback to specific version
registry.rollback_to_version('model_20260106_180235')
```

### Mark Failed

```python
registry.mark_failed(
    'model_20260106_180648',
    reason='High error rate in production',
    details='MAE increased from 15 to 45'
)
```

### Maintenance

```python
# Prune old archived models (keep last 10)
pruned = registry.prune_old_models(keep_last_n=10)

# View history
history = registry.get_history(limit=20)

# Get statistics
stats = registry.get_stats()
```

---

## Integration with Other Components

### With Auto-Trainer

```python
from auto_trainer import AutoTrainer
from model_registry import ModelRegistry

trainer = AutoTrainer()
registry = ModelRegistry()

# After training
model_id = trainer.train_model()

# Register in registry
registry.register_model(
    model_id=model_id,
    model_path=trainer.model_path,
    metrics=trainer.latest_metrics
)
```

### With Model Validator

```python
from model_validator import ModelValidator
from model_registry import ModelRegistry

validator = ModelValidator()
registry = ModelRegistry()

# Validate new model
new_model = 'model_20260106_180235'
current_model = registry.get_production()['model_id']

result = validator.validate(new_model, current_model)

if result['decision'] == 'APPROVE':
    # Promote to staging
    registry.promote_to_staging(new_model, validation_result=result)
    print(f"✅ {new_model} promoted to staging")
elif result['decision'] == 'REJECT':
    # Mark as failed
    registry.mark_failed(
        new_model,
        reason='Failed validation',
        details=result['reasons']
    )
```

### With API (FastAPI)

```python
from fastapi import FastAPI
from model_registry import ModelRegistry

app = FastAPI()
registry = ModelRegistry()

@app.get("/model/production")
def get_production_model():
    """Get current production model info."""
    prod = registry.get_production()
    return {
        "model_id": prod['model_id'],
        "metrics": prod['metrics'],
        "deployed_at": prod['promoted_to_production_at']
    }

@app.post("/model/rollback")
def rollback_model():
    """Emergency rollback to previous model."""
    result = registry.rollback_to_previous()
    return {
        "status": "success",
        "new_production": result['model_id']
    }
```

---

## Registry File Structure

The registry is stored in `registry.json`:

```json
{
  "production": {
    "model_id": "model_20260106_180235",
    "promoted_at": "2026-01-06T18:30:45",
    "promoted_by": "automated_pipeline"
  },
  "staging": {
    "model_id": "model_20260106_180648",
    "promoted_at": "2026-01-06T18:35:12"
  },
  "models": {
    "model_20260106_180235": {
      "model_id": "model_20260106_180235",
      "model_path": "/path/to/model",
      "status": "production",
      "registered_at": "2026-01-06T18:02:35",
      "promoted_to_production_at": "2026-01-06T18:30:45",
      "metrics": {
        "mae": 15.2,
        "r2": 0.85
      },
      "metadata": {
        "training_duration": 120,
        "samples": 10000
      }
    }
  },
  "history": [
    {
      "model_id": "model_20260105_120000",
      "status": "archived",
      "archived_at": "2026-01-06T18:30:45",
      "archive_reason": "Replaced by new model",
      "production_uptime_seconds": 86400
    }
  ]
}
```

---

## CLI Commands

### List Models

```bash
# All models
python model_registry.py list

# Candidates only
python model_registry.py list --status candidate

# Limit results
python model_registry.py list --limit 5
```

### View Current State

```bash
# Production model
python model_registry.py production

# Staging model
python model_registry.py staging

# Statistics
python model_registry.py stats
```

### History

```bash
# Last 10 entries
python model_registry.py history

# Last 20 entries
python model_registry.py history --limit 20
```

### Rollback

```bash
# Rollback to previous
python model_registry.py rollback

# Rollback to specific version
python model_registry.py rollback --to model_20260106_180235
```

### Maintenance

```bash
# Prune old models (keep last 10)
python model_registry.py prune --limit 10
```

---

## Best Practices

### 1. Always Validate Before Promotion

```python
# ✅ CORRECT
result = validator.validate(new_model, current_model)
if result['decision'] == 'APPROVE':
    registry.promote_to_staging(new_model)

# ❌ WRONG - don't promote blindly
registry.promote_to_production(new_model)  # No validation!
```

### 2. Test in Staging First

```python
# Promote to staging
registry.promote_to_staging(model_id)

# Run integration tests
test_results = run_staging_tests()

# Only then promote to production
if test_results['passed']:
    registry.promote_to_production(model_id)
```

### 3. Keep Rich Metadata

```python
registry.register_model(
    model_id=model_id,
    metrics={
        'mae': 15.2,
        'r2': 0.85,
        'rmse': 18.5,
        'mape': 12.3
    },
    metadata={
        'training_duration': 120,
        'training_samples': 10000,
        'features': 68,
        'algorithm': 'Adaptive Random Forest',
        'drift_detected': True,
        'data_date_range': '2024-01-01 to 2024-12-31'
    }
)
```

### 4. Regular Cleanup

```python
# Keep last 20 archived models
registry.prune_old_models(keep_last_n=20)
```

### 5. Monitor History

```python
# Check deployment frequency
history = registry.get_history(limit=50)
deployment_count = len(history)
print(f"Deployments in history: {deployment_count}")
```

---

## Rollback Decision Tree

```
Production Issue Detected
    │
    ├─ Is previous model available?
    │   │
    │   ├─ YES → rollback_to_previous()
    │   │
    │   └─ NO → rollback_to_version('known_good_model')
    │
    └─ Mark failed model
        registry.mark_failed(model_id, reason='...')
```

---

## Common Workflows

### Daily Operations

```python
# 1. Check production status
prod = registry.get_production()
print(f"Production: {prod['model_id']}")

# 2. Check for new candidates
candidates = registry.list_models(status='candidate')
print(f"Candidates: {len(candidates)}")

# 3. Review staging
staging = registry.get_staging()
if staging:
    print(f"Staging: {staging['model_id']}")
```

### Emergency Rollback

```python
# Quick rollback
try:
    result = registry.rollback_to_previous()
    print(f"✅ Rolled back to {result['model_id']}")
    
    # Notify team
    send_alert(f"Emergency rollback to {result['model_id']}")
except ValueError as e:
    print(f"❌ Rollback failed: {e}")
```

### Weekly Cleanup

```python
# Prune old archived models
pruned = registry.prune_old_models(keep_last_n=20)
print(f"Pruned {len(pruned)} old models")

# Review stats
stats = registry.get_stats()
print(f"Total models: {stats['total_models']}")
print(f"By status: {stats['by_status']}")
```

---

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
python test_model_registry.py

# Or use pytest
pytest test_model_registry.py -v
```

**Test Coverage:**
- Registry initialization
- Model registration
- List and filter models
- Promotion workflow (candidate → staging → production)
- Production replacement and archival
- Rollback (previous and specific version)
- Mark failed models
- History tracking
- Pruning old models
- Registry persistence

---

## Troubleshooting

### Issue: Model not found for rollback

**Solution:** Check history
```python
history = registry.get_history(limit=50)
for entry in history:
    print(f"{entry['model_id']} - {entry['status']}")
```

### Issue: Registry file corrupted

**Solution:** Registry auto-saves, but you can restore from backup
```bash
cp registry.json.backup registry.json
```

### Issue: Too many models

**Solution:** Prune old ones
```python
pruned = registry.prune_old_models(keep_last_n=10)
```

---

## Files Created

- `model_registry.py` - Main registry class (~500 lines)
- `test_model_registry.py` - Test suite (15 tests)
- `register_existing_models.py` - Utility to register existing models
- `registry.json` - Registry data (auto-created)
- `MODEL_REGISTRY_GUIDE.md` - Comprehensive learning guide
- `MODEL_REGISTRY_README.md` - This quick reference

---

## Next Steps

1. **Week 2 Day 4**: Build Self-Healing Orchestrator
   - Tie together drift detection + auto-trainer + validator + registry
   - Automated end-to-end workflow
   - API integration for deployment

2. **Week 3**: Monitoring & Alerting
   - Integrate with existing monitoring system
   - Alert on model degradation
   - Automated rollback triggers

3. **Week 4**: Containerization
   - Docker containers for each component
   - Docker Compose orchestration

4. **Week 5-6**: Kubernetes Deployment
   - K8s manifests
   - Horizontal scaling
   - Rolling updates

---

## Summary

The Model Registry provides:
- ✅ **Version Control** for ML models
- ✅ **Safe Deployment** with staging → production flow
- ✅ **Quick Recovery** via rollback
- ✅ **Complete History** for audit and debugging
- ✅ **Integration Ready** with other MLOps components

**Production-ready, tested, and documented!** 🚀
