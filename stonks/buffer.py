"""Thread-safe metric buffer with background flush for stonks."""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable

from loguru import logger

from stonks.exceptions import InvalidMetricError


class MetricBuffer:
    """Buffers metric data points and flushes them in batches.

    Metrics are accumulated in memory and flushed either when the buffer
    reaches a size threshold or after a time interval, whichever comes first.
    A background thread handles periodic flushing.

    Args:
        flush_fn: Callable that receives a list of (key, value, step, timestamp) tuples.
        max_size: Flush when buffer reaches this many entries.
        flush_interval: Flush every this many seconds.
        strict: If True, raise on invalid metrics. If False, log warning and skip.
    """

    def __init__(
        self,
        flush_fn: Callable[[list[tuple[str, float | None, int, float]]], None],
        max_size: int = 100,
        flush_interval: float = 1.0,
        strict: bool = False,
    ) -> None:
        self._flush_fn = flush_fn
        self._max_size = max_size
        self._flush_interval = flush_interval
        self._strict = strict
        self._buffer: list[tuple[str, float | None, int, float]] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the background flush thread."""
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._thread.start()
        logger.debug("MetricBuffer flush thread started")

    def stop(self) -> None:
        """Stop the background flush thread and flush remaining data."""
        if self._thread is None:
            return
        self._stop_event.set()
        self._thread.join(timeout=5.0)
        self._thread = None
        self.flush()
        logger.debug("MetricBuffer flush thread stopped")

    def add(self, metrics: dict[str, int | float], step: int) -> None:
        """Add metrics to the buffer.

        Args:
            metrics: Dictionary mapping metric keys to numeric values.
            step: The training step number.

        Raises:
            InvalidMetricError: If strict mode is on and a value is Inf.
        """
        timestamp = time.time()
        entries: list[tuple[str, float | None, int, float]] = []

        for key, value in metrics.items():
            if isinstance(value, float) and math.isinf(value):
                if self._strict:
                    raise InvalidMetricError(f"Inf value not allowed for metric '{key}'")
                logger.warning(f"Skipping Inf value for metric '{key}' at step {step}")
                continue

            if isinstance(value, float) and math.isnan(value):
                stored_value = None
            else:
                stored_value = float(value)

            entries.append((key, stored_value, step, timestamp))

        if entries:
            with self._lock:
                self._buffer.extend(entries)
                if len(self._buffer) >= self._max_size:
                    self._flush_locked()

    def flush(self) -> None:
        """Flush all buffered metrics to the store."""
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        """Flush buffer while lock is held. Must be called with self._lock acquired."""
        if not self._buffer:
            return
        batch = list(self._buffer)
        self._buffer.clear()
        try:
            self._flush_fn(batch)
            logger.debug(f"Flushed {len(batch)} metrics")
        except Exception:
            logger.exception(f"Failed to flush {len(batch)} metrics")
            if self._strict:
                raise

    def _flush_loop(self) -> None:
        """Background loop that periodically flushes the buffer."""
        while not self._stop_event.wait(self._flush_interval):
            self.flush()
