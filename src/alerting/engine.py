from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AlertRule:
    metric: str
    operator: str  # ">" or "<"
    threshold: float
    severity: str = "warning"


@dataclass
class Alert:
    hostname: str
    metric: str
    value: float
    threshold: float
    severity: str
    timestamp: float
    message: str


class AlertEngine:

    def __init__(
        self,
        rules: list[AlertRule],
        cooldown_seconds: float = 300.0,
    ):
        self.rules = rules
        self.cooldown_seconds = cooldown_seconds
        self._last_alert: dict[tuple[str, str], float] = {}
        self.alert_history: list[Alert] = []

    def _is_in_cooldown(self, hostname: str, metric: str, severity: str) -> bool:
        key = (hostname, metric, severity)
        last_time = self._last_alert.get(key, 0)
        return (time.time() - last_time) < self.cooldown_seconds

    def _evaluate_rule(self, rule: AlertRule, value: float) -> bool:
        if rule.operator == ">":
            return value > rule.threshold
        elif rule.operator == "<":
            return value < rule.threshold
        return False

    def _extract_metric_value(self, metrics: dict, metric_name: str) -> Optional[float]:
        if metric_name in metrics:
            return metrics[metric_name]

        # nested GPU metrics use dot notation, e.g. "gpu.0.load_percent"
        parts = metric_name.split(".")
        if parts[0] == "gpu" and len(parts) == 3:
            gpu_list = metrics.get("gpu_metrics", [])
            try:
                idx = int(parts[1])
                if idx < len(gpu_list):
                    return gpu_list[idx].get(parts[2])
            except (ValueError, IndexError):
                pass

        return None

    def evaluate(self, metrics: dict) -> list[Alert]:
        hostname = metrics.get("hostname", "unknown")
        triggered = []

        for rule in self.rules:
            value = self._extract_metric_value(metrics, rule.metric)
            if value is None:
                continue

            if not self._evaluate_rule(rule, value):
                continue

            if self._is_in_cooldown(hostname, rule.metric, rule.severity):
                logger.debug(
                    f"Alert suppressed (cooldown): {hostname}/{rule.metric}"
                )
                continue

            alert = Alert(
                hostname=hostname,
                metric=rule.metric,
                value=round(value, 1),
                threshold=rule.threshold,
                severity=rule.severity,
                timestamp=time.time(),
                message=(
                    f"{rule.severity.upper()}: {rule.metric} is {value:.1f}% "
                    f"on {hostname} (threshold: {rule.threshold}%)"
                ),
            )

            self._last_alert[(hostname, rule.metric, rule.severity)] = time.time()
            self.alert_history.append(alert)
            triggered.append(alert)
            logger.warning(alert.message)

        return triggered
