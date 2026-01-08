"""
Alert Manager - ML System Alerting and Notification

Monitors metrics and triggers alerts based on rules.
Supports multiple notification channels (Slack, Email).

Alert Severity Levels:
- P1 (Critical): Page immediately, system down or critical model failure
- P2 (High): Alert within 15 minutes, significant degradation
- P3 (Medium): Alert within 1 hour, minor issues
- P4 (Low): Daily digest, informational

Usage:
    from alert_manager import AlertManager, AlertRule
    
    alert_mgr = AlertManager()
    
    # Define alert rule
    rule = AlertRule(
        name='ModelDegraded',
        condition=lambda metrics: metrics.get('model_mae', 0) > 10.0,
        severity='P2',
        message='Model MAE exceeded threshold'
    )
    
    alert_mgr.add_rule(rule)
    alert_mgr.check_and_alert(metrics)
"""

import time
import json
import threading
import requests
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Callable, Optional, Any
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, asdict


@dataclass
class AlertRule:
    """Definition of an alert rule."""
    name: str
    condition: Callable[[Dict], bool]  # Function that checks metrics
    severity: str  # P1, P2, P3, P4
    message: str
    for_duration: int = 0  # Seconds condition must be true before alerting
    cooldown: int = 3600  # Minimum seconds between alerts (default 1 hour)
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class Alert:
    """An active alert."""
    rule_name: str
    severity: str
    message: str
    timestamp: str
    metrics_snapshot: Dict
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AlertManager:
    """
    Alert manager for ML system monitoring.
    
    Features:
    - Rule-based alerting
    - Multiple notification channels
    - Alert deduplication
    - Alert history
    - Severity-based routing
    """
    
    def __init__(self, config_path: str = None):
        """Initialize alert manager."""
        self.config = self._load_config(config_path)
        
        # Alert rules
        self.rules: List[AlertRule] = []
        
        # Alert state tracking
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.last_alert_time: Dict[str, datetime] = {}
        self.condition_first_seen: Dict[str, datetime] = {}
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Notification channels
        self.notification_handlers = {
            'slack': self._send_slack,
            'email': self._send_email,
            'console': self._send_console
        }
        
        # Alert logs directory
        self.log_dir = Path('training/alert_logs')
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize default rules
        self._initialize_default_rules()
    
    def _load_config(self, config_path: str = None) -> Dict:
        """Load alert configuration."""
        default_config = {
            'slack': {
                'enabled': False,
                'webhook_url': '',
                'channel': '#ml-alerts'
            },
            'email': {
                'enabled': False,
                'smtp_host': 'smtp.gmail.com',
                'smtp_port': 587,
                'from_email': '',
                'to_emails': [],
                'password': ''
            },
            'console': {
                'enabled': True
            },
            'severity_routing': {
                'P1': ['slack', 'email', 'console'],
                'P2': ['slack', 'email'],
                'P3': ['email'],
                'P4': ['console']
            }
        }
        
        if config_path and Path(config_path).exists():
            with open(config_path) as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def _initialize_default_rules(self):
        """Initialize default alert rules for ML system."""
        # Model performance degradation
        self.add_rule(AlertRule(
            name='ModelPerformanceDegraded',
            condition=lambda m: (lambda val: val > 10.0 if isinstance(val, (int, float)) else False)(m.get('gauges', {}).get('model_mae', {})),
            severity='P2',
            message='Model MAE exceeded 10.0 threshold',
            for_duration=600,  # 10 minutes
            cooldown=1800,  # 30 minutes
            metadata={'threshold': 10.0, 'metric': 'model_mae'}
        ))
        
        # High error rate
        self.add_rule(AlertRule(
            name='HighErrorRate',
            condition=lambda m: self._calculate_error_rate(m) > 0.05,
            severity='P2',
            message='Error rate exceeded 5%',
            for_duration=300,  # 5 minutes
            cooldown=1800,
            metadata={'threshold': 0.05}
        ))
        
        # Training failure
        self.add_rule(AlertRule(
            name='TrainingFailed',
            condition=lambda m: m.get('counters', {}).get('trainings_failed_total', {}).get('total', 0) > 0,
            severity='P2',
            message='Model training failed',
            for_duration=0,  # Alert immediately
            cooldown=3600,
            metadata={}
        ))
        
        # Severe model drift
        self.add_rule(AlertRule(
            name='SevereModelDrift',
            condition=lambda m: (lambda val: val > 0.3 if isinstance(val, (int, float)) else False)(m.get('gauges', {}).get('model_drift_psi', {})),
            severity='P1',
            message='Severe model drift detected (PSI > 0.3)',
            for_duration=600,
            cooldown=1800,
            metadata={'threshold': 0.3}
        ))
        
        # No predictions (system down?)
        self.add_rule(AlertRule(
            name='NoPredictions',
            condition=lambda m: self._check_no_recent_predictions(m),
            severity='P1',
            message='No predictions in last 10 minutes',
            for_duration=600,
            cooldown=1800,
            metadata={}
        ))
        
        # Model R² degradation
        self.add_rule(AlertRule(
            name='ModelR2Degraded',
            condition=lambda m: (lambda val: val < 0.7 if isinstance(val, (int, float)) else False)(m.get('gauges', {}).get('model_r2', {})),
            severity='P3',
            message='Model R² score below 0.7',
            for_duration=600,
            cooldown=3600,
            metadata={'threshold': 0.7}
        ))
        
        # Data quality issues
        self.add_rule(AlertRule(
            name='HighMissingDataRate',
            condition=lambda m: (lambda val: val > 0.1 if isinstance(val, (int, float)) else False)(m.get('gauges', {}).get('data_missing_rate', {})),
            severity='P3',
            message='Missing data rate above 10%',
            for_duration=600,
            cooldown=3600,
            metadata={'threshold': 0.1}
        ))
    
    def _calculate_error_rate(self, metrics: Dict) -> float:
        """Calculate error rate from metrics."""
        gauges = metrics.get('gauges', {})
        counters = metrics.get('counters', {})
        
        # Try to get from counters
        total_preds = counters.get('predictions_total', {}).get('total', 0)
        total_errors = counters.get('predictions_errors_total', {}).get('total', 0)
        
        if total_preds == 0:
            return 0.0
        
        return total_errors / total_preds
    
    def _check_no_recent_predictions(self, metrics: Dict) -> bool:
        """Check if there have been recent predictions."""
        # This is a simplified check
        # In production, you'd track timestamp of last prediction
        counters = metrics.get('counters', {})
        total_preds = counters.get('predictions_total', {}).get('total', 0)
        return total_preds == 0
    
    def add_rule(self, rule: AlertRule):
        """Add an alert rule."""
        with self.lock:
            self.rules.append(rule)
    
    def remove_rule(self, rule_name: str):
        """Remove an alert rule."""
        with self.lock:
            self.rules = [r for r in self.rules if r.name != rule_name]
    
    def check_and_alert(self, metrics: Dict):
        """
        Check all rules against metrics and trigger alerts.
        
        Args:
            metrics: Metrics dictionary from MetricsCollector.get_summary()
        """
        current_time = datetime.now()
        
        with self.lock:
            for rule in self.rules:
                try:
                    # Check condition
                    condition_met = rule.condition(metrics)
                    
                    if condition_met:
                        # Track when condition first seen
                        if rule.name not in self.condition_first_seen:
                            self.condition_first_seen[rule.name] = current_time
                        
                        # Check if condition has been true long enough
                        time_in_condition = (current_time - self.condition_first_seen[rule.name]).total_seconds()
                        
                        if time_in_condition < rule.for_duration:
                            continue  # Not yet time to alert
                        
                        # Check cooldown
                        last_alert = self.last_alert_time.get(rule.name)
                        if last_alert:
                            time_since_last = (current_time - last_alert).total_seconds()
                            if time_since_last < rule.cooldown:
                                continue  # Still in cooldown
                        
                        # Trigger alert
                        self._trigger_alert(rule, metrics)
                    
                    else:
                        # Condition no longer met, reset tracking
                        if rule.name in self.condition_first_seen:
                            del self.condition_first_seen[rule.name]
                        
                        # Resolve alert if active
                        if rule.name in self.active_alerts:
                            self._resolve_alert(rule.name)
                
                except Exception as e:
                    print(f"Error checking rule {rule.name}: {e}")
    
    def _trigger_alert(self, rule: AlertRule, metrics: Dict):
        """Trigger an alert."""
        alert = Alert(
            rule_name=rule.name,
            severity=rule.severity,
            message=rule.message,
            timestamp=datetime.now().isoformat(),
            metrics_snapshot=metrics,
            metadata=rule.metadata
        )
        
        # Store alert
        self.active_alerts[rule.name] = alert
        self.alert_history.append(alert)
        self.last_alert_time[rule.name] = datetime.now()
        
        # Send notifications
        self._send_notifications(alert)
        
        # Log alert
        self._log_alert(alert)
        
        print(f"🚨 ALERT TRIGGERED: {rule.name} [{rule.severity}]")
    
    def _resolve_alert(self, rule_name: str):
        """Resolve an active alert."""
        if rule_name in self.active_alerts:
            alert = self.active_alerts[rule_name]
            del self.active_alerts[rule_name]
            
            print(f"✅ ALERT RESOLVED: {rule_name}")
            
            # Log resolution
            self._log_resolution(rule_name)
    
    def _send_notifications(self, alert: Alert):
        """Send alert notifications to configured channels."""
        # Get channels for this severity
        channels = self.config['severity_routing'].get(alert.severity, ['console'])
        
        for channel in channels:
            if channel in self.notification_handlers:
                handler = self.notification_handlers[channel]
                try:
                    handler(alert)
                except Exception as e:
                    print(f"Error sending {channel} notification: {e}")
    
    def _send_slack(self, alert: Alert):
        """Send Slack notification."""
        if not self.config['slack']['enabled']:
            return
        
        webhook_url = self.config['slack']['webhook_url']
        if not webhook_url:
            return
        
        # Severity emoji
        emoji_map = {
            'P1': '🔴',
            'P2': '🟠',
            'P3': '🟡',
            'P4': '🔵'
        }
        emoji = emoji_map.get(alert.severity, '⚪')
        
        # Build Slack message
        message = {
            "text": f"{emoji} Alert: {alert.rule_name}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} {alert.severity}: {alert.rule_name}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Message:* {alert.message}\n*Time:* {alert.timestamp}"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Severity:*\n{alert.severity}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Rule:*\n{alert.rule_name}"
                        }
                    ]
                }
            ]
        }
        
        # Add metadata if present
        if alert.metadata:
            metadata_text = '\n'.join(f"• {k}: {v}" for k, v in alert.metadata.items())
            message["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Metadata:*\n{metadata_text}"
                }
            })
        
        response = requests.post(webhook_url, json=message, timeout=5)
        response.raise_for_status()
    
    def _send_email(self, alert: Alert):
        """Send email notification."""
        if not self.config['email']['enabled']:
            return
        
        email_config = self.config['email']
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"[{alert.severity}] {alert.rule_name}"
        msg['From'] = email_config['from_email']
        msg['To'] = ', '.join(email_config['to_emails'])
        
        # HTML body
        html = f"""
        <html>
        <head></head>
        <body>
            <h2 style="color: {'red' if alert.severity == 'P1' else 'orange' if alert.severity == 'P2' else 'gold'};">
                Alert: {alert.rule_name}
            </h2>
            <p><strong>Severity:</strong> {alert.severity}</p>
            <p><strong>Message:</strong> {alert.message}</p>
            <p><strong>Time:</strong> {alert.timestamp}</p>
            
            <h3>Metadata:</h3>
            <ul>
                {''.join(f'<li><strong>{k}:</strong> {v}</li>' for k, v in alert.metadata.items())}
            </ul>
            
            <p>Check the monitoring dashboard for more details.</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(html, 'html'))
        
        # Send email
        with smtplib.SMTP(email_config['smtp_host'], email_config['smtp_port']) as server:
            server.starttls()
            server.login(email_config['from_email'], email_config['password'])
            server.send_message(msg)
    
    def _send_console(self, alert: Alert):
        """Print alert to console."""
        print(f"\n{'='*60}")
        print(f"🚨 ALERT: {alert.rule_name} [{alert.severity}]")
        print(f"{'='*60}")
        print(f"Message: {alert.message}")
        print(f"Time: {alert.timestamp}")
        if alert.metadata:
            print("Metadata:")
            for k, v in alert.metadata.items():
                print(f"  {k}: {v}")
        print(f"{'='*60}\n")
    
    def _log_alert(self, alert: Alert):
        """Log alert to file."""
        log_file = self.log_dir / f"alerts_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(asdict(alert)) + '\n')
    
    def _log_resolution(self, rule_name: str):
        """Log alert resolution."""
        log_file = self.log_dir / f"alerts_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
        resolution = {
            'event': 'resolution',
            'rule_name': rule_name,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(resolution) + '\n')
    
    def get_active_alerts(self) -> List[Alert]:
        """Get list of active alerts."""
        with self.lock:
            return list(self.active_alerts.values())
    
    def get_alert_history(self, hours: int = 24) -> List[Alert]:
        """Get alert history for last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        with self.lock:
            recent = [
                alert for alert in self.alert_history
                if datetime.fromisoformat(alert.timestamp) > cutoff
            ]
            return recent
    
    def get_stats(self) -> Dict:
        """Get alert statistics."""
        with self.lock:
            recent_alerts = self.get_alert_history(hours=24)
            
            severity_counts = defaultdict(int)
            rule_counts = defaultdict(int)
            
            for alert in recent_alerts:
                severity_counts[alert.severity] += 1
                rule_counts[alert.rule_name] += 1
            
            return {
                'active_alerts': len(self.active_alerts),
                'alerts_24h': len(recent_alerts),
                'by_severity': dict(severity_counts),
                'by_rule': dict(rule_counts),
                'total_rules': len(self.rules)
            }


if __name__ == '__main__':
    # Demo usage
    print("Alert Manager Demo\n" + "="*50 + "\n")
    
    # Create alert manager without default rules for faster demo
    alert_mgr = AlertManager()
    
    # Add simple immediate alert rules (no for_duration)
    alert_mgr.add_rule(AlertRule(
        name='HighMAE',
        condition=lambda m: (lambda val: val > 10.0 if isinstance(val, (int, float)) else False)(m.get('gauges', {}).get('model_mae', 0)),
        severity='P2',
        message='Model MAE too high',
        for_duration=0,  # Alert immediately
        cooldown=60
    ))
    
    alert_mgr.add_rule(AlertRule(
        name='HighDrift',
        condition=lambda m: (lambda val: val > 0.3 if isinstance(val, (int, float)) else False)(m.get('gauges', {}).get('model_drift_psi', 0)),
        severity='P1',
        message='Severe drift detected',
        for_duration=0,
        cooldown=60
    ))
    
    # Simulate metrics with problems
    problem_metrics = {
        'gauges': {
            'model_mae': 12.5,  # Too high!
            'model_r2': 0.65,
            'model_drift_psi': 0.35  # Severe drift!
        },
        'counters': {
            'predictions_total': {'total': 1000},
            'predictions_errors_total': {'total': 60},
            'trainings_failed_total': {'total': 0}
        }
    }
    
    print("Checking metrics with problems...")
    alert_mgr.check_and_alert(problem_metrics)
    
    print("\n🚨 Active Alerts:")
    active = alert_mgr.get_active_alerts()
    if active:
        for alert in active:
            print(f"  - {alert.rule_name} [{alert.severity}]: {alert.message}")
    else:
        print("  No alerts triggered yet (they need sustained conditions)")
    
    print(f"\n📊 Statistics:")
    print(f"  Total rules: {len(alert_mgr.rules)}")
    print(f"  Active alerts: {len(alert_mgr.active_alerts)}")
    print(f"  Alert history: {len(alert_mgr.alert_history)}")
    
    print("\n✅ Demo complete. Check training/alert_logs/ for alert logs.")
