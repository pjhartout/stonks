"""Background hardware monitoring for stonks experiment tracking."""

from __future__ import annotations

import threading
from collections.abc import Callable

import psutil
from loguru import logger

try:
    import pynvml

    _HAS_PYNVML = True
except ImportError:
    _HAS_PYNVML = False

_BYTES_TO_MB = 1 / (1024 * 1024)
_BYTES_TO_GB = 1 / (1024 * 1024 * 1024)


class HardwareMonitor:
    """Polls system hardware metrics in a background thread.

    Metrics are logged through a provided callback using ``sys/`` prefixed keys.
    Collects CPU, RAM, disk I/O, and network counters, plus NVIDIA GPU stats
    when pynvml is available and enabled.

    Args:
        log_fn: Callable accepting (metrics_dict, step) — typically ``MetricBuffer.add``.
        interval: Seconds between polls. Minimum 1.0.
        enable_gpu: Whether to attempt GPU monitoring via pynvml.
    """

    def __init__(
        self,
        log_fn: Callable[[dict[str, int | float], int], None],
        interval: float = 5.0,
        enable_gpu: bool = True,
    ) -> None:
        self._log_fn = log_fn
        self._interval = max(1.0, interval)
        self._enable_gpu = enable_gpu and _HAS_PYNVML
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._step = 0
        self._gpu_count = 0
        self._nvml_initialized = False
        self._disk_baseline: tuple[float, float] | None = None
        self._net_baseline: tuple[float, float] | None = None

    def start(self) -> None:
        """Start the hardware monitoring background thread.

        Captures disk/network baselines, primes CPU measurement, and spawns
        a daemon thread that polls immediately then at the configured interval.
        Calling start() on an already-running monitor is a no-op.
        """
        if self._thread is not None:
            return

        self._stop_event.clear()
        self._step = 0

        # Init GPU
        if self._enable_gpu:
            try:
                pynvml.nvmlInit()
                self._gpu_count = pynvml.nvmlDeviceGetCount()
                self._nvml_initialized = True
                logger.info(f"Hardware monitor: found {self._gpu_count} GPU(s)")
            except Exception:
                logger.warning("Hardware monitor: failed to initialize NVML, GPU metrics disabled")
                self._enable_gpu = False
                self._gpu_count = 0

        # Capture baselines for cumulative counters
        try:
            disk = psutil.disk_io_counters()
            if disk is not None:
                self._disk_baseline = (disk.read_bytes, disk.write_bytes)
        except Exception:
            logger.warning("Hardware monitor: disk I/O counters unavailable")

        try:
            net = psutil.net_io_counters()
            if net is not None:
                self._net_baseline = (net.bytes_sent, net.bytes_recv)
        except Exception:
            logger.warning("Hardware monitor: network counters unavailable")

        # Prime cpu_percent (first call always returns 0.0)
        psutil.cpu_percent()

        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info(f"Hardware monitor started (interval={self._interval}s)")

    def stop(self) -> None:
        """Stop the hardware monitoring thread.

        Blocks until the thread exits. Shuts down NVML if it was initialized.
        Calling stop() on a stopped monitor is a no-op.
        """
        if self._thread is None:
            return

        self._stop_event.set()
        self._thread.join(timeout=5.0)
        self._thread = None

        if self._nvml_initialized:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
            self._nvml_initialized = False

        logger.info("Hardware monitor stopped")

    def _collect(self) -> dict[str, float]:
        """Collect all hardware metrics.

        Returns:
            Dictionary of ``sys/``-prefixed metric keys to float values.
            Metrics that fail to collect are silently skipped.
        """
        metrics: dict[str, float] = {}

        # CPU
        try:
            metrics["sys/cpu_percent"] = psutil.cpu_percent()
        except Exception:
            logger.warning("Hardware monitor: failed to collect CPU metrics")

        # RAM
        try:
            mem = psutil.virtual_memory()
            metrics["sys/ram_used_gb"] = mem.used * _BYTES_TO_GB
            metrics["sys/ram_total_gb"] = mem.total * _BYTES_TO_GB
            metrics["sys/ram_percent"] = mem.percent
        except Exception:
            logger.warning("Hardware monitor: failed to collect RAM metrics")

        # Disk I/O (cumulative since run start)
        try:
            disk = psutil.disk_io_counters()
            if disk is not None and self._disk_baseline is not None:
                read_base, write_base = self._disk_baseline
                metrics["sys/disk_read_mb"] = (disk.read_bytes - read_base) * _BYTES_TO_MB
                metrics["sys/disk_write_mb"] = (disk.write_bytes - write_base) * _BYTES_TO_MB
        except Exception:
            logger.warning("Hardware monitor: failed to collect disk I/O metrics")

        # Network (cumulative since run start)
        try:
            net = psutil.net_io_counters()
            if net is not None and self._net_baseline is not None:
                sent_base, recv_base = self._net_baseline
                metrics["sys/net_sent_mb"] = (net.bytes_sent - sent_base) * _BYTES_TO_MB
                metrics["sys/net_recv_mb"] = (net.bytes_recv - recv_base) * _BYTES_TO_MB
        except Exception:
            logger.warning("Hardware monitor: failed to collect network metrics")

        # GPU
        if self._enable_gpu and self._nvml_initialized:
            try:
                for i in range(self._gpu_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)

                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    metrics[f"sys/gpu{i}_util"] = util.gpu

                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    metrics[f"sys/gpu{i}_mem_used_gb"] = mem_info.used * _BYTES_TO_GB
                    metrics[f"sys/gpu{i}_mem_total_gb"] = mem_info.total * _BYTES_TO_GB
                    if mem_info.total > 0:
                        metrics[f"sys/gpu{i}_mem_percent"] = (
                            mem_info.used / mem_info.total
                        ) * 100.0
            except Exception:
                logger.warning("Hardware monitor: failed to collect GPU metrics")

        return metrics

    def _poll_loop(self) -> None:
        """Background loop: poll immediately, then at each interval."""
        # Immediate first poll
        metrics = self._collect()
        if metrics:
            self._log_fn(metrics, self._step)
            self._step += 1

        while not self._stop_event.wait(self._interval):
            metrics = self._collect()
            if metrics:
                self._log_fn(metrics, self._step)
                self._step += 1
