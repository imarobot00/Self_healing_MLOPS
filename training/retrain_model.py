#!/usr/bin/env python3
"""
Retrain AQI Model on Latest Data
=================================

Retrains the Adaptive Random Forest model using the most recent data
from all locations with proper time series validation.
"""

import pandas as pd
import numpy as np
import json
import dill
from pathlib import Path
from datetime import datetime, timedelta
import sys
import logging
from river.forest import ARFRegressor
from river.drift import ADWIN
from river import metrics

# Setup paths
project_root = Path(__file__).parent.parent
dataset_dir = project_root / "dataset"
preprocessed_dir = dataset_dir / "preprocessed"
models_dir = Path(__file__).parent / "models"

sys.path.insert(0, str(preprocessed_dir))

# Import preprocessing
import importlib.util
spec = importlib.util.spec_from_file_location("preprocessing", preprocessed_dir / "preprocessing.py")
preprocessing_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preprocessing_module)
StreamingPreprocessor = preprocessing_module.StreamingPreprocessor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_and_parse_data():
    """Load all location data and parse OpenAQ format"""
    location_files = list(dataset_dir.glob("location_*.json"))
    
    logger.info(f"Found {len(location_files)} location files")
    
    all_records = []
    
    for file in location_files:
        location_id = int(file.stem.replace('location_', ''))
        logger.info(f"Loading {file.name}...")
        
        try:
            with open(file, 'r') as f:
                raw_data = json.load(f)
            
            # Parse OpenAQ format
            for item in raw_data:
                try:
                    record = {
                        'location_id': location_id,
                        'parameter': item['parameter']['name'],
                        'value': item['value'],
                        'datetime': item['period']['datetimeFrom']['utc']
                    }
                    all_records.append(record)
                except (KeyError, TypeError):
                    continue
        except Exception as e:
            logger.error(f"Error loading {file}: {e}")
            continue
    
    if not all_records:
        raise ValueError("No valid records found")
    
    logger.info(f"Loaded {len(all_records)} total records")
    
    # Convert to DataFrame
    df = pd.DataFrame(all_records)
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    # Pivot to get one row per datetime/location with all parameters
    df_pivot = df.pivot_table(
        index=['datetime', 'location_id'], 
        columns='parameter', 
        values='value', 
        aggfunc='mean'
    ).reset_index()
    df_pivot.columns.name = None
    
    # Ensure required columns
    required = ['pm25', 'pm1', 'temperature', 'relativehumidity', 'um003']
    for col in required:
        if col not in df_pivot.columns:
            df_pivot[col] = 0
    
    # Clean data
    df_pivot[required] = df_pivot[required].fillna(method='ffill').fillna(method='bfill').fillna(0)
    
    # Calculate AQI
    df_pivot['aqi'] = df_pivot['pm25'].apply(calculate_aqi)
    
    # Sort by time
    df_pivot = df_pivot.sort_values('datetime')
    
    # Extract datetime components for time features
    df_pivot['hour'] = df_pivot['datetime'].dt.hour
    df_pivot['day'] = df_pivot['datetime'].dt.day
    df_pivot['month'] = df_pivot['datetime'].dt.month
    df_pivot['day_of_week'] = df_pivot['datetime'].dt.dayofweek
    
    logger.info(f"Prepared {len(df_pivot)} records for training")
    logger.info(f"Date range: {df_pivot['datetime'].min()} to {df_pivot['datetime'].max()}")
    
    return df_pivot


def calculate_aqi(pm25):
    """Calculate AQI from PM2.5"""
    breakpoints = [
        (0, 12.0, 0, 50),
        (12.1, 35.4, 51, 100),
        (35.5, 55.4, 101, 150),
        (55.5, 150.4, 151, 200),
        (150.5, 250.4, 201, 300),
        (250.5, 500.4, 301, 500)
    ]
    
    for c_low, c_high, i_low, i_high in breakpoints:
        if c_low <= pm25 <= c_high:
            aqi = ((i_high - i_low) / (c_high - c_low)) * (pm25 - c_low) + i_low
            return aqi
    
    return 500 if pm25 > 500.4 else 0


def create_features_batch(df):
    """Create features for the entire dataset using preprocessor"""
    logger.info("Creating features with StreamingPreprocessor...")
    
    preprocessor = StreamingPreprocessor(
        target_column='aqi',
        lag_features=[1, 2, 3, 6, 12, 24],
        rolling_windows=[3, 6, 12, 24],
        normalize=True,
        handle_outliers=True
    )
    
    # Use prepare_for_streaming to process the entire dataset
    logger.info(f"Processing {len(df)} records...")
    df_features = preprocessor.prepare_for_streaming(df, fit=True)
    
    # Save preprocessing stats
    stats_path = preprocessed_dir / "preprocessor_stats.json"
    preprocessor.save_statistics(str(stats_path))
    logger.info(f"Saved preprocessor stats to {stats_path}")
    
    logger.info(f"Total records with features: {len(df_features)}")
    logger.info(f"Feature columns: {len(df_features.columns) - 1} (excluding target)")
    
    return df_features, preprocessor


def train_model_with_validation(df, test_size=0.2):
    """Train model with time series split validation"""
    
    # Remove rows with NaN in target or features
    df = df.dropna(subset=['aqi'])
    df = df.fillna(0)
    
    # Time series split - last 20% for testing
    split_idx = int(len(df) * (1 - test_size))
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    
    logger.info(f"Training set: {len(train_df)} samples")
    logger.info(f"Test set: {len(test_df)} samples")
    
    # Initialize model
    model = ARFRegressor(
        n_models=10,
        max_features='sqrt',
        leaf_prediction='adaptive',
        drift_detector=ADWIN(),
        seed=42
    )
    
    # Metrics
    train_mae = metrics.MAE()
    train_rmse = metrics.RMSE()
    train_r2 = metrics.R2()
    
    test_mae = metrics.MAE()
    test_rmse = metrics.RMSE()
    test_r2 = metrics.R2()
    
    # Training
    logger.info("Training model...")
    
    # Exclude datetime and other non-numeric columns
    exclude_cols = ['aqi', 'datetime', 'location_id']
    feature_cols = [col for col in train_df.columns if col not in exclude_cols]
    
    logger.info(f"Training with {len(feature_cols)} features")
    
    predictions_train = []
    actuals_train = []
    
    for idx, row in train_df.iterrows():
        features = {col: row[col] for col in feature_cols}
        target = row['aqi']
        
        # Make prediction before learning
        pred = model.predict_one(features)
        if pred is not None:
            train_mae.update(target, pred)
            train_rmse.update(target, pred)
            train_r2.update(target, pred)
            predictions_train.append(pred)
            actuals_train.append(target)
        
        # Learn from this sample
        model.learn_one(features, target)
        
        if (idx % 1000) == 0:
            logger.info(f"  Processed {idx}/{len(train_df)} samples - MAE: {train_mae.get():.2f}")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"TRAINING PERFORMANCE")
    logger.info(f"{'='*60}")
    logger.info(f"MAE:  {train_mae.get():.2f}")
    logger.info(f"RMSE: {train_rmse.get():.2f}")
    logger.info(f"R²:   {train_r2.get():.4f}")
    
    # Testing
    logger.info(f"\n{'='*60}")
    logger.info(f"TESTING ON HELD-OUT DATA")
    logger.info(f"{'='*60}")
    
    predictions_test = []
    actuals_test = []
    
    for idx, row in test_df.iterrows():
        features = {col: row[col] for col in feature_cols}
        target = row['aqi']
        
        # Make prediction (without learning)
        pred = model.predict_one(features)
        if pred is not None:
            test_mae.update(target, pred)
            test_rmse.update(target, pred)
            test_r2.update(target, pred)
            predictions_test.append(pred)
            actuals_test.append(target)
    
    logger.info(f"MAE:  {test_mae.get():.2f}")
    logger.info(f"RMSE: {test_rmse.get():.2f}")
    logger.info(f"R²:   {test_r2.get():.4f}")
    logger.info(f"{'='*60}\n")
    
    # Save results
    results = {
        'train': {
            'mae': float(train_mae.get()),
            'rmse': float(train_rmse.get()),
            'r2': float(train_r2.get()),
            'samples': len(train_df)
        },
        'test': {
            'mae': float(test_mae.get()),
            'rmse': float(test_rmse.get()),
            'r2': float(test_r2.get()),
            'samples': len(test_df)
        },
        'timestamp': datetime.now().isoformat(),
        'features': feature_cols
    }
    
    return model, results, predictions_test, actuals_test


def save_model(model, results):
    """Save the trained model"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    model_path = models_dir / f"arf_model_{timestamp}.pkl"
    
    models_dir.mkdir(exist_ok=True)
    
    with open(model_path, 'wb') as f:
        dill.dump(model, f)
    
    logger.info(f"Model saved to: {model_path}")
    
    # Save results
    results_path = models_dir / f"training_results_{timestamp}.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Results saved to: {results_path}")
    
    return model_path


def main():
    """Main retraining pipeline"""
    logger.info(f"\n{'='*60}")
    logger.info(f"AQI MODEL RETRAINING")
    logger.info(f"{'='*60}\n")
    
    try:
        # Load data
        df = load_and_parse_data()
        
        # Create features
        df_features, preprocessor = create_features_batch(df)
        
        # Train model
        model, results, predictions, actuals = train_model_with_validation(df_features)
        
        # Save model
        model_path = save_model(model, results)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ RETRAINING COMPLETE!")
        logger.info(f"{'='*60}")
        logger.info(f"Model: {model_path}")
        logger.info(f"Test R²: {results['test']['r2']:.4f}")
        logger.info(f"Test MAE: {results['test']['mae']:.2f} AQI points")
        logger.info(f"{'='*60}\n")
        
        # Restart API suggestion
        logger.info("🔄 To use the new model, restart the API:")
        logger.info("   pkill -f 'python3 main.py'")
        logger.info("   cd api && python3 main.py")
        
    except Exception as e:
        logger.error(f"❌ Retraining failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
