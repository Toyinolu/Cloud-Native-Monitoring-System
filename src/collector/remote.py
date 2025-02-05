from __future__ import annotations

import time
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreaker:
    failure_count: int = 0
    last_failure_time: float = 0.0
    is_open: bool = False

    def record_failure(self, threshold: int, cooldown: float):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= threshold:
            self.is_open = True
            logger.warning(
                f"Circuit breaker OPEN after {self.failure_count} failures. "
                f"Cooldown: {cooldown}s"
            )

    def record_success(self):
        self.failure_count = 0
        self.is_open = False

    def should_skip(self, cooldown: float) -> bool:
        if not self.is_open:
            return False
        elapsed = time.time() - self.last_failure_time
        if elapsed >= cooldown:
            logger.info("Circuit breaker cooldown expired, retrying")
            self.is_open = False
            self.failure_count = 0
            return False
        return True


class RemoteCollector:

    def __init__(
        self,
        servers: list[dict],
        timeout: int = 10,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
    ):
        self.servers = servers
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.circuit_breakers: dict[str, CircuitBreaker] = {
            server["host"]: CircuitBreaker() for server in servers
        }

    async def _fetch_metrics(
        self, session: aiohttp.ClientSession, server: dict
    ) -> Optional[dict]:
        host = server["host"]
        port = server.get("port", 5000)
        name = server.get("name", host)

        breaker = self.circuit_breakers[host]
        if breaker.should_skip(self.cooldown_seconds):
            logger.debug(f"Skipping {name}, circuit breaker open")
            return None

        url = f"http://{host}:{port}/metrics"
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    breaker.record_success()
                    logger.debug(f"Collected metrics from {name}")
                    return data
                else:
                    logger.warning(f"{name} returned HTTP {response.status}")
                    breaker.record_failure(
                        self.failure_threshold, self.cooldown_seconds
                    )
                    return None
        except asyncio.TimeoutError:
            logger.warning(f"Timeout collecting metrics from {name}")
            breaker.record_failure(self.failure_threshold, self.cooldown_seconds)
            return None
        except aiohttp.ClientError as e:
            logger.warning(f"Connection error for {name}: {e}")
            breaker.record_failure(self.failure_threshold, self.cooldown_seconds)
            return None

    async def collect_all(self) -> list[dict]:
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            tasks = [
                self._fetch_metrics(session, server) for server in self.servers
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        metrics = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Unexpected error during collection: {result}")
            elif result is not None:
                metrics.append(result)

        logger.info(
            f"Collected metrics from {len(metrics)}/{len(self.servers)} servers"
        )
        return metrics
