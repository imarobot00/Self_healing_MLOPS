# 🔄 Self-Healing MLOps Implementation Guide

**Date**: January 6, 2026  
**Next Phase**: Automatic Drift Detection & Model Retraining  
**Goal**: Make your system truly "self-healing" - auto-recover from performance degradation

---

## 📊 Current System Status

### ✅ What You Have
- **Data Pipeline**: Fetches new data every 2 hours
- **Model Training**: ARF model with 93.2% R² score
- **API**: FastAPI serving predictions via `/predict` and `/forecast`
- **Monitoring**: Performance tracking (MAE, RMSE, R²), prediction logging, alerts

### ❌ What's Missing - THE SELF-HEALING PART!
Your system can:
- ✅ Detect when performance degrades (monitoring alerts)
- ❌ **Cannot automatically fix itself**
- ❌ **No drift detection in production**
- ❌ **No automatic retraining trigger**
- ❌ **No model versioning/rollback**
- ❌ **No A/B testing between model versions**

**Problem**: When the model starts performing poorly, someone (you!) has to manually:
1. Notice the alerts
2. Run retraining script
3. Deploy new model
4. Hope it works better

**Solution**: Build a self-healing loop that does this automatically!

---

## 🎯 Implementation Plan

### Phase 3A: Production Drift Detection (Week 1)
**Goal**: Detect when incoming data differs from training data

#### What You'll Build:
```
monitoring/
├── drift_detector.py       # NEW: Real-time drift detection
├── drift_config.yaml       # NEW: Thresholds and parameters
└── drift_report.html       # NEW: Visualization template
```

**Key Features**:
- **Statistical Drift Detection**:
  - Kolmogorov-Smirnov test (distribution changes)
  - Population Stability Index (PSI)
  - Jensen-Shannon divergence
- **Feature-level Monitoring**:
  - Track each feature separately (pm25, temp, humidity)
  - Alert when any feature drifts beyond threshold
- **Drift Severity Scoring**:
  - Low (0-0.3): Normal variation
  - Medium (0.3-0.5): Watch closely
  - High (>0.5): Trigger retraining

**Files to Create**:

1. **`monitoring/drift_detector.py`** (~300 lines)
```python
import numpy as np
from scipy.stats import ks_2samp
from typing import Dict, List
import json
from datetime import datetime

class DriftDetector:
    """Detects distribution drift in production data"""
    
    def __init__(self, baseline_data_path: str):
        # Load training data statistics
        self.baseline_stats = self._load_baseline()
        self.drift_history = []
        
    def detect_drift(self, recent_data: List[Dict]) -> Dict:
        """
        Compare recent production data to training baseline
        Returns drift scores for each feature
        """
        # Calculate KS test for each feature
        # Calculate PSI scores
        # Generate drift report
        pass
```

2. **`monitoring/drift_config.yaml`** (~50 lines)
```yaml
drift_detection:
  enabled: true
  check_interval_hours: 6
  window_size: 200  # Compare last 200 predictions
  
  thresholds:
    ks_statistic: 0.3      # KS test threshold
    psi_threshold: 0.2     # PSI threshold
    drift_score: 0.5       # Combined score threshold
  
  features_to_monitor:
    - pm25
    - pm1
    - temperature
    - relativehumidity
  
  actions:
    medium_drift:
      - log_warning
      - send_email
    high_drift:
      - log_critical
      - send_email
      - trigger_retraining
```

---

### Phase 3B: Automatic Retraining Pipeline (Week 2)
**Goal**: Automatically retrain model when drift/degradation detected

#### What You'll Build:
```
retraining/
├── auto_trainer.py         # NEW: Automatic retraining orchestrator
├── model_validator.py      # NEW: Validate new model before deployment
├── model_registry.py       # NEW: Track all model versions
└── retraining_policy.yaml  # NEW: When/how to retrain
```

**Key Features**:
- **Smart Retraining Triggers**:
  - Performance drops below threshold (MAE > 15)
  - High drift detected (score > 0.5)
  - Manual trigger via API
  - Scheduled retraining (weekly)
- **Model Validation**:
  - Test new model on validation set
  - Compare to current production model
  - Only deploy if improvement > 5%
- **Safe Deployment**:
  - Save old model as backup
  - Gradual rollout (canary deployment)
  - Automatic rollback if new model fails

**Files to Create**:

1. **`retraining/auto_trainer.py`** (~400 lines)
```python
from training.training import train_model
from pathlib import Path
import logging

class AutoTrainer:
    """Manages automatic model retraining"""
    
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.model_registry = ModelRegistry()
        
    def should_retrain(self) -> tuple[bool, str]:
        """
        Check if retraining is needed
        Returns: (should_retrain: bool, reason: str)
        """
        # Check performance metrics
        current_mae = self._get_latest_mae()
        if current_mae > self.config['thresholds']['max_mae']:
            return True, f"MAE degraded to {current_mae}"
        
        # Check drift scores
        drift_score = self._get_latest_drift()
        if drift_score > self.config['thresholds']['max_drift']:
            return True, f"High drift detected: {drift_score}"
        
        return False, "Performance within acceptable range"
    
    def retrain_and_validate(self) -> Dict:
        """
        1. Fetch latest data
        2. Retrain model
        3. Validate on test set
        4. Compare to production model
        5. Deploy if better
        """
        pass
```

2. **`retraining/model_registry.py`** (~200 lines)
```python
import json
from pathlib import Path
from typing import Dict, List

class ModelRegistry:
    """Track all model versions with metadata"""
    
    def __init__(self, registry_path: str):
        self.registry_path = Path(registry_path)
        self.registry = self._load_registry()
    
    def register_model(self, model_path: str, metrics: Dict, metadata: Dict):
        """
        Register new model version
        
        Args:
            model_path: Path to model file
            metrics: {mae, rmse, r2, drift_score}
            metadata: {training_date, data_version, trigger_reason}
        """
        version_id = self._generate_version_id()
        self.registry[version_id] = {
            'path': model_path,
            'metrics': metrics,
            'metadata': metadata,
            'status': 'registered',
            'deployed_at': None
        }
        self._save_registry()
    
    def promote_to_production(self, version_id: str):
        """Mark model as production-ready"""
        pass
    
    def get_production_model(self) -> Dict:
        """Get currently deployed model"""
        pass
    
    def rollback_to_previous(self):
        """Rollback to last good model"""
        pass
```

3. **`retraining/model_validator.py`** (~250 lines)
```python
from river.metrics import MAE, RMSE, R2
import pandas as pd

class ModelValidator:
    """Validate new model before deployment"""
    
    def validate_new_model(
        self, 
        new_model_path: str,
        current_model_path: str,
        test_data_path: str
    ) -> Dict:
        """
        Compare new model vs current production model
        
        Returns:
            {
                'new_model_mae': float,
                'current_model_mae': float,
                'improvement_pct': float,
                'recommendation': 'deploy' | 'reject',
                'reason': str
            }
        """
        # Load both models
        # Run on same test set
        # Compare metrics
        # Decide deployment
        pass
    
    def run_safety_checks(self, model_path: str) -> Dict:
        """
        Ensure model won't crash in production
        - Can load successfully
        - Prediction time < 100ms
        - Handles missing features
        - No NaN predictions
        """
        pass
```

---

### Phase 3C: Self-Healing Orchestrator (Week 3)
**Goal**: Tie everything together in a continuous loop

#### What You'll Build:
```
orchestrator/
├── self_healing_loop.py    # NEW: Main orchestration logic
├── scheduler.py            # NEW: APScheduler integration
└── health_manager.py       # NEW: Overall system health
```

**The Self-Healing Loop** (Runs every 6 hours):
```
┌─────────────────────────────────────────────┐
│  1. Collect Metrics                         │
│     - Fetch last 200 predictions            │
│     - Calculate MAE, R², RMSE               │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  2. Check for Drift                         │
│     - Compare to training distribution      │
│     - Calculate drift scores                │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  3. Evaluate Health                         │
│     - MAE > 15? → Degraded                  │
│     - Drift > 0.5? → High Drift             │
│     - Both OK? → Healthy                    │
└─────────────────┬───────────────────────────┘
                  ↓
        ┌─────────┴─────────┐
        │  Healthy?          │
        └─────────┬─────────┘
           NO ←   │   → YES
            │     │          │
            ↓     ↓          ↓
    ┌─────────────────┐  ┌──────────────┐
    │ 4. Auto-Retrain │  │ 5. Continue  │
    │                 │  │    Monitoring│
    │ - Pull data     │  └──────────────┘
    │ - Train model   │
    │ - Validate      │
    │ - Deploy if ✓   │
    └─────────────────┘
            │
            ↓
    ┌─────────────────┐
    │ 6. Verify Fix   │
    │ - Wait 2 hours  │
    │ - Re-check MAE  │
    │ - Rollback if ✗ │
    └─────────────────┘
```

**Files to Create**:

1. **`orchestrator/self_healing_loop.py`** (~500 lines)
```python
from monitoring.drift_detector import DriftDetector
from retraining.auto_trainer import AutoTrainer
from api.monitoring import PerformanceMonitor
import schedule
import time

class SelfHealingOrchestrator:
    """Main orchestrator for self-healing ML system"""
    
    def __init__(self):
        self.drift_detector = DriftDetector()
        self.auto_trainer = AutoTrainer()
        self.perf_monitor = PerformanceMonitor()
        self.healing_in_progress = False
    
    def run_health_check(self):
        """
        Complete health check cycle
        Returns: Health report with actions taken
        """
        report = {
            'timestamp': datetime.now(),
            'status': 'healthy',
            'actions_taken': []
        }
        
        # 1. Check performance
        metrics = self.perf_monitor.get_recent_metrics(window=200)
        if metrics['mae'] > 15.0:
            report['status'] = 'degraded'
            report['issues'] = ['High MAE']
        
        # 2. Check drift
        drift_report = self.drift_detector.check_drift()
        if drift_report['overall_score'] > 0.5:
            report['status'] = 'drifted'
            report['issues'].append('Data drift detected')
        
        # 3. Trigger healing if needed
        if report['status'] != 'healthy':
            self._initiate_healing(report)
        
        return report
    
    def _initiate_healing(self, health_report: Dict):
        """
        Start automatic healing process
        """
        if self.healing_in_progress:
            logger.warning("Healing already in progress, skipping")
            return
        
        self.healing_in_progress = True
        
        try:
            # 1. Trigger retraining
            logger.info("Starting automatic retraining...")
            retrain_result = self.auto_trainer.retrain_and_validate()
            
            # 2. Deploy if successful
            if retrain_result['recommendation'] == 'deploy':
                self._deploy_new_model(retrain_result['model_path'])
                health_report['actions_taken'].append('Deployed new model')
            else:
                logger.warning(f"Retraining failed: {retrain_result['reason']}")
                health_report['actions_taken'].append('Retraining attempted but rejected')
        
        finally:
            self.healing_in_progress = False
    
    def start_continuous_monitoring(self):
        """
        Run health checks every 6 hours
        """
        schedule.every(6).hours.do(self.run_health_check)
        
        logger.info("Self-healing loop started. Checking every 6 hours...")
        while True:
            schedule.run_pending()
            time.sleep(60)
```

---

## 📝 Implementation Checklist

### Week 1: Drift Detection
- [ ] Create `monitoring/drift_detector.py`
- [ ] Create `monitoring/drift_config.yaml`
- [ ] Calculate baseline statistics from training data
- [ ] Test drift detection with synthetic drifted data
- [ ] Add drift endpoint to API: `GET /monitoring/drift`
- [ ] Create drift visualization dashboard
- [ ] Test with real production data

### Week 2: Auto-Retraining
- [ ] Create `retraining/auto_trainer.py`
- [ ] Create `retraining/model_validator.py`
- [ ] Create `retraining/model_registry.py`
- [ ] Create `retraining/retraining_policy.yaml`
- [ ] Test retraining trigger logic
- [ ] Test model validation (new vs old comparison)
- [ ] Test model registration and versioning
- [ ] Add API endpoint: `POST /retrain/trigger`
- [ ] Add API endpoint: `GET /retrain/status`

### Week 3: Self-Healing Loop
- [ ] Create `orchestrator/self_healing_loop.py`
- [ ] Integrate drift detection + auto-retraining
- [ ] Add APScheduler for 6-hour checks
- [ ] Add rollback mechanism
- [ ] Test complete healing cycle manually
- [ ] Run 48-hour test with automated triggers
- [ ] Add logging/alerting for all healing actions
- [ ] Create self-healing dashboard

### Week 4: Production Hardening
- [ ] Add model A/B testing capability
- [ ] Add gradual rollout (canary deployment)
- [ ] Add automated rollback on failure
- [ ] Add comprehensive error handling
- [ ] Add retry logic for failed retraining
- [ ] Add circuit breaker for repeated failures
- [ ] Load testing with 1000 req/s
- [ ] Documentation and runbooks

---

## 🎨 New API Endpoints to Create

```python
# Drift Detection
GET  /monitoring/drift                    # Current drift status
GET  /monitoring/drift/history            # Drift over time
POST /monitoring/drift/reset-baseline     # Update baseline stats

# Retraining Control
POST /retrain/trigger                     # Manual trigger
GET  /retrain/status                      # Current retraining job
GET  /retrain/history                     # Past retraining jobs
POST /retrain/rollback                    # Rollback to previous model

# Model Registry
GET  /models/list                         # All registered models
GET  /models/{version_id}                 # Model details
GET  /models/production                   # Current prod model
POST /models/{version_id}/promote         # Promote to production

# Self-Healing Status
GET  /health/system                       # Overall system health
GET  /health/healing-history              # Past healing actions
POST /health/manual-heal                  # Force healing cycle
```

---

## 🔧 Configuration Files Needed

### 1. `retraining/retraining_policy.yaml`
```yaml
retraining:
  triggers:
    performance_degradation:
      enabled: true
      mae_threshold: 15.0
      r2_threshold: 0.75
    
    drift_detection:
      enabled: true
      drift_score_threshold: 0.5
    
    scheduled:
      enabled: true
      frequency: "weekly"  # weekly, daily, monthly
      day: "sunday"
      time: "02:00"
  
  validation:
    minimum_improvement: 0.05  # 5% improvement required
    test_data_size: 0.2
    validation_metrics:
      - mae
      - r2
      - rmse
  
  deployment:
    strategy: "immediate"  # immediate, canary, blue-green
    rollback_on_degradation: true
    monitoring_period_hours: 24

  data:
    min_samples_required: 1000
    max_age_days: 30  # Only use data from last 30 days
    include_recent_predictions: true
```

---

## 🚀 Quick Start (After Reading This)

### Step 1: Test Current Monitoring
```bash
# Make some predictions
curl http://localhost:8000/forecast

# Check monitoring
curl http://localhost:8000/monitoring/summary

# Update actuals
curl -X POST http://localhost:8000/monitoring/update-actuals
```

### Step 2: Start Drift Detection Implementation
```bash
# Create new directories
mkdir -p monitoring retraining orchestrator

# Start with drift detector
touch monitoring/drift_detector.py
touch monitoring/drift_config.yaml

# Open in VS Code
code monitoring/drift_detector.py
```

### Step 3: Calculate Training Baseline
You'll need baseline statistics from your training data:
```python
# Run this once to generate baseline
python -c "
import pandas as pd
import json

# Load training data
df = pd.read_csv('dataset/preprocessed/train_data.csv')

# Calculate statistics for each feature
baseline = {}
for col in ['pm25', 'pm1', 'temperature', 'relativehumidity']:
    baseline[col] = {
        'mean': float(df[col].mean()),
        'std': float(df[col].std()),
        'min': float(df[col].min()),
        'max': float(df[col].max()),
        'q25': float(df[col].quantile(0.25)),
        'q50': float(df[col].quantile(0.50)),
        'q75': float(df[col].quantile(0.75))
    }

# Save baseline
with open('monitoring/baseline_stats.json', 'w') as f:
    json.dump(baseline, f, indent=2)

print('Baseline statistics saved!')
"
```

---

## 📊 Success Metrics

After implementation, you should achieve:

1. **Automated Detection** (Week 1)
   - Drift detected within 6 hours
   - Alert sent immediately
   - 95% detection accuracy

2. **Automated Healing** (Week 2)
   - Retraining triggered automatically
   - New model deployed within 2 hours
   - Performance restored to >90% R²

3. **Zero Manual Intervention** (Week 3)
   - Run system for 1 week without touching it
   - System should auto-heal from degradation
   - All actions logged and auditable

4. **Production Stability** (Week 4)
   - <5 minutes downtime during model swap
   - Rollback works if new model fails
   - 99.9% API uptime maintained

---

## 🎯 Why This Matters

**Current State**:
- Model performs well initially (93.2% R²)
- Performance degrades over time (concept drift)
- You manually notice and retrain
- Downtime during manual intervention

**After Self-Healing**:
- Model performs well initially (93.2% R²)
- Performance degrades over time (concept drift)
- **System automatically detects and fixes itself**
- **Zero manual intervention**
- **Continuous high performance**

This is the difference between:
- ❌ "ML model deployed in production"
- ✅ **"Self-healing MLOps system"**

---

## 📚 Learning Resources

### Drift Detection:
- [Evidently AI Docs](https://docs.evidentlyai.com/user-guide/tests-and-reports/data-drift)
- [NannyML Drift Detection](https://nannyml.readthedocs.io/en/stable/)
- [River Drift Detection](https://riverml.xyz/latest/api/drift/)

### Model Monitoring:
- [Seldon Alibi Detect](https://docs.seldon.io/projects/alibi-detect/)
- [WhyLabs](https://whylabs.ai/documentation)

### MLOps Best Practices:
- [Google MLOps Guide](https://cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning)
- [Microsoft MLOps Maturity Model](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/mlops-maturity-model)

---

## 🎬 Next Action

**Read this guide thoroughly**, then we'll start implementing in this order:

1. **Drift Detection** (Most Important)
   - Start with `drift_detector.py`
   - Generate baseline statistics
   - Test with production data

2. **Auto-Retraining**
   - Build `auto_trainer.py`
   - Add validation logic
   - Test manual trigger first

3. **Orchestration**
   - Connect all pieces
   - Add scheduling
   - Test complete loop

Ready to start? Let me know and I'll help you build the drift detector first! 🚀
