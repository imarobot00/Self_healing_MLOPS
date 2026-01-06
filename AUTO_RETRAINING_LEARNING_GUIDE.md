# Auto-Retraining System - Learning Guide

## What is Auto-Retraining?

**Auto-retraining** is a system that automatically detects when your ML model's performance degrades and triggers retraining with fresh data - without human intervention.

### Why Do We Need It?

**The Problem**: ML models degrade over time due to:

1. **Data Drift**: Input data distribution changes
   - Example: Air quality patterns shift due to new pollution sources
   - Your model was trained on Sept-Dec data, now it's January with different weather

2. **Concept Drift**: Relationship between inputs and outputs changes
   - Example: New environmental regulations affect AQI calculations
   - PM2.5 → AQI relationship evolves

3. **Model Staleness**: Model gets outdated as new data accumulates
   - You have 3 months of new data the model has never seen
   - Fresh patterns aren't captured

**The Solution**: Automatically retrain when performance drops below threshold.

## How Auto-Retraining Works

```
┌─────────────────────────────────────────────────────────────┐
│                    PRODUCTION SYSTEM                         │
│                                                              │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐         │
│  │  Model   │─────▶│ Monitor  │─────▶│  Drift   │         │
│  │ Serving  │      │ Metrics  │      │ Detector │         │
│  └──────────┘      └──────────┘      └────┬─────┘         │
│                                            │                │
│                                            ▼                │
│                                    ┌──────────────┐        │
│                                    │ Drift > 0.15?│        │
│                                    └──────┬───────┘        │
│                                           │ YES             │
│                                           ▼                │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐        │
│  │   New    │◀─────│ Validate │◀─────│ Retrain  │        │
│  │  Model   │      │  Model   │      │  Model   │        │
│  │ Deployed │      └──────────┘      └──────────┘        │
│  └──────────┘                                             │
│       │                                                    │
│       └─────────────────┐                                 │
│                         ▼                                 │
│              ┌────────────────────┐                       │
│              │  Model Registry    │                       │
│              │  (Version History) │                       │
│              └────────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

## Components We'll Build

### 1. **Drift Detector** (✅ Already Built!)

**What**: Detects when input data distribution changes
**How**: Compares recent predictions vs training data using statistical tests
**Output**: Drift score (0.0 = no drift, 1.0 = complete drift)

**You already have**:
- `monitoring/drift_detector.py` - KS test + PSI calculation
- `monitoring/drift_config.yaml` - Thresholds configuration
- Baseline statistics from training data

**Current drift score**: 4.452 (critical drift detected!)

### 2. **Auto-Trainer** (To Build)

**What**: Automatically retrains model when drift exceeds threshold
**How**: 
- Monitors drift score continuously
- Triggers retraining when drift > 0.15
- Uses latest data from location files
- Saves new model with timestamp version

**Key Features**:
```python
class AutoTrainer:
    def should_retrain(self) -> bool:
        """Check if retraining is needed based on drift"""
        drift_score = self.drift_detector.calculate_drift_score()
        return drift_score > self.drift_threshold
    
    def retrain_model(self) -> str:
        """Retrain model with latest data"""
        # 1. Load fresh data from dataset/
        # 2. Preprocess and feature engineer
        # 3. Train new model
        # 4. Save with version (e.g., model_20260106_143000)
        # 5. Return model path
```

### 3. **Model Validator** (To Build)

**What**: Ensures new model is actually better before deployment
**How**:
- Compares new model vs current model on validation set
- Checks multiple metrics (MAE, RMSE, R²)
- Only promotes model if it's genuinely better

**Key Features**:
```python
class ModelValidator:
    def validate_model(self, new_model_path: str) -> bool:
        """Validate new model against current model"""
        # 1. Load validation data (latest 20% of data)
        # 2. Compare metrics:
        #    - New model MAE < Current MAE?
        #    - New model R² > Current R²?
        #    - No catastrophic failures?
        # 3. Return True only if new model is better
```

**Validation Criteria**:
- New MAE must be ≤ Current MAE + 5% tolerance
- New R² must be ≥ Current R² - 5% tolerance
- No predictions > 500 AQI or < 0 AQI (sanity check)

### 4. **Model Registry** (To Build)

**What**: Tracks all model versions with metadata and performance
**How**: 
- Saves each model with timestamp version
- Records training metrics, data stats, validation results
- Enables rollback if needed

**Structure**:
```
training/models/
├── model_20251215_233925/        ← Current production model
│   ├── model.pkl
│   ├── metadata.json
│   └── feature_engineer.pkl
├── model_20260106_143000/        ← New retrained model
│   ├── model.pkl
│   ├── metadata.json
│   ├── validation_results.json
│   └── feature_engineer.pkl
└── registry.json                  ← Master registry
```

**Registry Format**:
```json
{
  "models": [
    {
      "version": "20260106_143000",
      "created_at": "2026-01-06T14:30:00Z",
      "status": "production",
      "metrics": {
        "mae": 18.5,
        "rmse": 25.3,
        "r2": 0.94
      },
      "training_data": {
        "samples": 7500,
        "start_date": "2025-09-01",
        "end_date": "2026-01-06"
      },
      "validation": {
        "passed": true,
        "comparison_model": "20251215_233925",
        "improvement_pct": 12.5
      }
    }
  ]
}
```

## Complete Auto-Retraining Flow

### Phase 1: Detection (Every Hour)

```python
# Check if retraining needed
drift_score = drift_detector.calculate_drift_score()

if drift_score > 0.15:
    logger.warning(f"High drift detected: {drift_score}")
    trigger_retraining()
```

**Triggers**:
- Drift score > 0.15
- Prediction error > 50 AQI for 3 consecutive hours
- Manual trigger via API endpoint

### Phase 2: Retraining (20-30 minutes)

```python
# 1. Load latest data
data = load_all_location_data()  # All location_*.json files
logger.info(f"Loaded {len(data)} samples")

# 2. Preprocess
X_train, y_train = preprocess_and_engineer(data)

# 3. Train new model
new_model = AdaptiveRandomForestRegressor()
new_model.learn_many(X_train, y_train)

# 4. Save with version
version = datetime.now().strftime("%Y%m%d_%H%M%S")
save_model(new_model, f"models/model_{version}")
```

### Phase 3: Validation (5-10 minutes)

```python
# 1. Load validation data (latest 20%)
X_val, y_val = load_validation_data()

# 2. Compare models
current_mae = evaluate_model(current_model, X_val, y_val)
new_mae = evaluate_model(new_model, X_val, y_val)

# 3. Decide
if new_mae < current_mae * 1.05:  # Allow 5% tolerance
    logger.info(f"✅ New model better: MAE {new_mae} < {current_mae}")
    return True
else:
    logger.warning(f"❌ New model worse: MAE {new_mae} > {current_mae}")
    return False
```

### Phase 4: Deployment (1-2 minutes)

```python
if validator.validate_model(new_model_path):
    # 1. Update registry
    registry.register_model(new_model_path, status="production")
    registry.update_model_status(current_model_path, status="archived")
    
    # 2. Reload API
    reload_api_model(new_model_path)
    
    # 3. Reset baseline
    drift_detector.reset_baseline()
    
    logger.info("✅ New model deployed successfully")
else:
    logger.warning("❌ Validation failed, keeping current model")
```

## Key Concepts

### 1. Drift Threshold

**What**: The point at which you decide "model needs retraining"

**Typical Values**:
- **Conservative**: 0.10 (retrain often, always fresh)
- **Balanced**: 0.15 (retrain when clearly needed)
- **Aggressive**: 0.20 (tolerate more drift, retrain rarely)

**Your Setting**: 0.15 (in `drift_config.yaml`)

### 2. Validation Strategy

**Why**: Prevent deploying worse models

**Options**:

A. **Holdout Validation** (We'll use this)
   - Keep latest 20% of data for validation
   - Simple and fast
   
B. **Time-Based Split**
   - Train on data up to 2 weeks ago
   - Validate on last 2 weeks
   - Realistic for time-series

C. **Cross-Validation**
   - More robust but slower
   - Not ideal for time-series data

### 3. Model Versioning

**Format**: `model_YYYYMMDD_HHMMSS`
- Example: `model_20260106_143000` = Jan 6, 2026 at 2:30 PM
- Enables easy rollback: "Use model from yesterday"
- Clear audit trail: "When was this model trained?"

### 4. Rollback Strategy

**When to Rollback**:
- New model fails validation
- Production errors spike after deployment
- Manual decision (model behaves unexpectedly)

**How to Rollback**:
```python
registry.rollback_to_version("20251215_233925")
api.reload_model()
```

## What We'll Implement

### Week 2 - Day 1 (Today)

**File**: `training/auto_trainer.py` (~400 lines)
- Check drift score
- Trigger retraining
- Load and preprocess data
- Train new model
- Save with versioning

### Week 2 - Day 2

**File**: `training/model_validator.py` (~300 lines)
- Load validation data
- Evaluate both models
- Compare metrics
- Approve/reject new model

### Week 2 - Day 3

**File**: `training/model_registry.py` (~250 lines)
- Track all model versions
- Store metadata and metrics
- Enable model promotion/archival
- Support rollback

### Week 2 - Day 4

**File**: `training/orchestrator.py` (~200 lines)
- Tie everything together
- End-to-end retraining pipeline
- Error handling and logging
- API integration

## Expected Performance Improvements

### Before Auto-Retraining

- Model trained on Sept-Dec 2025 data
- Current drift score: **4.452** (critical!)
- Average error: **50-70 AQI points**
- Some predictions off by **100+ AQI**

### After Auto-Retraining

- Model includes Jan 2026 data
- Drift score reset to **~0.05**
- Average error: **20-30 AQI points** (40-60% improvement)
- Fewer extreme prediction failures

### Ongoing Benefits

- Model stays fresh automatically
- Performance degrades slower
- Early detection of issues
- No manual intervention needed

## Best Practices

### 1. **Don't Retrain Too Often**
- ❌ Every hour: Waste resources, no new data yet
- ✅ When drift > 0.15: Data-driven decision
- ✅ At least 24 hours between retrains: Give new data time to accumulate

### 2. **Always Validate Before Deployment**
- ❌ Deploy immediately after training
- ✅ Compare new vs current model
- ✅ Only deploy if genuinely better

### 3. **Keep Model History**
- ❌ Overwrite old models
- ✅ Version all models with timestamps
- ✅ Keep last 5-10 versions for rollback

### 4. **Monitor Retraining Process**
- Log every step
- Track training time
- Alert on failures
- Record validation results

### 5. **Test on Validation Set First**
- Don't deploy to production directly
- Use realistic validation data
- Check edge cases

## Common Pitfalls

### 1. **Overfitting to Recent Data**
**Problem**: New model trained only on last week's data
**Solution**: Include at least 2-3 months of historical data

### 2. **Training on Dirty Data**
**Problem**: Include bad predictions/actuals in training
**Solution**: Filter outliers, validate data quality first

### 3. **No Validation**
**Problem**: Deploy model that's actually worse
**Solution**: Always validate on holdout set

### 4. **Ignoring Seasonality**
**Problem**: Winter model fails in summer
**Solution**: Include full seasonal cycle in training data

### 5. **Resource Exhaustion**
**Problem**: Retraining too often consumes too much CPU/memory
**Solution**: Rate limit retraining (max 1x per day)

## Success Metrics

Track these to measure auto-retraining effectiveness:

1. **Drift Score Over Time**
   - Should reset to ~0.05 after retraining
   - Should grow slowly between retrains

2. **Prediction Error Trend**
   - Average MAE should decrease after retraining
   - Fewer extreme errors (>100 AQI)

3. **Retraining Frequency**
   - Balanced: 1-2x per week
   - Too frequent: System unstable
   - Too rare: Model getting stale

4. **Validation Success Rate**
   - Target: >80% of retrains improve model
   - If <50%: Training strategy needs adjustment

5. **Model Deployment Time**
   - End-to-end: <30 minutes
   - Training: <20 minutes
   - Validation: <5 minutes
   - Deployment: <2 minutes

## Next Steps

Now that you understand auto-retraining, we'll build it step by step:

1. **Auto-Trainer**: Detect drift → Trigger retraining → Save new model
2. **Model Validator**: Evaluate new model → Compare metrics → Approve/reject
3. **Model Registry**: Version tracking → Metadata storage → Rollback support
4. **Orchestrator**: End-to-end pipeline → API integration → Error handling

Ready to start building? Let's begin with the Auto-Trainer! 🚀

---

**Current Status**: 
- ✅ Drift detection working (score: 4.452)
- ✅ Prediction matching working (82 matched predictions)
- ✅ Performance tracking ready
- 🔄 Auto-retraining system - Ready to build!
