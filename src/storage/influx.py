import logging
from datetime import datetime

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

logger = logging.getLogger(__name__)


class InfluxStorage:

    def __init__(
        self,
        url: str = "http://localhost:8086",
        token: str = "",
        org: str = "cloud-monitor",
        bucket: str = "metrics",
    ):
        self.url = url
        self.org = org
        self.bucket = bucket
        self._client = InfluxDBClient(url=url, token=token, org=org)
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
        self._query_api = self._client.query_api()

    def write_metrics(self, metrics: dict) -> bool:
        try:
            hostname = metrics.get("hostname", "unknown")
            timestamp = datetime.utcfromtimestamp(metrics["timestamp"])

            points = [
                Point("cpu")
                .tag("host", hostname)
                .field("usage_percent", float(metrics["cpu_percent"]))
                .time(timestamp, WritePrecision.S),
                Point("memory")
                .tag("host", hostname)
                .field("usage_percent", float(metrics["memory_percent"]))
                .field("used_gb", float(metrics["memory_used_gb"]))
                .field("total_gb", float(metrics["memory_total_gb"]))
                .time(timestamp, WritePrecision.S),
                Point("disk")
                .tag("host", hostname)
                .field("usage_percent", float(metrics["disk_percent"]))
                .field("used_gb", float(metrics["disk_used_gb"]))
                .field("total_gb", float(metrics["disk_total_gb"]))
                .time(timestamp, WritePrecision.S),
                Point("network")
                .tag("host", hostname)
                .field("bytes_sent", int(metrics["net_bytes_sent"]))
                .field("bytes_recv", int(metrics["net_bytes_recv"]))
                .time(timestamp, WritePrecision.S),
            ]

            for i, core_pct in enumerate(metrics.get("cpu_per_core", [])):
                points.append(
                    Point("cpu_core")
                    .tag("host", hostname)
                    .tag("core", str(i))
                    .field("usage_percent", float(core_pct))
                    .time(timestamp, WritePrecision.S)
                )

            for gpu in metrics.get("gpu_metrics", []):
                points.append(
                    Point("gpu")
                    .tag("host", hostname)
                    .tag("gpu_id", str(gpu["id"]))
                    .tag("gpu_name", gpu["name"])
                    .field("load_percent", float(gpu["load_percent"]))
                    .field("memory_percent", float(gpu["memory_percent"]))
                    .field("memory_used_mb", float(gpu["memory_used_mb"]))
                    .field("temperature_c", float(gpu["temperature_c"]))
                    .time(timestamp, WritePrecision.S)
                )

            self._write_api.write(bucket=self.bucket, record=points)
            logger.debug(f"Wrote {len(points)} points for {hostname}")
            return True

        except Exception as e:
            logger.error(f"Failed to write metrics to InfluxDB: {e}")
            return False

    def query_latest(self, hostname: str, metric: str = "cpu") -> list[dict]:
        query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: -1h)
            |> filter(fn: (r) => r._measurement == "{metric}")
            |> filter(fn: (r) => r.host == "{hostname}")
            |> last()
        '''
        try:
            tables = self._query_api.query(query, org=self.org)
            results = []
            for table in tables:
                for record in table.records:
                    results.append({
                        "time": record.get_time().isoformat(),
                        "field": record.get_field(),
                        "value": record.get_value(),
                    })
            return results
        except Exception as e:
            logger.error(f"InfluxDB query failed: {e}")
            return []

    def close(self):
        self._client.close()
        logger.info("InfluxDB connection closed")
