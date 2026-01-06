# Model Registry Learning Guide 📚

**Week 2 Day 3: Building the Model Registry**

## Table of Contents
1. [Why Model Registry Matters](#why-model-registry-matters)
2. [Registry Architecture](#registry-architecture)
3. [Model States & Lifecycle](#model-states--lifecycle)
4. [Version Tracking](#version-tracking)
5. [Promotion & Deployment](#promotion--deployment)
6. [Rollback Strategy](#rollback-strategy)
7. [Implementation Guide](#implementation-guide)
8. [Best Practices](#best-practices)

---

## Why Model Registry Matters

### The Problem Without Registry

```
❌ CHAOS:
/models/
  ├── model.pkl                    ← Which version?
  ├── model_backup.pkl             ← When was this created?
  ├── model_old.pkl                ← Is this still needed?
  ├── model_new_20260106.pkl       ← Is this deployed?
  └── model_best.pkl               ← Best by what metric?

Questions you can't answer:
• Which model is in production?
• When was it deployed?
• What were its metrics?
• Can I rollback to previous version?
• Which models can I safely delete?
```

### The Solution With Registry

```
✅ ORGANIZED:
registry.json:
{
  "production": {
    "model_id": "model_20260106_180235",
    "deployed_at": "2026-01-06T18:30:00Z",
    "metrics": {"mae": 6.82, "r2": 0.9303},
    "status": "production"
  },
  "staging": {
    "model_id": "model_20260106_180648",
    "validated_at": "2026-01-06T18:37:00Z",
    "metrics": {"mae": 6.80, "r2": 0.9310}
  },
  "history": [...]
}

Now you can:
✅ Track which model is in production
✅ See deployment history
✅ Compare model metrics
✅ Rollback to any previous version
✅ Archive old models safely
```

---

## Registry Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                      MODEL REGISTRY                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Production  │  │   Staging    │  │   Archive    │     │
│  │   (Active)   │  │ (Validated)  │  │   (Backup)   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                  │                   │            │
│         ├──────────────────┴───────────────────┘            │
│         │                                                    │
│  ┌──────▼────────────────────────────────────────────────┐ │
│  │            Master Registry (registry.json)            │ │
│  │  • All model metadata                                 │ │
│  │  • Deployment history                                 │ │
│  │  • Validation results                                 │ │
│  │  • Performance metrics                                │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Data Structure

```json
{
  "production": {
    "model_id": "model_20260106_180235",
    "model_path": "training/models/model_20260106_180235",
    "status": "production",
    "promoted_at": "2026-01-06T18:30:00Z",
    "promoted_by": "auto-trainer",
    "metrics": {
      "mae": 6.82,
      "rmse": 11.30,
      "r2": 0.9303,
      "samples": 6941
    },
    "validation": {
      "decision": "APPROVE",
      "compared_to": "model_20260105_120000",
      "improvements": {
        "mae": 12.5,
        "r2_absolute": 0.0250
      }
    },
    "metadata": {
      "created_at": "2026-01-06T18:02:35Z",
      "training_samples": 6941,
      "features": 68
    }
  },
  "staging": {
    "model_id": "model_20260106_180648",
    "status": "staging",
    "validated_at": "2026-01-06T18:37:00Z",
    "metrics": {...},
    "validation": {...}
  },
  "history": [
    {
      "model_id": "model_20260105_120000",
      "status": "archived",
      "archived_at": "2026-01-06T18:30:00Z",
      "was_production": true,
      "production_duration": "86400s",
      "metrics": {...}
    }
  ]
}
```

---

## Model States & Lifecycle

### State Diagram

```
┌─────────────┐
│    NEW      │  New model trained
│  (Created)  │
└──────┬──────┘
       │
       │ Auto-Trainer
       ▼
┌─────────────┐
│  CANDIDATE  │  Ready for validation
│ (Unverified)│
└──────┬──────┘
       │
       │ Model Validator
       ▼
    ┌──────┐
    │PASS? │
    └──┬───┘
       │
   ┌───┴───────────┐
   │               │
   │ YES           │ NO
   ▼               ▼
┌─────────────┐ ┌─────────────┐
│   STAGING   │ │   REJECTED  │
│ (Validated) │ │  (Failed)   │
└──────┬──────┘ └─────────────┘
       │
       │ Manual/Auto Promotion
       ▼
┌─────────────┐
│ PRODUCTION  │
│  (Active)   │
└──────┬──────┘
       │
       │ Replaced by newer model
       ▼
┌─────────────┐
│  ARCHIVED   │
│  (Backup)   │
└─────────────┘
```

### State Transitions

**1. NEW → CANDIDATE**
```python
# After training completes
registry.register_model(
    model_id="model_20260106_180235",
    status="candidate"
)
```

**2. CANDIDATE → STAGING**
```python
# After validation passes
validation_result = validator.validate(current, new)
if validation_result['decision'] == 'APPROVE':
    registry.promote_to_staging(model_id)
```

**3. STAGING → PRODUCTION**
```python
# Manual or automatic promotion
registry.promote_to_production(
    model_id,
    promoted_by="orchestrator"
)
```

**4. PRODUCTION → ARCHIVED**
```python
# When replaced by newer model
registry.archive_model(
    model_id,
    reason="Replaced by better model"
)
```

---

## Version Tracking

### Unique Identifiers

**Timestamp-Based IDs:**
```
model_YYYYMMDD_HHMMSS
model_20260106_180235  ← Created Jan 6, 2026 at 18:02:35
```

**Benefits:**
- Chronologically sortable
- Human-readable
- No collisions (second-level precision)
- Easy to find in logs

### Version History

```python
{
  "history": [
    {
      "model_id": "model_20260106_180235",
      "status": "production",
      "deployed_at": "2026-01-06T18:30:00Z",
      "replaced_at": "2026-01-07T12:00:00Z",
      "uptime": "63000s",  # ~17.5 hours
      "metrics": {
        "mae": 6.82,
        "r2": 0.9303
      },
      "performance": {
        "predictions_made": 2500,
        "avg_response_time": "45ms"
      }
    },
    {
      "model_id": "model_20260105_120000",
      "status": "archived",
      "deployed_at": "2026-01-05T12:00:00Z",
      "replaced_at": "2026-01-06T18:30:00Z",
      "uptime": "108600s",  # ~30 hours
      "metrics": {...}
    }
  ]
}
```

---

## Promotion & Deployment

### Promotion Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    PROMOTION WORKFLOW                        │
└─────────────────────────────────────────────────────────────┘

1. TRAIN NEW MODEL
   • Auto-Trainer creates model_20260106_180648
   • Status: CANDIDATE
   
2. VALIDATE
   • ModelValidator compares vs current production
   • Decision: APPROVE (MAE improved 12.5%, R² +0.025)
   • Status: CANDIDATE → STAGING
   
3. STAGING PERIOD (Optional)
   • Test in staging environment
   • Monitor for 24 hours
   • A/B test with 10% traffic
   
4. PROMOTE TO PRODUCTION
   • Current production → ARCHIVED
   • Staging model → PRODUCTION
   • Update API to use new model
   
5. MONITOR
   • Track real-world performance
   • Compare vs validation metrics
   • Ready to rollback if needed
```

### Safe Deployment Checklist

```
Before Promoting to Production:
☐ Validation passed (APPROVE decision)
☐ Metrics better than current
☐ Model files exist and loadable
☐ Feature engineer compatible
☐ No breaking changes in API
☐ Rollback plan ready
☐ Monitoring configured
☐ Team notified (if manual)
```

---

## Rollback Strategy

### When to Rollback

```
⚠️ ROLLBACK TRIGGERS:

1. Performance Degradation
   • Real MAE > Validation MAE + 20%
   • Prediction errors spike
   • Response time increases

2. System Issues
   • Model fails to load
   • Memory errors
   • Crashes/exceptions

3. Business Impact
   • User complaints increase
   • Downstream systems affected
   • SLA violations
```

### Rollback Process

```python
# 1. Identify issue
print("⚠️ Production MAE: 15.2 (expected: 6.8)")
print("🚨 ROLLBACK NEEDED!")

# 2. Get previous production model
previous = registry.get_previous_production()
print(f"Rolling back to: {previous['model_id']}")

# 3. Execute rollback
registry.rollback_to_previous()

# 4. Verify
current = registry.get_production()
print(f"✅ Rolled back to: {current['model_id']}")
print(f"   MAE: {current['metrics']['mae']}")

# 5. Investigate failure
# Mark failed model for investigation
registry.mark_failed(
    model_id="model_20260106_180648",
    reason="High production MAE",
    details="Real MAE 15.2 vs validation 6.8"
)
```

### Rollback Examples

**Example 1: Simple Rollback**
```bash
# Production model is bad, go back to previous
python model_registry.py rollback
```

**Example 2: Rollback to Specific Version**
```bash
# Go back to specific model
python model_registry.py rollback --to model_20260105_120000
```

**Example 3: Emergency Rollback**
```bash
# Immediate rollback + disable auto-deployment
python model_registry.py rollback --emergency
```

---

## Implementation Guide

### Core Class Structure

```python
class ModelRegistry:
    """
    Centralized registry for model version tracking.
    """
    
    def __init__(self, registry_path):
        self.registry_path = registry_path
        self.registry = self.load_registry()
    
    # Version Management
    def register_model(self, model_id, metadata)
    def get_model(self, model_id)
    def list_models(self, status=None)
    
    # Status Management
    def promote_to_staging(self, model_id)
    def promote_to_production(self, model_id)
    def archive_model(self, model_id)
    
    # Queries
    def get_production(self)
    def get_staging(self)
    def get_history(self, limit=10)
    def get_previous_production(self)
    
    # Rollback
    def rollback_to_previous(self)
    def rollback_to_version(self, model_id)
    
    # Cleanup
    def prune_old_models(self, keep_last_n=5)
    def mark_failed(self, model_id, reason)
```

### Key Methods

**Register New Model:**
```python
def register_model(self, model_id, metadata):
    """
    Register a new model in the registry.
    
    Args:
        model_id: Unique model identifier
        metadata: Dict with metrics, paths, etc.
    """
    entry = {
        'model_id': model_id,
        'status': 'candidate',
        'registered_at': datetime.now().isoformat(),
        'metadata': metadata
    }
    
    self.registry['models'][model_id] = entry
    self.save_registry()
```

**Promote to Production:**
```python
def promote_to_production(self, model_id):
    """
    Promote model to production.
    Archives current production model.
    """
    # Archive current production
    current = self.get_production()
    if current:
        self.archive_model(current['model_id'])
    
    # Promote new model
    self.registry['production'] = {
        'model_id': model_id,
        'promoted_at': datetime.now().isoformat()
    }
    
    self.save_registry()
```

**Rollback:**
```python
def rollback_to_previous(self):
    """
    Rollback to previous production model.
    """
    previous = self.get_previous_production()
    if not previous:
        raise ValueError("No previous production model found")
    
    # Current production → failed
    current = self.get_production()
    self.mark_failed(current['model_id'], "Rolled back")
    
    # Previous → production
    self.promote_to_production(previous['model_id'])
```

---

## Best Practices

### 1. Always Keep History

```python
# DON'T: Delete old models immediately
os.remove(f"models/{old_model_id}")

# DO: Keep history for analysis
registry.archive_model(old_model_id, reason="Replaced")
# Prune after 30 days
registry.prune_old_models(days=30)
```

### 2. Atomic Updates

```python
# DON'T: Multiple operations without transaction
registry.archive_model(old_id)
registry.promote_to_production(new_id)  # If this fails, inconsistent state!

# DO: Atomic promotion
registry.promote_to_production_atomic(
    new_id=new_id,
    archive_current=True
)
```

### 3. Validation Before Promotion

```python
# DON'T: Promote without validation
registry.promote_to_production(model_id)

# DO: Validate first
validation = validator.validate(current, new)
if validation['decision'] == 'APPROVE':
    registry.promote_to_production(model_id)
else:
    registry.mark_failed(model_id, validation['reasons'])
```

### 4. Metadata is Gold

```python
# DON'T: Minimal metadata
registry.register_model(model_id, {'mae': 6.82})

# DO: Rich metadata
registry.register_model(model_id, {
    'metrics': {'mae': 6.82, 'r2': 0.9303},
    'training': {
        'samples': 6941,
        'duration': '37s',
        'features': 68
    },
    'validation': {
        'decision': 'APPROVE',
        'improvements': {'mae': 12.5}
    },
    'environment': {
        'python': '3.13',
        'river': '0.21.0'
    }
})
```

### 5. Regular Cleanup

```python
# Set up periodic cleanup
def cleanup_old_models():
    """Run daily to manage disk space."""
    # Keep last 10 models in registry
    registry.prune_old_models(keep_last_n=10)
    
    # Delete archived models older than 90 days
    registry.delete_old_archives(days=90)
    
    # Archive failed models after 30 days
    registry.archive_failed_models(days=30)
```

---

## Common Patterns

### Pattern 1: Blue-Green Deployment

```python
# Keep both old and new in production briefly
registry.promote_to_production(new_model_id)
# Old model still available for 1 hour
time.sleep(3600)
registry.archive_model(old_model_id)
```

### Pattern 2: Canary Deployment

```python
# Deploy to small percentage first
registry.promote_to_staging(new_model_id)
# Route 10% traffic to staging
deploy_canary(staging_model, traffic_percentage=10)
# Monitor for 2 hours
if canary_metrics_good():
    registry.promote_to_production(new_model_id)
```

### Pattern 3: Shadow Mode

```python
# Run new model in shadow (predictions not used)
registry.set_shadow_mode(new_model_id)
# Compare predictions for 24 hours
compare_shadow_vs_production()
if shadow_performance_good():
    registry.promote_to_production(new_model_id)
```

---

## Summary

**Model Registry = Source of Truth**

```
┌───────────────────────────────────────────────────────────┐
│                                                            │
│  Model Registry provides:                                 │
│  ✅ Single source of truth for model versions             │
│  ✅ Complete deployment history                           │
│  ✅ Easy rollback capability                              │
│  ✅ Production/Staging separation                         │
│  ✅ Metadata tracking                                     │
│  ✅ Cleanup automation                                    │
│                                                            │
│  Key Benefits:                                            │
│  • No more "which model is deployed?"                     │
│  • Instant rollback when needed                           │
│  • Full audit trail                                       │
│  • Safe experimentation                                   │
│                                                            │
└───────────────────────────────────────────────────────────┘
```

**Next:** Implement the Model Registry class!
