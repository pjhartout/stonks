"""Tests for the HardwareMonitor."""

import time
from unittest.mock import patch

from stonks.hardware import HardwareMonitor


class TestHardwareMonitor:
    def test_collects_cpu_and_ram(self):
        """Monitor should collect CPU and RAM metrics."""
        collected = []

        def log_fn(metrics, step):
            collected.append((dict(metrics), step))

        mon = HardwareMonitor(log_fn=log_fn, interval=0.1, enable_gpu=False)
        mon.start()
        time.sleep(0.4)
        mon.stop()

        assert len(collected) >= 1
        first = collected[0][0]
        assert "sys/cpu_percent" in first
        assert "sys/ram_used_gb" in first
        assert "sys/ram_total_gb" in first
        assert "sys/ram_percent" in first

    def test_collects_disk_io(self):
        """Monitor should collect disk I/O metrics when available."""
        collected = []

        def log_fn(metrics, step):
            collected.append(dict(metrics))

        mon = HardwareMonitor(log_fn=log_fn, interval=0.1, enable_gpu=False)
        mon.start()
        time.sleep(0.3)
        mon.stop()

        assert len(collected) >= 1
        first = collected[0]
        # Disk counters may not be available in all environments (e.g. some CI)
        # but if they are, they should be non-negative
        if "sys/disk_read_mb" in first:
            assert first["sys/disk_read_mb"] >= 0
            assert first["sys/disk_write_mb"] >= 0

    def test_collects_network(self):
        """Monitor should collect network metrics when available."""
        collected = []

        def log_fn(metrics, step):
            collected.append(dict(metrics))

        mon = HardwareMonitor(log_fn=log_fn, interval=0.1, enable_gpu=False)
        mon.start()
        time.sleep(0.3)
        mon.stop()

        assert len(collected) >= 1
        first = collected[0]
        if "sys/net_sent_mb" in first:
            assert first["sys/net_sent_mb"] >= 0
            assert first["sys/net_recv_mb"] >= 0

    def test_step_increments(self):
        """Step counter should increment monotonically."""
        steps = []

        def log_fn(metrics, step):
            steps.append(step)

        mon = HardwareMonitor(log_fn=log_fn, interval=1.0, enable_gpu=False)
        mon.start()
        # Need >1s to get at least 2 polls (immediate + 1 interval)
        time.sleep(1.5)
        mon.stop()

        assert len(steps) >= 2
        for i in range(len(steps)):
            assert steps[i] == i

    def test_start_stop_idempotent(self):
        """Calling start/stop multiple times should be safe."""
        collected = []

        def log_fn(metrics, step):
            collected.append(step)

        mon = HardwareMonitor(log_fn=log_fn, interval=0.1, enable_gpu=False)

        # Double start
        mon.start()
        mon.start()
        time.sleep(0.2)

        # Double stop
        mon.stop()
        mon.stop()

        assert len(collected) >= 1

    def test_gpu_skipped_when_disabled(self):
        """No GPU metrics should appear when enable_gpu=False."""
        collected = []

        def log_fn(metrics, step):
            collected.append(dict(metrics))

        mon = HardwareMonitor(log_fn=log_fn, interval=0.1, enable_gpu=False)
        mon.start()
        time.sleep(0.2)
        mon.stop()

        assert len(collected) >= 1
        for snapshot in collected:
            for key in snapshot:
                assert not key.startswith("sys/gpu"), f"Unexpected GPU key: {key}"

    def test_gpu_skipped_when_pynvml_unavailable(self):
        """GPU metrics should be skipped gracefully when pynvml is not installed."""
        collected = []

        def log_fn(metrics, step):
            collected.append(dict(metrics))

        with patch("stonks.hardware._HAS_PYNVML", False):
            mon = HardwareMonitor(log_fn=log_fn, interval=0.1, enable_gpu=True)
            mon.start()
            time.sleep(0.2)
            mon.stop()

        assert len(collected) >= 1
        for snapshot in collected:
            for key in snapshot:
                assert not key.startswith("sys/gpu"), f"Unexpected GPU key: {key}"

    def test_thread_is_daemon(self):
        """The polling thread should be a daemon thread."""
        mon = HardwareMonitor(log_fn=lambda m, s: None, interval=0.1, enable_gpu=False)
        mon.start()
        assert mon._thread is not None
        assert mon._thread.daemon is True
        mon.stop()

    def test_interval_minimum_enforced(self):
        """Interval below 1.0 should be clamped to 1.0."""
        mon = HardwareMonitor(log_fn=lambda m, s: None, interval=0.5, enable_gpu=False)
        assert mon._interval == 1.0

    def test_immediate_first_poll(self):
        """The first poll should happen immediately, before waiting for interval."""
        collected = []

        def log_fn(metrics, step):
            collected.append(time.time())

        mon = HardwareMonitor(log_fn=log_fn, interval=10.0, enable_gpu=False)
        mon.start()
        time.sleep(0.3)
        mon.stop()

        # Should have at least one data point despite 10s interval
        assert len(collected) >= 1
