# Self-Healing Orchestrator - Comprehensive Learning Guide

## What is a Self-Healing Orchestrator?

A **Self-Healing Orchestrator** is the brain of an autonomous MLOps system. It continuously monitors model performance, detects when something goes wrong, and automatically fixes the problem by retraining, validating, and deploying better models—all without human intervention.

Think of it as an **autopilot for your ML system**:
- 🔍 **Monitors**: Watches for drift and degradation
- 🚨 **Detects**: Identifies when model needs updating
- 🔧 **Fixes**: Automatically trains and deploys better models
- 🛡️ **Protects**: Validates before deployment, rolls back if needed

---

## Why Do We Need Orchestration?

### Without Orchestrator: Manual Chaos

```
Drift detected → Email to ML engineer
                → Engineer notices (maybe tomorrow)
                → Manually runs training script
                → Manually validates model
                → Manually updates deployment
                → Model deployed (days later)
                → Problem: Drift already caused bad predictions
```

**Problems:**
- ⏰ **Slow response** - Hours or days to fix
- 😴 **Human delay** - People sleep, take vacations
- 🐛 **Manual errors** - Forgot validation step, deployed wrong model
- 📉 **Lost revenue** - Bad predictions during delay

### With Orchestrator: Automated Healing

```
Drift detected → Orchestrator triggers training (immediately)
              → New model trained (automated)
              → Validation (automated)
              → Registry promotion (automated)
              → Production deployment (automated)
              → Problem fixed (minutes, not days)
```

**Benefits:**
- ⚡ **Fast response** - Minutes to fix
- 🤖 **No human needed** - Runs 24/7
- ✅ **No errors** - Consistent workflow
- 💰 **No lost revenue** - Quick recovery

---

## Core Concepts

### 1. Orchestration vs Automation

| Automation | Orchestration |
|------------|---------------|
| Runs one task | Coordinates multiple tasks |
| Script to retrain model | Detect → Train → Validate → Deploy |
| "Do this" | "When this, then do that, then check, then..." |

**Example:**
- **Automation**: Script that retrains model when you run it
- **Orchestration**: System that detects drift, triggers training, validates result, promotes to production, monitors outcome

### 2. Event-Driven Architecture

The orchestrator responds to **events**:

```python
# Traditional (polling - wasteful)
while True:
    check_for_drift()  # Checks every minute even if no drift
    time.sleep(60)

# Event-driven (efficient)
monitor.on_drift_detected(lambda: orchestrator.handle_drift())
```

**Events in our system:**
- Drift detected (monitor.py)
- Training completed (auto_trainer.py)
- Validation finished (model_validator.py)
- Deployment succeeded/failed (API)

### 3. State Machine

The orchestrator is a **state machine** tracking workflow state:

```
IDLE ──drift──> TRAINING ──complete──> VALIDATING 
                   │                        │
                   │                        ├──approved──> PROMOTING
                   │                        │                  │
                   │                        │                  ├──success──> DEPLOYED ──> IDLE
                   │                        │                  │
                   │                        │                  └──failure──> ROLLBACK
                   │                        │
                   │                        └──rejected──> FAILED ──> IDLE
                   │
                   └──failed──> ERROR ──> IDLE
```

### 4. Workflow Stages

Our self-healing workflow has **6 stages**:

1. **Monitoring** - Continuously check for drift
2. **Detection** - Drift threshold exceeded
3. **Training** - Auto-trainer creates new model
4. **Validation** - Validator compares new vs current
5. **Promotion** - Registry manages deployment
6. **Deployment** - API loads new model

---

## The Self-Healing Workflow

### Step-by-Step Example

**Scenario:** PM2.5 predictions are drifting

#### Stage 1: Monitoring (Continuous)

```python
# monitor.py runs continuously
drift_detector.check()
# PSI score: 0.15 (below 0.25 threshold) ✅
# PSI score: 0.18 (still good) ✅
# PSI score: 0.28 (ALERT! Above 0.25) 🚨
```

**Output:** Drift detected event

#### Stage 2: Detection (Immediate)

```python
orchestrator.on_drift_detected(drift_info)
# drift_info = {
#     'psi_score': 0.28,
#     'threshold': 0.25,
#     'feature': 'pm25',
#     'detected_at': '2026-01-07T10:30:00'
# }
```

**Decision:** Should we retrain?
- ✅ PSI > 0.25 (YES)
- ✅ Last retrain > 24h ago (YES)
- ✅ Not currently training (YES)

**Action:** Trigger training

#### Stage 3: Training (10-20 minutes)

```python
orchestrator.trigger_training()
# → auto_trainer.train_model()
# → Creates model_20260107_103045
# → Training complete: MAE=6.5, R²=0.94
```

**Output:** New model available

#### Stage 4: Validation (1-2 minutes)

```python
orchestrator.validate_model('model_20260107_103045')
# → validator.validate(new='model_20260107_103045', 
#                      current='model_20260106_180235')
#
# Results:
# Current: MAE=6.82, R²=0.93
# New:     MAE=6.50, R²=0.94
# 
# MAE improved: 4.7% (> 5% threshold) ✅
# R² improved: 0.01 (< 0.02 threshold) ❌
```

**Decision:** Should we promote?
- ✅ MAE better by 4.7%
- ❌ R² only 0.01 better (need 0.02)

**Result:** MARGINAL (small improvement)

**Action:** Don't promote automatically, notify human

#### Alternative: Approved Model

If validation returned APPROVE:

```python
# Results:
# Current: MAE=6.82, R²=0.93
# New:     MAE=6.20, R²=0.95
# 
# MAE improved: 9.1% (> 5% threshold) ✅
# R² improved: 0.02 (>= 0.02 threshold) ✅
```

**Decision:** APPROVE ✅

**Action:** Promote to production

#### Stage 5: Promotion (1 second)

```python
orchestrator.promote_model('model_20260107_103045')
# → registry.promote_to_staging(model_id, validation_result)
# → registry.promote_to_production(model_id)
# 
# Old production (model_20260106_180235) → archived
# New production (model_20260107_103045) → active
```

**Output:** New model in registry as production

#### Stage 6: Deployment (5-10 seconds)

```python
orchestrator.deploy_model('model_20260107_103045')
# → API reloads model
# → Health check passes
# → Traffic switches to new model
```

**Output:** New model serving predictions

#### Stage 7: Post-Deployment Monitoring (24 hours)

```python
orchestrator.monitor_deployment('model_20260107_103045')
# Watch for:
# - Error rate increase
# - Latency increase
# - Metric degradation
#
# If problems detected → ROLLBACK
# If stable for 24h → SUCCESS
```

---

## Orchestrator Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│                  Self-Healing Orchestrator              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Drift      │  │   Training   │  │  Validation  │ │
│  │   Monitor    │  │   Manager    │  │   Manager    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│          │                 │                 │          │
│          └─────────────────┴─────────────────┘          │
│                          │                              │
│                  ┌───────┴────────┐                     │
│                  │  Orchestrator  │                     │
│                  │  Core Engine   │                     │
│                  └───────┬────────┘                     │
│                          │                              │
│          ┌───────────────┼────────────────┐            │
│          │               │                │            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Registry    │  │  Deployment  │  │  Rollback    │ │
│  │  Manager     │  │  Manager     │  │  Manager     │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                         │
└─────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
    monitor.py    auto_trainer.py  model_validator.py  model_registry.py
         │              │              │              │
         ▼              ▼              ▼              ▼
    dataset/       training/       training/       training/
```

### Class Structure

```python
class SelfHealingOrchestrator:
    def __init__(self):
        self.monitor = DriftMonitor()
        self.trainer = AutoTrainer()
        self.validator = ModelValidator()
        self.registry = ModelRegistry()
        self.state = "IDLE"
        self.current_workflow = None
    
    # Main workflow
    def handle_drift(self, drift_info)
    def train_new_model(self)
    def validate_new_model(self, new_model_id)
    def promote_model(self, model_id)
    def deploy_model(self, model_id)
    
    # Monitoring
    def monitor_production(self)
    def check_deployment_health(self, model_id)
    
    # Recovery
    def rollback(self, reason)
    def handle_failure(self, stage, error)
    
    # State management
    def set_state(self, new_state)
    def get_workflow_status(self)
```

---

## Decision Trees

### 1. Should We Retrain?

```
Drift Detected
    │
    ├─ PSI score > threshold (0.25)?
    │   │
    │   NO → Continue monitoring
    │   │
    │   YES → ├─ Last retrain < 24h ago?
    │           │
    │           YES → Skip (too soon), log alert
    │           │
    │           NO → ├─ Currently training?
    │                   │
    │                   YES → Skip (already training)
    │                   │
    │                   NO → ✅ TRIGGER TRAINING
```

### 2. Should We Promote?

```
Validation Complete
    │
    ├─ Decision = APPROVE?
    │   │
    │   YES → ✅ PROMOTE TO PRODUCTION
    │   │
    │   NO → ├─ Decision = MARGINAL?
    │           │
    │           YES → ├─ Auto-promote enabled?
    │           │       │
    │           │       YES → ⚠️  PROMOTE WITH WARNING
    │           │       │
    │           │       NO → 📧 NOTIFY HUMAN
    │           │
    │           NO → ❌ DON'T PROMOTE (log rejection)
```

### 3. Should We Rollback?

```
Production Monitoring
    │
    ├─ Error rate > baseline + 20%?
    │   │
    │   YES → 🚨 IMMEDIATE ROLLBACK
    │   │
    │   NO → ├─ MAE degraded > 10%?
    │           │
    │           YES → 🚨 IMMEDIATE ROLLBACK
    │           │
    │           NO → ├─ Latency > 2x baseline?
    │                   │
    │                   YES → ⚠️  GRADUAL ROLLBACK
    │                   │
    │                   NO → ✅ CONTINUE MONITORING
```

---

## Configuration

### Orchestrator Config

```python
orchestrator_config = {
    # Drift thresholds
    'drift_threshold': 0.25,          # PSI threshold
    'drift_check_interval': 3600,     # Check every hour
    
    # Training controls
    'min_retrain_interval': 86400,    # 24 hours
    'max_concurrent_trainings': 1,
    'training_timeout': 3600,         # 1 hour
    
    # Validation thresholds
    'mae_improvement_threshold': 0.05,  # 5% better
    'r2_improvement_threshold': 0.02,   # 0.02 absolute
    'auto_promote_marginal': False,     # Require human approval
    
    # Deployment
    'deployment_health_check': True,
    'health_check_retries': 3,
    'deployment_timeout': 60,
    
    # Monitoring
    'post_deployment_monitoring': 24,    # 24 hours
    'error_rate_threshold': 1.2,         # 20% increase
    'mae_degradation_threshold': 1.1,    # 10% degradation
    
    # Rollback
    'auto_rollback': True,
    'rollback_on_errors': True,
    'rollback_on_degradation': True,
    
    # Notifications
    'slack_webhook': 'https://...',
    'email_alerts': ['team@company.com'],
    'alert_on_drift': True,
    'alert_on_training': True,
    'alert_on_promotion': True,
    'alert_on_rollback': True
}
```

---

## Error Handling

### Training Failure

```python
try:
    model_id = trainer.train_model()
except TrainingError as e:
    orchestrator.handle_failure('training', e)
    # Actions:
    # 1. Log error with full context
    # 2. Alert team
    # 3. Return to IDLE (keep current model)
    # 4. Retry after cooldown (6 hours)
```

### Validation Failure

```python
try:
    result = validator.validate(new_model, current_model)
except ValidationError as e:
    orchestrator.handle_failure('validation', e)
    # Actions:
    # 1. Log error
    # 2. Mark model as failed in registry
    # 3. Keep current production model
    # 4. Alert team
```

### Deployment Failure

```python
try:
    orchestrator.deploy_model(model_id)
except DeploymentError as e:
    orchestrator.handle_failure('deployment', e)
    # Actions:
    # 1. Immediate rollback to previous model
    # 2. Mark new model as failed
    # 3. Alert team (high priority)
    # 4. Health check current model
```

---

## Monitoring & Alerting

### What to Monitor

**1. Workflow Health:**
- Drift check frequency (should be hourly)
- Training success rate (>95%)
- Validation success rate (>98%)
- Deployment success rate (>99%)

**2. Model Performance:**
- Production MAE (should be <15)
- Production R² (should be >0.80)
- Prediction latency (<100ms)
- Error rate (<1%)

**3. Orchestrator Health:**
- State transitions (should not get stuck)
- Memory usage (avoid leaks)
- CPU usage (should be low when idle)
- Workflow queue length (should be 0-1)

### When to Alert

**🔴 Critical (Immediate):**
- Deployment failure
- Rollback triggered
- Error rate spike (>20%)
- Orchestrator crashed

**🟡 Warning (15 minutes):**
- Training failure
- Validation rejected model
- Drift detected but can't retrain
- Health check failed

**🟢 Info (Daily digest):**
- Drift detected, training started
- New model promoted
- Validation approved
- System healthy

---

## Testing Strategy

### Unit Tests

```python
def test_drift_detection():
    """Test orchestrator responds to drift."""
    orchestrator = SelfHealingOrchestrator()
    
    # Simulate drift
    drift_info = {'psi_score': 0.30, 'threshold': 0.25}
    
    # Should trigger training
    orchestrator.handle_drift(drift_info)
    
    assert orchestrator.state == 'TRAINING'
    assert orchestrator.current_workflow is not None

def test_validation_approval():
    """Test promotion after approval."""
    orchestrator = SelfHealingOrchestrator()
    
    # Mock validation result
    result = {'decision': 'APPROVE', 'new_metrics': {...}}
    
    # Should promote
    orchestrator.handle_validation_result('model_123', result)
    
    prod = orchestrator.registry.get_production()
    assert prod['model_id'] == 'model_123'
```

### Integration Tests

```python
def test_end_to_end_workflow():
    """Test complete drift → deployment workflow."""
    orchestrator = SelfHealingOrchestrator()
    
    # 1. Trigger drift
    orchestrator.handle_drift({'psi_score': 0.30})
    
    # 2. Wait for training (mock)
    orchestrator.state = 'VALIDATING'
    
    # 3. Validation approves
    orchestrator.handle_validation_result('model_new', {
        'decision': 'APPROVE'
    })
    
    # 4. Check promotion
    assert orchestrator.registry.get_production()['model_id'] == 'model_new'
```

### Chaos Tests

```python
def test_training_failure_recovery():
    """Test recovery from training failure."""
    orchestrator = SelfHealingOrchestrator()
    
    # Inject training failure
    with mock.patch.object(trainer, 'train_model', side_effect=Exception):
        orchestrator.handle_drift({'psi_score': 0.30})
    
    # Should recover to IDLE
    assert orchestrator.state == 'IDLE'
    assert orchestrator.current_workflow is None

def test_deployment_rollback():
    """Test automatic rollback on deployment failure."""
    orchestrator = SelfHealingOrchestrator()
    
    previous_prod = orchestrator.registry.get_production()['model_id']
    
    # Inject deployment failure
    with mock.patch.object(api, 'reload_model', side_effect=Exception):
        orchestrator.deploy_model('model_new')
    
    # Should rollback
    current_prod = orchestrator.registry.get_production()['model_id']
    assert current_prod == previous_prod
```

---

## Best Practices

### 1. Graceful Degradation

```python
# ✅ GOOD - Fail safely
try:
    orchestrator.deploy_model(new_model)
except Exception as e:
    logger.error(f"Deployment failed: {e}")
    orchestrator.rollback()  # Keep system working
    orchestrator.alert_team(e)

# ❌ BAD - Crash entire system
orchestrator.deploy_model(new_model)  # No error handling!
```

### 2. Idempotency

```python
# ✅ GOOD - Can retry safely
def promote_model(self, model_id):
    if self.registry.get_production()['model_id'] == model_id:
        logger.info(f"{model_id} already in production")
        return  # Safe to retry
    
    self.registry.promote_to_production(model_id)

# ❌ BAD - Can't retry
def promote_model(self, model_id):
    self.registry.promote_to_production(model_id)  # Crashes if already promoted
```

### 3. State Tracking

```python
# ✅ GOOD - Always know state
orchestrator.set_state('TRAINING')
try:
    train()
    orchestrator.set_state('VALIDATING')
except Exception as e:
    orchestrator.set_state('ERROR')
    orchestrator.handle_failure(e)

# ❌ BAD - State gets out of sync
train()  # If this fails, state is wrong
orchestrator.state = 'VALIDATING'
```

### 4. Observability

```python
# ✅ GOOD - Rich logging
logger.info(f"Starting training", extra={
    'workflow_id': workflow_id,
    'trigger': 'drift_detected',
    'drift_score': 0.30,
    'previous_model': prev_model
})

# ❌ BAD - No context
logger.info("Training started")
```

---

## Production Deployment

### Running the Orchestrator

**Option 1: Systemd Service (Linux)**

```bash
# /etc/systemd/system/self-healing-orchestrator.service
[Unit]
Description=Self-Healing ML Orchestrator
After=network.target

[Service]
Type=simple
User=mlops
WorkingDirectory=/home/mlops/Self Healing MLOps
ExecStart=/usr/bin/python3 training/self_healing_orchestrator.py --daemon
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable self-healing-orchestrator
sudo systemctl start self-healing-orchestrator
sudo systemctl status self-healing-orchestrator
```

**Option 2: Docker Container**

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "training/self_healing_orchestrator.py", "--daemon"]
```

```bash
docker build -t self-healing-orchestrator .
docker run -d --name orchestrator self-healing-orchestrator
```

**Option 3: Kubernetes CronJob**

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: drift-checker
spec:
  schedule: "0 * * * *"  # Every hour
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: orchestrator
            image: self-healing-orchestrator:latest
            command: ["python", "training/self_healing_orchestrator.py", "--check-drift"]
```

---

## Integration Examples

### With FastAPI

```python
from fastapi import FastAPI
from self_healing_orchestrator import SelfHealingOrchestrator

app = FastAPI()
orchestrator = SelfHealingOrchestrator()

@app.post("/orchestrator/trigger-training")
def trigger_training():
    """Manually trigger training."""
    orchestrator.handle_drift({'manual_trigger': True})
    return {"status": "training started"}

@app.get("/orchestrator/status")
def get_status():
    """Get orchestrator status."""
    return {
        "state": orchestrator.state,
        "workflow": orchestrator.get_workflow_status(),
        "production_model": orchestrator.registry.get_production()
    }

@app.post("/orchestrator/rollback")
def emergency_rollback():
    """Emergency rollback."""
    orchestrator.rollback("Manual emergency rollback")
    return {"status": "rolled back"}
```

### With Monitoring Dashboard

```python
@app.get("/orchestrator/metrics")
def get_metrics():
    """Prometheus-compatible metrics."""
    metrics = orchestrator.get_metrics()
    return {
        "drift_checks_total": metrics['drift_checks'],
        "trainings_total": metrics['trainings'],
        "trainings_success_rate": metrics['training_success_rate'],
        "validations_total": metrics['validations'],
        "deployments_total": metrics['deployments'],
        "rollbacks_total": metrics['rollbacks'],
        "current_state": orchestrator.state
    }
```

---

## Summary

The Self-Healing Orchestrator is the **control center** of your MLOps system:

✅ **Autonomous** - Runs 24/7 without human intervention  
✅ **Fast** - Responds to issues in minutes, not days  
✅ **Safe** - Validates before deployment, rolls back on failure  
✅ **Observable** - Rich logging and metrics  
✅ **Resilient** - Graceful error handling and recovery  

**Next:** Implement the orchestrator class and integrate all components!
