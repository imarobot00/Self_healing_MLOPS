#!/usr/bin/env python3
"""
Comprehensive test suite for AutoTrainer
"""

import sys
from pathlib import Path
import json
import dill
import pandas as pd
import numpy as np
import importlib.util

# Load AutoTrainer
project_root = Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location(
    "auto_trainer",
    project_root / "training" / "auto_trainer.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
AutoTrainer = module.AutoTrainer


def test_model_loading():
    """Test that the new model can be loaded and used"""
    print("="*70)
    print("TEST 1: Model Loading")
    print("="*70)
    
    model_path = Path("training/models/model_20260106_180235/model.pkl")
    fe_path = Path("training/models/model_20260106_180235/feature_engineer.pkl")
    
    # Load model
    with open(model_path, 'rb') as f:
        model = dill.load(f)
    print("✅ Model loaded successfully")
    
    # Load feature engineer
    with open(fe_path, 'rb') as f:
        fe = dill.load(f)
    print("✅ Feature engineer loaded successfully")
    
    # Test prediction with realistic features
    test_features = {
        'pm25': 45.5,
        'pm1': 30.2,
        'temperature': 25.0,
        'relativehumidity': 65.0,
        'um003': 100.0,
        'hour_sin': 0.5,
        'hour_cos': 0.866,
        'pm25_lag_1h': 44.0,
        'pm25_lag_2h': 43.5,
        'pm25_lag_3h': 42.0,
        'pm25_rolling_mean_3h': 43.5,
        'pm25_rolling_std_3h': 1.5,
    }
    
    pred = model.predict_one(test_features)
    print(f"✅ Test prediction: {pred:.2f} AQI")
    
    # Verify prediction is in valid range
    assert 0 <= pred <= 500, f"Invalid prediction: {pred}"
    print("✅ Prediction in valid range (0-500)")
    
    print()
    return True


def test_model_comparison():
    """Compare new model vs old model"""
    print("="*70)
    print("TEST 2: Model Performance Comparison")
    print("="*70)
    
    # Find all models
    models_dir = Path("training/models")
    model_dirs = sorted([d for d in models_dir.glob("model_*") if d.is_dir()])
    
    if len(model_dirs) < 2:
        print("⚠️  Only one model found, skipping comparison")
        print()
        return True
    
    # Get latest two models
    old_model = model_dirs[-2]
    new_model = model_dirs[-1]
    
    # Load metadata
    with open(old_model / "metadata.json") as f:
        old_meta = json.load(f)
    with open(new_model / "metadata.json") as f:
        new_meta = json.load(f)
    
    print(f"Old Model: {old_model.name}")
    print(f"  MAE:     {old_meta['metrics']['mae']:.2f} AQI")
    print(f"  RMSE:    {old_meta['metrics']['rmse']:.2f} AQI")
    print(f"  R²:      {old_meta['metrics']['r2']:.4f}")
    print(f"  Samples: {old_meta['metrics']['samples']:,}")
    print()
    
    print(f"New Model: {new_model.name}")
    print(f"  MAE:     {new_meta['metrics']['mae']:.2f} AQI")
    print(f"  RMSE:    {new_meta['metrics']['rmse']:.2f} AQI")
    print(f"  R²:      {new_meta['metrics']['r2']:.4f}")
    print(f"  Samples: {new_meta['metrics']['samples']:,}")
    print()
    
    # Calculate improvements
    mae_improvement = ((old_meta['metrics']['mae'] - new_meta['metrics']['mae']) / old_meta['metrics']['mae']) * 100
    rmse_improvement = ((old_meta['metrics']['rmse'] - new_meta['metrics']['rmse']) / old_meta['metrics']['rmse']) * 100
    r2_improvement = ((new_meta['metrics']['r2'] - old_meta['metrics']['r2']) / old_meta['metrics']['r2']) * 100
    
    print("🎯 Performance Changes:")
    print(f"  MAE:  {mae_improvement:+.1f}% {'✅' if mae_improvement > 0 else '⚠️'}")
    print(f"  RMSE: {rmse_improvement:+.1f}% {'✅' if rmse_improvement > 0 else '⚠️'}")
    print(f"  R²:   {r2_improvement:+.1f}% {'✅' if r2_improvement > 0 else '⚠️'}")
    print()
    
    return True


def test_batch_predictions():
    """Test model with batch of realistic data"""
    print("="*70)
    print("TEST 3: Batch Prediction Test")
    print("="*70)
    
    # Load model
    model_path = Path("training/models/model_20260106_180235/model.pkl")
    with open(model_path, 'rb') as f:
        model = dill.load(f)
    
    # Load some test data
    test_data_path = Path("dataset/preprocessed/test_data.csv")
    if not test_data_path.exists():
        print("⚠️  Test data not found, using synthetic data")
        # Create synthetic test data
        n_samples = 10
        test_data = []
        for i in range(n_samples):
            pm25 = np.random.uniform(20, 100)
            features = {
                'pm25': pm25,
                'pm1': pm25 * 0.8,
                'temperature': np.random.uniform(15, 30),
                'relativehumidity': np.random.uniform(40, 80),
                'um003': np.random.uniform(50, 200),
                'hour_sin': np.sin(2 * np.pi * i / 24),
                'hour_cos': np.cos(2 * np.pi * i / 24),
            }
            test_data.append(features)
    else:
        df = pd.read_csv(test_data_path)
        feature_cols = [col for col in df.columns if col not in ['aqi', 'datetime', 'location_id']]
        test_data = df[feature_cols].head(10).to_dict('records')
    
    # Make predictions
    predictions = []
    for features in test_data:
        pred = model.predict_one(features)
        predictions.append(pred)
    
    print(f"✅ Made {len(predictions)} predictions")
    print(f"   Min: {min(predictions):.2f} AQI")
    print(f"   Max: {max(predictions):.2f} AQI")
    print(f"   Mean: {np.mean(predictions):.2f} AQI")
    print(f"   Std: {np.std(predictions):.2f} AQI")
    
    # Verify all predictions are valid
    assert all(0 <= p <= 500 for p in predictions), "Some predictions out of range"
    print("✅ All predictions in valid range")
    
    print()
    return True


def test_drift_check():
    """Test drift detection"""
    print("="*70)
    print("TEST 4: Drift Detection")
    print("="*70)
    
    trainer = AutoTrainer()
    
    # Check drift
    should_retrain, reasons = trainer.should_retrain()
    
    print(f"Drift Score: {reasons['drift_score']:.4f}")
    print(f"Threshold: {trainer.drift_threshold}")
    print(f"Drift Exceeded: {reasons['drift_exceeded']}")
    print(f"Time Since Last Retrain: {reasons['time_since_last_retrain']:.1f} hours" if reasons['time_since_last_retrain'] else "Time Since Last Retrain: 0.0 hours (just retrained)")
    print(f"Decision: {reasons['decision']}")
    print()
    
    if should_retrain:
        print("⚠️  Retraining recommended")
    else:
        print("✅ No retraining needed")
    
    print()
    return True


def test_metadata_consistency():
    """Test that metadata is properly saved"""
    print("="*70)
    print("TEST 5: Metadata Consistency")
    print("="*70)
    
    metadata_path = Path("training/models/model_20260106_180235/metadata.json")
    with open(metadata_path) as f:
        metadata = json.load(f)
    
    # Check required fields
    required_fields = ['version', 'created_at', 'metrics', 'model_type']
    for field in required_fields:
        assert field in metadata, f"Missing field: {field}"
        print(f"✅ {field}: {metadata[field] if field != 'metrics' else '...'}")
    
    # Check metrics
    required_metrics = ['mae', 'rmse', 'r2', 'samples', 'features']
    for metric in required_metrics:
        assert metric in metadata['metrics'], f"Missing metric: {metric}"
        print(f"✅ metrics.{metric}: {metadata['metrics'][metric]}")
    
    print()
    return True


def main():
    """Run all tests"""
    print("\n")
    print("🧪 AUTO-TRAINER TEST SUITE")
    print("="*70)
    print()
    
    tests = [
        ("Model Loading", test_model_loading),
        ("Model Comparison", test_model_comparison),
        ("Batch Predictions", test_batch_predictions),
        ("Drift Detection", test_drift_check),
        ("Metadata Consistency", test_metadata_consistency),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"❌ {test_name} FAILED: {e}")
            failed += 1
            import traceback
            traceback.print_exc()
            print()
    
    print("="*70)
    print("📊 TEST RESULTS")
    print("="*70)
    print(f"Passed: {passed}/{len(tests)} ✅")
    print(f"Failed: {failed}/{len(tests)} {'❌' if failed > 0 else ''}")
    print("="*70)
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! Auto-Trainer is working correctly.\n")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review errors above.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
