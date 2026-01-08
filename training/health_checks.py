"""
Health Check System - Liveness, Readiness, and Startup Probes

Provides health check endpoints for ML system components.

Health Check Types:
1. Liveness: Is the service alive? (restart if failing)
2. Readiness: Can the service handle requests? (stop sending traffic if failing)
3. Startup: Has the service finished initializing? (wait before liveness checks)

Usage:
    from health_checks import HealthChecker
    
    health = HealthChecker()
    
    # Add custom checks
    health.add_check('database', check_db_connection, check_type='readiness')
    health.add_check('model', check_model_loaded, check_type='startup')
    
    # Run checks
    if health.is_healthy():
        print("System healthy")
    
    # Get detailed status
    status = health.get_status()
"""

import time
import psutil
import threading
from datetime import datetime
from typing import Dict, Callable, Optional, List
from pathlib import Path
import json


class HealthChecker:
    """
    Health check system for ML services.
    
    Implements three types of checks:
    - Liveness: Basic aliveness check
    - Readiness: Can serve traffic
    - Startup: Initialization complete
    """
    
    def __init__(self, service_name: str = "mlops_service"):
        """Initialize health checker."""
        self.service_name = service_name
        self.start_time = time.time()
        
        # Health checks by type
        self.liveness_checks: Dict[str, Callable[[], bool]] = {}
        self.readiness_checks: Dict[str, Callable[[], bool]] = {}
        self.startup_checks: Dict[str, Callable[[], bool]] = {}
        
        # Check results cache
        self.check_results: Dict[str, Dict] = {}
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Configuration
        self.cpu_threshold = 95.0  # %
        self.memory_threshold = 90.0  # %
        self.disk_threshold = 95.0  # %
        
        # Initialize default checks
        self._initialize_default_checks()
    
    def _initialize_default_checks(self):
        """Initialize default system health checks."""
        # Liveness checks (basic aliveness)
        self.add_check(
            'process_alive',
            self._check_process_alive,
            check_type='liveness'
        )
        
        # Readiness checks (can serve traffic)
        self.add_check(
            'cpu_usage',
            self._check_cpu_usage,
            check_type='readiness'
        )
        self.add_check(
            'memory_usage',
            self._check_memory_usage,
            check_type='readiness'
        )
        self.add_check(
            'disk_space',
            self._check_disk_space,
            check_type='readiness'
        )
    
    def add_check(
        self,
        name: str,
        check_func: Callable[[], bool],
        check_type: str = 'readiness'
    ):
        """
        Add a health check.
        
        Args:
            name: Check name
            check_func: Function that returns True if healthy
            check_type: 'liveness', 'readiness', or 'startup'
        """
        with self.lock:
            if check_type == 'liveness':
                self.liveness_checks[name] = check_func
            elif check_type == 'readiness':
                self.readiness_checks[name] = check_func
            elif check_type == 'startup':
                self.startup_checks[name] = check_func
            else:
                raise ValueError(f"Invalid check_type: {check_type}")
    
    def remove_check(self, name: str, check_type: str = 'readiness'):
        """Remove a health check."""
        with self.lock:
            if check_type == 'liveness':
                self.liveness_checks.pop(name, None)
            elif check_type == 'readiness':
                self.readiness_checks.pop(name, None)
            elif check_type == 'startup':
                self.startup_checks.pop(name, None)
    
    def _run_check(self, name: str, check_func: Callable) -> Dict:
        """Run a single check and cache result."""
        start = time.time()
        
        try:
            passed = check_func()
            duration = time.time() - start
            
            result = {
                'name': name,
                'passed': passed,
                'duration_ms': round(duration * 1000, 2),
                'timestamp': datetime.now().isoformat(),
                'error': None
            }
        except Exception as e:
            duration = time.time() - start
            result = {
                'name': name,
                'passed': False,
                'duration_ms': round(duration * 1000, 2),
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
        
        # Cache result
        self.check_results[name] = result
        return result
    
    def _run_checks(self, checks: Dict[str, Callable]) -> Dict:
        """Run a set of checks."""
        results = {}
        all_passed = True
        
        for name, check_func in checks.items():
            result = self._run_check(name, check_func)
            results[name] = result
            
            if not result['passed']:
                all_passed = False
        
        return {
            'healthy': all_passed,
            'checks': results
        }
    
    def is_alive(self) -> bool:
        """Check if service is alive (liveness probe)."""
        with self.lock:
            result = self._run_checks(self.liveness_checks)
            return result['healthy']
    
    def is_ready(self) -> bool:
        """Check if service is ready to serve traffic (readiness probe)."""
        with self.lock:
            result = self._run_checks(self.readiness_checks)
            return result['healthy']
    
    def is_started(self) -> bool:
        """Check if service has finished startup (startup probe)."""
        with self.lock:
            result = self._run_checks(self.startup_checks)
            return result['healthy']
    
    def is_healthy(self) -> bool:
        """Overall health check (all probes)."""
        return self.is_alive() and self.is_ready() and self.is_started()
    
    def get_status(self) -> Dict:
        """Get detailed health status."""
        with self.lock:
            liveness_result = self._run_checks(self.liveness_checks)
            readiness_result = self._run_checks(self.readiness_checks)
            startup_result = self._run_checks(self.startup_checks)
            
            uptime = time.time() - self.start_time
            
            return {
                'service': self.service_name,
                'timestamp': datetime.now().isoformat(),
                'uptime_seconds': round(uptime, 2),
                'healthy': liveness_result['healthy'] and readiness_result['healthy'] and startup_result['healthy'],
                'liveness': liveness_result,
                'readiness': readiness_result,
                'startup': startup_result
            }
    
    # Default check implementations
    
    def _check_process_alive(self) -> bool:
        """Check if process is alive."""
        return True  # If we can run this, we're alive!
    
    def _check_cpu_usage(self) -> bool:
        """Check CPU usage is below threshold."""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        return cpu_percent < self.cpu_threshold
    
    def _check_memory_usage(self) -> bool:
        """Check memory usage is below threshold."""
        memory = psutil.virtual_memory()
        return memory.percent < self.memory_threshold
    
    def _check_disk_space(self) -> bool:
        """Check disk space is above threshold."""
        disk = psutil.disk_usage('/')
        return disk.percent < self.disk_threshold
    
    def export_prometheus_format(self) -> str:
        """
        Export health status as Prometheus metrics.
        
        Returns:
            String in Prometheus format
        """
        lines = []
        
        # Health status gauge (1 = healthy, 0 = unhealthy)
        lines.append('# HELP service_health Service health status')
        lines.append('# TYPE service_health gauge')
        lines.append(f'service_health{{service="{self.service_name}"}} {1 if self.is_healthy() else 0}')
        lines.append('')
        
        # Individual check status
        lines.append('# HELP health_check_status Health check status')
        lines.append('# TYPE health_check_status gauge')
        
        status = self.get_status()
        for check_type in ['liveness', 'readiness', 'startup']:
            checks = status.get(check_type, {}).get('checks', {})
            for name, result in checks.items():
                value = 1 if result['passed'] else 0
                lines.append(f'health_check_status{{service="{self.service_name}",type="{check_type}",check="{name}"}} {value}')
        
        lines.append('')
        
        # Check duration
        lines.append('# HELP health_check_duration_ms Health check duration in milliseconds')
        lines.append('# TYPE health_check_duration_ms gauge')
        
        for name, result in self.check_results.items():
            duration = result.get('duration_ms', 0)
            lines.append(f'health_check_duration_ms{{service="{self.service_name}",check="{name}"}} {duration}')
        
        lines.append('')
        
        # Uptime
        lines.append('# HELP service_uptime_seconds Service uptime in seconds')
        lines.append('# TYPE service_uptime_seconds gauge')
        uptime = time.time() - self.start_time
        lines.append(f'service_uptime_seconds{{service="{self.service_name}"}} {uptime}')
        
        return '\n'.join(lines)


# Utility functions for common checks

def check_file_exists(filepath: str) -> Callable[[], bool]:
    """Create a check that verifies file exists."""
    def check():
        return Path(filepath).exists()
    return check


def check_model_loaded(model_path: str) -> Callable[[], bool]:
    """Create a check that verifies model is loaded."""
    def check():
        return Path(model_path).exists() and Path(model_path).stat().st_size > 0
    return check


def check_database_connection(connection_func: Callable) -> Callable[[], bool]:
    """Create a check that verifies database connection."""
    def check():
        try:
            connection_func()
            return True
        except Exception:
            return False
    return check


def check_api_endpoint(url: str, timeout: int = 5) -> Callable[[], bool]:
    """Create a check that verifies API endpoint is responsive."""
    import requests
    
    def check():
        try:
            response = requests.get(url, timeout=timeout)
            return response.status_code == 200
        except Exception:
            return False
    return check


def check_dependency_service(check_func: Callable) -> Callable[[], bool]:
    """Create a check for a dependency service."""
    return check_func


class DependencyHealthChecker:
    """
    Extended health checker with dependency tracking.
    
    Tracks dependencies and their health status.
    """
    
    def __init__(self, service_name: str = "mlops_service"):
        """Initialize dependency health checker."""
        self.base_checker = HealthChecker(service_name)
        self.dependencies: Dict[str, Dict] = {}
    
    def add_dependency(
        self,
        name: str,
        check_func: Callable[[], bool],
        critical: bool = True,
        description: str = ""
    ):
        """
        Add a dependency check.
        
        Args:
            name: Dependency name
            check_func: Function to check dependency health
            critical: If True, service not ready if dependency fails
            description: Description of dependency
        """
        self.dependencies[name] = {
            'check_func': check_func,
            'critical': critical,
            'description': description
        }
        
        # Add to readiness checks if critical
        if critical:
            self.base_checker.add_check(
                f'dependency_{name}',
                check_func,
                check_type='readiness'
            )
    
    def get_dependency_status(self) -> Dict:
        """Get status of all dependencies."""
        status = {}
        
        for name, dep in self.dependencies.items():
            try:
                healthy = dep['check_func']()
                status[name] = {
                    'healthy': healthy,
                    'critical': dep['critical'],
                    'description': dep['description']
                }
            except Exception as e:
                status[name] = {
                    'healthy': False,
                    'critical': dep['critical'],
                    'description': dep['description'],
                    'error': str(e)
                }
        
        return status
    
    def get_full_status(self) -> Dict:
        """Get full status including base checks and dependencies."""
        base_status = self.base_checker.get_status()
        dep_status = self.get_dependency_status()
        
        base_status['dependencies'] = dep_status
        
        return base_status


if __name__ == '__main__':
    # Demo usage
    print("Health Check System Demo\n" + "="*50 + "\n")
    
    # Basic health checker
    health = HealthChecker(service_name="ml_api")
    
    # Add custom checks
    def check_model():
        """Check if model file exists."""
        model_path = Path('training/models/model_production.joblib')
        return model_path.exists()
    
    def check_data():
        """Check if data is available."""
        data_path = Path('dataset/preprocessed/test_data.csv')
        return data_path.exists()
    
    health.add_check('model_loaded', check_model, check_type='startup')
    health.add_check('data_available', check_data, check_type='readiness')
    
    # Run checks
    print("Running health checks...")
    status = health.get_status()
    
    print(f"\n{'='*60}")
    print(f"Service: {status['service']}")
    print(f"Uptime: {status['uptime_seconds']:.2f}s")
    print(f"Overall Health: {'✅ HEALTHY' if status['healthy'] else '❌ UNHEALTHY'}")
    print(f"{'='*60}\n")
    
    print("Liveness:", "✅ PASS" if status['liveness']['healthy'] else "❌ FAIL")
    for name, result in status['liveness']['checks'].items():
        icon = "✅" if result['passed'] else "❌"
        print(f"  {icon} {name}: {result['duration_ms']}ms")
    
    print("\nReadiness:", "✅ PASS" if status['readiness']['healthy'] else "❌ FAIL")
    for name, result in status['readiness']['checks'].items():
        icon = "✅" if result['passed'] else "❌"
        print(f"  {icon} {name}: {result['duration_ms']}ms")
    
    print("\nStartup:", "✅ PASS" if status['startup']['healthy'] else "❌ FAIL")
    for name, result in status['startup']['checks'].items():
        icon = "✅" if result['passed'] else "❌"
        print(f"  {icon} {name}: {result['duration_ms']}ms")
    
    print("\n\n📈 Prometheus Format:")
    print("-" * 50)
    print(health.export_prometheus_format())
    
    # Demo dependency health checker
    print("\n\n" + "="*60)
    print("Dependency Health Checker Demo")
    print("="*60 + "\n")
    
    dep_health = DependencyHealthChecker(service_name="ml_orchestrator")
    
    # Add dependencies
    dep_health.add_dependency(
        'model_registry',
        lambda: True,  # Simulated check
        critical=True,
        description='Model registry service'
    )
    dep_health.add_dependency(
        'metrics_database',
        lambda: True,  # Simulated check
        critical=True,
        description='Metrics storage database'
    )
    dep_health.add_dependency(
        'slack_notifications',
        lambda: False,  # Simulated failure
        critical=False,
        description='Slack notification service'
    )
    
    dep_status = dep_health.get_dependency_status()
    
    print("Dependencies:")
    for name, status in dep_status.items():
        icon = "✅" if status['healthy'] else "❌"
        critical = " (CRITICAL)" if status['critical'] else ""
        print(f"  {icon} {name}{critical}")
        print(f"     {status['description']}")
    
    print("\n✅ Demo complete!")
