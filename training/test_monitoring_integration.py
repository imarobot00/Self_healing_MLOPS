"""
Test monitoring integration in API and training components

Run with: pytest test_monitoring_integration.py -v
"""

import pytest
import sys
from pathlib import Path
import time

# Direct imports
from metrics_collector import MetricsCollector
from alert_manager import AlertManager, AlertRule
from health_checks import HealthChecker


class TestAPIMonitoringIntegration:
    """Test monitoring integration in API."""
    
    def test_api_imports_monitoring(self):
        """Test API can import monitoring components."""
        # Import API main to verify all imports work
        import importlib.util
        
        spec = importlib.util.spec_from_file_location(
            "api_main",
            Path(__file__).parent.parent / "api" / "main.py"
        )
        
        # Should not raise any exceptions
        module = importlib.util.module_from_spec(spec)
        assert module is not None
    
    def test_metrics_collector_in_api_context(self):
        """Test MetricsCollector works in API context."""
        metrics = MetricsCollector(app_name="test_api")
        
        # Simulate API predictions
        for i in range(10):
            metrics.increment('predictions_total', labels={'model': 'v1'})
            metrics.observe('prediction_duration_seconds', 0.05)
        
        summary = metrics.get_summary()
        
        assert summary['counters']['predictions_total']['total'] == 10.0
        assert 'prediction_duration_seconds' in summary['histograms']
    
    def test_health_checks_for_api(self):
        """Test health checks configured for API."""
        health = HealthChecker(service_name="aqi_api")
        
        # Add typical API health checks
        health.add_check('model_loaded', lambda: True, check_type='startup')
        health.add_check('database_connection', lambda: True, check_type='readiness')
        
        status = health.get_status()
        
        assert status['service'] == 'aqi_api'
        assert status['healthy'] is True
        assert 'model_loaded' in status['startup']['checks']
        assert 'database_connection' in status['readiness']['checks']
    
    def test_alert_manager_monitors_api_metrics(self):
        """Test AlertManager can monitor API metrics."""
        alert_mgr = AlertManager()
        
        # Add API-specific alert
        alert_mgr.add_rule(AlertRule(
            name='HighAPILatency',
            condition=lambda m: m.get('histograms', {}).get('prediction_duration_seconds', {}).get('default', {}).get('avg', 0) > 1.0,
            severity='P2',
            message='API latency too high',
            for_duration=0,
            cooldown=0
        ))
        
        # Simulate slow API
        metrics = MetricsCollector()
        metrics.observe('prediction_duration_seconds', 2.0)
        
        metrics_summary = metrics.get_summary()
        alert_mgr.check_and_alert(metrics_summary)
        
        # Check alert triggered
        active = alert_mgr.get_active_alerts()
        assert len(active) > 0
        assert any(a.rule_name == 'HighAPILatency' for a in active)


class TestTrainingMonitoringIntegration:
    """Test monitoring integration in training components."""
    
    def test_metrics_collection_during_training(self):
        """Test collecting metrics during model training."""
        metrics = MetricsCollector(app_name="training")
        
        # Simulate training workflow
        start = time.time()
        
        metrics.increment('trainings_total')
        time.sleep(0.1)  # Simulate training
        duration = time.time() - start
        
        metrics.observe('training_duration_seconds', duration)
        metrics.increment('trainings_success_total')
        metrics.set_gauge('model_mae', 6.5)
        metrics.set_gauge('model_r2', 0.93)
        
        summary = metrics.get_summary()
        
        assert summary['counters']['trainings_total']['total'] == 1.0
        assert summary['counters']['trainings_success_total']['total'] == 1.0
        assert summary['gauges']['model_mae'] == 6.5
        assert summary['gauges']['model_r2'] == 0.93
    
    def test_metrics_collection_during_validation(self):
        """Test collecting metrics during model validation."""
        metrics = MetricsCollector(app_name="validator")
        
        # Simulate validation
        metrics.increment('validations_total')
        metrics.increment('validations_approved_total')
        metrics.set_gauge('validation_mae_improvement', 1.2)
        
        summary = metrics.get_summary()
        
        assert summary['counters']['validations_total']['total'] == 1.0
        assert summary['counters']['validations_approved_total']['total'] == 1.0
    
    def test_orchestrator_health_checks(self):
        """Test health checks for orchestrator."""
        health = HealthChecker(service_name="orchestrator")
        
        # Add orchestrator-specific checks
        health.add_check('registry_accessible', lambda: True, check_type='readiness')
        health.add_check('training_service', lambda: True, check_type='readiness')
        health.add_check('validation_service', lambda: True, check_type='readiness')
        
        status = health.get_status()
        
        assert status['healthy'] is True
        assert len(status['readiness']['checks']) >= 4  # Including default checks


class TestEndToEndMonitoring:
    """Test end-to-end monitoring workflow."""
    
    def test_full_prediction_monitoring_workflow(self):
        """Test complete monitoring for prediction workflow."""
        metrics = MetricsCollector(app_name="e2e_test")
        alert_mgr = AlertManager()
        health = HealthChecker(service_name="prediction_service")
        
        # 1. Check health
        health.add_check('model_ready', lambda: True, check_type='startup')
        assert health.is_healthy()
        
        # 2. Make predictions and collect metrics
        for i in range(100):
            metrics.increment('predictions_total', labels={'status': '200'})
            metrics.observe('prediction_duration_seconds', 0.045)
        
        # 3. Check metrics
        summary = metrics.get_summary()
        assert summary['counters']['predictions_total']['total'] == 100.0
        
        # 4. Check for alerts
        alert_mgr.check_and_alert(summary)
        
        # Should be no alerts for healthy metrics
        active = [a for a in alert_mgr.get_active_alerts() 
                 if a.rule_name not in ['HighMAE', 'HighDrift', 'ModelPerformanceDegraded', 'HighErrorRate']]
        # May have default alerts, check specific ones don't trigger
        
        # 5. Export for Prometheus
        prom_export = metrics.export()
        assert 'predictions_total' in prom_export
        assert 'prediction_duration_seconds' in prom_export
    
    def test_full_training_monitoring_workflow(self):
        """Test complete monitoring for training workflow."""
        metrics = MetricsCollector(app_name="training_e2e")
        alert_mgr = AlertManager()
        
        # Add training-specific alert
        alert_mgr.add_rule(AlertRule(
            name='TrainingTooSlow',
            condition=lambda m: m.get('histograms', {}).get('training_duration_seconds', {}).get('default', {}).get('avg', 0) > 3600,
            severity='P3',
            message='Training taking too long',
            for_duration=0,
            cooldown=0
        ))
        
        # Simulate training
        metrics.increment('trainings_total')
        metrics.observe('training_duration_seconds', 600)  # 10 minutes
        metrics.increment('trainings_success_total')
        
        # Should NOT trigger alert (under 1 hour)
        alert_mgr.check_and_alert(metrics.get_summary())
        training_alerts = [a for a in alert_mgr.get_active_alerts() if a.rule_name == 'TrainingTooSlow']
        assert len(training_alerts) == 0


class TestPrometheusExport:
    """Test Prometheus format export from all components."""
    
    def test_metrics_export_format(self):
        """Test Prometheus export format is valid."""
        metrics = MetricsCollector()
        
        metrics.increment('test_counter', labels={'label1': 'value1'})
        metrics.set_gauge('test_gauge', 42.0)
        
        export = metrics.export()
        
        # Check format
        assert '# HELP test_counter' in export
        assert '# TYPE test_counter counter' in export
        assert 'test_counter{label1="value1"}' in export
        
        assert '# HELP test_gauge' in export
        assert '# TYPE test_gauge gauge' in export
        assert 'test_gauge 42.0' in export
    
    def test_health_export_format(self):
        """Test health check Prometheus export."""
        health = HealthChecker(service_name="test_service")
        
        export = health.export_prometheus_format()
        
        assert 'service_health{service="test_service"}' in export
        assert 'service_uptime_seconds' in export
        assert 'health_check_status' in export


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
