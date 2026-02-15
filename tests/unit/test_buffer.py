"""Tests for stonks MetricBuffer."""

import threading
import time

import pytest

from stonks.buffer import MetricBuffer
from stonks.exceptions import InvalidMetricError


class TestMetricBuffer:
    def test_flush_on_max_size(self):
        flushed = []

        def flush_fn(batch):
            flushed.append(list(batch))

        buf = MetricBuffer(flush_fn=flush_fn, max_size=3)
        buf.add({"a": 1.0, "b": 2.0}, step=0)  # 2 entries
        assert len(flushed) == 0
        buf.add({"c": 3.0}, step=1)  # 3 entries -> flush
        assert len(flushed) == 1
        assert len(flushed[0]) == 3

    def test_manual_flush(self):
        flushed = []

        def flush_fn(batch):
            flushed.append(list(batch))

        buf = MetricBuffer(flush_fn=flush_fn, max_size=100)
        buf.add({"loss": 0.5}, step=0)
        buf.flush()
        assert len(flushed) == 1
        assert flushed[0][0][0] == "loss"

    def test_empty_flush_is_noop(self):
        call_count = 0

        def flush_fn(batch):
            nonlocal call_count
            call_count += 1

        buf = MetricBuffer(flush_fn=flush_fn)
        buf.flush()
        assert call_count == 0

    def test_nan_stored_as_none(self):
        flushed = []

        def flush_fn(batch):
            flushed.append(list(batch))

        buf = MetricBuffer(flush_fn=flush_fn, max_size=100)
        buf.add({"loss": float("nan")}, step=0)
        buf.flush()
        assert flushed[0][0][1] is None

    def test_inf_rejected_in_strict_mode(self):
        buf = MetricBuffer(flush_fn=lambda b: None, strict=True)
        with pytest.raises(InvalidMetricError, match="Inf"):
            buf.add({"loss": float("inf")}, step=0)

    def test_inf_skipped_in_lenient_mode(self):
        flushed = []

        def flush_fn(batch):
            flushed.append(list(batch))

        buf = MetricBuffer(flush_fn=flush_fn, max_size=100, strict=False)
        buf.add({"loss": float("inf"), "acc": 0.9}, step=0)
        buf.flush()
        # Only acc should be in the buffer, inf skipped
        assert len(flushed[0]) == 1
        assert flushed[0][0][0] == "acc"

    def test_background_flush(self):
        flushed = []

        def flush_fn(batch):
            flushed.append(list(batch))

        buf = MetricBuffer(flush_fn=flush_fn, max_size=1000, flush_interval=0.1)
        buf.start()
        buf.add({"loss": 0.5}, step=0)
        time.sleep(0.3)  # Wait for background flush
        buf.stop()
        assert len(flushed) >= 1

    def test_thread_safety(self):
        flushed = []
        lock = threading.Lock()

        def flush_fn(batch):
            with lock:
                flushed.extend(batch)

        buf = MetricBuffer(flush_fn=flush_fn, max_size=50)

        def writer(start):
            for i in range(100):
                buf.add({"loss": float(i)}, step=start + i)

        threads = [threading.Thread(target=writer, args=(i * 100,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        buf.flush()
        assert len(flushed) == 400

    def test_flush_error_swallowed_in_lenient_mode(self):
        def flush_fn(batch):
            raise RuntimeError("DB error")

        buf = MetricBuffer(flush_fn=flush_fn, strict=False)
        buf.add({"loss": 0.5}, step=0)
        buf.flush()  # Should not raise

    def test_flush_error_raised_in_strict_mode(self):
        def flush_fn(batch):
            raise RuntimeError("DB error")

        buf = MetricBuffer(flush_fn=flush_fn, strict=True)
        buf.add({"loss": 0.5}, step=0)
        with pytest.raises(RuntimeError, match="DB error"):
            buf.flush()
