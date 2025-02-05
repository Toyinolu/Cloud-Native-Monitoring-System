import time

from src.collector.metrics import MetricsCollector, SystemMetrics


class TestMetricsCollector:

    def setup_method(self):
        self.collector = MetricsCollector(hostname="test-host")

    def test_collect_returns_system_metrics(self):
        result = self.collector.collect()
        assert isinstance(result, SystemMetrics)
        assert result.hostname == "test-host"

    def test_cpu_percent_in_range(self):
        result = self.collector.collect()
        assert 0.0 <= result.cpu_percent <= 100.0

    def test_memory_values_valid(self):
        result = self.collector.collect()
        assert 0.0 <= result.memory_percent <= 100.0
        assert result.memory_total_gb > 0
        assert result.memory_used_gb >= 0

    def test_disk_values_valid(self):
        result = self.collector.collect()
        assert 0.0 <= result.disk_percent <= 100.0
        assert result.disk_total_gb > 0

    def test_network_counters_non_negative(self):
        result = self.collector.collect()
        assert result.net_bytes_sent >= 0
        assert result.net_bytes_recv >= 0

    def test_cpu_per_core_matches_core_count(self):
        result = self.collector.collect()
        assert len(result.cpu_per_core) > 0
        for core in result.cpu_per_core:
            assert 0.0 <= core <= 100.0

    def test_to_dict_has_all_fields(self):
        result = self.collector.collect()
        d = result.to_dict()
        expected_keys = {
            "timestamp", "hostname", "cpu_percent", "cpu_per_core",
            "memory_percent", "memory_used_gb", "memory_total_gb",
            "disk_percent", "disk_used_gb", "disk_total_gb",
            "net_bytes_sent", "net_bytes_recv", "gpu_metrics",
        }
        assert set(d.keys()) == expected_keys

    def test_timestamp_is_recent(self):
        result = self.collector.collect()
        assert abs(result.timestamp - time.time()) < 5
