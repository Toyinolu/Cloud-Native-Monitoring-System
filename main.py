import signal
import asyncio
import logging
import threading

from src.config.loader import Config
from src.logging_config import setup_logging
from src.collector.metrics import MetricsCollector
from src.collector.remote import RemoteCollector
from src.alerting.engine import AlertEngine
from src.alerting.notifier import EmailNotifier
from src.storage.influx import InfluxStorage
from src.api.health import create_app

logger = logging.getLogger(__name__)


class CloudMonitor:

    def __init__(self, config_path: str = "config.yaml"):
        self.config = Config(config_path)
        self._shutdown_event = asyncio.Event()

        setup_logging(
            level=self.config.log_level,
            fmt=self.config.log_format,
        )

        self.collector = MetricsCollector(hostname="monitor-host")
        self.alert_engine = AlertEngine(
            rules=self.config.alert_rules,
            cooldown_seconds=self.config.alert_cooldown,
        )
        self.storage = InfluxStorage(**self.config.influxdb_config)

        email_cfg = self.config.email_config
        if email_cfg.get("username"):
            self.notifier = EmailNotifier(
                smtp_host=email_cfg["smtp_host"],
                smtp_port=email_cfg["smtp_port"],
                username=email_cfg["username"],
                password=email_cfg["password"],
                sender=email_cfg["sender"],
                recipients=email_cfg["recipients"],
                use_tls=email_cfg.get("use_tls", True),
            )
        else:
            self.notifier = None
            logger.warning("Email notifications disabled, SMTP not configured")

        if self.config.mode == "remote":
            cb_config = self.config.circuit_breaker_config
            self.remote_collector = RemoteCollector(
                servers=self.config.servers,
                failure_threshold=cb_config["failure_threshold"],
                cooldown_seconds=cb_config["cooldown_seconds"],
            )
        else:
            self.remote_collector = None

        logger.info(f"Cloud Monitor initialized in {self.config.mode} mode")

    def _start_api(self):
        app = create_app(
            collector=self.collector,
            alert_engine=self.alert_engine,
        )
        api_cfg = self.config.api_config
        app.run(
            host=api_cfg.get("host", "0.0.0.0"),
            port=api_cfg.get("port", 5000),
            use_reloader=False,
            threaded=True,
        )

    def _process_metrics(self, metrics: dict):
        alerts = self.alert_engine.evaluate(metrics)
        for alert in alerts:
            if self.notifier:
                self.notifier.send(alert)
        self.storage.write_metrics(metrics)

    async def _local_loop(self):
        logger.info(
            f"Starting local monitoring loop "
            f"(interval: {self.config.poll_interval}s)"
        )
        while not self._shutdown_event.is_set():
            try:
                snapshot = self.collector.collect()
                metrics = snapshot.to_dict()
                self._process_metrics(metrics)
                logger.info(
                    f"CPU: {metrics['cpu_percent']}%, "
                    f"Memory: {metrics['memory_percent']}%"
                )
            except Exception as e:
                logger.error(f"Error in local collection cycle: {e}")

            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.config.poll_interval,
                )
            except asyncio.TimeoutError:
                pass

    async def _remote_loop(self):
        logger.info(
            f"Starting remote monitoring loop "
            f"({len(self.config.servers)} servers, "
            f"interval: {self.config.poll_interval}s)"
        )
        while not self._shutdown_event.is_set():
            try:
                all_metrics = await self.remote_collector.collect_all()
                for metrics in all_metrics:
                    self._process_metrics(metrics)
            except Exception as e:
                logger.error(f"Error in remote collection cycle: {e}")

            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.config.poll_interval,
                )
            except asyncio.TimeoutError:
                pass

    def _handle_shutdown(self, signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name}, shutting down...")
        self._shutdown_event.set()

    async def run(self):
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        api_thread = threading.Thread(target=self._start_api, daemon=True)
        api_thread.start()
        logger.info("Health check API started")

        try:
            if self.config.mode == "remote":
                await self._remote_loop()
            else:
                await self._local_loop()
        finally:
            self.storage.close()
            logger.info("Cloud Monitor shut down complete")


def main():
    monitor = CloudMonitor()
    asyncio.run(monitor.run())


if __name__ == "__main__":
    main()
