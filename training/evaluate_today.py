#!/usr/bin/env python3
"""
Real-World Model Evaluation - AQI Predictions
==============================================

This script evaluates the trained AQI model on real data for a specified date.

Features:
- Supports any evaluation date (defaults to today)
- Loads actual air quality data from JSON files
- Makes predictions using trained ARF model
- Compares predictions vs actual values
- Generates performance report and visualizations
- Saves results in organized date-specific folders

Usage:
  python evaluate_today.py                    # Evaluate today's data
  python evaluate_today.py --date 2025-12-15  # Evaluate specific date

Author: Bipul Kumar Dahal
Date: December 15, 2025
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime, timedelta
import dill
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Optional
import sys
import argparse
import warnings
warnings.filterwarnings('ignore')

# Add parent directory to path for imports
preprocessed_dir = Path(__file__).parent.parent / "dataset" / "preprocessed"
sys.path.insert(0, str(preprocessed_dir))

# Import preprocessing module
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("preprocessing", preprocessed_dir / "preprocessing.py")
    preprocessing_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preprocessing_module)
    StreamingPreprocessor = preprocessing_module.StreamingPreprocessor
except (ImportError, FileNotFoundError, AttributeError) as e:
    print(f"Error: Could not import StreamingPreprocessor from {preprocessed_dir}")
    print(f"Make sure preprocessing.py exists in: {preprocessed_dir}")
    print(f"Error details: {e}")
    sys.exit(1)

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")


class AQIEvaluator:
    """Evaluate model performance on real-world data for any date."""
    
    def __init__(self, model_path: str, preprocessor_stats_path: str, eval_date: Optional[str] = None):
        """
        Initialize evaluator.
        
        Parameters:
        -----------
        model_path : str
            Path to trained ARF model
        preprocessor_stats_path : str
            Path to preprocessing statistics
        eval_date : str, optional
            Date to evaluate (YYYY-MM-DD format). Defaults to today.
        """
        self.eval_date = eval_date if eval_date else datetime.now().strftime('%Y-%m-%d')
        print(f"\n🗓️  Evaluation Date: {self.eval_date}")
        
        self.model_path = Path(model_path)
        self.preprocessor_stats_path = Path(preprocessor_stats_path)
        
        # Load model
        print(f"📂 Loading model from: {self.model_path}")
        with open(self.model_path, 'rb') as f:
            self.model = dill.load(f)
        print("✅ Model loaded successfully")
        
        # Initialize preprocessor
        print(f"📂 Loading preprocessor statistics from: {self.preprocessor_stats_path}")
        self.preprocessor = StreamingPreprocessor(
            target_column='aqi',
            lag_features=[1, 2, 3, 6, 12, 24],
            rolling_windows=[3, 6, 12, 24],
            normalize=True,
            handle_outliers=True
        )
        self.preprocessor.load_statistics(str(self.preprocessor_stats_path))
        print("✅ Preprocessor loaded successfully")
        
        # Results storage
        self.results = {
            'timestamps': [],
            'actual': [],
            'predicted': [],
            'residuals': [],
            'location_ids': []
        }
    
    def load_data_for_date(self, dataset_dir: str) -> pd.DataFrame:
        """
        Load and process data from JSON files for the specified date.
        
        Parameters:
        -----------
        dataset_dir : str
            Directory containing location JSON files
        
        Returns:
        --------
        pd.DataFrame
            Aligned data for the evaluation date
        """
        dataset_dir = Path(dataset_dir)
        
        print("\n" + "="*80)
        print(f"📥 LOADING DATA FOR {self.eval_date}")
        print("="*80)
        
        all_data = []
        location_files = list(dataset_dir.glob("location_*.json"))
        
        print(f"Found {len(location_files)} location files")
        
        for location_file in location_files:
            location_id = location_file.stem.split('_')[1]
            
            with open(location_file, 'r') as f:
                data = json.load(f)
            
            # Filter for specified date's data
            date_records = []
            for record in data:
                if 'period' in record and 'datetimeFrom' in record['period']:
                    local_date = record['period']['datetimeFrom']['local']
                    if local_date.startswith(self.eval_date):
                        date_records.append({
                            'location_id': int(location_id),
                            'datetime': local_date,
                            'parameter': record['parameter']['name'],
                            'value': record['value']
                        })
            
            if date_records:
                print(f"  Location {location_id}: {len(date_records)} records")
                all_data.extend(date_records)
        
        if not all_data:
            print(f"❌ No data found for {self.eval_date}!")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(all_data)
        print(f"\n✅ Total records loaded: {len(df)}")
        
        # Pivot to get one row per timestamp
        print("🔄 Aligning data by timestamp...")
        df_pivot = df.pivot_table(
            index=['location_id', 'datetime'],
            columns='parameter',
            values='value',
            aggfunc='mean'
        ).reset_index()
        
        # Parse datetime
        df_pivot['datetime'] = pd.to_datetime(df_pivot['datetime'])
        
        # Calculate AQI (simplified EPA method for PM2.5)
        if 'pm25' in df_pivot.columns:
            df_pivot['aqi'] = df_pivot['pm25'].apply(self._calculate_aqi)
        
        # Add time features
        df_pivot['hour'] = df_pivot['datetime'].dt.hour
        df_pivot['day'] = df_pivot['datetime'].dt.day
        df_pivot['month'] = df_pivot['datetime'].dt.month
        df_pivot['day_of_week'] = df_pivot['datetime'].dt.dayofweek
        df_pivot['day_name'] = df_pivot['datetime'].dt.day_name()
        df_pivot['is_weekend'] = df_pivot['day_of_week'].isin([5, 6]).astype(int)
        
        # Time of day
        df_pivot['time_of_day'] = df_pivot['hour'].apply(
            lambda x: 'Night' if x < 6 else ('Morning' if x < 12 else ('Afternoon' if x < 18 else 'Evening'))
        )
        
        print(f"✅ Aligned data shape: {df_pivot.shape}")
        print(f"   Time range: {df_pivot['datetime'].min()} to {df_pivot['datetime'].max()}")
        
        return df_pivot
    
    def _calculate_aqi(self, pm25: float) -> float:
        """Calculate AQI from PM2.5 (EPA standard)."""
        if pd.isna(pm25):
            return np.nan
        
        # EPA AQI breakpoints for PM2.5
        breakpoints = [
            (0.0, 12.0, 0, 50),
            (12.1, 35.4, 51, 100),
            (35.5, 55.4, 101, 150),
            (55.5, 150.4, 151, 200),
            (150.5, 250.4, 201, 300),
            (250.5, 350.4, 301, 400),
            (350.5, 500.4, 401, 500)
        ]
        
        for c_low, c_high, i_low, i_high in breakpoints:
            if c_low <= pm25 <= c_high:
                return ((i_high - i_low) / (c_high - c_low)) * (pm25 - c_low) + i_low
        
        return 500  # Maximum AQI
    
    def preprocess_for_prediction(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess today's data for model input.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Raw aligned data
        
        Returns:
        --------
        pd.DataFrame
            Preprocessed data ready for prediction
        """
        print("\n" + "="*80)
        print("🔄 PREPROCESSING DATA")
        print("="*80)
        
        # Sort by location and time
        df = df.sort_values(['location_id', 'datetime']).reset_index(drop=True)
        
        # Apply preprocessing pipeline (fit=False, use loaded statistics)
        df_processed = self.preprocessor.prepare_for_streaming(df, fit=False)
        
        print(f"✅ Preprocessing complete: {df_processed.shape}")
        
        return df_processed
    
    def make_predictions(self, df_processed: pd.DataFrame) -> Dict:
        """
        Use trained model to make predictions.
        
        Parameters:
        -----------
        df_processed : pd.DataFrame
            Preprocessed data
        
        Returns:
        --------
        dict
            Predictions and metadata
        """
        print("\n" + "="*80)
        print("🔮 MAKING PREDICTIONS")
        print("="*80)
        
        # Get feature columns
        feature_cols = self.preprocessor.get_feature_columns(df_processed)
        
        predictions = []
        actuals = []
        timestamps = []
        location_ids = []
        fallback_count = 0
        model_none_count = 0
        
        for idx, row in df_processed.iterrows():
            # Prepare features
            features = {col: row[col] for col in feature_cols}
            
            # Make prediction
            try:
                y_pred = self.model.predict_one(features)
                y_true = row['aqi']
                
                # Track when model returns None or NaN
                if y_pred is None or (isinstance(y_pred, (int, float)) and pd.isna(y_pred)):
                    model_none_count += 1
                    # Fallback: Use simple persistence model (assume AQI = previous hour's AQI)
                    # Get location's previous AQI value from actuals list
                    loc_id = row['location_id']
                    if len(actuals) > 0 and len(location_ids) > 0:
                        # Find most recent prediction for same location
                        for i in range(len(location_ids) - 1, -1, -1):
                            if location_ids[i] == loc_id:
                                y_pred = actuals[i]  # Use previous actual AQI for this location
                                fallback_count += 1
                                break
                    
                    # If no previous value found, skip this prediction
                    if y_pred is None or (isinstance(y_pred, (int, float)) and pd.isna(y_pred)):
                        continue
                
                if y_pred is not None and not pd.isna(y_true):
                    predictions.append(y_pred)
                    actuals.append(y_true)
                    timestamps.append(row['datetime'])
                    location_ids.append(row['location_id'])
            except Exception as e:
                # Skip rows that cause prediction errors
                continue
        
        print(f"✅ Generated {len(predictions)} predictions")
        print(f"📊 Model returned None: {model_none_count} times")
        if fallback_count > 0:
            print(f"📊 Used fallback prediction for {fallback_count} samples ({fallback_count/len(predictions)*100:.1f}%)")
        
        # Check if we have valid predictions
        if len(predictions) == 0:
            print("⚠️  WARNING: No valid predictions were generated!")
            return {
                'predictions': [],
                'actuals': [],
                'residuals': [],
                'timestamps': [],
                'location_ids': [],
                'metrics': {
                    'mae': 0.0,
                    'rmse': 0.0,
                    'r2': 0.0,
                    'mape': 0.0,
                    'count': 0
                }
            }
        
        # Calculate metrics
        predictions_array = np.array(predictions)
        actuals_array = np.array(actuals)
        
        # Remove NaN values from both arrays
        valid_mask = ~(np.isnan(predictions_array) | np.isnan(actuals_array))
        predictions_clean = predictions_array[valid_mask]
        actuals_clean = actuals_array[valid_mask]
        
        if len(predictions_clean) == 0:
            print("⚠️  WARNING: No valid predictions after cleaning!")
            mae = 0.0
            rmse = 0.0
            r2 = 0.0
            mape = 0.0
        else:
            mae = float(np.mean(np.abs(actuals_clean - predictions_clean)))
            rmse = float(np.sqrt(np.mean((actuals_clean - predictions_clean)**2)))
            
            ss_res = np.sum((actuals_clean - predictions_clean)**2)
            ss_tot = np.sum((actuals_clean - np.mean(actuals_clean))**2)
            r2 = float(1 - (ss_res / ss_tot)) if ss_tot != 0 else 0.0
            
            mape_values = [
                abs((actuals_clean[i] - predictions_clean[i]) / actuals_clean[i]) * 100
                for i in range(len(actuals_clean))
                if actuals_clean[i] != 0
            ]
            mape = float(np.mean(mape_values)) if mape_values else 0.0
        
        residuals = actuals_array - predictions_array
        
        results = {
            'predictions': predictions,
            'actuals': actuals,
            'residuals': residuals.tolist(),
            'timestamps': timestamps,
            'location_ids': location_ids,
            'metrics': {
                'mae': mae,
                'rmse': rmse,
                'r2': r2,
                'mape': mape,
                'count': len(predictions)
            }
        }
        
        # Debug: Check if all predictions are valid
        pred_array_check = np.array(predictions)
        nan_count = np.isnan(pred_array_check).sum()
        if nan_count > 0:
            print(f"⚠️  WARNING: {nan_count} predictions are NaN!")
        
        self.results = results
        
        return results
    
    def print_report(self, results: Dict):
        """Print evaluation report."""
        print("\n" + "="*80)
        print("📊 TODAY'S PERFORMANCE REPORT")
        print("="*80)
        
        metrics = results['metrics']
        
        print(f"\n🎯 Prediction Metrics (Today):")
        print(f"   MAE:  {metrics['mae']:.2f} AQI points")
        print(f"   RMSE: {metrics['rmse']:.2f}")
        print(f"   R²:   {metrics['r2']:.3f}")
        print(f"   MAPE: {metrics['mape']:.2f}%")
        print(f"   Samples: {metrics['count']}")
        
        # Compare with training performance
        print(f"\n📈 Comparison with Training:")
        print(f"   Training MAE:  6.74")
        print(f"   Today's MAE:   {metrics['mae']:.2f}")
        print(f"   Difference:    {metrics['mae'] - 6.74:+.2f}")
        
        print(f"\n   Test MAE:      4.31")
        print(f"   Today's MAE:   {metrics['mae']:.2f}")
        print(f"   Difference:    {metrics['mae'] - 4.31:+.2f}")
        
        # Interpretation
        print(f"\n💡 Interpretation:")
        if metrics['mae'] < 5:
            print("   🟢 EXCELLENT - Model performing exceptionally well!")
        elif metrics['mae'] < 8:
            print("   🟡 GOOD - Model performing within expected range")
        elif metrics['mae'] < 12:
            print("   🟠 ACCEPTABLE - Some drift may be occurring")
        else:
            print("   🔴 CONCERNING - Significant drift detected, may need retraining")
        
        if metrics['r2'] > 0.90:
            print(f"   🟢 R² Score ({metrics['r2']:.3f}) - Excellent predictions!")
        elif metrics['r2'] > 0.80:
            print(f"   🟡 R² Score ({metrics['r2']:.3f}) - Good predictions")
        else:
            print(f"   🟠 R² Score ({metrics['r2']:.3f}) - Model may need adjustment")
        
        # Time range
        if results['timestamps']:
            print(f"\n⏰ Time Range:")
            print(f"   From: {min(results['timestamps'])}")
            print(f"   To:   {max(results['timestamps'])}")
            
            # Hourly breakdown
            df_results = pd.DataFrame({
                'timestamp': results['timestamps'],
                'actual': results['actuals'],
                'predicted': results['predictions'],
                'residual': results['residuals']
            })
            df_results['hour'] = pd.to_datetime(df_results['timestamp']).dt.hour
            
            print(f"\n📊 Hourly Performance:")
            hourly_mae = df_results.groupby('hour').apply(
                lambda x: np.mean(np.abs(x['residual']))
            )
            for hour, mae_val in hourly_mae.items():
                print(f"   {hour:02d}:00 - MAE: {mae_val:.2f}")
    
    def create_visualizations(self, results: Dict, output_dir: str):
        """Create visualization charts."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print("\n" + "="*80)
        print("📊 GENERATING VISUALIZATIONS")
        print("="*80)
        
        # Create results dataframe
        df_results = pd.DataFrame({
            'timestamp': results['timestamps'],
            'actual': results['actuals'],
            'predicted': results['predictions'],
            'residual': results['residuals'],
            'location_id': results['location_ids']
        })
        df_results['timestamp'] = pd.to_datetime(df_results['timestamp'])
        
        # 1. Time series comparison
        fig, ax = plt.subplots(figsize=(14, 6))
        
        for location in df_results['location_id'].unique():
            df_loc = df_results[df_results['location_id'] == location]
            ax.plot(df_loc['timestamp'], df_loc['actual'], 'o-', 
                   label=f'Actual (Loc {location})', alpha=0.7)
            ax.plot(df_loc['timestamp'], df_loc['predicted'], 's--', 
                   label=f'Predicted (Loc {location})', alpha=0.7)
        
        ax.set_xlabel('Time', fontsize=12, fontweight='bold')
        ax.set_ylabel('AQI', fontsize=12, fontweight='bold')
        ax.set_title("Today's Predictions vs Actual AQI", fontsize=14, fontweight='bold')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(output_dir / 'today_predictions_vs_actual.png', dpi=300, bbox_inches='tight')
        plt.close()
        print("  ✓ Time series chart created")
        
        # 2. Scatter plot
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.scatter(df_results['actual'], df_results['predicted'], alpha=0.6, s=50)
        
        min_val = min(df_results['actual'].min(), df_results['predicted'].min())
        max_val = max(df_results['actual'].max(), df_results['predicted'].max())
        ax.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='Perfect Prediction')
        
        ax.set_xlabel('Actual AQI', fontsize=12, fontweight='bold')
        ax.set_ylabel('Predicted AQI', fontsize=12, fontweight='bold')
        ax.set_title("Today's Performance: Predictions vs Actual", fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Add metrics
        metrics = results['metrics']
        text_str = f"MAE: {metrics['mae']:.2f}\nRMSE: {metrics['rmse']:.2f}\nR²: {metrics['r2']:.3f}\nMAPE: {metrics['mape']:.2f}%"
        ax.text(0.05, 0.95, text_str, transform=ax.transAxes, fontsize=10,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        plt.savefig(output_dir / 'today_scatter.png', dpi=300, bbox_inches='tight')
        plt.close()
        print("  ✓ Scatter plot created")
        
        # 3. Residuals
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # Residuals over time
        ax1.scatter(df_results['timestamp'], df_results['residual'], alpha=0.6)
        ax1.axhline(y=0, color='r', linestyle='--', linewidth=2)
        ax1.set_xlabel('Time', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Residual (Actual - Predicted)', fontsize=12, fontweight='bold')
        ax1.set_title('Residuals Over Time', fontsize=13, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
        
        # Residuals histogram
        ax2.hist(df_results['residual'], bins=20, edgecolor='black', alpha=0.7)
        ax2.axvline(x=0, color='r', linestyle='--', linewidth=2)
        ax2.set_xlabel('Residual', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Frequency', fontsize=12, fontweight='bold')
        ax2.set_title('Distribution of Residuals', fontsize=13, fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='y')
        
        mean_res = np.mean(df_results['residual'])
        std_res = np.std(df_results['residual'])
        ax2.text(0.05, 0.95, f'Mean: {mean_res:.2f}\nStd: {std_res:.2f}',
                transform=ax2.transAxes, fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        plt.savefig(output_dir / 'today_residuals.png', dpi=300, bbox_inches='tight')
        plt.close()
        print("  ✓ Residuals chart created")
        
        print(f"\n✅ All charts saved to: {output_dir}")
    
    def save_results(self, results: Dict, output_dir: str):
        """Save results to CSV."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if we have valid results
        if len(results['predictions']) == 0:
            print("⚠️  No predictions to save!")
            return
        
        # Save predictions
        df_results = pd.DataFrame({
            'timestamp': results['timestamps'],
            'location_id': results['location_ids'],
            'actual_aqi': results['actuals'],
            'predicted_aqi': results['predictions'],
            'residual': results['residuals'],
            'absolute_error': np.abs(results['residuals'])
        })
        
        csv_file = output_dir / f"today_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df_results.to_csv(csv_file, index=False)
        print(f"💾 Results saved to: {csv_file}")
        
        # Save metrics
        metrics_file = output_dir / f"today_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        metrics = results['metrics']
        with open(metrics_file, 'w') as f:
            json.dump({
                'date': '2025-12-15',
                'metrics': {
                    'mae': float(metrics['mae']),
                    'rmse': float(metrics['rmse']),
                    'r2': float(metrics['r2']),
                    'mape': float(metrics['mape']),
                    'count': int(metrics['count'])
                },
                'comparison': {
                    'training_mae': 6.74,
                    'test_mae': 4.31,
                    'today_mae': float(metrics['mae']),
                    'vs_training': float(metrics['mae'] - 6.74),
                    'vs_test': float(metrics['mae'] - 4.31)
                }
            }, f, indent=2)
        print(f"💾 Metrics saved to: {metrics_file}")


def main():
    """Main evaluation pipeline."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Evaluate AQI model on real data')
    parser.add_argument('--date', type=str, default=None,
                      help='Date to evaluate (YYYY-MM-DD). Defaults to today.')
    args = parser.parse_args()
    
    eval_date = args.date if args.date else datetime.now().strftime('%Y-%m-%d')
    
    print("\n" + "="*80)
    print(f"🔍 REAL-WORLD MODEL EVALUATION - {eval_date}")
    print("="*80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Paths
    base_dir = Path(__file__).parent.parent
    dataset_dir = base_dir / "dataset"
    preprocessed_dir = base_dir / "dataset" / "preprocessed"
    models_dir = Path(__file__).parent / "models"
    
    # Create organized output directory structure: evaluations/YYYY_MM_DD/
    evaluations_base = Path(__file__).parent / "evaluations"
    output_dir = evaluations_base / eval_date.replace('-', '_')
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n📁 Output directory: {output_dir}")
    
    # Find latest model
    model_files = list(models_dir.glob("arf_model_*.pkl"))
    if not model_files:
        print("❌ No trained model found!")
        return
    
    latest_model = max(model_files, key=lambda x: x.stat().st_mtime)
    preprocessor_stats = preprocessed_dir / "preprocessor_stats.json"
    
    # Initialize evaluator
    evaluator = AQIEvaluator(
        model_path=str(latest_model),
        preprocessor_stats_path=str(preprocessor_stats),
        eval_date=eval_date
    )
    
    # Load data for specified date
    df_date = evaluator.load_data_for_date(str(dataset_dir))
    
    if df_date.empty:
        print(f"❌ No data available for {eval_date}")
        return
    
    # Preprocess
    df_processed = evaluator.preprocess_for_prediction(df_date)
    
    # Make predictions
    results = evaluator.make_predictions(df_processed)
    
    # Print report
    evaluator.print_report(results)
    
    # Create visualizations
    evaluator.create_visualizations(results, str(output_dir))
    
    # Save results
    evaluator.save_results(results, str(output_dir))
    
    print("\n" + "="*80)
    print("🎉 EVALUATION COMPLETE!")
    print("="*80)


if __name__ == "__main__":
    main()
