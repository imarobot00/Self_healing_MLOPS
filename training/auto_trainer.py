#!/usr/bin/env python3
"""
Auto-Trainer Module for Self-Healing MLOps
===========================================

Automatically detects drift and triggers model retraining when needed.
Uses latest data from all locations to train a fresh model.

Features:
- Drift-based retraining trigger
- Automatic data loading from all locations
- Full preprocessing and feature engineering
- Model versioning with timestamps
- Comprehensive logging and metrics tracking

Author: Bipul Kumar Dahal
Date: January 6, 2026
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# River library for online learning
from river import forest, drift, metrics as river_metrics
import dill

# Add parent directories to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import with absolute paths
import importlib.util

# Load FeatureEngineer
fe_spec = importlib.util.spec_from_file_location(
    "feature_engineer",
    project_root / "api" / "feature_engineer.py"
)
fe_module = importlib.util.module_from_spec(fe_spec)
fe_spec.loader.exec_module(fe_module)
FeatureEngineer = fe_module.FeatureEngineer

# Load DriftDetector  
dd_spec = importlib.util.spec_from_file_location(
    "drift_detector",
    project_root / "monitoring" / "drift_detector.py"
)
dd_module = importlib.util.module_from_spec(dd_spec)
dd_spec.loader.exec_module(dd_module)
DriftDetector = dd_module.DriftDetector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AutoTrainer:
    """
    Automatic training system that monitors drift and retrains when needed.
    """
    
    def __init__(
        self,
        data_dir: str = "dataset",
        models_dir: str = "training/models",
        drift_config_path: str = "monitoring/drift_config.yaml",
        drift_threshold: float = 0.15,
        min_samples: int = 1000,
        min_hours_between_retrains: int = 24
    ):
        """
        Initialize the auto-trainer.
        
        Parameters:
        -----------
        data_dir : str
            Directory containing location JSON files
        models_dir : str
            Directory to save trained models
        drift_config_path : str
            Path to drift detection config
        drift_threshold : float
            Drift score threshold to trigger retraining (default: 0.15)
        min_samples : int
            Minimum samples required for training (default: 1000)
        min_hours_between_retrains : int
            Minimum hours between retraining runs (default: 24)
        """
        self.data_dir = Path(data_dir)
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(exist_ok=True, parents=True)
        
        self.drift_threshold = drift_threshold
        self.min_samples = min_samples
        self.min_hours_between_retrains = min_hours_between_retrains
        
        # Initialize drift detector
        self.drift_detector = DriftDetector(config_path=drift_config_path)
        
        # Initialize feature engineer
        self.feature_engineer = FeatureEngineer(data_dir=str(self.data_dir))
        
        # Training statistics
        self.last_retrain_time = self._get_last_retrain_time()
        
        logger.info(f"AutoTrainer initialized")
        logger.info(f"Data directory: {self.data_dir}")
        logger.info(f"Models directory: {self.models_dir}")
        logger.info(f"Drift threshold: {self.drift_threshold}")
        logger.info(f"Last retrain: {self.last_retrain_time}")
    
    def _get_last_retrain_time(self) -> Optional[datetime]:
        """Get timestamp of last retraining from model metadata."""
        try:
            # Find most recent model directory
            model_dirs = sorted([d for d in self.models_dir.glob("model_*") if d.is_dir()])
            if not model_dirs:
                return None
            
            latest_model = model_dirs[-1]
            metadata_file = latest_model / "metadata.json"
            
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    return datetime.fromisoformat(metadata.get('created_at', ''))
        except Exception as e:
            logger.warning(f"Could not get last retrain time: {e}")
        
        return None
    
    def should_retrain(self) -> Tuple[bool, Dict]:
        """
        Check if retraining is needed based on drift and time constraints.
        
        Returns:
        --------
        (should_retrain, reason_dict) : Tuple[bool, Dict]
            Boolean indicating if retraining should happen and reasons
        """
        reasons = {
            'drift_score': None,
            'drift_exceeded': False,
            'time_since_last_retrain': None,
            'time_constraint_met': True,
            'decision': 'no_retrain'
        }
        
        # Check drift score
        try:
            drift_result = self.drift_detector.run_drift_check(days=7)
        except Exception as e:
            logger.error(f"Error running drift check: {e}")
            reasons['decision'] = 'error_drift_calculation'
            return False, reasons

        # run_drift_check returns an error dict (no score) when the baseline or recent
        # prediction data is missing — treat that as "can't decide", not a crash.
        if 'overall_drift_score' not in drift_result:
            reason = drift_result.get('error', 'drift score unavailable')
            logger.warning(f"⏸️  Skipping drift check: {reason}")
            reasons['decision'] = 'drift_data_unavailable'
            return False, reasons

        drift_score = drift_result['overall_drift_score']
        reasons['drift_score'] = drift_score
        reasons['drift_exceeded'] = drift_score > self.drift_threshold
        logger.info(f"Current drift score: {drift_score:.4f} (threshold: {self.drift_threshold})")
        
        # Check time since last retrain
        if self.last_retrain_time:
            time_since = datetime.now() - self.last_retrain_time
            hours_since = time_since.total_seconds() / 3600
            reasons['time_since_last_retrain'] = hours_since
            reasons['time_constraint_met'] = hours_since >= self.min_hours_between_retrains
            
            logger.info(f"Hours since last retrain: {hours_since:.1f} (minimum: {self.min_hours_between_retrains})")
        
        # Decision logic
        if reasons['drift_exceeded'] and reasons['time_constraint_met']:
            reasons['decision'] = 'retrain_needed'
            logger.info("✅ Retraining needed: Drift exceeded and time constraint met")
            return True, reasons
        elif reasons['drift_exceeded'] and not reasons['time_constraint_met']:
            reasons['decision'] = 'drift_but_too_soon'
            logger.info(f"⏳ Drift exceeded but retraining too soon (wait {self.min_hours_between_retrains - reasons['time_since_last_retrain']:.1f} more hours)")
            return False, reasons
        else:
            reasons['decision'] = 'no_retrain_needed'
            logger.info("✅ No retraining needed: Drift within acceptable range")
            return False, reasons
    
    def load_all_location_data(self) -> pd.DataFrame:
        """
        Load preprocessed training data.
        
        Returns:
        --------
        pd.DataFrame : Training data with all features
        """
        logger.info("Loading preprocessed training data...")
        
        # Try preprocessed data first
        preprocessed_file = self.data_dir / "preprocessed" / "train_data.csv"
        
        if preprocessed_file.exists():
            logger.info(f"Loading from {preprocessed_file}")
            df = pd.read_csv(preprocessed_file)
            df['datetime'] = pd.to_datetime(df['datetime'])
            
            logger.info(f"✅ Loaded {len(df):,} samples from preprocessed data")
            logger.info(f"   Date range: {df['datetime'].min()} to {df['datetime'].max()}")
            logger.info(f"   Features: {len(df.columns)}")
            
            return df
        
        # Fallback: Use existing train data in training/
        train_file = Path("training") / "train_data.csv"
        if train_file.exists():
            logger.info(f"Loading from {train_file}")
            df = pd.read_csv(train_file)
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'])
            
            logger.info(f"✅ Loaded {len(df):,} samples from training data")
            return df
        
        raise FileNotFoundError(
            f"No training data found. Please run data preprocessing first.\n"
            f"  Looked for: {preprocessed_file} or {train_file}"
        )
    
    def preprocess_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess data: clean, filter, and prepare for feature engineering.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Raw data from locations
        
        Returns:
        --------
        pd.DataFrame : Preprocessed data
        """
        logger.info("Preprocessing data...")
        
        initial_count = len(df)
        
        # Remove rows with missing critical values
        critical_cols = ['pm25', 'datetime']
        df = df.dropna(subset=critical_cols)
        logger.info(f"  Removed {initial_count - len(df)} rows with missing critical values")
        
        # Remove outliers (PM2.5 > 500 µg/m³ is extremely rare)
        df = df[df['pm25'] <= 500]
        df = df[df['pm25'] >= 0]
        logger.info(f"  Removed outliers, {len(df)} rows remaining")
        
        # Fill missing values in other columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if col not in ['datetime', 'location_id'] and df[col].isnull().any():
                df[col] = df[col].fillna(df[col].median())
        
        # Calculate AQI if not present
        if 'aqi' not in df.columns or df['aqi'].isnull().all():
            logger.info("  Calculating AQI from PM2.5...")
            df['aqi'] = df['pm25'].apply(self._calculate_aqi)
        
        logger.info(f"✅ Preprocessing complete: {len(df):,} samples ready")
        
        return df
    
    def _calculate_aqi(self, pm25: float) -> float:
        """Calculate AQI from PM2.5 using EPA formula."""
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
                return ((i_high - i_low) / (c_high - c_low)) * (pm25 - c_low) + i_low
        
        return 500 if pm25 > 500 else 0
    
    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create time-series features from preprocessed data.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Preprocessed data
        
        Returns:
        --------
        pd.DataFrame : Data with engineered features
        """
        logger.info("Engineering features...")
        
        feature_df = df.copy()
        
        # Time-based features
        feature_df['hour'] = feature_df['datetime'].dt.hour
        feature_df['day_of_week'] = feature_df['datetime'].dt.dayofweek
        feature_df['month'] = feature_df['datetime'].dt.month
        feature_df['hour_sin'] = np.sin(2 * np.pi * feature_df['hour'] / 24)
        feature_df['hour_cos'] = np.cos(2 * np.pi * feature_df['hour'] / 24)
        
        # Group by location for lag features
        for location_id in feature_df['location_id'].unique():
            loc_mask = feature_df['location_id'] == location_id
            loc_data = feature_df[loc_mask].copy()
            
            # Lag features (1, 2, 3, 6, 12, 24 hours)
            for lag in [1, 2, 3, 6, 12, 24]:
                feature_df.loc[loc_mask, f'pm25_lag_{lag}h'] = loc_data['pm25'].shift(lag)
                feature_df.loc[loc_mask, f'aqi_lag_{lag}h'] = loc_data['aqi'].shift(lag)
            
            # Rolling features (3h, 6h, 12h, 24h windows)
            for window in [3, 6, 12, 24]:
                feature_df.loc[loc_mask, f'pm25_rolling_mean_{window}h'] = loc_data['pm25'].rolling(window, min_periods=1).mean()
                feature_df.loc[loc_mask, f'pm25_rolling_std_{window}h'] = loc_data['pm25'].rolling(window, min_periods=1).std()
                feature_df.loc[loc_mask, f'pm25_rolling_min_{window}h'] = loc_data['pm25'].rolling(window, min_periods=1).min()
                feature_df.loc[loc_mask, f'pm25_rolling_max_{window}h'] = loc_data['pm25'].rolling(window, min_periods=1).max()
        
        # Fill NaN values created by lag/rolling features
        feature_df = feature_df.fillna(method='bfill').fillna(method='ffill')
        
        # Remove first 24 rows per location (insufficient lag data)
        rows_before = len(feature_df)
        feature_df = feature_df.groupby('location_id').apply(lambda x: x.iloc[24:]).reset_index(drop=True)
        logger.info(f"  Removed {rows_before - len(feature_df)} rows with insufficient lag data")
        
        logger.info(f"✅ Feature engineering complete: {len(feature_df.columns)} features")
        
        return feature_df
    
    def train_model(
        self,
        df: pd.DataFrame,
        n_models: int = 10,
        max_depth: Optional[int] = None,
        seed: int = 42
    ) -> Tuple[object, object, Dict]:
        """
        Train Adaptive Random Forest model on streaming data.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Data with engineered features
        n_models : int
            Number of trees in forest
        max_depth : int
            Maximum tree depth (None = unlimited)
        seed : int
            Random seed
        
        Returns:
        --------
        (model, feature_engineer, metrics) : Tuple
            Trained model, feature engineer, and training metrics
        """
        logger.info("="*80)
        logger.info("🚀 TRAINING ADAPTIVE RANDOM FOREST MODEL")
        logger.info("="*80)
        
        # Define feature columns (exclude target and metadata)
        exclude_cols = ['aqi', 'datetime', 'location_id']
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        
        logger.info(f"Training samples: {len(df):,}")
        logger.info(f"Features: {len(feature_cols)}")
        logger.info(f"Trees: {n_models}")
        logger.info(f"Target: aqi")
        
        # Initialize model with drift detection
        drift_detector = drift.ADWIN(delta=0.01)
        warning_detector = drift.ADWIN(delta=0.05)
        
        model = forest.ARFRegressor(
            n_models=n_models,
            max_depth=max_depth,
            seed=seed,
            drift_detector=drift_detector,
            warning_detector=warning_detector,
            grace_period=25,
            lambda_value=6,
            max_features='sqrt',
            aggregation_method='median',
            disable_weighted_vote=True,
            leaf_prediction='adaptive',
            min_samples_split=5
        )
        
        # Metrics tracking
        mae_metric = river_metrics.MAE()
        rmse_metric = river_metrics.RMSE()
        r2_metric = river_metrics.R2()
        
        predictions = []
        actuals = []
        
        # Stream training
        start_time = datetime.now()
        log_interval = max(1, len(df) // 20)  # Log 20 times during training
        
        for idx, row in df.iterrows():
            # Prepare features
            x = {col: row[col] for col in feature_cols}
            y_true = row['aqi']
            
            # Predict then learn (test-then-train)
            y_pred = model.predict_one(x)
            model.learn_one(x, y_true)
            
            # Update metrics
            if y_pred is not None:
                mae_metric.update(y_true, y_pred)
                rmse_metric.update(y_true, y_pred)
                r2_metric.update(y_true, y_pred)
                predictions.append(y_pred)
                actuals.append(y_true)
            
            # Log progress
            if (idx + 1) % log_interval == 0:
                progress = (idx + 1) / len(df) * 100
                logger.info(f"  Progress: {progress:.1f}% | MAE: {mae_metric.get():.2f} | R²: {r2_metric.get():.4f}")
        
        training_time = (datetime.now() - start_time).total_seconds()
        
        # Final metrics
        final_metrics = {
            'mae': float(mae_metric.get()),
            'rmse': float(rmse_metric.get()),
            'r2': float(r2_metric.get()),
            'samples': len(df),
            'features': len(feature_cols),
            'training_time_seconds': training_time,
            'predictions_count': len(predictions)
        }
        
        logger.info("="*80)
        logger.info("✅ TRAINING COMPLETE")
        logger.info(f"   MAE:  {final_metrics['mae']:.2f} AQI points")
        logger.info(f"   RMSE: {final_metrics['rmse']:.2f} AQI points")
        logger.info(f"   R²:   {final_metrics['r2']:.4f}")
        logger.info(f"   Time: {training_time:.1f} seconds")
        logger.info("="*80)
        
        return model, self.feature_engineer, final_metrics
    
    def save_model(
        self,
        model,
        feature_engineer,
        metrics: Dict,
        version: Optional[str] = None
    ) -> Path:
        """
        Save trained model with metadata.
        
        Parameters:
        -----------
        model : object
            Trained model
        feature_engineer : FeatureEngineer
            Feature engineering pipeline
        metrics : Dict
            Training metrics
        version : str
            Model version (default: timestamp)
        
        Returns:
        --------
        Path : Path to saved model directory
        """
        if version is None:
            version = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        model_dir = self.models_dir / f"model_{version}"
        model_dir.mkdir(exist_ok=True, parents=True)
        
        logger.info(f"Saving model to {model_dir}...")
        
        # Save model
        model_path = model_dir / "model.pkl"
        with open(model_path, 'wb') as f:
            dill.dump(model, f)
        logger.info(f"  ✓ Saved model: {model_path}")
        
        # Save feature engineer
        fe_path = model_dir / "feature_engineer.pkl"
        with open(fe_path, 'wb') as f:
            dill.dump(feature_engineer, f)
        logger.info(f"  ✓ Saved feature engineer: {fe_path}")
        
        # Save metadata
        metadata = {
            'version': version,
            'created_at': datetime.now().isoformat(),
            'metrics': metrics,
            'drift_threshold': self.drift_threshold,
            'min_samples': self.min_samples,
            'model_type': 'AdaptiveRandomForestRegressor',
            'retrain_trigger': 'automatic_drift_detection'
        }
        
        metadata_path = model_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"  ✓ Saved metadata: {metadata_path}")
        
        logger.info(f"✅ Model saved successfully: {model_dir}")
        
        return model_dir
    
    def retrain(self) -> Tuple[bool, Optional[Path], Dict]:
        """
        Execute complete retraining pipeline.
        
        Returns:
        --------
        (success, model_path, info) : Tuple[bool, Optional[Path], Dict]
            Success status, path to new model, and retraining info
        """
        info = {
            'started_at': datetime.now().isoformat(),
            'completed_at': None,
            'success': False,
            'model_path': None,
            'metrics': None,
            'error': None
        }
        
        try:
            logger.info("="*80)
            logger.info("🔄 STARTING AUTO-RETRAINING PIPELINE")
            logger.info("="*80)
            
            # Step 1: Load data (already preprocessed with features)
            df = self.load_all_location_data()
            
            if len(df) < self.min_samples:
                raise ValueError(f"Insufficient samples: {len(df)} < {self.min_samples}")
            
            # Step 2: Train model (data already preprocessed and feature-engineered)
            model, feature_engineer, metrics = self.train_model(df)
            
            # Step 5: Save model
            model_dir = self.save_model(model, feature_engineer, metrics)
            
            # Update info
            info['completed_at'] = datetime.now().isoformat()
            info['success'] = True
            info['model_path'] = str(model_dir)
            info['metrics'] = metrics
            
            # Update last retrain time
            self.last_retrain_time = datetime.now()
            
            logger.info("="*80)
            logger.info("✅ AUTO-RETRAINING COMPLETED SUCCESSFULLY")
            logger.info(f"   New model: {model_dir}")
            logger.info(f"   MAE: {metrics['mae']:.2f} | R²: {metrics['r2']:.4f}")
            logger.info("="*80)
            
            return True, model_dir, info
            
        except Exception as e:
            logger.error(f"❌ Auto-retraining failed: {e}", exc_info=True)
            info['completed_at'] = datetime.now().isoformat()
            info['error'] = str(e)
            return False, None, info
    
    def run(self, force: bool = False) -> Tuple[bool, Optional[Path], Dict]:
        """
        Check if retraining is needed and execute if required.
        
        Parameters:
        -----------
        force : bool
            Force retraining regardless of drift/time constraints
        
        Returns:
        --------
        (retrained, model_path, info) : Tuple[bool, Optional[Path], Dict]
            Whether retraining happened, path to model, and info
        """
        logger.info("="*80)
        logger.info("🤖 AUTO-TRAINER RUN")
        logger.info("="*80)
        
        if force:
            logger.info("⚠️  FORCED RETRAINING - Skipping drift/time checks")
            return self.retrain()
        
        # Check if retraining needed
        should_retrain, reasons = self.should_retrain()
        
        if not should_retrain:
            logger.info(f"✅ No retraining needed: {reasons['decision']}")
            return False, None, reasons
        
        # Execute retraining
        return self.retrain()


def main():
    """Main entry point for manual execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Auto-Trainer for Self-Healing MLOps')
    parser.add_argument('--force', action='store_true', help='Force retraining regardless of drift')
    parser.add_argument('--drift-threshold', type=float, default=0.15, help='Drift threshold (default: 0.15)')
    parser.add_argument('--data-dir', default='dataset', help='Data directory')
    parser.add_argument('--models-dir', default='training/models', help='Models directory')
    
    args = parser.parse_args()
    
    # Initialize trainer
    trainer = AutoTrainer(
        data_dir=args.data_dir,
        models_dir=args.models_dir,
        drift_threshold=args.drift_threshold
    )
    
    # Run
    retrained, model_path, info = trainer.run(force=args.force)
    
    if retrained:
        print(f"\n✅ Model retrained successfully: {model_path}")
        print(f"   MAE: {info['metrics']['mae']:.2f} | R²: {info['metrics']['r2']:.4f}")
    else:
        print(f"\n⏸️  No retraining performed: {info.get('decision', 'Unknown reason')}")
    
    return 0 if retrained or not args.force else 1


if __name__ == "__main__":
    sys.exit(main())
