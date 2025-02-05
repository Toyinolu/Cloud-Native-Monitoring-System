import json

from src.api.health import create_app
from src.alerting.engine import AlertEngine, AlertRule


class TestHealthAPI:

    def setup_method(self):
        app = create_app()
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_health_returns_200(self):
        response = self.client.get("/health")
        assert response.status_code == 200

    def test_health_response_structure(self):
        response = self.client.get("/health")
        data = json.loads(response.data)
        assert "status" in data
        assert data["status"] == "healthy"
        assert "uptime_seconds" in data
        assert "timestamp" in data

    def test_metrics_returns_200(self):
        response = self.client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_response_has_cpu(self):
        response = self.client.get("/metrics")
        data = json.loads(response.data)
        assert "cpu_percent" in data
        assert "memory_percent" in data
        assert "hostname" in data


class TestAlertsAPI:

    def setup_method(self):
        rules = [
            AlertRule(metric="cpu_percent", operator=">", threshold=80.0),
        ]
        self.engine = AlertEngine(rules=rules)
        app = create_app(alert_engine=self.engine)
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_alerts_returns_200(self):
        response = self.client.get("/alerts")
        assert response.status_code == 200

    def test_alerts_empty_initially(self):
        response = self.client.get("/alerts")
        data = json.loads(response.data)
        assert data["total"] == 0
        assert data["alerts"] == []
