"""
Model Validator - Quality Gate for Auto-Retraining System

This module validates new models against the current production model
to ensure only better models are deployed.

Key Features:
- Compares metrics (MAE, RMSE, R², MAPE)
- Enforces improvement thresholds
- Prevents model degradation
- Generates detailed validation reports
- Supports human-in-the-loop for marginal cases

Usage:
    python model_validator.py --current model_dir --new new_model_dir
    
    Or programmatically:
    validator = ModelValidator()
    result = validator.validate(current_model_dir, new_model_dir)
"""

import os
import sys
import json
import logging
import argparse
import importlib.util
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any

import dill
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelValidator:
    """
    Validates new models against current production model.
    
    Acts as a quality gate to prevent deploying degraded models.
    """
    
    def __init__(
        self,
        models_dir: str = None,
        validation_data_path: str = None,
        mae_improvement_threshold: float = 0.05,  # 5% minimum improvement
        r2_improvement_threshold: float = 0.02,   # 2% minimum absolute improvement
        min_r2: float = 0.80,                     # Not used - kept for compatibility
        max_mae: float = 15.0                     # Not used - kept for compatibility
    ):
        """
        Initialize Model Validator.
        
        Compares new model against current production model.
        Validates based on RELATIVE improvement, not absolute thresholds.
        
        Args:
            models_dir: Directory containing model folders
            validation_data_path: Path to validation data CSV
            mae_improvement_threshold: Minimum MAE improvement (as fraction, e.g., 0.05 = 5%)
            r2_improvement_threshold: Minimum R² improvement (absolute, e.g., 0.02 = 2% points)
            min_r2: Deprecated - not used in comparison
            max_mae: Deprecated - not used in comparison
        """
        # Set paths
        if models_dir is None:
            models_dir = os.path.join(
                os.path.dirname(__file__), 
                'models'
            )
        self.models_dir = Path(models_dir)
        
        if validation_data_path is None:
            # Use last 15% of test data for validation
            validation_data_path = os.path.join(
                os.path.dirname(__file__),
                '..',
                'dataset',
                'preprocessed',
                'test_data.csv'
            )
        self.validation_data_path = Path(validation_data_path)
        
        # Load preprocessor stats for denormalization
        preprocessor_stats_path = Path(__file__).parent.parent / 'dataset' / 'preprocessed' / 'preprocessor_stats.json'
        with open(preprocessor_stats_path, 'r') as f:
            stats = json.load(f)
            self.pm25_min = stats['feature_stats']['pm25']['min']
            self.pm25_max = stats['feature_stats']['pm25']['max']
        
        # Thresholds
        self.mae_improvement_threshold = mae_improvement_threshold
        self.r2_improvement_threshold = r2_improvement_threshold
        self.min_r2 = min_r2
        self.max_mae = max_mae
        
        logger.info(f"Initialized ModelValidator")
        logger.info(f"Models directory: {self.models_dir}")
        logger.info(f"Validation data: {self.validation_data_path}")
        logger.info(f"PM2.5 range: {self.pm25_min:.2f} to {self.pm25_max:.2f}")
        logger.info(f"MAE improvement threshold: {mae_improvement_threshold*100}%")
        logger.info(f"R² improvement threshold: {r2_improvement_threshold*100}%")
    
    def load_model(self, model_dir: Path) -> Tuple[Any, Any, Dict]:
        """
        Load model, feature engineer, and metadata.
        
        Args:
            model_dir: Path to model directory
            
        Returns:
            (model, feature_engineer, metadata)
        """
        model_path = model_dir / 'model.pkl'
        fe_path = model_dir / 'feature_engineer.pkl'
        metadata_path = model_dir / 'metadata.json'
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        if not fe_path.exists():
            raise FileNotFoundError(f"Feature engineer not found: {fe_path}")
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata not found: {metadata_path}")
        
        # Load model
        with open(model_path, 'rb') as f:
            model = dill.load(f)
        
        # Load feature engineer
        with open(fe_path, 'rb') as f:
            feature_engineer = dill.load(f)
        
        # Load metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        logger.info(f"Loaded model from {model_dir.name}")
        return model, feature_engineer, metadata
    
    def load_validation_data(self) -> pd.DataFrame:
        """
        Load validation dataset.
        
        Returns last 15% of test data for validation.
        """
        if not self.validation_data_path.exists():
            raise FileNotFoundError(f"Validation data not found: {self.validation_data_path}")
        
        # Load test data
        df = pd.read_csv(self.validation_data_path)
        
        # Use last 15% for validation
        n_samples = len(df)
        validation_start = int(n_samples * 0.85)
        validation_df = df.iloc[validation_start:].copy()
        
        logger.info(f"Loaded validation data: {len(validation_df)} samples")
        logger.info(f"Date range: {validation_df['datetime'].min()} to {validation_df['datetime'].max()}")
        
        return validation_df
    
    def generate_predictions(
        self, 
        model: Any, 
        feature_engineer: Any, 
        validation_df: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate predictions on validation set.
        
        Args:
            model: Trained model
            feature_engineer: Feature engineer instance (not used - data already has features)
            validation_df: Validation dataframe (already has all features)
            
        Returns:
            (y_true, y_pred)
        """
        y_true = []
        y_pred = []
        
        # Extract feature columns (exclude location_id, datetime, aqi, pm25)
        exclude_cols = ['location_id', 'datetime', 'aqi', 'pm25']
        feature_cols = [col for col in validation_df.columns if col not in exclude_cols]
        
        for idx, row in validation_df.iterrows():
            # Extract normalized true value and denormalize it
            normalized_value = row['pm25']
            true_value = normalized_value * (self.pm25_max - self.pm25_min) + self.pm25_min
            
            try:
                # Create feature dict from preprocessed columns
                features = row[feature_cols].to_dict()
                
                # Make prediction (model already returns denormalized values)
                pred = model.predict_one(features)
                
                y_true.append(true_value)
                y_pred.append(pred)
            except Exception as e:
                logger.warning(f"Prediction failed for row {idx}: {e}")
                continue
        
        return np.array(y_true), np.array(y_pred)
    
    def calculate_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        """
        Calculate all evaluation metrics.
        
        Args:
            y_true: True values
            y_pred: Predicted values
            
        Returns:
            Dictionary with all metrics
        """
        # Remove any NaN or infinite values
        mask = np.isfinite(y_true) & np.isfinite(y_pred)
        y_true = y_true[mask]
        y_pred = y_pred[mask]
        
        if len(y_true) < 10:
            raise ValueError(f"Insufficient valid predictions: {len(y_true)}")
        
        # Calculate metrics
        mae = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        r2 = r2_score(y_true, y_pred)
        
        # MAPE (handle division by zero)
        mape_values = []
        for true, pred in zip(y_true, y_pred):
            if abs(true) > 0.1:  # Avoid division by very small numbers
                mape_values.append(abs((true - pred) / true) * 100)
        mape = np.mean(mape_values) if mape_values else 0.0
        
        # Additional metrics
        max_error = np.max(np.abs(y_true - y_pred))
        median_error = np.median(np.abs(y_true - y_pred))
        
        return {
            'mae': round(mae, 2),
            'rmse': round(rmse, 2),
            'r2': round(r2, 4),
            'mape': round(mape, 2),
            'max_error': round(max_error, 2),
            'median_error': round(median_error, 2),
            'n_predictions': len(y_true)
        }
    
    def check_prediction_validity(self, y_pred: np.ndarray) -> Tuple[bool, List[str]]:
        """
        Check if predictions are valid.
        
        Args:
            y_pred: Predicted values
            
        Returns:
            (is_valid, issues)
        """
        issues = []
        
        # Check for NaN
        if np.any(np.isnan(y_pred)):
            n_nan = np.sum(np.isnan(y_pred))
            issues.append(f"{n_nan} NaN predictions")
        
        # Check for infinite
        if np.any(np.isinf(y_pred)):
            n_inf = np.sum(np.isinf(y_pred))
            issues.append(f"{n_inf} infinite predictions")
        
        # Check for negative (AQI can't be negative)
        if np.any(y_pred < 0):
            n_neg = np.sum(y_pred < 0)
            issues.append(f"{n_neg} negative predictions")
        
        # Check for unrealistic values (AQI typically 0-500)
        if np.any(y_pred > 500):
            n_high = np.sum(y_pred > 500)
            issues.append(f"{n_high} predictions > 500")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    def compare_metrics(
        self, 
        current_metrics: Dict[str, float], 
        new_metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Compare metrics between current and new model.
        
        Args:
            current_metrics: Metrics from current model
            new_metrics: Metrics from new model
            
        Returns:
            Comparison results with decision
        """
        # Calculate improvements (positive = better for MAE/RMSE, negative = worse)
        # For R², positive = better
        mae_improvement = ((current_metrics['mae'] - new_metrics['mae']) / 
                          abs(current_metrics['mae'])) * 100 if current_metrics['mae'] != 0 else 0
        rmse_improvement = ((current_metrics['rmse'] - new_metrics['rmse']) / 
                           abs(current_metrics['rmse'])) * 100 if current_metrics['rmse'] != 0 else 0
        
        # For R², calculate absolute improvement (not percentage)
        r2_improvement_abs = new_metrics['r2'] - current_metrics['r2']
        
        improvements = {
            'mae': round(mae_improvement, 2),
            'rmse': round(rmse_improvement, 2),
            'r2_absolute': round(r2_improvement_abs, 4)
        }
        
        # Decision logic - compare new vs current model
        reasons = []
        
        # Check for metric degradation (new model is worse)
        mae_degraded = new_metrics['mae'] > current_metrics['mae'] * 1.01  # Allow 1% tolerance
        r2_degraded = r2_improvement_abs < -0.01  # Allow 0.01 absolute tolerance
        
        if mae_degraded:
            decision = "REJECT"
            reasons.append(f"MAE degraded: {current_metrics['mae']:.2f} → {new_metrics['mae']:.2f} ({mae_improvement:+.1f}%)")
        elif r2_degraded:
            decision = "REJECT"
            reasons.append(f"R² degraded: {current_metrics['r2']:.4f} → {new_metrics['r2']:.4f} ({r2_improvement_abs:+.4f})")
        else:
            # Check for sufficient improvement
            mae_improved = mae_improvement >= (self.mae_improvement_threshold * 100)
            r2_improved = r2_improvement_abs >= self.r2_improvement_threshold
            
            if mae_improved and r2_improved:
                decision = "APPROVE"
                reasons.append(f"MAE improved: {current_metrics['mae']:.2f} → {new_metrics['mae']:.2f} ({mae_improvement:+.1f}%)")
                reasons.append(f"R² improved: {current_metrics['r2']:.4f} → {new_metrics['r2']:.4f} ({r2_improvement_abs:+.4f})")
                reasons.append("Both metrics show sufficient improvement")
            elif mae_improvement > 0 and r2_improvement_abs > 0:
                decision = "MARGINAL"
                reasons.append(f"MAE improved: {current_metrics['mae']:.2f} → {new_metrics['mae']:.2f} ({mae_improvement:+.1f}%)")
                reasons.append(f"R² improved: {current_metrics['r2']:.4f} → {new_metrics['r2']:.4f} ({r2_improvement_abs:+.4f})")
                reasons.append(f"Improvements below threshold (need {self.mae_improvement_threshold*100}% MAE, {self.r2_improvement_threshold} R²)")
                reasons.append("Consider human review before deployment")
            elif abs(mae_improvement) < 0.1 and abs(r2_improvement_abs) < 0.001:
                decision = "MARGINAL"
                reasons.append(f"Models are essentially identical")
                reasons.append(f"MAE: {current_metrics['mae']:.2f} vs {new_metrics['mae']:.2f}")
                reasons.append(f"R²: {current_metrics['r2']:.4f} vs {new_metrics['r2']:.4f}")
                reasons.append("No meaningful difference - deployment optional")
            else:
                decision = "REJECT"
                reasons.append(f"Insufficient improvement")
                reasons.append(f"MAE change: {mae_improvement:+.1f}% (need {self.mae_improvement_threshold*100}%)")
                reasons.append(f"R² change: {r2_improvement_abs:+.4f} (need {self.r2_improvement_threshold})")
        
        return {
            'decision': decision,
            'improvements': improvements,
            'reasons': reasons
        }
    
    def validate(
        self, 
        current_model_dir: str, 
        new_model_dir: str,
        save_report: bool = True
    ) -> Dict[str, Any]:
        """
        Validate new model against current model.
        
        Args:
            current_model_dir: Path to current production model
            new_model_dir: Path to new candidate model
            save_report: Whether to save validation report
            
        Returns:
            Validation results with decision
        """
        logger.info("="*70)
        logger.info("Starting Model Validation")
        logger.info("="*70)
        
        # Convert to Path objects
        current_dir = Path(current_model_dir)
        new_dir = Path(new_model_dir)
        
        # Load models
        logger.info(f"Loading current model: {current_dir.name}")
        current_model, current_fe, current_metadata = self.load_model(current_dir)
        
        logger.info(f"Loading new model: {new_dir.name}")
        new_model, new_fe, new_metadata = self.load_model(new_dir)
        
        # Load validation data
        validation_df = self.load_validation_data()
        
        # Generate predictions for current model
        logger.info("Generating predictions for current model...")
        y_true_current, y_pred_current = self.generate_predictions(
            current_model, current_fe, validation_df
        )
        
        # Check validity of current model predictions
        is_valid, issues = self.check_prediction_validity(y_pred_current)
        if not is_valid:
            logger.error(f"Current model has invalid predictions: {issues}")
        
        # Generate predictions for new model
        logger.info("Generating predictions for new model...")
        y_true_new, y_pred_new = self.generate_predictions(
            new_model, new_fe, validation_df
        )
        
        # Check validity of new model predictions
        is_valid, issues = self.check_prediction_validity(y_pred_new)
        if not is_valid:
            logger.error(f"New model has invalid predictions: {issues}")
            return {
                'decision': 'REJECT',
                'reasons': [f"Invalid predictions: {', '.join(issues)}"],
                'current_model': current_dir.name,
                'new_model': new_dir.name,
                'timestamp': datetime.now().isoformat()
            }
        
        # Calculate metrics
        logger.info("Calculating metrics...")
        current_metrics = self.calculate_metrics(y_true_current, y_pred_current)
        new_metrics = self.calculate_metrics(y_true_new, y_pred_new)
        
        # Compare and decide
        comparison = self.compare_metrics(current_metrics, new_metrics)
        
        # Build final result
        result = {
            'decision': comparison['decision'],
            'reasons': comparison['reasons'],
            'current_model': current_dir.name,
            'new_model': new_dir.name,
            'current_metrics': current_metrics,
            'new_metrics': new_metrics,
            'improvements': comparison['improvements'],
            'timestamp': datetime.now().isoformat(),
            'validation_samples': len(y_true_new)
        }
        
        # Log results
        logger.info("="*70)
        logger.info(f"VALIDATION DECISION: {result['decision']}")
        logger.info("="*70)
        logger.info(f"Current Model: {current_dir.name}")
        logger.info(f"  MAE: {current_metrics['mae']:.2f} | RMSE: {current_metrics['rmse']:.2f} | R²: {current_metrics['r2']:.4f}")
        logger.info(f"New Model: {new_dir.name}")
        logger.info(f"  MAE: {new_metrics['mae']:.2f} | RMSE: {new_metrics['rmse']:.2f} | R²: {new_metrics['r2']:.4f}")
        logger.info(f"Improvements:")
        logger.info(f"  MAE: {comparison['improvements']['mae']:+.1f}%")
        logger.info(f"  RMSE: {comparison['improvements']['rmse']:+.1f}%")
        logger.info(f"  R²: {comparison['improvements']['r2_absolute']:+.4f} (absolute)")
        logger.info(f"Reasons:")
        for reason in result['reasons']:
            logger.info(f"  • {reason}")
        logger.info("="*70)
        
        # Save report
        if save_report:
            self._save_report(result)
        
        return result
    
    def _save_report(self, result: Dict[str, Any]):
        """Save validation report to file."""
        # Create validations directory
        validations_dir = self.models_dir.parent / 'validations'
        validations_dir.mkdir(exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"validation_{timestamp}.json"
        filepath = validations_dir / filename
        
        # Save report
        with open(filepath, 'w') as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"Validation report saved: {filepath}")


def main():
    """CLI interface for model validation."""
    parser = argparse.ArgumentParser(description="Validate new model against current model")
    parser.add_argument(
        '--current',
        type=str,
        required=True,
        help='Path to current production model directory'
    )
    parser.add_argument(
        '--new',
        type=str,
        required=True,
        help='Path to new candidate model directory'
    )
    parser.add_argument(
        '--mae-threshold',
        type=float,
        default=0.05,
        help='Minimum MAE improvement threshold (default: 0.05 = 5%%)'
    )
    parser.add_argument(
        '--r2-threshold',
        type=float,
        default=0.02,
        help='Minimum R² improvement threshold (default: 0.02 = 2%%)'
    )
    parser.add_argument(
        '--min-r2',
        type=float,
        default=0.80,
        help='Minimum acceptable R² (default: 0.80)'
    )
    parser.add_argument(
        '--max-mae',
        type=float,
        default=15.0,
        help='Maximum acceptable MAE (default: 15.0)'
    )
    
    args = parser.parse_args()
    
    # Initialize validator
    validator = ModelValidator(
        mae_improvement_threshold=args.mae_threshold,
        r2_improvement_threshold=args.r2_threshold,
        min_r2=args.min_r2,
        max_mae=args.max_mae
    )
    
    # Run validation
    result = validator.validate(args.current, args.new)
    
    # Exit with appropriate code
    if result['decision'] == 'APPROVE':
        sys.exit(0)
    elif result['decision'] == 'MARGINAL':
        sys.exit(2)
    else:  # REJECT
        sys.exit(1)


if __name__ == '__main__':
    main()
