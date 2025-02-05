import time

from src.alerting.engine import AlertEngine, AlertRule, Alert


def _make_metrics(cpu=50.0, memory=50.0, disk=50.0, hostname="test-host"):
    return {
        "hostname": hostname,
        "timestamp": time.time(),
        "cpu_percent": cpu,
        "memory_percent": memory,
        "disk_percent": disk,
        "cpu_per_core": [cpu],
        "memory_used_gb": 4.0,
        "memory_total_gb": 16.0,
        "disk_used_gb": 50.0,
        "disk_total_gb": 100.0,
        "net_bytes_sent": 1000,
        "net_bytes_recv": 2000,
        "gpu_metrics": [],
    }


class TestAlertEngine:

    def setup_method(self):
        self.rules = [
            AlertRule(metric="cpu_percent", operator=">", threshold=80.0, severity="warning"),
            AlertRule(metric="memory_percent", operator=">", threshold=80.0, severity="warning"),
            AlertRule(metric="disk_percent", operator=">", threshold=85.0, severity="critical"),
        ]
        self.engine = AlertEngine(rules=self.rules, cooldown_seconds=300)

    def test_no_alert_below_threshold(self):
        metrics = _make_metrics(cpu=50.0, memory=60.0, disk=40.0)
        alerts = self.engine.evaluate(metrics)
        assert len(alerts) == 0

    def test_alert_fires_above_threshold(self):
        metrics = _make_metrics(cpu=92.0)
        alerts = self.engine.evaluate(metrics)
        assert len(alerts) == 1
        assert alerts[0].metric == "cpu_percent"
        assert alerts[0].value == 92.0
        assert alerts[0].severity == "warning"

    def test_multiple_alerts_fire(self):
        metrics = _make_metrics(cpu=85.0, memory=90.0, disk=95.0)
        alerts = self.engine.evaluate(metrics)
        assert len(alerts) == 3

    def test_cooldown_suppresses_repeat_alerts(self):
        metrics = _make_metrics(cpu=92.0)
        alerts1 = self.engine.evaluate(metrics)
        assert len(alerts1) == 1
        alerts2 = self.engine.evaluate(metrics)
        assert len(alerts2) == 0

    def test_different_hosts_alert_independently(self):
        metrics1 = _make_metrics(cpu=92.0, hostname="host-1")
        metrics2 = _make_metrics(cpu=92.0, hostname="host-2")
        alerts1 = self.engine.evaluate(metrics1)
        alerts2 = self.engine.evaluate(metrics2)
        assert len(alerts1) == 1
        assert len(alerts2) == 1

    def test_alert_history_tracked(self):
        metrics = _make_metrics(cpu=92.0, memory=90.0)
        self.engine.evaluate(metrics)
        assert len(self.engine.alert_history) == 2

    def test_alert_message_format(self):
        metrics = _make_metrics(cpu=92.0)
        alerts = self.engine.evaluate(metrics)
        assert "92.0%" in alerts[0].message
        assert "test-host" in alerts[0].message
