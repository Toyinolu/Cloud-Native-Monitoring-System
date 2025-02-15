from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field

import psutil

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    timestamp: float
    hostname: str
    cpu_percent: float
    cpu_per_core: list[float]
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    net_bytes_sent: int
    net_bytes_recv: int
    gpu_metrics: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "hostname": self.hostname,
            "cpu_percent": self.cpu_percent,
            "cpu_per_core": self.cpu_per_core,
            "memory_percent": self.memory_percent,
            "memory_used_gb": round(self.memory_used_gb, 2),
            "memory_total_gb": round(self.memory_total_gb, 2),
            "disk_percent": self.disk_percent,
            "disk_used_gb": round(self.disk_used_gb, 2),
            "disk_total_gb": round(self.disk_total_gb, 2),
            "net_bytes_sent": self.net_bytes_sent,
            "net_bytes_recv": self.net_bytes_recv,
            "gpu_metrics": self.gpu_metrics,
        }


class MetricsCollector:

    def __init__(self, hostname: str = "localhost"):
        self.hostname = hostname
        self._gpu_available = self._check_gpu()

    def _check_gpu(self) -> bool:
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            return len(gpus) > 0
        except Exception:
            logger.info("No GPU detected, skipping GPU metrics")
            return False

    def _collect_gpu(self) -> list[dict]:
        if not self._gpu_available:
            return []
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            return [
                {
                    "id": gpu.id,
                    "name": gpu.name,
                    "load_percent": round(gpu.load * 100, 1),
                    "memory_used_mb": round(gpu.memoryUsed, 1),
                    "memory_total_mb": round(gpu.memoryTotal, 1),
                    "memory_percent": round(
                        (gpu.memoryUsed / gpu.memoryTotal) * 100, 1
                    ) if gpu.memoryTotal > 0 else 0.0,
                    "temperature_c": gpu.temperature,
                }
                for gpu in gpus
            ]
        except Exception as e:
            logger.warning(f"GPU metric collection failed: {e}")
            return []

    def collect(self) -> SystemMetrics:
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_per_core = psutil.cpu_percent(interval=0, percpu=True)

        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net = psutil.net_io_counters()

        return SystemMetrics(
            timestamp=time.time(),
            hostname=self.hostname,
            cpu_percent=cpu_percent,
            cpu_per_core=cpu_per_core,
            memory_percent=memory.percent,
            memory_used_gb=memory.used / (1024 ** 3),
            memory_total_gb=memory.total / (1024 ** 3),
            disk_percent=disk.percent,
            disk_used_gb=disk.used / (1024 ** 3),
            disk_total_gb=disk.total / (1024 ** 3),
            net_bytes_sent=net.bytes_sent,
            net_bytes_recv=net.bytes_recv,
            gpu_metrics=self._collect_gpu(),
        )
