# Fallback Prediction System for AQI Forecasting

## Overview

This document explains the fallback prediction mechanism implemented in the AQI (Air Quality Index) forecasting system to ensure 100% prediction coverage across all hours of the day, particularly during midday hours when the Adaptive Random Forest (ARF) model may return uncertain predictions.

---

## Problem Statement

### Initial Issue
The ARF model was unable to predict AQI values for approximately 30% of samples, predominantly during midday hours (12:00-17:00). This resulted in:

- **Coverage gaps**: Only 132 out of 189 predictions (70% coverage)
- **Midday blind spots**: Only 16.7% coverage during 12:00-17:00 hours
- **Missing critical data**: Users couldn't monitor air quality during peak afternoon hours

### Root Cause Analysis

1. **Model Behavior**: The ARF model returns `NaN` (Not a Number) when it encounters feature combinations that are significantly different from its training distribution
   
2. **Midday Characteristics**: Afternoon hours have unique air quality patterns:
   - **Lower AQI values** (~90) compared to morning/evening (~180)
   - **Higher temperatures** (22-23°C vs 16-19°C)
   - **Lower humidity** (28-37% vs 40-46%)
   - **Different pollution dynamics** (cleaner air due to atmospheric mixing)

3. **Model Uncertainty**: When the ARF model encounters these atypical feature combinations, it conservatively returns `NaN` rather than making unreliable predictions

---

## Solution: Fallback Prediction Mechanism

### What is Fallback Prediction?

A **fallback prediction** is a simple, robust baseline method that provides reasonable estimates when the primary model (ARF) is uncertain or unable to generate predictions. It acts as a safety net to ensure continuous monitoring capability.

### Fallback Strategy: Persistence Model

We implemented a **persistence model** as our fallback mechanism, which operates on the principle:

```
Current AQI ≈ Previous Hour's Actual AQI
```

This is based on the meteorological principle of **temporal continuity** - air quality tends to change gradually rather than abruptly (except during sudden events like traffic rushes or weather changes).

---

## Implementation Details

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Input: Preprocessed Features              │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Adaptive Random Forest Model                   │
│              (Primary Predictor)                            │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │  Prediction   │
                    │  Valid?       │
                    └───────┬───────┘
                            │
                ┌───────────┴───────────┐
                │                       │
            ✅ YES                    ❌ NO (NaN)
                │                       │
                ▼                       ▼
    ┌─────────────────────┐   ┌─────────────────────┐
    │  Use ARF            │   │  Fallback:          │
    │  Prediction         │   │  Use Previous Hour  │
    │                     │   │  Actual AQI         │
    └─────────────────────┘   └─────────────────────┘
                │                       │
                └───────────┬───────────┘
                            │
                            ▼
                ┌─────────────────────┐
                │  Final Prediction   │
                └─────────────────────┘
```

### Code Implementation

The fallback mechanism is implemented in `training/evaluate_today.py` within the `make_predictions()` method:

```python
# Track predictions and fallbacks
predictions = []
actuals = []
timestamps = []
location_ids = []
fallback_count = 0
model_none_count = 0

for idx, row in df_processed.iterrows():
    # Prepare features
    features = {col: row[col] for col in feature_cols}
    
    # Make prediction with ARF model
    y_pred = self.model.predict_one(features)
    y_true = row['aqi']
    
    # Check if model returned None or NaN (uncertain prediction)
    if y_pred is None or (isinstance(y_pred, (int, float)) and pd.isna(y_pred)):
        model_none_count += 1
        
        # FALLBACK: Use persistence model
        # Find most recent actual AQI for same location
        loc_id = row['location_id']
        if len(actuals) > 0 and len(location_ids) > 0:
            for i in range(len(location_ids) - 1, -1, -1):
                if location_ids[i] == loc_id:
                    y_pred = actuals[i]  # Use previous actual AQI
                    fallback_count += 1
                    break
        
        # If no previous value found, skip this prediction
        if y_pred is None or (isinstance(y_pred, (int, float)) and pd.isna(y_pred)):
            continue
    
    # Store valid prediction
    if y_pred is not None and not pd.isna(y_true):
        predictions.append(y_pred)
        actuals.append(y_true)
        timestamps.append(row['datetime'])
        location_ids.append(row['location_id'])

print(f"✅ Generated {len(predictions)} predictions")
print(f"📊 Model returned None: {model_none_count} times")
if fallback_count > 0:
    print(f"📊 Used fallback prediction for {fallback_count} samples ({fallback_count/len(predictions)*100:.1f}%)")
```

### Key Implementation Features

1. **Per-Location Tracking**: Fallback predictions use the previous hour's AQI for the **same location**, not globally, ensuring spatial accuracy

2. **Graceful Degradation**: System continues operating even when ARF model is uncertain, maintaining user trust

3. **Transparency**: System logs when fallback predictions are used, allowing for quality monitoring

4. **No External Dependencies**: Uses already-collected actual AQI values, no additional data sources needed

---

## Performance Results

### Before Fallback Implementation

| Time Period | Coverage | MAE (when available) |
|-------------|----------|---------------------|
| Night (00-05) | 100% | ~5.5 |
| Morning (06-11) | 96.3% | ~6.0 |
| **Midday (12-17)** | **16.7%** | N/A |
| Evening (18-23) | 63.0% | ~7.0 |
| **Overall** | **70%** | **~7.0** |

### After Fallback Implementation

| Time Period | Coverage | MAE | Notes |
|-------------|----------|-----|-------|
| Night (00-05) | 100% | 9.94 | Mostly ARF predictions |
| Morning (06-11) | 100% | 5.80 | Mostly ARF predictions |
| **Midday (12-17)** | **100%** | **26.17** | **~80% fallback predictions** |
| Evening (18-23) | 100% | 14.46 | Mixed ARF + fallback |
| **Overall** | **100%** | **14.04** | **30% fallback** |

### Key Metrics

- **Total Predictions**: 189/189 (100% coverage)
- **Overall MAE**: 14.04 AQI points
- **Overall MAPE**: 8.76%
- **Fallback Usage**: 57/189 samples (30.2%)
- **R² Score**: 0.281

### Accuracy Analysis

**Midday Predictions (Location 6093550 Example):**

| Time | Actual AQI | Predicted AQI | Error | Error % |
|------|-----------|---------------|-------|---------|
| 12:45 | 88.2 | 169.4 | 81.2 | 92.1% |
| 13:45 | 93.0 | 88.2 | 4.8 | 5.1% |
| 14:45 | 89.4 | 93.0 | 3.5 | 3.9% |
| 15:45 | 94.1 | 89.4 | 4.7 | 5.0% |
| 16:45 | 109.3 | 94.1 | 15.2 | 13.9% |
| 17:45 | 133.2 | 109.3 | 23.9 | 17.9% |

**Observations:**
- First fallback prediction (12:45) has high error due to using morning AQI
- Subsequent predictions improve as fallback "catches up" to midday patterns
- Average midday error acceptable for monitoring purposes

---

## Configuration Changes

### ARF Model Optimization

To reduce reliance on fallback, we optimized the ARF model configuration in `training/training.py`:

```python
self.model = forest.ARFRegressor(
    n_models=10,                      # Number of trees in ensemble
    seed=seed,
    drift_detector=drift.ADWIN(delta=0.01),     # Increased from 0.002 (less conservative)
    warning_detector=drift.ADWIN(delta=0.05),   # Added warning detector
    grace_period=25,                  # Reduced from 50 (earlier predictions)
    lambda_value=6,                   # Poisson bagging parameter
    max_features='sqrt',              # Feature sampling strategy
    aggregation_method='median',      # Robust aggregation
    disable_weighted_vote=True,       # Simpler prediction behavior
    leaf_prediction='adaptive',       # Adaptive leaf models
    min_samples_split=5               # Minimum samples for split
)
```

**Key Changes:**
- `grace_period`: 50 → 25 (model makes predictions with less warm-up data)
- `drift_detector delta`: 0.002 → 0.01 (more adaptive to changing patterns)
- Added `warning_detector` for early drift detection
- `aggregation_method`: 'median' for robustness against outliers

---

## Trade-offs and Considerations

### Advantages

1. **Complete Coverage**: 100% prediction availability ensures continuous monitoring
2. **Operational Reliability**: System never fails to provide estimates
3. **Simple Implementation**: No complex fallback models or additional infrastructure
4. **Low Latency**: Persistence model has zero computation overhead
5. **Interpretability**: Users can understand why fallback predictions may lag reality

### Disadvantages

1. **Higher MAE**: Overall error increases from ~7 to 14 AQI points
2. **Midday Accuracy**: Fallback predictions less accurate during pattern changes
3. **Lag Effect**: Persistence model always lags by 1 hour
4. **First Prediction Issue**: No fallback available for first hour of monitoring

### When Fallback is Acceptable

Fallback predictions are suitable when:
- **Monitoring > Precision**: Continuous awareness more valuable than perfect accuracy
- **Trend Detection**: Changes over multiple hours more important than exact values
- **Alerting**: Triggering warnings when AQI exceeds thresholds
- **Data Logging**: Maintaining complete historical records

### When ARF Should Be Improved

Consider retraining ARF or using alternative models when:
- Fallback usage exceeds 40-50%
- Midday MAE consistently >30 AQI points
- Critical decisions depend on midday accuracy
- Real-time interventions needed

---

## Future Improvements

### Short-term

1. **Weighted Fallback**: Use exponential moving average instead of simple persistence
   ```python
   y_pred = 0.7 * actuals[i] + 0.3 * actuals[i-1]
   ```

2. **Feature-based Fallback**: Use temperature/humidity to adjust persistence prediction
   ```python
   temp_adjustment = (current_temp - prev_temp) * scaling_factor
   y_pred = actuals[i] + temp_adjustment
   ```

3. **Confidence Scoring**: Mark fallback predictions with confidence flags for downstream use

### Long-term

1. **Ensemble Fallback**: Train a lightweight XGBoost model specifically for midday predictions
2. **Transfer Learning**: Use pre-trained models from similar locations/seasons
3. **Multi-model Voting**: Combine ARF + LSTM + Gradient Boosting with weighted voting
4. **Causal Models**: Incorporate meteorological forecasts for better midday prediction

---

## Usage

### Running Evaluation with Fallback

```bash
# Evaluate specific date
python training/evaluate_today.py --date 2025-12-15

# Evaluate today
python training/evaluate_today.py
```

### Output Interpretation

The evaluation output shows fallback usage:
```
✅ Generated 189 predictions
📊 Model returned None: 57 times
📊 Used fallback prediction for 57 samples (30.2%)
```

### Monitoring Fallback Performance

Check the evaluation CSV to identify fallback predictions:
```python
import pandas as pd

df = pd.read_csv('training/evaluations/2025_12_15/today_evaluation_*.csv')

# High residuals during midday may indicate fallback usage
midday = df[df['timestamp'].str.contains('12:|13:|14:|15:|16:|17:')]
print(f"Midday MAE: {midday['absolute_error'].mean():.2f}")
```

---

## Technical Details

### Why ARF Returns NaN

The Adaptive Random Forest may return `NaN` when:

1. **Leaf Node Emptiness**: Decision tree reaches a leaf with insufficient samples
2. **Feature Space Novelty**: Input features outside training distribution boundaries
3. **Drift Detection**: Recent concept drift triggered tree replacement
4. **Aggregation Failure**: All trees in ensemble return None/NaN

### Persistence Model Mathematics

The persistence model assumes temporal autocorrelation in time series:

```
P(AQI_t | AQI_{t-1}) ≈ AQI_{t-1}

where:
- AQI_t = AQI at current time
- AQI_{t-1} = AQI at previous time (1 hour ago)
- Assumption: Strong positive autocorrelation (ρ ≈ 0.8-0.9)
```

This works because air quality exhibits **temporal persistence** - pollutant concentrations don't change instantaneously.

---

## Related Files

- `training/evaluate_today.py` - Main evaluation script with fallback logic
- `training/training.py` - ARF model configuration
- `training/evaluations/README.md` - Evaluation system documentation
- `docs/TIME_SERIES_FEATURES_EXPLAINED.md` - Feature engineering details

---

## Conclusion

The fallback prediction mechanism successfully addresses the midday prediction gap in our AQI forecasting system. While it introduces a slight accuracy trade-off (MAE 14 vs 7), it ensures **100% operational availability**, which is critical for real-world air quality monitoring applications.

The system now provides:
- ✅ Complete 24-hour coverage
- ✅ Continuous monitoring capability
- ✅ Acceptable accuracy for alerting/trending
- ✅ Transparent fallback usage reporting

This implementation demonstrates a pragmatic approach to production ML systems: **prioritizing reliability and availability while maintaining acceptable accuracy levels**.

---

**Last Updated**: December 15, 2025  
**Authors**: Bipul Kumar Dahal  
**Version**: 1.0
