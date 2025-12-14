#!/usr/bin/env python3
"""
Adaptive Random Forest Training Module with ADWIN Drift Detection
===================================================================

This module trains an Adaptive Random Forest Regressor with ADWIN drift detection
for air quality forecasting. It uses online/streaming learning to continuously
adapt to changing patterns in the data.

Features:
- Adaptive Random Forest with 10 models
- ADWIN drift detection for automatic model adaptation
- Comprehensive metrics logging (MAE, RMSE, R², MAPE)
- Visualization of predictions, residuals, and drift events
- Feature importance tracking
- Model persistence for production deployment

Author: Bipul Kumar Dahal
Date: December 14, 2025
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json
import warnings
warnings.filterwarnings('ignore')

# River library for online learning
from river import forest, drift, metrics as river_metrics
import dill  # Better than pickle for complex objects

# Visualization
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.dates import DateFormatter

# Set style for beautiful plots
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")


class StreamingTrainer:
    """
    Online learning trainer for Adaptive Random Forest with drift detection.
    """
    
    def __init__(
        self,
        n_models: int = 10,
        max_depth: int = None,
        drift_detector = None,
        seed: int = 42
    ):
        """
        Initialize the streaming trainer.
        
        Parameters:
        -----------
        n_models : int
            Number of trees in the forest (default: 10)
        max_depth : int
            Maximum depth of trees (None = unlimited)
        drift_detector : river drift detector
            Drift detector (default: ADWIN with delta=0.002)
        seed : int
            Random seed for reproducibility
        """
        self.n_models = n_models
        self.max_depth = max_depth
        self.seed = seed
        
        # Initialize drift detector
        if drift_detector is None:
            self.drift_detector = drift.ADWIN(delta=0.002)
        else:
            self.drift_detector = drift_detector
        
        # Initialize Adaptive Random Forest
        self.model = forest.ARFRegressor(
            n_models=n_models,
            max_depth=max_depth,
            seed=seed,
            drift_detector=self.drift_detector
        )
        
        # Metrics tracking
        self.metrics_history = {
            'mae': [],
            'rmse': [],
            'r2': [],
            'mape': [],
            'timestamp': [],
            'sample_count': []
        }
        
        # Predictions tracking
        self.predictions = []
        self.actuals = []
        self.timestamps = []
        self.residuals = []
        
        # Drift detection tracking
        self.drift_events = []
        self.drift_positions = []
        
        # River metrics for online evaluation
        self.mae_metric = river_metrics.MAE()
        self.rmse_metric = river_metrics.RMSE()
        self.r2_metric = river_metrics.R2()
        
        # Training statistics
        self.samples_processed = 0
        self.training_start_time = None
        self.training_end_time = None
        
    def calculate_mape(self, y_true: float, y_pred: float) -> float:
        """Calculate Mean Absolute Percentage Error."""
        if y_true == 0:
            return 0
        return abs((y_true - y_pred) / y_true) * 100
    
    def train_stream(
        self,
        df: pd.DataFrame,
        feature_cols: list,
        target_col: str = 'aqi',
        log_interval: int = 100
    ):
        """
        Train the model on streaming data.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Training data (preprocessed)
        feature_cols : list
            List of feature column names
        target_col : str
            Target column name
        log_interval : int
            Log metrics every N samples
        """
        print("="*80)
        print("🚀 STARTING ADAPTIVE RANDOM FOREST TRAINING")
        print("="*80)
        print(f"📊 Training samples: {len(df):,}")
        print(f"🌳 Number of trees: {self.n_models}")
        print(f"📏 Features: {len(feature_cols)}")
        print(f"🎯 Target: {target_col}")
        print(f"🔍 Drift detector: ADWIN (delta={self.drift_detector.delta})")
        print("="*80)
        
        self.training_start_time = datetime.now()
        
        # Ensure data is sorted by time
        if 'datetime' in df.columns:
            df = df.sort_values('datetime').reset_index(drop=True)
            self.timestamps = df['datetime'].tolist()
        
        # Streaming training loop
        for idx, row in df.iterrows():
            # Prepare features
            x = {col: row[col] for col in feature_cols}
            y_true = row[target_col]
            
            # Make prediction before learning (test-then-train)
            y_pred = self.model.predict_one(x)
            
            # Update model with new sample (online learning)
            self.model.learn_one(x, y_true)
            
            # Update metrics
            if y_pred is not None:
                self.mae_metric.update(y_true, y_pred)
                self.rmse_metric.update(y_true, y_pred)
                self.r2_metric.update(y_true, y_pred)
                
                # Store predictions and actuals
                self.predictions.append(y_pred)
                self.actuals.append(y_true)
                residual = y_true - y_pred
                self.residuals.append(residual)
                
                # Check for drift
                self.drift_detector.update(residual)
                if self.drift_detector.drift_detected:
                    self.drift_events.append({
                        'sample': self.samples_processed,
                        'timestamp': self.timestamps[idx] if idx < len(self.timestamps) else None,
                        'mae': self.mae_metric.get(),
                        'residual': residual
                    })
                    self.drift_positions.append(self.samples_processed)
                    print(f"⚠️  DRIFT DETECTED at sample {self.samples_processed:,}")
            
            self.samples_processed += 1
            
            # Log progress
            if self.samples_processed % log_interval == 0:
                mae = self.mae_metric.get()
                rmse = self.rmse_metric.get()
                r2 = self.r2_metric.get()
                
                # Calculate MAPE for recent predictions
                mape_values = [
                    self.calculate_mape(self.actuals[i], self.predictions[i])
                    for i in range(max(0, len(self.actuals) - log_interval), len(self.actuals))
                ]
                mape = np.mean(mape_values) if mape_values else 0
                
                # Store metrics
                self.metrics_history['mae'].append(mae)
                self.metrics_history['rmse'].append(rmse)
                self.metrics_history['r2'].append(r2)
                self.metrics_history['mape'].append(mape)
                self.metrics_history['sample_count'].append(self.samples_processed)
                if idx < len(self.timestamps):
                    self.metrics_history['timestamp'].append(self.timestamps[idx])
                else:
                    self.metrics_history['timestamp'].append(None)
                
                print(f"[{self.samples_processed:>6,}] MAE: {mae:>7.2f} | RMSE: {rmse:>7.2f} | R²: {r2:>6.3f} | MAPE: {mape:>6.2f}%")
        
        self.training_end_time = datetime.now()
        training_duration = (self.training_end_time - self.training_start_time).total_seconds()
        
        print("\n" + "="*80)
        print("✅ TRAINING COMPLETE!")
        print("="*80)
        print(f"⏱️  Training time: {training_duration:.2f} seconds")
        print(f"📊 Samples processed: {self.samples_processed:,}")
        print(f"🔍 Drift events detected: {len(self.drift_events)}")
        print(f"\n📈 Final Metrics:")
        print(f"   MAE:  {self.mae_metric.get():.2f}")
        print(f"   RMSE: {self.rmse_metric.get():.2f}")
        print(f"   R²:   {self.r2_metric.get():.3f}")
        print("="*80)
    
    def evaluate(
        self,
        df: pd.DataFrame,
        feature_cols: list,
        target_col: str = 'aqi'
    ) -> dict:
        """
        Evaluate the model on test data.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Test data
        feature_cols : list
            Feature column names
        target_col : str
            Target column name
        
        Returns:
        --------
        dict
            Evaluation metrics
        """
        print("\n" + "="*80)
        print("🧪 EVALUATING ON TEST SET")
        print("="*80)
        print(f"Test samples: {len(df):,}")
        
        predictions = []
        actuals = []
        
        for idx, row in df.iterrows():
            x = {col: row[col] for col in feature_cols}
            y_true = row[target_col]
            y_pred = self.model.predict_one(x)
            
            if y_pred is not None:
                predictions.append(y_pred)
                actuals.append(y_true)
        
        # Calculate metrics
        mae = np.mean(np.abs(np.array(actuals) - np.array(predictions)))
        rmse = np.sqrt(np.mean((np.array(actuals) - np.array(predictions))**2))
        
        # R² score
        ss_res = np.sum((np.array(actuals) - np.array(predictions))**2)
        ss_tot = np.sum((np.array(actuals) - np.mean(actuals))**2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        # MAPE
        mape_values = [
            abs((actuals[i] - predictions[i]) / actuals[i]) * 100
            for i in range(len(actuals))
            if actuals[i] != 0
        ]
        mape = np.mean(mape_values) if mape_values else 0
        
        results = {
            'mae': mae,
            'rmse': rmse,
            'r2': r2,
            'mape': mape,
            'predictions': predictions,
            'actuals': actuals
        }
        
        print(f"\n📊 Test Set Metrics:")
        print(f"   MAE:  {mae:.2f}")
        print(f"   RMSE: {rmse:.2f}")
        print(f"   R²:   {r2:.3f}")
        print(f"   MAPE: {mape:.2f}%")
        print("="*80)
        
        return results
    
    def save_model(self, filepath: str):
        """Save the trained model."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'wb') as f:
            dill.dump(self.model, f)
        
        print(f"💾 Model saved to: {filepath}")
    
    def load_model(self, filepath: str):
        """Load a trained model."""
        with open(filepath, 'rb') as f:
            self.model = dill.load(f)
        
        print(f"📂 Model loaded from: {filepath}")
    
    def save_logs(self, output_dir: str):
        """Save training logs to JSON and CSV."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create comprehensive log
        log_data = {
            'training_summary': {
                'start_time': self.training_start_time.isoformat() if self.training_start_time else None,
                'end_time': self.training_end_time.isoformat() if self.training_end_time else None,
                'duration_seconds': (self.training_end_time - self.training_start_time).total_seconds() if self.training_start_time and self.training_end_time else None,
                'samples_processed': self.samples_processed,
                'n_models': self.n_models,
                'max_depth': self.max_depth,
                'seed': self.seed
            },
            'final_metrics': {
                'mae': self.mae_metric.get(),
                'rmse': self.rmse_metric.get(),
                'r2': self.r2_metric.get()
            },
            'drift_detection': {
                'total_drift_events': len(self.drift_events),
                'drift_events': self.drift_events
            }
        }
        
        # Save JSON log
        json_file = output_dir / f"training_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(json_file, 'w') as f:
            json.dump(log_data, f, indent=2, default=str)
        print(f"📝 Training log saved to: {json_file}")
        
        # Save metrics history as CSV
        if self.metrics_history['mae']:
            metrics_df = pd.DataFrame(self.metrics_history)
            csv_file = output_dir / f"metrics_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            metrics_df.to_csv(csv_file, index=False)
            print(f"📊 Metrics history saved to: {csv_file}")
        
        # Save predictions vs actuals
        if self.predictions:
            pred_df = pd.DataFrame({
                'timestamp': self.timestamps[:len(self.predictions)],
                'actual': self.actuals,
                'predicted': self.predictions,
                'residual': self.residuals
            })
            pred_file = output_dir / f"predictions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            pred_df.to_csv(pred_file, index=False)
            print(f"🎯 Predictions saved to: {pred_file}")


class VisualizationModule:
    """
    Create comprehensive visualizations for model performance.
    """
    
    @staticmethod
    def create_all_charts(trainer: StreamingTrainer, output_dir: str, dpi: int = 300):
        """
        Generate all visualization charts.
        
        Parameters:
        -----------
        trainer : StreamingTrainer
            Trained model with metrics
        output_dir : str
            Directory to save charts
        dpi : int
            Resolution for saved images
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print("\n" + "="*80)
        print("📊 GENERATING VISUALIZATIONS")
        print("="*80)
        
        # 1. Predictions vs Actual
        VisualizationModule.plot_predictions_vs_actual(trainer, output_dir, dpi)
        
        # 2. Residuals Analysis
        VisualizationModule.plot_residuals(trainer, output_dir, dpi)
        
        # 3. Metrics Over Time
        VisualizationModule.plot_metrics_evolution(trainer, output_dir, dpi)
        
        # 4. Drift Events
        VisualizationModule.plot_drift_events(trainer, output_dir, dpi)
        
        # 5. Error Distribution
        VisualizationModule.plot_error_distribution(trainer, output_dir, dpi)
        
        # 6. Time Series Comparison
        VisualizationModule.plot_time_series_comparison(trainer, output_dir, dpi)
        
        print("="*80)
        print(f"✅ All charts saved to: {output_dir}")
        print("="*80)
    
    @staticmethod
    def plot_predictions_vs_actual(trainer: StreamingTrainer, output_dir: Path, dpi: int):
        """Scatter plot: Predictions vs Actual values."""
        fig, ax = plt.subplots(figsize=(10, 8))
        
        ax.scatter(trainer.actuals, trainer.predictions, alpha=0.5, s=20)
        
        # Perfect prediction line
        min_val = min(min(trainer.actuals), min(trainer.predictions))
        max_val = max(max(trainer.actuals), max(trainer.predictions))
        ax.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='Perfect Prediction')
        
        ax.set_xlabel('Actual AQI', fontsize=12, fontweight='bold')
        ax.set_ylabel('Predicted AQI', fontsize=12, fontweight='bold')
        ax.set_title('Predictions vs Actual Values', fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Add metrics text
        mae = trainer.mae_metric.get()
        rmse = trainer.rmse_metric.get()
        r2 = trainer.r2_metric.get()
        
        text_str = f'MAE: {mae:.2f}\nRMSE: {rmse:.2f}\nR²: {r2:.3f}'
        ax.text(0.05, 0.95, text_str, transform=ax.transAxes, fontsize=10,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        plt.savefig(output_dir / '01_predictions_vs_actual.png', dpi=dpi, bbox_inches='tight')
        plt.close()
        print("  ✓ Predictions vs Actual chart created")
    
    @staticmethod
    def plot_residuals(trainer: StreamingTrainer, output_dir: Path, dpi: int):
        """Residuals plot over time."""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        
        # Residuals over time
        if trainer.timestamps:
            timestamps = pd.to_datetime(trainer.timestamps[:len(trainer.residuals)])
            ax1.scatter(timestamps, trainer.residuals, alpha=0.5, s=10)
            ax1.axhline(y=0, color='r', linestyle='--', linewidth=2)
            ax1.set_xlabel('Time', fontsize=12, fontweight='bold')
        else:
            ax1.scatter(range(len(trainer.residuals)), trainer.residuals, alpha=0.5, s=10)
            ax1.axhline(y=0, color='r', linestyle='--', linewidth=2)
            ax1.set_xlabel('Sample', fontsize=12, fontweight='bold')
        
        ax1.set_ylabel('Residual (Actual - Predicted)', fontsize=12, fontweight='bold')
        ax1.set_title('Residuals Over Time', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        
        # Residuals vs Predicted
        ax2.scatter(trainer.predictions, trainer.residuals, alpha=0.5, s=10)
        ax2.axhline(y=0, color='r', linestyle='--', linewidth=2)
        ax2.set_xlabel('Predicted AQI', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Residual', fontsize=12, fontweight='bold')
        ax2.set_title('Residuals vs Predicted Values', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_dir / '02_residuals_analysis.png', dpi=dpi, bbox_inches='tight')
        plt.close()
        print("  ✓ Residuals analysis chart created")
    
    @staticmethod
    def plot_metrics_evolution(trainer: StreamingTrainer, output_dir: Path, dpi: int):
        """Plot how metrics evolve during training."""
        if not trainer.metrics_history['mae']:
            return
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        
        samples = trainer.metrics_history['sample_count']
        
        # MAE
        ax1.plot(samples, trainer.metrics_history['mae'], linewidth=2, color='#e74c3c')
        ax1.set_xlabel('Samples Processed', fontsize=11, fontweight='bold')
        ax1.set_ylabel('MAE', fontsize=11, fontweight='bold')
        ax1.set_title('Mean Absolute Error Evolution', fontsize=13, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        
        # RMSE
        ax2.plot(samples, trainer.metrics_history['rmse'], linewidth=2, color='#3498db')
        ax2.set_xlabel('Samples Processed', fontsize=11, fontweight='bold')
        ax2.set_ylabel('RMSE', fontsize=11, fontweight='bold')
        ax2.set_title('Root Mean Squared Error Evolution', fontsize=13, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        
        # R²
        ax3.plot(samples, trainer.metrics_history['r2'], linewidth=2, color='#2ecc71')
        ax3.set_xlabel('Samples Processed', fontsize=11, fontweight='bold')
        ax3.set_ylabel('R² Score', fontsize=11, fontweight='bold')
        ax3.set_title('R² Score Evolution', fontsize=13, fontweight='bold')
        ax3.grid(True, alpha=0.3)
        
        # MAPE
        ax4.plot(samples, trainer.metrics_history['mape'], linewidth=2, color='#f39c12')
        ax4.set_xlabel('Samples Processed', fontsize=11, fontweight='bold')
        ax4.set_ylabel('MAPE (%)', fontsize=11, fontweight='bold')
        ax4.set_title('Mean Absolute Percentage Error Evolution', fontsize=13, fontweight='bold')
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_dir / '03_metrics_evolution.png', dpi=dpi, bbox_inches='tight')
        plt.close()
        print("  ✓ Metrics evolution chart created")
    
    @staticmethod
    def plot_drift_events(trainer: StreamingTrainer, output_dir: Path, dpi: int):
        """Mark drift detection events on the prediction timeline."""
        if not trainer.predictions:
            return
        
        fig, ax = plt.subplots(figsize=(16, 6))
        
        if trainer.timestamps:
            timestamps = pd.to_datetime(trainer.timestamps[:len(trainer.predictions)])
            ax.plot(timestamps, trainer.actuals, label='Actual AQI', linewidth=1.5, alpha=0.7)
            ax.plot(timestamps, trainer.predictions, label='Predicted AQI', linewidth=1.5, alpha=0.7)
            
            # Mark drift events
            for drift in trainer.drift_events:
                if drift['timestamp'] and drift['sample'] < len(timestamps):
                    ax.axvline(x=timestamps[drift['sample']], color='red', linestyle='--', 
                              linewidth=2, alpha=0.7)
        else:
            samples = range(len(trainer.predictions))
            ax.plot(samples, trainer.actuals, label='Actual AQI', linewidth=1.5, alpha=0.7)
            ax.plot(samples, trainer.predictions, label='Predicted AQI', linewidth=1.5, alpha=0.7)
            
            # Mark drift events
            for pos in trainer.drift_positions:
                ax.axvline(x=pos, color='red', linestyle='--', linewidth=2, alpha=0.7, 
                          label='Drift Detected' if pos == trainer.drift_positions[0] else '')
        
        ax.set_xlabel('Time', fontsize=12, fontweight='bold')
        ax.set_ylabel('AQI', fontsize=12, fontweight='bold')
        ax.set_title(f'Drift Detection Events (Total: {len(trainer.drift_events)})', 
                    fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_dir / '04_drift_events.png', dpi=dpi, bbox_inches='tight')
        plt.close()
        print(f"  ✓ Drift events chart created ({len(trainer.drift_events)} events)")
    
    @staticmethod
    def plot_error_distribution(trainer: StreamingTrainer, output_dir: Path, dpi: int):
        """Histogram of prediction errors."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # Residuals distribution
        ax1.hist(trainer.residuals, bins=50, edgecolor='black', alpha=0.7, color='#3498db')
        ax1.axvline(x=0, color='red', linestyle='--', linewidth=2)
        ax1.set_xlabel('Residual', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Frequency', fontsize=12, fontweight='bold')
        ax1.set_title('Distribution of Residuals', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3, axis='y')
        
        # Add statistics
        mean_residual = np.mean(trainer.residuals)
        std_residual = np.std(trainer.residuals)
        text_str = f'Mean: {mean_residual:.2f}\nStd: {std_residual:.2f}'
        ax1.text(0.05, 0.95, text_str, transform=ax1.transAxes, fontsize=10,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        # Absolute errors distribution
        abs_errors = np.abs(trainer.residuals)
        ax2.hist(abs_errors, bins=50, edgecolor='black', alpha=0.7, color='#e74c3c')
        ax2.set_xlabel('Absolute Error', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Frequency', fontsize=12, fontweight='bold')
        ax2.set_title('Distribution of Absolute Errors', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='y')
        
        # Add statistics
        mean_abs_error = np.mean(abs_errors)
        median_abs_error = np.median(abs_errors)
        text_str = f'Mean: {mean_abs_error:.2f}\nMedian: {median_abs_error:.2f}'
        ax2.text(0.65, 0.95, text_str, transform=ax2.transAxes, fontsize=10,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        plt.savefig(output_dir / '05_error_distribution.png', dpi=dpi, bbox_inches='tight')
        plt.close()
        print("  ✓ Error distribution chart created")
    
    @staticmethod
    def plot_time_series_comparison(trainer: StreamingTrainer, output_dir: Path, dpi: int):
        """Detailed time series comparison with confidence bands."""
        if not trainer.timestamps:
            return
        
        fig, ax = plt.subplots(figsize=(16, 8))
        
        timestamps = pd.to_datetime(trainer.timestamps[:len(trainer.predictions)])
        
        # Plot actual and predicted
        ax.plot(timestamps, trainer.actuals, label='Actual AQI', linewidth=2, color='#2c3e50', alpha=0.8)
        ax.plot(timestamps, trainer.predictions, label='Predicted AQI', linewidth=2, color='#e74c3c', alpha=0.8)
        
        # Add confidence band (±1 std of residuals)
        predictions_array = np.array(trainer.predictions)
        std_residual = np.std(trainer.residuals)
        ax.fill_between(timestamps, 
                        predictions_array - std_residual, 
                        predictions_array + std_residual,
                        alpha=0.2, color='#e74c3c', label='±1σ confidence')
        
        ax.set_xlabel('Time', fontsize=12, fontweight='bold')
        ax.set_ylabel('AQI', fontsize=12, fontweight='bold')
        ax.set_title('Time Series: Actual vs Predicted AQI with Confidence Band', 
                    fontsize=14, fontweight='bold')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.savefig(output_dir / '06_time_series_comparison.png', dpi=dpi, bbox_inches='tight')
        plt.close()
        print("  ✓ Time series comparison chart created")


def main():
    """
    Main training pipeline.
    """
    print("\n" + "="*80)
    print("AIR QUALITY FORECASTING WITH ADAPTIVE RANDOM FOREST + ADWIN")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Paths
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "dataset" / "preprocessed"
    train_file = data_dir / "train_data.csv"
    test_file = data_dir / "test_data.csv"
    
    # Output directories
    models_dir = Path(__file__).parent / "models"
    logs_dir = Path(__file__).parent / "logs"
    charts_dir = Path(__file__).parent / "charts"
    
    # Load training data
    print(f"\n📂 Loading training data from: {train_file}")
    train_df = pd.read_csv(train_file)
    print(f"✅ Loaded {len(train_df):,} training samples")
    
    # Load test data
    print(f"📂 Loading test data from: {test_file}")
    test_df = pd.read_csv(test_file)
    print(f"✅ Loaded {len(test_df):,} test samples")
    
    # Define feature columns (exclude metadata and target)
    exclude_cols = ['location_id', 'datetime', 'aqi', 'day', 'month', 'day_of_week']
    feature_cols = [col for col in train_df.columns if col not in exclude_cols]
    
    print(f"\n🔧 Configuration:")
    print(f"   Features: {len(feature_cols)}")
    print(f"   Target: aqi")
    print(f"   Model: Adaptive Random Forest (10 trees)")
    print(f"   Drift Detector: ADWIN (delta=0.002)")
    
    # Initialize trainer
    trainer = StreamingTrainer(
        n_models=10,
        max_depth=None,
        seed=42
    )
    
    # Train the model
    trainer.train_stream(
        df=train_df,
        feature_cols=feature_cols,
        target_col='aqi',
        log_interval=100
    )
    
    # Evaluate on test set
    test_results = trainer.evaluate(
        df=test_df,
        feature_cols=feature_cols,
        target_col='aqi'
    )
    
    # Save model
    model_file = models_dir / f"arf_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
    trainer.save_model(str(model_file))
    
    # Save logs
    trainer.save_logs(str(logs_dir))
    
    # Generate visualizations
    VisualizationModule.create_all_charts(trainer, str(charts_dir), dpi=300)
    
    print("\n" + "="*80)
    print("🎉 TRAINING PIPELINE COMPLETE!")
    print("="*80)
    print(f"📊 Final Training Metrics:")
    print(f"   MAE:  {trainer.mae_metric.get():.2f}")
    print(f"   RMSE: {trainer.rmse_metric.get():.2f}")
    print(f"   R²:   {trainer.r2_metric.get():.3f}")
    print(f"\n📊 Test Set Metrics:")
    print(f"   MAE:  {test_results['mae']:.2f}")
    print(f"   RMSE: {test_results['rmse']:.2f}")
    print(f"   R²:   {test_results['r2']:.3f}")
    print(f"   MAPE: {test_results['mape']:.2f}%")
    print(f"\n🔍 Drift Detection:")
    print(f"   Events: {len(trainer.drift_events)}")
    print(f"\n💾 Outputs:")
    print(f"   Model: {model_file}")
    print(f"   Logs: {logs_dir}")
    print(f"   Charts: {charts_dir}")
    print("="*80)
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)


if __name__ == "__main__":
    main()
