#!/usr/bin/env python3
"""
Multi-Parameter Training Module
================================

Trains separate ARF + ADWIN models for each environmental parameter:
- PM2.5
- PM10
- Temperature
- Relative Humidity
- Pressure
- PM1

Each model uses adaptive window sizes optimized for the parameter's characteristics.

Author: Bipul Kumar Dahal
Date: December 15, 2025
"""

import pandas as pd
import numpy as np
from pathlib import Path
import dill
import json
from datetime import datetime
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
import seaborn as sns
from river import forest, drift, metrics
import warnings
warnings.filterwarnings('ignore')

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")


class MultiParameterTrainer:
    """Train separate ARF + ADWIN models for multiple parameters."""
    
    # Parameter-specific ADWIN configurations
    PARAMETER_CONFIGS = {
        'pm25': {
            'name': 'PM2.5',
            'unit': 'µg/m³',
            'adwin_delta': 0.001,  # More sensitive - air quality changes rapidly
            'description': 'Fine Particulate Matter'
        },
        'pm10': {
            'name': 'PM10',
            'unit': 'µg/m³',
            'adwin_delta': 0.001,  # More sensitive
            'description': 'Coarse Particulate Matter'
        },
        'pm1': {
            'name': 'PM1',
            'unit': 'µg/m³',
            'adwin_delta': 0.001,  # More sensitive
            'description': 'Ultra-fine Particulate Matter'
        },
        'temperature': {
            'name': 'Temperature',
            'unit': '°C',
            'adwin_delta': 0.01,  # Less sensitive - temperature changes gradually
            'description': 'Ambient Temperature'
        },
        'relativehumidity': {
            'name': 'Relative Humidity',
            'unit': '%',
            'adwin_delta': 0.005,  # Moderate sensitivity
            'description': 'Relative Humidity'
        },
        'pressure': {
            'name': 'Pressure',
            'unit': 'hPa',
            'adwin_delta': 0.01,  # Less sensitive - pressure changes slowly
            'description': 'Atmospheric Pressure'
        }
    }
    
    def __init__(self, data_path: str, output_dir: str):
        """
        Initialize multi-parameter trainer.
        
        Parameters:
        -----------
        data_path : str
            Path to preprocessed training data
        output_dir : str
            Directory to save trained models and results
        """
        self.data_path = Path(data_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories for each parameter
        for param in self.PARAMETER_CONFIGS.keys():
            (self.output_dir / 'models' / param).mkdir(parents=True, exist_ok=True)
            (self.output_dir / 'logs' / param).mkdir(parents=True, exist_ok=True)
            (self.output_dir / 'charts' / param).mkdir(parents=True, exist_ok=True)
        
        self.models = {}
        self.results = {}
    
    def load_data(self) -> pd.DataFrame:
        """Load preprocessed training data."""
        print("="*80)
        print("📂 LOADING PREPROCESSED DATA")
        print("="*80)
        
        df = pd.read_csv(self.data_path)
        print(f"✅ Loaded {len(df)} samples")
        print(f"   Columns: {list(df.columns)}")
        print(f"   Date range: {df['datetime'].min()} to {df['datetime'].max()}")
        
        return df
    
    def create_model(self, parameter: str) -> Tuple[forest.ARFRegressor, drift.ADWIN]:
        """
        Create ARF model with ADWIN drift detector for a parameter.
        
        Parameters:
        -----------
        parameter : str
            Parameter name (e.g., 'pm25', 'temperature')
        
        Returns:
        --------
        tuple
            (model, drift_detector)
        """
        config = self.PARAMETER_CONFIGS[parameter]
        
        # Adaptive Random Forest
        model = forest.ARFRegressor(
            n_models=10,
            max_features='sqrt',
            lambda_value=6,
            drift_detector=None,  # We'll handle drift detection separately
            warning_detector=None,
            seed=42
        )
        
        # ADWIN Drift Detector with parameter-specific delta
        drift_detector = drift.ADWIN(delta=config['adwin_delta'])
        
        print(f"\n🌲 Created ARF model for {config['name']}")
        print(f"   Trees: 10")
        print(f"   ADWIN Delta: {config['adwin_delta']} ({'sensitive' if config['adwin_delta'] < 0.005 else 'moderate' if config['adwin_delta'] < 0.01 else 'stable'})")
        
        return model, drift_detector
    
    def prepare_features(self, df: pd.DataFrame, target: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Prepare features and target for a specific parameter.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Full dataset
        target : str
            Target parameter name
        
        Returns:
        --------
        tuple
            (X, y) - features and target
        """
        # Exclude target and other parameters from features
        exclude_cols = ['datetime', 'location_id', target]
        
        # Also exclude other target parameters (we don't want to use pm10 to predict pm25, etc.)
        other_params = [p for p in self.PARAMETER_CONFIGS.keys() if p != target]
        exclude_cols.extend(other_params)
        
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        
        X = df[feature_cols]
        y = df[target]
        
        return X, y
    
    def train_parameter_model(self, parameter: str, df: pd.DataFrame) -> Dict:
        """
        Train a single parameter model.
        
        Parameters:
        -----------
        parameter : str
            Parameter to train (e.g., 'pm25')
        df : pd.DataFrame
            Training data
        
        Returns:
        --------
        dict
            Training results and metrics
        """
        config = self.PARAMETER_CONFIGS[parameter]
        
        print("\n" + "="*80)
        print(f"🚀 TRAINING {config['name'].upper()} MODEL")
        print("="*80)
        
        # Prepare data
        X, y = self.prepare_features(df, parameter)
        
        print(f"\n📊 Data Shape:")
        print(f"   Features: {X.shape[1]}")
        print(f"   Samples: {len(X)}")
        print(f"   Target: {parameter} ({config['unit']})")
        print(f"   Target range: {y.min():.2f} - {y.max():.2f} {config['unit']}")
        
        # Create model
        model, drift_detector = self.create_model(parameter)
        
        # Training metrics
        mae_metric = metrics.MAE()
        rmse_metric = metrics.RMSE()
        r2_metric = metrics.R2()
        
        # Storage for tracking
        predictions = []
        actuals = []
        drift_points = []
        mae_history = []
        
        # Training loop
        print(f"\n⏳ Training in progress...")
        start_time = datetime.now()
        
        for idx in range(len(X)):
            x_dict = X.iloc[idx].to_dict()
            y_true = y.iloc[idx]
            
            # Skip NaN values
            if pd.isna(y_true) or any(pd.isna(v) for v in x_dict.values()):
                continue
            
            # Test-then-train
            y_pred = model.predict_one(x_dict)
            
            if y_pred is not None:
                # Calculate error
                error = abs(y_true - y_pred)
                
                # Update metrics
                mae_metric.update(y_true, y_pred)
                rmse_metric.update(y_true, y_pred)
                r2_metric.update(y_true, y_pred)
                
                # Store predictions
                predictions.append(y_pred)
                actuals.append(y_true)
                
                # Drift detection
                drift_detector.update(error)
                
                if drift_detector.drift_detected:
                    drift_points.append(len(predictions))
                    print(f"   🔄 Drift detected at sample {len(predictions)} (error: {error:.2f} {config['unit']})")
            
            # Train model
            model.learn_one(x_dict, y_true)
            
            # Track progress
            if (idx + 1) % 1000 == 0:
                current_mae = mae_metric.get()
                mae_history.append({
                    'sample': idx + 1,
                    'mae': current_mae,
                    'r2': r2_metric.get()
                })
                print(f"   Sample {idx+1}/{len(X)} - MAE: {current_mae:.2f} {config['unit']}, R²: {r2_metric.get():.3f}")
        
        training_time = (datetime.now() - start_time).total_seconds()
        
        # Final metrics
        final_mae = mae_metric.get()
        final_rmse = rmse_metric.get()
        final_r2 = r2_metric.get()
        
        # Calculate MAPE
        mape_values = [abs((actuals[i] - predictions[i]) / actuals[i]) * 100 
                      for i in range(len(actuals)) if actuals[i] != 0]
        final_mape = np.mean(mape_values) if mape_values else 0
        
        print(f"\n✅ Training Complete!")
        print(f"   Time: {training_time:.1f} seconds")
        print(f"   MAE: {final_mae:.2f} {config['unit']}")
        print(f"   RMSE: {final_rmse:.2f} {config['unit']}")
        print(f"   R²: {final_r2:.3f}")
        print(f"   MAPE: {final_mape:.2f}%")
        print(f"   Drift events: {len(drift_points)}")
        
        # Save model
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        model_path = self.output_dir / 'models' / parameter / f'{parameter}_model_{timestamp}.pkl'
        
        with open(model_path, 'wb') as f:
            dill.dump({
                'model': model,
                'drift_detector': drift_detector,
                'config': config,
                'feature_cols': list(X.columns)
            }, f)
        
        print(f"💾 Model saved: {model_path}")
        
        # Save training log
        log_data = {
            'parameter': parameter,
            'name': config['name'],
            'unit': config['unit'],
            'training_date': datetime.now().isoformat(),
            'training_time_seconds': training_time,
            'samples': len(predictions),
            'metrics': {
                'mae': float(final_mae),
                'rmse': float(final_rmse),
                'r2': float(final_r2),
                'mape': float(final_mape)
            },
            'drift_events': len(drift_points),
            'drift_points': drift_points,
            'adwin_delta': config['adwin_delta'],
            'target_range': {
                'min': float(y.min()),
                'max': float(y.max()),
                'mean': float(y.mean()),
                'std': float(y.std())
            }
        }
        
        log_path = self.output_dir / 'logs' / parameter / f'{parameter}_training_log_{timestamp}.json'
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        # Create visualizations
        self.create_visualizations(parameter, predictions, actuals, drift_points, mae_history, timestamp)
        
        return {
            'model': model,
            'metrics': log_data['metrics'],
            'drift_events': len(drift_points),
            'predictions': predictions,
            'actuals': actuals
        }
    
    def create_visualizations(self, parameter: str, predictions: List, actuals: List,
                            drift_points: List, mae_history: List, timestamp: str):
        """Create visualization charts for a parameter."""
        config = self.PARAMETER_CONFIGS[parameter]
        charts_dir = self.output_dir / 'charts' / parameter
        
        print(f"\n📊 Creating visualizations for {config['name']}...")
        
        # 1. Predictions vs Actual
        fig, ax = plt.subplots(figsize=(14, 6))
        
        sample_indices = range(len(predictions))
        ax.plot(sample_indices, actuals, 'b-', alpha=0.6, label='Actual', linewidth=1)
        ax.plot(sample_indices, predictions, 'r-', alpha=0.6, label='Predicted', linewidth=1)
        
        # Mark drift points
        for dp in drift_points:
            ax.axvline(x=dp, color='orange', linestyle='--', alpha=0.5, linewidth=1)
        
        ax.set_xlabel('Sample Index', fontsize=11, fontweight='bold')
        ax.set_ylabel(f'{config["name"]} ({config["unit"]})', fontsize=11, fontweight='bold')
        ax.set_title(f'{config["name"]} - Predictions vs Actual', fontsize=13, fontweight='bold')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(charts_dir / f'{parameter}_predictions_{timestamp}.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 2. Scatter plot
        fig, ax = plt.subplots(figsize=(10, 8))
        
        ax.scatter(actuals, predictions, alpha=0.5, s=20)
        
        min_val = min(min(actuals), min(predictions))
        max_val = max(max(actuals), max(predictions))
        ax.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='Perfect Prediction')
        
        ax.set_xlabel(f'Actual {config["name"]} ({config["unit"]})', fontsize=11, fontweight='bold')
        ax.set_ylabel(f'Predicted {config["name"]} ({config["unit"]})', fontsize=11, fontweight='bold')
        ax.set_title(f'{config["name"]} - Prediction Accuracy', fontsize=13, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(charts_dir / f'{parameter}_scatter_{timestamp}.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 3. MAE Evolution
        if mae_history:
            fig, ax = plt.subplots(figsize=(12, 6))
            
            samples = [h['sample'] for h in mae_history]
            maes = [h['mae'] for h in mae_history]
            
            ax.plot(samples, maes, 'b-', linewidth=2)
            ax.set_xlabel('Sample Index', fontsize=11, fontweight='bold')
            ax.set_ylabel(f'MAE ({config["unit"]})', fontsize=11, fontweight='bold')
            ax.set_title(f'{config["name"]} - MAE Evolution During Training', fontsize=13, fontweight='bold')
            ax.grid(True, alpha=0.3)
            
            plt.tight_layout()
            plt.savefig(charts_dir / f'{parameter}_mae_evolution_{timestamp}.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        print(f"   ✓ Charts saved to {charts_dir}")
    
    def train_all_parameters(self, df: pd.DataFrame):
        """Train models for all parameters."""
        print("\n" + "="*80)
        print("🚀 MULTI-PARAMETER TRAINING PIPELINE")
        print("="*80)
        print(f"\nTraining {len(self.PARAMETER_CONFIGS)} parameter models:")
        for param, config in self.PARAMETER_CONFIGS.items():
            print(f"   - {config['name']} ({config['unit']})")
        
        overall_start = datetime.now()
        
        for parameter in self.PARAMETER_CONFIGS.keys():
            if parameter in df.columns:
                result = self.train_parameter_model(parameter, df)
                self.results[parameter] = result
            else:
                print(f"\n⚠️  Warning: {parameter} not found in dataset, skipping...")
        
        total_time = (datetime.now() - overall_start).total_seconds()
        
        # Print summary
        print("\n" + "="*80)
        print("📊 TRAINING SUMMARY - ALL PARAMETERS")
        print("="*80)
        print(f"\nTotal training time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
        print(f"Models trained: {len(self.results)}/{len(self.PARAMETER_CONFIGS)}")
        print()
        
        for parameter, result in self.results.items():
            config = self.PARAMETER_CONFIGS[parameter]
            metrics = result['metrics']
            
            print(f"📌 {config['name']} ({config['unit']})")
            print(f"   MAE:  {metrics['mae']:.2f}")
            print(f"   RMSE: {metrics['rmse']:.2f}")
            print(f"   R²:   {metrics['r2']:.3f}")
            print(f"   MAPE: {metrics['mape']:.2f}%")
            print(f"   Drift events: {result['drift_events']}")
            print()
        
        # Save overall summary
        summary = {
            'training_date': datetime.now().isoformat(),
            'total_time_seconds': total_time,
            'parameters_trained': list(self.results.keys()),
            'results': {
                param: {
                    'metrics': result['metrics'],
                    'drift_events': result['drift_events']
                }
                for param, result in self.results.items()
            }
        }
        
        summary_path = self.output_dir / 'training_summary.json'
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"💾 Summary saved: {summary_path}")
        print("\n" + "="*80)
        print("✅ ALL MODELS TRAINED SUCCESSFULLY!")
        print("="*80)


def main():
    """Main training pipeline."""
    print("\n" + "="*80)
    print("🌟 MULTI-PARAMETER TRAINING - ARF + ADWIN")
    print("="*80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Paths
    base_dir = Path(__file__).parent.parent
    data_path = base_dir / "dataset" / "preprocessed" / "train_data.csv"
    output_dir = Path(__file__).parent / "multi_params"
    
    # Initialize trainer
    trainer = MultiParameterTrainer(
        data_path=str(data_path),
        output_dir=str(output_dir)
    )
    
    # Load data
    df = trainer.load_data()
    
    # Train all parameters
    trainer.train_all_parameters(df)
    
    print("\n🎉 Training pipeline complete!")


if __name__ == "__main__":
    main()
