#!/usr/bin/env python3
"""
Multi-Parameter Model Evaluation - Today's Data
================================================

Evaluates all trained models (PM2.5, PM1, Temperature, Humidity) on today's real-world data.

Author: Bipul Kumar Dahal
Date: December 15, 2025
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime
import dill
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List
import sys
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
    print(f"Error details: {e}")
    sys.exit(1)

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")


class MultiParameterEvaluator:
    """Evaluate multiple parameter models on today's real-world data."""
    
    PARAMETERS = {
        'pm25': {'name': 'PM2.5', 'unit': 'µg/m³'},
        'pm1': {'name': 'PM1', 'unit': 'µg/m³'},
        'temperature': {'name': 'Temperature', 'unit': '°C'},
        'relativehumidity': {'name': 'Relative Humidity', 'unit': '%'}
    }
    
    def __init__(self, models_dir: str, preprocessor_stats_path: str):
        """
        Initialize multi-parameter evaluator.
        
        Parameters:
        -----------
        models_dir : str
            Directory containing trained models
        preprocessor_stats_path : str
            Path to preprocessing statistics
        """
        self.models_dir = Path(models_dir)
        self.preprocessor_stats_path = Path(preprocessor_stats_path)
        
        self.models = {}
        self.preprocessor = None
        self.results = {}
        
        self._load_models()
        self._load_preprocessor()
    
    def _load_models(self):
        """Load all trained parameter models."""
        print("="*80)
        print("📂 LOADING TRAINED MODELS")
        print("="*80)
        
        for param, config in self.PARAMETERS.items():
            param_dir = self.models_dir / param
            
            if not param_dir.exists():
                print(f"⚠️  {config['name']}: Model directory not found")
                continue
            
            # Find latest model file
            model_files = list(param_dir.glob(f"{param}_model_*.pkl"))
            
            if not model_files:
                print(f"⚠️  {config['name']}: No model file found")
                continue
            
            latest_model = max(model_files, key=lambda x: x.stat().st_mtime)
            
            try:
                with open(latest_model, 'rb') as f:
                    model_data = dill.load(f)
                
                self.models[param] = model_data
                print(f"✅ {config['name']}: {latest_model.name}")
                
            except Exception as e:
                print(f"❌ {config['name']}: Failed to load - {e}")
        
        print(f"\n✅ Loaded {len(self.models)}/{len(self.PARAMETERS)} models")
    
    def _load_preprocessor(self):
        """Initialize and load preprocessor statistics."""
        print("\n📂 Loading preprocessor statistics...")
        
        self.preprocessor = StreamingPreprocessor(
            target_column='aqi',
            lag_features=[1, 2, 3, 6, 12, 24],
            rolling_windows=[3, 6, 12, 24],
            normalize=True,
            handle_outliers=True
        )
        self.preprocessor.load_statistics(str(self.preprocessor_stats_path))
        
        # Load normalization ranges for denormalization
        with open(self.preprocessor_stats_path, 'r') as f:
            stats = json.load(f)
        
        self.normalization_params = {}
        if 'normalization' in stats:
            for param in self.PARAMETERS.keys():
                if param in stats['normalization']:
                    self.normalization_params[param] = stats['normalization'][param]
        
        print("✅ Preprocessor loaded successfully")
    
    def _denormalize(self, values, parameter):
        """Denormalize values back to original scale."""
        if parameter not in self.normalization_params:
            return values
        
        params = self.normalization_params[parameter]
        min_val = params['min']
        max_val = params['max']
        
        # Reverse min-max normalization: original = normalized * (max - min) + min
        return np.array(values) * (max_val - min_val) + min_val
    
    def load_todays_data(self, dataset_dir: str) -> pd.DataFrame:
        """Load and align today's data from JSON files."""
        dataset_dir = Path(dataset_dir)
        
        print("\n" + "="*80)
        print("📥 LOADING TODAY'S DATA")
        print("="*80)
        
        all_data = []
        location_files = list(dataset_dir.glob("location_*.json"))
        
        print(f"Found {len(location_files)} location files")
        
        for location_file in location_files:
            location_id = location_file.stem.split('_')[1]
            
            with open(location_file, 'r') as f:
                data = json.load(f)
            
            # Filter for today's data
            today_records = []
            for record in data:
                if 'period' in record and 'datetimeFrom' in record['period']:
                    local_date = record['period']['datetimeFrom']['local']
                    if local_date.startswith('2025-12-15'):
                        today_records.append({
                            'location_id': int(location_id),
                            'datetime': local_date,
                            'parameter': record['parameter']['name'],
                            'value': record['value']
                        })
            
            if today_records:
                print(f"  Location {location_id}: {len(today_records)} records")
                all_data.extend(today_records)
        
        if not all_data:
            print("❌ No data found for today!")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(all_data)
        print(f"\n✅ Total records loaded: {len(df)}")
        
        # Pivot to get one row per timestamp
        df_pivot = df.pivot_table(
            index=['location_id', 'datetime'],
            columns='parameter',
            values='value',
            aggfunc='mean'
        ).reset_index()
        
        # Parse datetime
        df_pivot['datetime'] = pd.to_datetime(df_pivot['datetime'])
        
        # Calculate AQI from PM2.5
        if 'pm25' in df_pivot.columns:
            df_pivot['aqi'] = df_pivot['pm25'].apply(self._calculate_aqi)
        
        # Add time features
        df_pivot['hour'] = df_pivot['datetime'].dt.hour
        df_pivot['day'] = df_pivot['datetime'].dt.day
        df_pivot['month'] = df_pivot['datetime'].dt.month
        df_pivot['day_of_week'] = df_pivot['datetime'].dt.dayofweek
        df_pivot['day_name'] = df_pivot['datetime'].dt.day_name()
        df_pivot['is_weekend'] = df_pivot['day_of_week'].isin([5, 6]).astype(int)
        
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
        
        return 500
    
    def preprocess_for_prediction(self, df: pd.DataFrame) -> pd.DataFrame:
        """Preprocess today's data for model input."""
        print("\n" + "="*80)
        print("🔄 PREPROCESSING DATA")
        print("="*80)
        
        df = df.sort_values(['location_id', 'datetime']).reset_index(drop=True)
        df_processed = self.preprocessor.prepare_for_streaming(df, fit=False)
        
        print(f"✅ Preprocessing complete: {df_processed.shape}")
        
        return df_processed
    
    def make_predictions(self, df_processed: pd.DataFrame) -> Dict:
        """Use trained models to make predictions for all parameters."""
        print("\n" + "="*80)
        print("🔮 MAKING MULTI-PARAMETER PREDICTIONS")
        print("="*80)
        
        results = {param: {
            'predictions': [],
            'actuals': [],
            'timestamps': [],
            'location_ids': []
        } for param in self.models.keys()}
        
        # Get feature columns (exclude all target parameters)
        exclude_cols = ['datetime', 'location_id', 'aqi'] + list(self.PARAMETERS.keys())
        feature_cols = [col for col in df_processed.columns if col not in exclude_cols]
        
        for idx, row in df_processed.iterrows():
            features = {col: row[col] for col in feature_cols}
            
            # Make predictions for each parameter
            for param, model_data in self.models.items():
                model = model_data['model']
                y_true = row[param]
                
                try:
                    y_pred = model.predict_one(features)
                    
                    if y_pred is not None and not pd.isna(y_true):
                        results[param]['predictions'].append(y_pred)
                        results[param]['actuals'].append(y_true)
                        results[param]['timestamps'].append(row['datetime'])
                        results[param]['location_ids'].append(row['location_id'])
                        
                except Exception:
                    continue
        
        # Calculate metrics for each parameter
        print()
        for param, data in results.items():
            if len(data['predictions']) > 0:
                config = self.PARAMETERS[param]
                
                # Denormalize predictions and actuals
                predictions_normalized = np.array(data['predictions'])
                actuals_normalized = np.array(data['actuals'])
                
                predictions_array = self._denormalize(predictions_normalized, param)
                actuals_array = self._denormalize(actuals_normalized, param)
                
                # Store denormalized values
                data['predictions_denorm'] = predictions_array.tolist()
                data['actuals_denorm'] = actuals_array.tolist()
                
                mae = float(np.mean(np.abs(actuals_array - predictions_array)))
                rmse = float(np.sqrt(np.mean((actuals_array - predictions_array)**2)))
                
                ss_res = np.sum((actuals_array - predictions_array)**2)
                ss_tot = np.sum((actuals_array - np.mean(actuals_array))**2)
                r2 = float(1 - (ss_res / ss_tot)) if ss_tot != 0 else 0.0
                
                mape_values = [
                    abs((actuals_array[i] - predictions_array[i]) / actuals_array[i]) * 100
                    for i in range(len(actuals_array))
                    if actuals_array[i] != 0
                ]
                mape = float(np.mean(mape_values)) if mape_values else 0.0
                
                residuals = actuals_array - predictions_array
                
                data['metrics'] = {
                    'mae': mae,
                    'rmse': rmse,
                    'r2': r2,
                    'mape': mape,
                    'count': len(predictions_array)
                }
                data['residuals'] = residuals.tolist()
                
                print(f"✅ {config['name']}: {len(predictions_array)} predictions")
                print(f"   MAE: {mae:.2f} {config['unit']}, R²: {r2:.3f}, MAPE: {mape:.2f}%")
        
        self.results = results
        return results
    
    def print_report(self):
        """Print comprehensive evaluation report."""
        print("\n" + "="*80)
        print("📊 MULTI-PARAMETER PERFORMANCE REPORT")
        print("="*80)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        for param, data in self.results.items():
            if 'metrics' not in data:
                continue
            
            config = self.PARAMETERS[param]
            metrics = data['metrics']
            
            print(f"\n📌 {config['name']} ({config['unit']})")
            print(f"   Samples:     {metrics['count']}")
            print(f"   MAE:         {metrics['mae']:.2f} {config['unit']}")
            print(f"   RMSE:        {metrics['rmse']:.2f} {config['unit']}")
            print(f"   R²:          {metrics['r2']:.3f}")
            print(f"   MAPE:        {metrics['mape']:.2f}%")
            
            # Interpretation
            if metrics['r2'] > 0.90:
                print(f"   Assessment:  🟢 Excellent")
            elif metrics['r2'] > 0.80:
                print(f"   Assessment:  🟡 Good")
            elif metrics['r2'] > 0.70:
                print(f"   Assessment:  🟠 Acceptable")
            else:
                print(f"   Assessment:  🔴 Needs improvement")
        
        print("\n" + "="*80)
    
    def create_visualizations(self, output_dir: str):
        """Create visualization charts for all parameters."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print("\n" + "="*80)
        print("📊 GENERATING VISUALIZATIONS")
        print("="*80)
        
        # Create subplots for all parameters
        n_params = len([d for d in self.results.values() if 'metrics' in d])
        
        if n_params == 0:
            print("⚠️  No predictions to visualize")
            return
        
        # 1. Combined predictions vs actual
        fig, axes = plt.subplots(n_params, 1, figsize=(14, 4*n_params))
        if n_params == 1:
            axes = [axes]
        
        for idx, (param, data) in enumerate(self.results.items()):
            if 'metrics' not in data:
                continue
            
            config = self.PARAMETERS[param]
            ax = axes[idx]
            
            timestamps = pd.to_datetime(data['timestamps'])
            # Use denormalized values if available
            if 'actuals_denorm' in data and 'predictions_denorm' in data:
                actuals = data['actuals_denorm']
                predictions = data['predictions_denorm']
            else:
                actuals = data['actuals']
                predictions = data['predictions']
            
            ax.plot(timestamps, actuals, 'b-', alpha=0.7, label='Actual', linewidth=2)
            ax.plot(timestamps, predictions, 'r--', alpha=0.7, label='Predicted', linewidth=2)
            
            ax.set_xlabel('Time', fontsize=11, fontweight='bold')
            ax.set_ylabel(f'{config["name"]} ({config["unit"]})', fontsize=11, fontweight='bold')
            ax.set_title(f'{config["name"]} - Predictions vs Actual', fontsize=13, fontweight='bold')
            ax.legend(loc='best')
            ax.grid(True, alpha=0.3)
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        plt.savefig(output_dir / 'multi_param_predictions.png', dpi=300, bbox_inches='tight')
        plt.close()
        print("  ✓ Combined predictions chart created")
        
        # 2. Scatter plots
        fig, axes = plt.subplots(2, 2, figsize=(14, 12))
        axes = axes.flatten()
        
        for idx, (param, data) in enumerate(self.results.items()):
            if 'metrics' not in data or idx >= 4:
                continue
            
            config = self.PARAMETERS[param]
            metrics = data['metrics']
            ax = axes[idx]
            
            # Use denormalized values if available
            if 'actuals_denorm' in data and 'predictions_denorm' in data:
                actuals = data['actuals_denorm']
                predictions = data['predictions_denorm']
            else:
                actuals = data['actuals']
                predictions = data['predictions']
            
            ax.scatter(actuals, predictions, alpha=0.6, s=50)
            
            min_val = min(min(actuals), min(predictions))
            max_val = max(max(actuals), max(predictions))
            ax.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='Perfect')
            
            ax.set_xlabel(f'Actual ({config["unit"]})', fontsize=11, fontweight='bold')
            ax.set_ylabel(f'Predicted ({config["unit"]})', fontsize=11, fontweight='bold')
            ax.set_title(config["name"], fontsize=13, fontweight='bold')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            # Add metrics text
            text_str = f"MAE: {metrics['mae']:.2f}\nR²: {metrics['r2']:.3f}\nMAPE: {metrics['mape']:.2f}%"
            ax.text(0.05, 0.95, text_str, transform=ax.transAxes, fontsize=9,
                   verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        plt.savefig(output_dir / 'multi_param_scatter.png', dpi=300, bbox_inches='tight')
        plt.close()
        print("  ✓ Scatter plots created")
        
        print(f"\n✅ All charts saved to: {output_dir}")
    
    def save_results(self, output_dir: str):
        """Save results to CSV and JSON."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save combined CSV
        all_data = []
        
        for param, data in self.results.items():
            if 'metrics' not in data:
                continue
            
            config = self.PARAMETERS[param]
            
            # Use denormalized values if available
            if 'actuals_denorm' in data and 'predictions_denorm' in data:
                actuals = data['actuals_denorm']
                predictions = data['predictions_denorm']
                residuals = data['residuals']  # Already denormalized
            else:
                actuals = data['actuals']
                predictions = data['predictions']
                residuals = data['residuals']
            
            for i in range(len(predictions)):
                row = {
                    'timestamp': data['timestamps'][i],
                    'location_id': data['location_ids'][i],
                    'parameter': config['name'],
                    'actual': actuals[i],
                    'predicted': predictions[i],
                    'residual': residuals[i],
                    'absolute_error': abs(residuals[i])
                }
                all_data.append(row)
        
        if all_data:
            df_results = pd.DataFrame(all_data)
            csv_file = output_dir / f"multi_param_evaluation_{timestamp}.csv"
            df_results.to_csv(csv_file, index=False)
            print(f"💾 Results saved to: {csv_file}")
        
        # Save metrics JSON
        metrics_summary = {
            'date': '2025-12-15',
            'timestamp': timestamp,
            'parameters': {}
        }
        
        for param, data in self.results.items():
            if 'metrics' in data:
                config = self.PARAMETERS[param]
                metrics_summary['parameters'][param] = {
                    'name': config['name'],
                    'unit': config['unit'],
                    'metrics': data['metrics']
                }
        
        metrics_file = output_dir / f"multi_param_metrics_{timestamp}.json"
        with open(metrics_file, 'w') as f:
            json.dump(metrics_summary, f, indent=2)
        print(f"💾 Metrics saved to: {metrics_file}")


def main():
    """Main evaluation pipeline."""
    print("\n" + "="*80)
    print("🔍 MULTI-PARAMETER MODEL EVALUATION - TODAY'S DATA")
    print("="*80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Paths
    base_dir = Path(__file__).parent.parent
    dataset_dir = base_dir / "dataset"
    preprocessed_dir = base_dir / "dataset" / "preprocessed"
    models_dir = Path(__file__).parent / "multi_params" / "models"
    output_dir = Path(__file__).parent / "multi_params_evaluation"
    
    preprocessor_stats = preprocessed_dir / "preprocessor_stats.json"
    
    # Initialize evaluator
    evaluator = MultiParameterEvaluator(
        models_dir=str(models_dir),
        preprocessor_stats_path=str(preprocessor_stats)
    )
    
    # Load today's data
    df_today = evaluator.load_todays_data(str(dataset_dir))
    
    if df_today.empty:
        print("❌ No data available for evaluation")
        return
    
    # Preprocess
    df_processed = evaluator.preprocess_for_prediction(df_today)
    
    # Make predictions
    evaluator.make_predictions(df_processed)
    
    # Print report
    evaluator.print_report()
    
    # Create visualizations
    evaluator.create_visualizations(str(output_dir))
    
    # Save results
    evaluator.save_results(str(output_dir))
    
    print("\n" + "="*80)
    print("🎉 MULTI-PARAMETER EVALUATION COMPLETE!")
    print("="*80)


if __name__ == "__main__":
    main()
