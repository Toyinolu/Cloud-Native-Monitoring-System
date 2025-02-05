from __future__ import annotations

import os
import re
import logging
from pathlib import Path

import yaml

from src.alerting.engine import AlertRule

logger = logging.getLogger(__name__)

ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def _substitute_env_vars(value):
    if isinstance(value, str):
        def replacer(match):
            var_name = match.group(1)
            env_val = os.environ.get(var_name, "")
            if not env_val:
                logger.warning(f"Environment variable {var_name} is not set")
            return env_val
        return ENV_VAR_PATTERN.sub(replacer, value)
    elif isinstance(value, dict):
        return {k: _substitute_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_substitute_env_vars(item) for item in value]
    return value


class Config:

    def __init__(self, config_path: str = "config.yaml"):
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(path) as f:
            raw = yaml.safe_load(f)

        self._data = _substitute_env_vars(raw)
        logger.info(f"Configuration loaded from {config_path}")

    @property
    def poll_interval(self) -> int:
        return self._data.get("monitor", {}).get("poll_interval", 30)

    @property
    def mode(self) -> str:
        return self._data.get("monitor", {}).get("mode", "local")

    @property
    def servers(self) -> list[dict]:
        return self._data.get("servers", [])

    @property
    def alert_cooldown(self) -> float:
        return self._data.get("alerts", {}).get("cooldown_seconds", 300.0)

    @property
    def alert_rules(self) -> list[AlertRule]:
        rules_data = self._data.get("alerts", {}).get("rules", [])
        return [
            AlertRule(
                metric=r["metric"],
                operator=r["operator"],
                threshold=r["threshold"],
                severity=r.get("severity", "warning"),
            )
            for r in rules_data
        ]

    @property
    def email_config(self) -> dict:
        return self._data.get("email", {})

    @property
    def influxdb_config(self) -> dict:
        return self._data.get("influxdb", {})

    @property
    def api_config(self) -> dict:
        return self._data.get("api", {"host": "0.0.0.0", "port": 5000})

    @property
    def log_level(self) -> str:
        return self._data.get("logging", {}).get("level", "INFO")

    @property
    def log_format(self) -> str:
        return self._data.get("logging", {}).get("format", "json")

    @property
    def circuit_breaker_config(self) -> dict:
        return self._data.get("circuit_breaker", {
            "failure_threshold": 3,
            "cooldown_seconds": 60,
        })
