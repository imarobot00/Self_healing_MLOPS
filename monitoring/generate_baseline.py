"""
Generate baseline statistics from training data.

This script calculates distribution statistics for all monitored features
from the training dataset. These statistics serve as the reference point
for drift detection in production.

Usage:
    python monitoring/generate_baseline.py
"""

import pandas as pd
import json
import yaml
from pathlib import Path
from datetime import datetime
import sys


def load_config(config_path: str = "monitoring/drift_config.yaml") -> dict:
    """Load drift detection configuration"""
    config_path = Path(config_path)
    
    if not config_path.exists():
        print(f"⚠️  Config file not found: {config_path}")
        print("Using default configuration...")
        return {
            'baseline': {
                'training_data': 'dataset/preprocessed/train_data.csv',
                'stats_file': 'monitoring/baseline_stats.json'
            },
            'drift_detection': {
                'features_to_monitor': ['pm25', 'pm1', 'temperature', 'relativehumidity']
            }
        }
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def calculate_statistics(df: pd.DataFrame, features: list) -> dict:
    """Calculate comprehensive statistics for each feature"""
    
    baseline = {
        'generated_at': datetime.now().isoformat(),
        'num_samples': len(df),
        'features': {}
    }
    
    for col in features:
        if col not in df.columns:
            print(f"⚠️  Feature '{col}' not found in training data, skipping...")
            continue
        
        # Remove NaN values
        data = df[col].dropna()
        
        if len(data) == 0:
            print(f"⚠️  No valid data for feature '{col}', skipping...")
            continue
        
        # Calculate statistics
        baseline['features'][col] = {
            # Central tendency
            'mean': float(data.mean()),
            'median': float(data.median()),
            'std': float(data.std()),
            
            # Range
            'min': float(data.min()),
            'max': float(data.max()),
            'range': float(data.max() - data.min()),
            
            # Quartiles
            'q25': float(data.quantile(0.25)),
            'q50': float(data.quantile(0.50)),
            'q75': float(data.quantile(0.75)),
            'q95': float(data.quantile(0.95)),
            'q99': float(data.quantile(0.99)),
            
            # Interquartile range
            'iqr': float(data.quantile(0.75) - data.quantile(0.25)),
            
            # Sample info
            'count': int(data.count()),
            'missing': int(df[col].isna().sum()),
            
            # Histogram for PSI calculation (10 bins)
            'histogram': {
                'bins': [float(x) for x in data.quantile([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]).values],
                'counts': [int(x) for x in pd.cut(data, bins=10, include_lowest=True).value_counts().sort_index().values]
            }
        }
        
        # Print summary
        print(f"✅ {col:20s} mean={baseline['features'][col]['mean']:8.2f}  "
              f"std={baseline['features'][col]['std']:7.2f}  "
              f"range=[{baseline['features'][col]['min']:6.2f}, {baseline['features'][col]['max']:6.2f}]  "
              f"samples={baseline['features'][col]['count']}")
    
    return baseline


def generate_baseline():
    """Main function to generate baseline statistics"""
    
    print("\n" + "="*70)
    print("📊 BASELINE STATISTICS GENERATOR")
    print("="*70)
    
    # Load configuration
    config = load_config()
    
    # Get paths from config
    training_data_path = Path(config['baseline']['training_data'])
    output_path = Path(config['baseline']['stats_file'])
    features = config['drift_detection']['features_to_monitor']
    
    print(f"\n📁 Training data: {training_data_path}")
    print(f"📁 Output file: {output_path}")
    print(f"🎯 Features to track: {', '.join(features)}")
    
    # Check if training data exists
    if not training_data_path.exists():
        print(f"\n❌ ERROR: Training data not found at {training_data_path}")
        print("\nPlease ensure the training data exists. Expected path:")
        print(f"   {training_data_path.absolute()}")
        sys.exit(1)
    
    # Load training data
    print(f"\n📖 Loading training data...")
    try:
        df = pd.read_csv(training_data_path)
        print(f"✅ Loaded {len(df):,} samples with {len(df.columns)} features")
    except Exception as e:
        print(f"❌ ERROR loading training data: {e}")
        sys.exit(1)
    
    # Calculate baseline statistics
    print(f"\n📊 Calculating baseline statistics...\n")
    baseline = calculate_statistics(df, features)
    
    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save baseline
    with open(output_path, 'w') as f:
        json.dump(baseline, f, indent=2)
    
    print(f"\n" + "="*70)
    print(f"💾 BASELINE SAVED")
    print("="*70)
    print(f"📁 Location: {output_path.absolute()}")
    print(f"📊 Features tracked: {len(baseline['features'])}")
    print(f"📅 Generated: {baseline['generated_at']}")
    print(f"🔢 Total samples: {baseline['num_samples']:,}")
    print("="*70)
    
    # Display summary statistics
    print("\n📈 SUMMARY STATISTICS:")
    print("-" * 70)
    print(f"{'Feature':<20} {'Mean':<10} {'Std':<10} {'Min':<10} {'Max':<10}")
    print("-" * 70)
    
    for feature, stats in baseline['features'].items():
        print(f"{feature:<20} {stats['mean']:<10.2f} {stats['std']:<10.2f} "
              f"{stats['min']:<10.2f} {stats['max']:<10.2f}")
    
    print("-" * 70)
    print("\n✅ Baseline generation complete!")
    print("You can now run drift detection: python monitoring/drift_detector.py\n")


if __name__ == "__main__":
    generate_baseline()
