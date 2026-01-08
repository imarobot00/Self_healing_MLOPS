"""
Tests for monitoring components:
- MetricsCollector
- AlertManager
- HealthChecker

Run with: pytest test_monitoring.py -v
"""

import pytest
import time
from pathlib import Path
import json

from metrics_collector import MetricsCollector, get_metrics
from alert_manager import AlertManager, AlertRule, Alert
from health_checks import HealthChecker, DependencyHealthChecker


class TestMetricsCollector:
    """Tests for MetricsCollector."""
    
    def test_counter_increment(self):
        """Test counter increments correctly."""
        metrics = MetricsCollector()
        
        metrics.increment('test_counter', 1.0)
        metrics.increment('test_counter', 2.0)
        
        summary = metrics.get_summary()
        assert summary['counters']['test_counter']['total'] == 3.0
    
    def test_counter_with_labels(self):
        """Test counter with labels."""
        metrics = MetricsCollector()
        
        metrics.increment('requests', labels={'status': '200'})
        metrics.increment('requests', labels={'status': '404'})
        metrics.increment('requests', labels={'status': '200'})
        
        summary = metrics.get_summary()
        assert summary['counters']['requests']['total'] == 3.0
        assert 'status="200"' in summary['counters']['requests']['by_labels']
        assert summary['counters']['requests']['by_labels']['status="200"'] == 2.0
    
    def test_gauge_set(self):
        """Test gauge sets value correctly."""
        metrics = MetricsCollector()
        
        metrics.set_gauge('temperature', 25.5)
        metrics.set_gauge('temperature', 30.0)
        
        summary = metrics.get_summary()
        assert summary['gauges']['temperature'] == 30.0
    
    def test_histogram_observe(self):
        """Test histogram records observations."""
        metrics = MetricsCollector()
        
        metrics.observe('response_time', 0.1)
        metrics.observe('response_time', 0.2)
        metrics.observe('response_time', 0.3)
        
        summary = metrics.get_summary()
        hist = summary['histograms']['response_time']['default']
        
        assert hist['count'] == 3
        assert hist['sum'] == pytest.approx(0.6)
        assert hist['avg'] == pytest.approx(0.2)
    
    def test_prometheus_export_format(self):
        """Test Prometheus format export."""
        metrics = MetricsCollector()
        
        metrics.increment('requests_total', labels={'method': 'GET'})
        metrics.set_gauge('cpu_usage', 45.5)
        
        export = metrics.export()
        
        assert '# TYPE requests_total counter' in export
        assert 'requests_total{method="GET"} 1.0' in export
        assert '# TYPE cpu_usage gauge' in export
        assert 'cpu_usage 45.5' in export
    
    def test_histogram_buckets(self):
        """Test histogram bucket distribution."""
        metrics = MetricsCollector()
        metrics.register_histogram('latency', 'Latency test', buckets=[0.1, 0.5, 1.0])
        
        metrics.observe('latency', 0.05)
        metrics.observe('latency', 0.3)
        metrics.observe('latency', 0.8)
        
        export = metrics.export()
        
        # Check buckets in export
        assert 'latency_bucket{le="0.1"}' in export
        assert 'latency_bucket{le="0.5"}' in export
        assert 'latency_bucket{le="1.0"}' in export
        assert 'latency_bucket{le="+Inf"}' in export
    
    def test_metrics_snapshot(self, tmp_path):
        """Test saving metrics snapshot."""
        metrics = MetricsCollector()
        
        metrics.increment('events', 10)
        metrics.set_gauge('status', 1)
        
        snapshot_file = tmp_path / 'snapshot.json'
        metrics.save_snapshot(str(snapshot_file))
        
        assert snapshot_file.exists()
        
        with open(snapshot_file) as f:
            data = json.load(f)
            assert 'counters' in data
            assert 'gauges' in data
            assert 'timestamp' in data
    
    def test_reset_metrics(self):
        """Test metrics can be reset."""
        metrics = MetricsCollector()
        
        metrics.increment('counter', 5)
        metrics.set_gauge('gauge', 100)
        
        metrics.reset()
        
        summary = metrics.get_summary()
        assert len(summary['counters']) == 0
        assert len(summary['gauges']) == 0


class TestAlertManager:
    """Tests for AlertManager."""
    
    def test_alert_rule_creation(self):
        """Test creating alert rules."""
        rule = AlertRule(
            name='TestRule',
            condition=lambda m: m.get('value', 0) > 100,
            severity='P2',
            message='Value too high',
            for_duration=0
        )
        
        assert rule.name == 'TestRule'
        assert rule.severity == 'P2'
        assert rule.for_duration == 0
    
    def test_add_remove_rules(self):
        """Test adding and removing rules."""
        alert_mgr = AlertManager()
        initial_count = len(alert_mgr.rules)
        
        rule = AlertRule(
            name='CustomRule',
            condition=lambda m: False,
            severity='P3',
            message='Test',
            for_duration=0
        )
        
        alert_mgr.add_rule(rule)
        assert len(alert_mgr.rules) == initial_count + 1
        
        alert_mgr.remove_rule('CustomRule')
        assert len(alert_mgr.rules) == initial_count
    
    def test_alert_triggering(self):
        """Test alert gets triggered when condition met."""
        alert_mgr = AlertManager()
        
        # Add rule with immediate trigger
        alert_mgr.add_rule(AlertRule(
            name='HighValue',
            condition=lambda m: m.get('gauges', {}).get('value', 0) > 100,
            severity='P2',
            message='Value exceeded threshold',
            for_duration=0,  # Immediate
            cooldown=0
        ))
        
        # Check with high value
        metrics = {'gauges': {'value': 150}}
        alert_mgr.check_and_alert(metrics)
        
        # Verify alert was triggered
        active = alert_mgr.get_active_alerts()
        assert len(active) > 0
        assert any(a.rule_name == 'HighValue' for a in active)
    
    def test_alert_cooldown(self):
        """Test alert respects cooldown period."""
        alert_mgr = AlertManager()
        
        rule = AlertRule(
            name='CooldownTest',
            condition=lambda m: m.get('gauges', {}).get('trigger', False),
            severity='P3',
            message='Test alert',
            for_duration=0,
            cooldown=3600  # 1 hour cooldown
        )
        alert_mgr.add_rule(rule)
        
        metrics = {'gauges': {'trigger': True}}
        
        # First check - should trigger
        alert_mgr.check_and_alert(metrics)
        first_count = len(alert_mgr.alert_history)
        
        # Second immediate check - should NOT trigger (cooldown)
        alert_mgr.check_and_alert(metrics)
        second_count = len(alert_mgr.alert_history)
        
        assert second_count == first_count  # No new alert due to cooldown
    
    def test_alert_resolution(self):
        """Test alert gets resolved when condition no longer met."""
        alert_mgr = AlertManager()
        
        alert_mgr.add_rule(AlertRule(
            name='ResolutionTest',
            condition=lambda m: m.get('gauges', {}).get('problem', False),
            severity='P2',
            message='Problem detected',
            for_duration=0,
            cooldown=0
        ))
        
        # Trigger alert
        alert_mgr.check_and_alert({'gauges': {'problem': True}})
        assert len(alert_mgr.get_active_alerts()) > 0
        
        # Resolve alert
        alert_mgr.check_and_alert({'gauges': {'problem': False}})
        
        # Check if still active (may need to wait for resolution logic)
        # Note: Current implementation resolves immediately
        active_after = [a for a in alert_mgr.get_active_alerts() if a.rule_name == 'ResolutionTest']
        assert len(active_after) == 0
    
    def test_alert_severity_levels(self):
        """Test different severity levels."""
        severities = ['P1', 'P2', 'P3', 'P4']
        
        for sev in severities:
            rule = AlertRule(
                name=f'Rule_{sev}',
                condition=lambda m: True,
                severity=sev,
                message=f'{sev} alert',
                for_duration=0
            )
            assert rule.severity == sev
    
    def test_alert_history(self):
        """Test alert history tracking."""
        alert_mgr = AlertManager()
        
        alert_mgr.add_rule(AlertRule(
            name='HistoryTest',
            condition=lambda m: True,
            severity='P3',
            message='Test',
            for_duration=0,
            cooldown=0
        ))
        
        initial_history_len = len(alert_mgr.alert_history)
        
        alert_mgr.check_and_alert({'test': True})
        
        assert len(alert_mgr.alert_history) > initial_history_len


class TestHealthChecker:
    """Tests for HealthChecker."""
    
    def test_liveness_check(self):
        """Test liveness probe."""
        health = HealthChecker()
        
        # Basic liveness should always pass
        assert health.is_alive() is True
    
    def test_add_custom_check(self):
        """Test adding custom health check."""
        health = HealthChecker()
        
        def custom_check():
            return True
        
        health.add_check('custom', custom_check, check_type='readiness')
        
        status = health.get_status()
        assert 'custom' in status['readiness']['checks']
    
    def test_failing_check(self):
        """Test health check that fails."""
        health = HealthChecker()
        
        def failing_check():
            return False
        
        health.add_check('failing', failing_check, check_type='readiness')
        
        assert health.is_ready() is False
    
    def test_check_with_exception(self):
        """Test health check that raises exception."""
        health = HealthChecker()
        
        def error_check():
            raise ValueError("Check failed")
        
        health.add_check('error', error_check, check_type='readiness')
        
        status = health.get_status()
        error_result = status['readiness']['checks']['error']
        
        assert error_result['passed'] is False
        assert error_result['error'] is not None
    
    def test_overall_health(self):
        """Test overall health combines all checks."""
        health = HealthChecker()
        
        health.add_check('pass1', lambda: True, check_type='liveness')
        health.add_check('pass2', lambda: True, check_type='readiness')
        health.add_check('pass3', lambda: True, check_type='startup')
        
        assert health.is_healthy() is True
    
    def test_health_status_structure(self):
        """Test health status has correct structure."""
        health = HealthChecker(service_name="test_service")
        
        status = health.get_status()
        
        assert 'service' in status
        assert status['service'] == "test_service"
        assert 'timestamp' in status
        assert 'uptime_seconds' in status
        assert 'healthy' in status
        assert 'liveness' in status
        assert 'readiness' in status
        assert 'startup' in status
    
    def test_uptime_tracking(self):
        """Test uptime is tracked correctly."""
        health = HealthChecker()
        
        time.sleep(0.1)
        
        status = health.get_status()
        assert status['uptime_seconds'] >= 0.1
    
    def test_prometheus_export(self):
        """Test Prometheus format export."""
        health = HealthChecker(service_name="test")
        
        export = health.export_prometheus_format()
        
        assert 'service_health{service="test"}' in export
        assert 'service_uptime_seconds{service="test"}' in export
        assert 'health_check_status' in export


class TestDependencyHealthChecker:
    """Tests for DependencyHealthChecker."""
    
    def test_add_dependency(self):
        """Test adding dependencies."""
        health = DependencyHealthChecker()
        
        health.add_dependency(
            'database',
            lambda: True,
            critical=True,
            description='Main database'
        )
        
        deps = health.get_dependency_status()
        assert 'database' in deps
        assert deps['database']['healthy'] is True
        assert deps['database']['critical'] is True
    
    def test_critical_dependency_affects_readiness(self):
        """Test critical dependency affects readiness."""
        health = DependencyHealthChecker()
        
        health.add_dependency(
            'critical_service',
            lambda: False,  # Failing
            critical=True
        )
        
        # Critical dependency failure should make service not ready
        assert health.base_checker.is_ready() is False
    
    def test_non_critical_dependency(self):
        """Test non-critical dependency doesn't block."""
        health = DependencyHealthChecker()
        
        health.add_dependency(
            'optional_service',
            lambda: False,  # Failing
            critical=False
        )
        
        # Non-critical dependency failure shouldn't block readiness
        # (assuming other checks pass)
        deps = health.get_dependency_status()
        assert deps['optional_service']['healthy'] is False
        assert deps['optional_service']['critical'] is False
    
    def test_full_status(self):
        """Test full status includes dependencies."""
        health = DependencyHealthChecker()
        
        health.add_dependency('dep1', lambda: True, critical=True)
        
        status = health.get_full_status()
        
        assert 'dependencies' in status
        assert 'dep1' in status['dependencies']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
