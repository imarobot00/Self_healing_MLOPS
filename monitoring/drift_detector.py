"""
Production Drift Detector for Self-Healing ML System

This module detects distribution drift between training data and production data
using statistical tests (Kolmogorov-Smirnov, PSI). When significant drift is detected,
it triggers alerts and can initiate automatic model retraining.

Usage:
    # Standalone
    python monitoring/drift_detector.py
    
    # Programmatic
    from monitoring.drift_detector import DriftDetector
    detector = DriftDetector()
    report = detector.run_drift_check()
"""

import json
import pandas as pd
import numpy as np
import yaml
from scipy.stats import ks_2samp
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DriftDetector:
    """Detects distribution drift between training and production data"""
    
    def __init__(self, config_path: str = "monitoring/drift_config.yaml"):
        """
        Initialize drift detector
        
        Args:
            config_path: Path to drift configuration file
        """
        self.config = self._load_config(config_path)
        self.baseline_stats = self._load_baseline()
        self.drift_history = []
        
        logger.info(f"DriftDetector initialized with {len(self.baseline_stats.get('features', {}))} features")
    
    def _load_config(self, config_path: str) -> dict:
        """Load drift detection configuration"""
        config_path = Path(config_path)
        
        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return self._default_config()
        
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _default_config(self) -> dict:
        """Default configuration if file not found"""
        return {
            'drift_detection': {
                'window_size': 200,
                'thresholds': {
                    'ks_statistic': 0.3,
                    'p_value': 0.05,
                    'drift_score': 0.5
                },
                'features_to_monitor': ['pm25', 'pm1', 'temperature', 'relativehumidity']
            },
            'baseline': {
                'stats_file': 'monitoring/baseline_stats.json'
            },
            'reporting': {
                'save_reports': True,
                'reports_dir': 'monitoring/reports'
            }
        }
    
    def _load_baseline(self) -> Dict:
        """Load baseline statistics from training data"""
        baseline_path = Path(self.config['baseline']['stats_file'])
        
        # If relative path, resolve from this file's directory
        if not baseline_path.is_absolute():
            baseline_path = Path(__file__).parent / baseline_path.name
        
        if not baseline_path.exists():
            logger.warning(f"Baseline not found at {baseline_path}")
            logger.warning("Run: python monitoring/generate_baseline.py")
            return {}
        
        with open(baseline_path, 'r') as f:
            baseline = json.load(f)
        
        logger.info(f"Baseline loaded: {len(baseline.get('features', {}))} features, "
                   f"{baseline.get('num_samples', 0)} training samples")
        return baseline
    
    def calculate_ks_test(self, recent_data: np.ndarray, baseline_stats: Dict) -> Tuple[float, float]:
        """
        Calculate Kolmogorov-Smirnov test statistic
        
        Args:
            recent_data: Recent production data
            baseline_stats: Baseline statistics from training
        
        Returns:
            (ks_statistic, p_value)
        """
        # Generate synthetic baseline from saved statistics
        baseline_mean = baseline_stats['mean']
        baseline_std = baseline_stats['std']
        
        # Create synthetic baseline with same size as recent data
        synthetic_baseline = np.random.normal(
            baseline_mean, 
            baseline_std, 
            size=len(recent_data)
        )
        
        # Perform KS test
        ks_stat, p_value = ks_2samp(recent_data, synthetic_baseline)
        
        return float(ks_stat), float(p_value)
    
    def calculate_psi(self, recent_data: np.ndarray, baseline_stats: Dict) -> float:
        """
        Calculate Population Stability Index (PSI)
        
        PSI measures how much a population has shifted over time
        PSI < 0.1: No significant change
        PSI < 0.2: Small change
        PSI >= 0.2: Significant change (investigate)
        
        Args:
            recent_data: Recent production data
            baseline_stats: Baseline statistics
        
        Returns:
            PSI score
        """
        try:
            # Get baseline histogram bins
            baseline_bins = baseline_stats.get('histogram', {}).get('bins', [])
            baseline_counts = baseline_stats.get('histogram', {}).get('counts', [])
            
            if not baseline_bins or not baseline_counts:
                return 0.0
            
            # Create bins for recent data using baseline bin edges
            # Add -inf and +inf to handle all values
            bins = [-np.inf] + baseline_bins + [np.inf]
            recent_counts, _ = np.histogram(recent_data, bins=bins)
            
            # Convert to percentages
            baseline_pct = np.array(baseline_counts) / sum(baseline_counts)
            recent_pct = recent_counts / sum(recent_counts)
            
            # Avoid division by zero
            baseline_pct = np.where(baseline_pct == 0, 0.0001, baseline_pct)
            recent_pct = np.where(recent_pct == 0, 0.0001, recent_pct)
            
            # Calculate PSI
            psi = np.sum((recent_pct - baseline_pct) * np.log(recent_pct / baseline_pct))
            
            return float(psi)
        
        except Exception as e:
            logger.warning(f"Error calculating PSI: {e}")
            return 0.0
    
    def analyze_feature_drift(
        self, 
        feature_name: str, 
        recent_data: np.ndarray, 
        baseline_stats: Dict
    ) -> Dict:
        """
        Analyze drift for a single feature
        
        Args:
            feature_name: Name of the feature
            recent_data: Recent production data for this feature
            baseline_stats: Baseline statistics for this feature
        
        Returns:
            Drift analysis results
        """
        # Calculate KS test
        ks_stat, p_value = self.calculate_ks_test(recent_data, baseline_stats)
        
        # Calculate PSI
        psi = self.calculate_psi(recent_data, baseline_stats)
        
        # Determine drift severity
        thresholds = self.config['drift_detection']['thresholds']
        
        is_drifted = (
            ks_stat > thresholds['ks_statistic'] or 
            p_value < thresholds['p_value'] or
            psi > thresholds.get('psi_threshold', 0.2)
        )
        
        # Severity classification
        if ks_stat > 0.5 or psi > 0.3:
            severity = 'critical'
        elif ks_stat > 0.3 or psi > 0.2:
            severity = 'high'
        elif ks_stat > 0.2 or psi > 0.1:
            severity = 'medium'
        else:
            severity = 'low'
        
        # Calculate distribution changes
        recent_mean = float(np.mean(recent_data))
        recent_std = float(np.std(recent_data))
        
        mean_change_pct = ((recent_mean - baseline_stats['mean']) / baseline_stats['mean']) * 100
        std_change_pct = ((recent_std - baseline_stats['std']) / baseline_stats['std']) * 100
        
        return {
            'feature': feature_name,
            'drifted': is_drifted,
            'severity': severity,
            'tests': {
                'ks_statistic': ks_stat,
                'ks_p_value': p_value,
                'psi': psi
            },
            'distribution_changes': {
                'baseline_mean': baseline_stats['mean'],
                'recent_mean': recent_mean,
                'mean_change_pct': mean_change_pct,
                'baseline_std': baseline_stats['std'],
                'recent_std': recent_std,
                'std_change_pct': std_change_pct
            },
            'sample_size': len(recent_data)
        }
    
    def load_recent_predictions(self, days: int = 1, max_samples: int = None) -> pd.DataFrame:
        """
        Load recent predictions from API logs
        
        Args:
            days: Number of days to look back
            max_samples: Maximum number of samples to load
        
        Returns:
            DataFrame with recent predictions
        """
        # Try multiple possible paths for predictions directory
        possible_paths = [
            Path("api/logs/predictions"),
            Path("logs/predictions"),
            Path(__file__).parent.parent / "api" / "logs" / "predictions"
        ]
        
        predictions_dir = None
        for path in possible_paths:
            if path.exists():
                predictions_dir = path
                break
        
        if predictions_dir is None:
            logger.warning(f"Predictions directory not found. Tried: {[str(p) for p in possible_paths]}")
            return pd.DataFrame()
        
        # Find recent prediction files
        all_files = sorted(predictions_dir.glob("predictions_*.jsonl"))
        
        if not all_files:
            logger.warning("No prediction files found")
            return pd.DataFrame()
        
        # Get files from last N days
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_files = [
            f for f in all_files 
            if datetime.fromtimestamp(f.stat().st_mtime) >= cutoff_date
        ]
        
        if not recent_files:
            recent_files = all_files[-days:]
        
        # Read predictions
        all_predictions = []
        for file in recent_files:
            try:
                with open(file, 'r') as f:
                    for line in f:
                        try:
                            pred = json.loads(line)
                            # Handle both 'features' and 'input_features' keys
                            features = pred.get('features') or pred.get('input_features')
                            if features:
                                # Normalize feature names (some logs use 'humidity' instead of 'relativehumidity')
                                if 'humidity' in features and 'relativehumidity' not in features:
                                    features['relativehumidity'] = features.pop('humidity')
                                all_predictions.append(features)
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                logger.warning(f"Error reading {file}: {e}")
                continue
        
        if not all_predictions:
            logger.warning("No valid predictions found")
            return pd.DataFrame()
        
        df = pd.DataFrame(all_predictions)
        
        # Limit samples if specified
        if max_samples and len(df) > max_samples:
            df = df.tail(max_samples)
        
        logger.info(f"Loaded {len(df)} predictions from {len(recent_files)} files")
        return df
    
    def calculate_overall_drift_score(self, feature_results: Dict) -> float:
        """
        Calculate overall drift score across all features
        
        Args:
            feature_results: Dictionary of feature drift results
        
        Returns:
            Overall drift score (0-1)
        """
        if not feature_results:
            return 0.0
        
        # Weight by KS statistic and PSI
        ks_scores = [r['tests']['ks_statistic'] for r in feature_results.values()]
        psi_scores = [r['tests']['psi'] for r in feature_results.values()]
        
        # Combined score (weighted average)
        overall_score = (np.mean(ks_scores) * 0.6) + (np.mean(psi_scores) * 0.4)
        
        return float(overall_score)
    
    def generate_recommendation(self, overall_score: float, feature_results: Dict) -> str:
        """Generate human-readable recommendation based on drift analysis"""
        
        critical_features = [
            name for name, result in feature_results.items() 
            if result['severity'] == 'critical'
        ]
        
        high_features = [
            name for name, result in feature_results.items() 
            if result['severity'] == 'high'
        ]
        
        if overall_score > 0.5 or critical_features:
            return (
                f"🔴 CRITICAL: Immediate retraining required! "
                f"Overall drift score: {overall_score:.3f}. "
                f"Critical features: {', '.join(critical_features) if critical_features else 'Multiple'}"
            )
        elif overall_score > 0.3 or high_features:
            return (
                f"🟡 WARNING: Significant drift detected (score: {overall_score:.3f}). "
                f"Monitor closely and consider retraining soon. "
                f"Affected features: {', '.join(high_features) if high_features else 'Multiple'}"
            )
        elif overall_score > 0.2:
            return f"🟢 MINOR: Small drift detected (score: {overall_score:.3f}). Continue monitoring."
        else:
            return f"✅ HEALTHY: No significant drift detected (score: {overall_score:.3f})."
    
    def run_drift_check(self, days: int = 1) -> Dict:
        """
        Main method: Run complete drift detection analysis
        
        Args:
            days: Number of days to analyze
        
        Returns:
            Complete drift report
        """
        logger.info("="*70)
        logger.info("🔍 DRIFT DETECTION ANALYSIS")
        logger.info("="*70)
        
        # Check baseline
        if not self.baseline_stats or 'features' not in self.baseline_stats:
            return {
                'error': 'No baseline statistics available',
                'recommendation': 'Run: python monitoring/generate_baseline.py'
            }
        
        # Load recent predictions
        window_size = self.config['drift_detection'].get('window_size', 200)
        recent_data = self.load_recent_predictions(days=days, max_samples=window_size)
        
        if recent_data.empty:
            return {
                'error': 'No recent prediction data available',
                'recommendation': 'Make predictions via API first: POST /forecast'
            }
        
        # Analyze each feature
        features_to_monitor = self.config['drift_detection']['features_to_monitor']
        feature_results = {}
        
        for feature in features_to_monitor:
            if feature not in recent_data.columns:
                logger.warning(f"Feature '{feature}' not in recent data")
                continue
            
            if feature not in self.baseline_stats['features']:
                logger.warning(f"Feature '{feature}' not in baseline")
                continue
            
            # Get clean data
            feature_data = recent_data[feature].dropna().values
            
            if len(feature_data) < 30:
                logger.warning(f"Insufficient data for '{feature}' ({len(feature_data)} samples)")
                continue
            
            # Analyze drift
            baseline_stats = self.baseline_stats['features'][feature]
            result = self.analyze_feature_drift(feature, feature_data, baseline_stats)
            feature_results[feature] = result
        
        # Calculate overall drift score
        overall_score = self.calculate_overall_drift_score(feature_results)
        
        # Generate recommendation
        recommendation = self.generate_recommendation(overall_score, feature_results)
        
        # Create report
        report = {
            'timestamp': datetime.now().isoformat(),
            'analysis_window_days': days,
            'num_samples_analyzed': len(recent_data),
            'overall_drift_score': overall_score,
            'recommendation': recommendation,
            'features': feature_results,
            'baseline_info': {
                'generated_at': self.baseline_stats.get('generated_at'),
                'num_training_samples': self.baseline_stats.get('num_samples')
            }
        }
        
        # Log summary
        self._log_drift_summary(report)
        
        # Save report
        if self.config['reporting'].get('save_reports', True):
            self._save_report(report)
        
        return report
    
    def _log_drift_summary(self, report: Dict):
        """Print drift detection summary to console"""
        
        print("\n" + "="*70)
        print("📊 DRIFT DETECTION SUMMARY")
        print("="*70)
        print(f"Samples Analyzed: {report['num_samples_analyzed']}")
        print(f"Overall Drift Score: {report['overall_drift_score']:.3f}")
        print(f"Recommendation: {report['recommendation']}")
        
        print("\n📈 FEATURE-LEVEL RESULTS:")
        print("-" * 70)
        print(f"{'Feature':<20} {'Drifted':<10} {'Severity':<12} {'KS Stat':<10} {'PSI':<10}")
        print("-" * 70)
        
        for feature, result in report['features'].items():
            emoji = "🔴" if result['severity'] in ['critical', 'high'] else "🟡" if result['drifted'] else "🟢"
            print(f"{emoji} {feature:<18} {str(result['drifted']):<10} {result['severity']:<12} "
                  f"{result['tests']['ks_statistic']:<10.3f} {result['tests']['psi']:<10.3f}")
        
        print("-" * 70)
        print("="*70 + "\n")
    
    def _save_report(self, report: Dict):
        """Save drift report to file"""
        reports_dir = Path(self.config['reporting']['reports_dir'])
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = reports_dir / f"drift_report_{timestamp}.json"
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"💾 Report saved to: {report_file}")


def main():
    """Main function for standalone execution"""
    
    # Create drift detector
    detector = DriftDetector()
    
    # Run drift check
    report = detector.run_drift_check(days=1)
    
    # Check for errors
    if 'error' in report:
        print(f"\n❌ ERROR: {report['error']}")
        print(f"💡 {report['recommendation']}\n")
        return
    
    # Check if retraining needed
    if report['overall_drift_score'] > 0.5:
        print("\n🚨 HIGH DRIFT DETECTED - RETRAINING RECOMMENDED")
        print("Next step: Trigger model retraining\n")
    elif report['overall_drift_score'] > 0.3:
        print("\n⚠️  MODERATE DRIFT - MONITOR CLOSELY\n")
    else:
        print("\n✅ SYSTEM HEALTHY - NO ACTION NEEDED\n")


if __name__ == "__main__":
    main()
