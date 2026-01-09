"""
Metrics Collector - Centralized metrics collection for ML system

Collects metrics from all components:
- Orchestrator (workflow metrics)
- Trainer (training metrics)
- Validator (validation metrics)
- Registry (model metrics)
- API (request metrics)

Exposes Prometheus-compatible /metrics endpoint.

Usage:
    from metrics_collector import MetricsCollector
    
    metrics = MetricsCollector()
    
    # Increment counter
    metrics.increment('predictions_total', labels={'model': 'model_v1'})
    
    # Set gauge
    metrics.set_gauge('model_mae', 6.5, labels={'model': 'model_v1'})
    
    # Record histogram
    metrics.observe('request_duration', 0.045)
    
    # Export for Prometheus
    print(metrics.export())
"""

import time
import threading
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional, Any
import json
from pathlib import Path


class MetricsCollector:
    """
    Centralized metrics collection supporting Prometheus format.
    
    Supports:
    - Counters (monotonically increasing)
    - Gauges (can go up or down)
    - Histograms (distributions)
    - Summaries (pre-computed percentiles)
    """
    
    def __init__(self, app_name: str = "mlops_system"):
        """Initialize metrics collector."""
        self.app_name = app_name
        
        # Metrics storage
        self.counters = defaultdict(lambda: defaultdict(float))
        self.gauges = defaultdict(lambda: defaultdict(float))
        self.histograms = defaultdict(lambda: {'buckets': defaultdict(int), 'sum': 0, 'count': 0})
        
        # Metric metadata (help text, type)
        self.metadata = {}
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Initialize standard metrics
        self._initialize_standard_metrics()
    
    def _initialize_standard_metrics(self):
        """Initialize standard metrics for ML system."""
        # API metrics
        self.register_counter(
            'predictions_total',
            'Total number of predictions made'
        )
        self.register_counter(
            'predictions_errors_total',
            'Total number of prediction errors'
        )
        self.register_histogram(
            'prediction_duration_seconds',
            'Time to generate prediction',
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
        )
        
        # Model metrics
        self.register_gauge(
            'model_mae',
            'Current model Mean Absolute Error'
        )
        self.register_gauge(
            'model_r2',
            'Current model R² score'
        )
        self.register_gauge(
            'model_drift_psi',
            'Current PSI drift score'
        )
        
        # Training metrics
        self.register_counter(
            'trainings_total',
            'Total number of training runs'
        )
        self.register_counter(
            'trainings_success_total',
            'Number of successful training runs'
        )
        self.register_counter(
            'trainings_failed_total',
            'Number of failed training runs'
        )
        self.register_histogram(
            'training_duration_seconds',
            'Time to train model',
            buckets=[60, 300, 600, 1200, 1800, 3600]
        )
        
        # Validation metrics
        self.register_counter(
            'validations_total',
            'Total number of validations'
        )
        self.register_counter(
            'validations_approved_total',
            'Number of approved validations'
        )
        self.register_counter(
            'validations_rejected_total',
            'Number of rejected validations'
        )
        
        # Registry metrics
        self.register_gauge(
            'models_total',
            'Total number of models in registry'
        )
        self.register_gauge(
            'models_by_status',
            'Number of models by status'
        )
        self.register_counter(
            'deployments_total',
            'Total number of model deployments'
        )
        self.register_counter(
            'rollbacks_total',
            'Total number of rollbacks'
        )
        
        # Orchestrator metrics
        self.register_counter(
            'drift_checks_total',
            'Total number of drift checks'
        )
        self.register_counter(
            'healing_workflows_total',
            'Total number of healing workflows triggered'
        )
        self.register_gauge(
            'orchestrator_state',
            'Current orchestrator state (encoded)'
        )
        
        # Data quality metrics
        self.register_gauge(
            'data_missing_rate',
            'Percentage of missing values in data'
        )
        self.register_gauge(
            'data_freshness_seconds',
            'Seconds since data was last updated'
        )
    
    def register_counter(self, name: str, help_text: str):
        """Register a counter metric."""
        with self.lock:
            self.metadata[name] = {'type': 'counter', 'help': help_text}
    
    def register_gauge(self, name: str, help_text: str):
        """Register a gauge metric."""
        with self.lock:
            self.metadata[name] = {'type': 'gauge', 'help': help_text}
    
    def register_histogram(self, name: str, help_text: str, buckets: List[float] = None):
        """Register a histogram metric."""
        with self.lock:
            if buckets is None:
                buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
            
            self.metadata[name] = {
                'type': 'histogram',
                'help': help_text,
                'buckets': buckets
            }
    
    def increment(self, name: str, value: float = 1.0, labels: Dict[str, str] = None):
        """Increment a counter metric."""
        with self.lock:
            label_key = self._serialize_labels(labels or {})
            self.counters[name][label_key] += value
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Set a gauge metric value."""
        if value is None:
            return  # Skip None values
        with self.lock:
            label_key = self._serialize_labels(labels or {})
            self.gauges[name][label_key] = value
    
    def observe(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record a histogram observation."""
        with self.lock:
            label_key = self._serialize_labels(labels or {})
            
            if name not in self.histograms:
                self.histograms[name] = {}
            
            if label_key not in self.histograms[name]:
                self.histograms[name][label_key] = {
                    'buckets': defaultdict(int),
                    'sum': 0,
                    'count': 0
                }
            
            hist = self.histograms[name][label_key]
            hist['sum'] += value
            hist['count'] += 1
            
            # Increment buckets
            buckets = self.metadata.get(name, {}).get('buckets', [])
            for bucket in buckets:
                if value <= bucket:
                    hist['buckets'][bucket] += 1
            
            # +Inf bucket
            hist['buckets'][float('inf')] += 1
    
    def _serialize_labels(self, labels: Dict[str, str]) -> str:
        """Serialize labels to string key."""
        if not labels:
            return ''
        return ','.join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    
    def _parse_labels(self, label_key: str) -> str:
        """Parse labels back to Prometheus format."""
        if not label_key:
            return ''
        return '{' + label_key + '}'
    
    def export(self) -> str:
        """
        Export metrics in Prometheus format.
        
        Returns:
            String in Prometheus exposition format
        """
        lines = []
        
        with self.lock:
            # Export counters
            for name in sorted(self.counters.keys()):
                meta = self.metadata.get(name, {})
                lines.append(f"# HELP {name} {meta.get('help', '')}")
                lines.append(f"# TYPE {name} {meta.get('type', 'counter')}")
                
                for label_key, value in sorted(self.counters[name].items()):
                    label_str = self._parse_labels(label_key)
                    lines.append(f"{name}{label_str} {value}")
                
                lines.append('')
            
            # Export gauges
            for name in sorted(self.gauges.keys()):
                meta = self.metadata.get(name, {})
                lines.append(f"# HELP {name} {meta.get('help', '')}")
                lines.append(f"# TYPE {name} {meta.get('type', 'gauge')}")
                
                for label_key, value in sorted(self.gauges[name].items()):
                    label_str = self._parse_labels(label_key)
                    lines.append(f"{name}{label_str} {value}")
                
                lines.append('')
            
            # Export histograms
            for name in sorted(self.histograms.keys()):
                meta = self.metadata.get(name, {})
                lines.append(f"# HELP {name} {meta.get('help', '')}")
                lines.append(f"# TYPE {name} {meta.get('type', 'histogram')}")
                
                for label_key, hist in sorted(self.histograms[name].items()):
                    label_str = self._parse_labels(label_key)
                    
                    # Export buckets
                    for bucket, count in sorted(hist['buckets'].items()):
                        bucket_str = '+Inf' if bucket == float('inf') else str(bucket)
                        lines.append(f'{name}_bucket{{le="{bucket_str}"{("," + label_key) if label_key else ""}}} {count}')
                    
                    # Export sum and count
                    lines.append(f"{name}_sum{label_str} {hist['sum']}")
                    lines.append(f"{name}_count{label_str} {hist['count']}")
                
                lines.append('')
        
        return '\n'.join(lines)
    
    def get_summary(self) -> Dict:
        """Get human-readable summary of metrics."""
        with self.lock:
            summary = {
                'timestamp': datetime.now().isoformat(),
                'counters': {},
                'gauges': {},
                'histograms': {}
            }
            
            # Summarize counters
            for name, values in self.counters.items():
                total = sum(values.values())
                summary['counters'][name] = {
                    'total': total,
                    'by_labels': dict(values)
                }
            
            # Summarize gauges
            for name, values in self.gauges.items():
                if len(values) == 1 and '' in values:
                    summary['gauges'][name] = values['']
                else:
                    summary['gauges'][name] = dict(values)
            
            # Summarize histograms
            for name, hists in self.histograms.items():
                summary['histograms'][name] = {}
                for label_key, hist in hists.items():
                    avg = hist['sum'] / hist['count'] if hist['count'] > 0 else 0
                    summary['histograms'][name][label_key or 'default'] = {
                        'count': hist['count'],
                        'sum': hist['sum'],
                        'avg': avg
                    }
            
            return summary
    
    def save_snapshot(self, filepath: str):
        """Save metrics snapshot to file."""
        summary = self.get_summary()
        
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)
    
    def reset(self):
        """Reset all metrics (useful for testing)."""
        with self.lock:
            self.counters.clear()
            self.gauges.clear()
            self.histograms.clear()


# Global metrics instance
_metrics_instance = None

def get_metrics() -> MetricsCollector:
    """Get global metrics collector instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = MetricsCollector()
    return _metrics_instance


# Convenience functions
def increment(name: str, value: float = 1.0, labels: Dict[str, str] = None):
    """Increment a counter."""
    get_metrics().increment(name, value, labels)

def set_gauge(name: str, value: float, labels: Dict[str, str] = None):
    """Set a gauge value."""
    get_metrics().set_gauge(name, value, labels)

def observe(name: str, value: float, labels: Dict[str, str] = None):
    """Record a histogram observation."""
    get_metrics().observe(name, value, labels)

def export_metrics() -> str:
    """Export all metrics in Prometheus format."""
    return get_metrics().export()


if __name__ == '__main__':
    # Demo usage
    print("Metrics Collector Demo\n" + "="*50 + "\n")
    
    metrics = MetricsCollector()
    
    # Simulate some activity
    print("Simulating ML system activity...")
    
    # API requests
    for i in range(100):
        metrics.increment('predictions_total', labels={'model': 'model_v1'})
        metrics.observe('prediction_duration_seconds', 0.045)
    
    for i in range(50):
        metrics.increment('predictions_total', labels={'model': 'model_v2'})
        metrics.observe('prediction_duration_seconds', 0.032)
    
    # Some errors
    metrics.increment('predictions_errors_total', 3, labels={'model': 'model_v1'})
    
    # Model metrics
    metrics.set_gauge('model_mae', 6.5, labels={'model': 'model_v1'})
    metrics.set_gauge('model_r2', 0.93, labels={'model': 'model_v1'})
    metrics.set_gauge('model_drift_psi', 0.18)
    
    # Training
    metrics.increment('trainings_total')
    metrics.increment('trainings_success_total')
    metrics.observe('training_duration_seconds', 720)  # 12 minutes
    
    # Validation
    metrics.increment('validations_total')
    metrics.increment('validations_approved_total')
    
    # Registry
    metrics.set_gauge('models_total', 5)
    metrics.set_gauge('models_by_status', 2, labels={'status': 'candidate'})
    metrics.set_gauge('models_by_status', 1, labels={'status': 'production'})
    metrics.increment('deployments_total')
    
    print("\n📊 Summary:")
    print(json.dumps(metrics.get_summary(), indent=2))
    
    print("\n\n📈 Prometheus Format:")
    print("-" * 50)
    print(metrics.export())
    
    # Save snapshot
    metrics.save_snapshot('training/metrics_snapshot.json')
    print("\n💾 Snapshot saved to training/metrics_snapshot.json")
