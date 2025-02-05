import time
import logging
from typing import Optional

from flask import Flask, jsonify

from src.collector.metrics import MetricsCollector

logger = logging.getLogger(__name__)


def create_app(
    collector: Optional[MetricsCollector] = None,
    alert_engine=None,
) -> Flask:
    app = Flask(__name__)
    _collector = collector or MetricsCollector()
    _start_time = time.time()

    @app.route("/health", methods=["GET"])
    def health():
        uptime = time.time() - _start_time
        return jsonify({
            "status": "healthy",
            "uptime_seconds": round(uptime, 1),
            "timestamp": time.time(),
        }), 200

    @app.route("/metrics", methods=["GET"])
    def metrics():
        try:
            snapshot = _collector.collect()
            return jsonify(snapshot.to_dict()), 200
        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")
            return jsonify({"error": "Metrics collection failed"}), 500

    @app.route("/alerts", methods=["GET"])
    def alerts():
        if alert_engine is None:
            return jsonify({"alerts": [], "total": 0}), 200

        recent = alert_engine.alert_history[-50:]
        return jsonify({
            "alerts": [
                {
                    "hostname": a.hostname,
                    "metric": a.metric,
                    "value": a.value,
                    "threshold": a.threshold,
                    "severity": a.severity,
                    "timestamp": a.timestamp,
                    "message": a.message,
                }
                for a in recent
            ],
            "total": len(alert_engine.alert_history),
        }), 200

    return app
