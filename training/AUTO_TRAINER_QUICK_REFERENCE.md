# Auto-Trainer Quick Reference

## Usage

### Basic Check (Respects Cooldown)
```bash
python training/auto_trainer.py
```
- Checks drift score
- Only retrains if drift > 0.15 AND 24+ hours since last retrain
- Safe to run frequently

### Force Retrain (Bypass Cooldown)
```bash
python training/auto_trainer.py --force
```
- Ignores cooldown period
- Retrains immediately
- Use after major data updates

### Custom Drift Threshold
```bash
python training/auto_trainer.py --drift-threshold 0.20
```
- Default: 0.15 (balanced)
- Lower (0.10): More sensitive, retrain often
- Higher (0.20): Less sensitive, retrain rarely

### Custom Paths
```bash
python training/auto_trainer.py \
  --data-dir /path/to/data \
  --models-dir /path/to/models
```

## Output Interpretation

### Drift Check Results

**Scenario 1: No Retraining Needed**
```
Current drift score: 0.08 (threshold: 0.15)
✅ No retraining needed: Drift within acceptable range
```
→ Model performing well, no action needed

**Scenario 2: Drift Exceeded, But Too Soon**
```
Current drift score: 0.25 (threshold: 0.15)
Hours since last retrain: 8.5 (minimum: 24)
⏳ Drift exceeded but retraining too soon (wait 15.5 more hours)
```
→ Wait for cooldown to complete

**Scenario 3: Retraining Triggered**
```
Current drift score: 4.546 (threshold: 0.15)
✅ Retraining needed: Drift exceeded and time constraint met
🔄 STARTING AUTO-RETRAINING PIPELINE
```
→ Retraining in progress

### Training Progress

```
Progress: 50.0% | MAE: 8.34 | R²: 0.9147
```
- MAE: Mean Absolute Error (lower is better)
- R²: Coefficient of determination (higher is better, max 1.0)
- Target: MAE < 10, R² > 0.90

### Final Results

```
✅ TRAINING COMPLETE
   MAE:  6.82 AQI points
   RMSE: 11.30 AQI points
   R²:   0.9303
   Time: 37.1 seconds

✅ Model saved successfully: training/models/model_20260106_180235
```

## Performance Targets

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| MAE | < 10 AQI | 6.82 | ✅ Excellent |
| RMSE | < 15 AQI | 11.30 | ✅ Good |
| R² | > 0.90 | 0.9303 | ✅ Excellent |
| Training Time | < 60s | 37s | ✅ Fast |

## Troubleshooting

### Error: "No training data found"
**Cause**: Missing preprocessed CSV file  
**Solution**: Run data preprocessing first
```bash
cd dataset
python data_preprocessor.py
```

### Error: "Insufficient samples: X < 1000"
**Cause**: Not enough data for reliable training  
**Solution**: 
- Collect more data
- Lower min_samples threshold (not recommended)

### Error: "ModuleNotFoundError"
**Cause**: Missing dependencies  
**Solution**: Install requirements
```bash
pip install -r training/requirements.txt
pip install -r api/requirements.txt
```

### Warning: "Drift exceeded but too soon"
**Cause**: Trying to retrain within 24-hour cooldown  
**Solution**: 
- Wait for cooldown period, OR
- Use `--force` flag if urgent

### Low R² Score (< 0.85)
**Cause**: Poor model quality  
**Possible Reasons**:
1. Insufficient training data
2. Poor feature quality
3. High data noise
4. Data distribution shift

**Solution**:
1. Check data quality
2. Increase training samples
3. Review feature engineering
4. Consider different model parameters

## Integration Examples

### Cron Job (Every 6 Hours)
```bash
0 */6 * * * cd /path/to/project && python training/auto_trainer.py >> logs/auto_trainer.log 2>&1
```

### Python Script
```python
from training.auto_trainer import AutoTrainer

# Initialize
trainer = AutoTrainer(
    drift_threshold=0.15,
    min_samples=1000,
    min_hours_between_retrains=24
)

# Check if retraining needed
should_retrain, reasons = trainer.should_retrain()

if should_retrain:
    # Retrain
    success, model_path, info = trainer.retrain()
    
    if success:
        print(f"New model: {model_path}")
        print(f"MAE: {info['metrics']['mae']:.2f}")
    else:
        print(f"Error: {info['error']}")
```

### API Integration (Future)
```python
# In FastAPI endpoint
@app.post("/admin/trigger-retrain")
async def trigger_retrain(force: bool = False):
    trainer = AutoTrainer()
    retrained, model_path, info = trainer.run(force=force)
    
    return {
        "retrained": retrained,
        "model_path": str(model_path) if model_path else None,
        "info": info
    }
```

## File Locations

### Input Files
- Training data: `dataset/preprocessed/train_data.csv`
- Drift config: `monitoring/drift_config.yaml`
- Prediction logs: `api/logs/predictions/*.jsonl`

### Output Files
- Models: `training/models/model_YYYYMMDD_HHMMSS/`
  - `model.pkl` - Trained model
  - `feature_engineer.pkl` - Feature engineering pipeline
  - `metadata.json` - Training metadata

### Log Files
- Auto-trainer log: `logs/auto_trainer.log` (if using cron)
- Drift reports: `monitoring/reports/drift_report_*.json`

## Model Versioning

Models are automatically versioned with timestamp:
- Format: `model_YYYYMMDD_HHMMSS`
- Example: `model_20260106_180235` = Jan 6, 2026 at 18:02:35

### List All Models
```bash
ls -lt training/models/model_*
```

### View Model Metadata
```bash
cat training/models/model_20260106_180235/metadata.json | jq
```

### Load Specific Model
```python
import dill
with open('training/models/model_20260106_180235/model.pkl', 'rb') as f:
    model = dill.load(f)
```

## Best Practices

1. **Run regularly**: Set up cron job to check every 6-12 hours
2. **Monitor logs**: Review retraining logs weekly
3. **Track metrics**: Compare MAE/R² across model versions
4. **Validate before deploy**: Use Model Validator (Week 2 Day 2)
5. **Keep history**: Don't delete old models (for rollback)
6. **Alert on failures**: Set up notifications for training errors
7. **Test after retrain**: Run predictions to verify new model

## Quick Status Check

```bash
# Check drift without retraining
python training/auto_trainer.py 2>&1 | grep -E "(drift score|Decision)"

# View latest model info
ls -t training/models/model_*/metadata.json | head -1 | xargs cat | jq '.metrics'

# Count total models
ls -d training/models/model_* 2>/dev/null | wc -l
```

## Exit Codes

- `0`: Success (retrained or correctly decided not to)
- `1`: Error occurred during execution

---

**Status**: ✅ Production Ready  
**Version**: 1.0  
**Last Updated**: January 6, 2026
