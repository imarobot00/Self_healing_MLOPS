# Model Evaluations

This directory contains organized evaluation results for the AQI prediction model.

## Directory Structure

```
evaluations/
├── README.md                    # This file
├── YYYY_MM_DD/                 # Evaluation for specific date
│   ├── today_evaluation_*.csv  # Prediction results with timestamps
│   ├── today_metrics_*.json    # Performance metrics
│   ├── today_predictions_vs_actual.png  # Time series visualization
│   ├── today_scatter.png       # Predicted vs Actual scatter plot
│   └── today_residuals.png     # Residual distribution
└── ...                         # More date folders
```

## Usage

### Evaluate Today's Data

```bash
python training/evaluate_today.py
```

This will:
- Load the latest trained model
- Fetch today's data from JSON files
- Make predictions and compare with actual values
- Save results in `evaluations/YYYY_MM_DD/` folder

### Evaluate Specific Date

```bash
python training/evaluate_today.py --date 2025-12-15
```

This allows you to:
- Re-evaluate past dates
- Compare model performance across different days
- Track model drift over time

### Example: Evaluate Last Week

```bash
# Evaluate each day of last week
python training/evaluate_today.py --date 2025-12-08
python training/evaluate_today.py --date 2025-12-09
python training/evaluate_today.py --date 2025-12-10
# ... and so on
```

## Output Files

### 1. CSV Results (`today_evaluation_*.csv`)
Contains detailed predictions for each location and timestamp:
- `timestamp`: When the prediction was made
- `location_id`: Sensor location identifier
- `actual_aqi`: Actual observed AQI
- `predicted_aqi`: Model's predicted AQI
- `residual`: Difference (actual - predicted)
- `absolute_error`: Absolute value of residual

### 2. Metrics JSON (`today_metrics_*.json`)
Performance metrics summary:
```json
{
  "date": "2025-12-15",
  "mae": 8.14,
  "rmse": 33.68,
  "r2": 0.085,
  "mape": 3.21,
  "samples": 189
}
```

### 3. Visualizations (PNG files)

**Time Series Plot** (`today_predictions_vs_actual.png`):
- Shows predicted vs actual AQI over time
- Helps identify patterns and trends
- Color-coded by AQI health categories

**Scatter Plot** (`today_scatter.png`):
- Predicted vs actual values
- Perfect prediction line (y=x)
- R² score and error statistics

**Residuals Plot** (`today_residuals.png`):
- Distribution of prediction errors
- Identifies systematic biases
- Normal distribution indicates good model

## Performance Interpretation

### MAE (Mean Absolute Error)
- **< 10 AQI points**: Excellent ✅
- **10-20 AQI points**: Good ⚠️
- **> 20 AQI points**: Needs improvement ❌

### MAPE (Mean Absolute Percentage Error)
- **< 5%**: Excellent ✅
- **5-10%**: Good ⚠️
- **> 10%**: Needs improvement ❌

### R² Score (Coefficient of Determination)
- **> 0.9**: Excellent ✅
- **0.7-0.9**: Good ⚠️
- **< 0.7**: Needs improvement ❌

## Monitoring Model Health

### Check for Drift
Compare MAE across different dates:
```bash
# Get MAE for multiple days
grep "mae" evaluations/2025_12_*/today_metrics_*.json
```

### Hourly Performance Analysis
Check CSV files to identify which hours have higher errors:
- Morning rush hours (7-9 AM) typically harder to predict
- Night hours (12-5 AM) usually more stable

## Example Workflow

1. **Daily Evaluation**
   ```bash
   # Run every day to monitor performance
   python training/evaluate_today.py
   ```

2. **Weekly Review**
   ```bash
   # Compare last 7 days
   ls -lh training/evaluations/
   ```

3. **Historical Analysis**
   ```bash
   # Re-evaluate a past date after model update
   python training/evaluate_today.py --date 2025-12-10
   ```

## Notes

- Each evaluation creates timestamped files to prevent overwrites
- Multiple evaluations on same date are stored separately
- Visualizations are regenerated each time for latest results
- The script automatically uses the most recent trained model

## Troubleshooting

**No data found for date:**
- Check if JSON files contain data for that date
- Verify date format is YYYY-MM-DD
- Ensure data has been fetched from OpenAQ

**Model file not found:**
- Train model first using `training/training.py`
- Check `training/models/` directory exists

**Poor performance:**
- Check if model needs retraining
- Verify preprocessing statistics are current
- Consider concept drift if recent performance degrades

---

**Last Updated**: December 15, 2025  
**Project**: Self-Healing MLOps - AQI Prediction
