"""Run context manager for stonks experiment tracking."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType

from loguru import logger

from stonks.buffer import MetricBuffer
from stonks.models import RunInfo
from stonks.store import (
    create_connection,
    create_experiment,
    create_run,
    finish_run,
    initialize_db,
    insert_metrics,
    update_heartbeat,
    update_run_config,
)


class Run:
    """A training run that logs metrics to SQLite.

    Use as a context manager for automatic lifecycle management:

        with Run("my-experiment", db="./stonks.db") as run:
            run.log({"loss": 0.5}, step=1)

    Args:
        experiment_name: Name of the experiment to log under.
        db: Path to the SQLite database file.
        config: Optional hyperparameter configuration dict.
        run_name: Optional display name for this run.
        strict: If True, raise on logging errors. If False, swallow and warn.
    """

    def __init__(
        self,
        experiment_name: str,
        db: str | Path,
        config: dict | None = None,
        run_name: str | None = None,
        strict: bool = False,
    ) -> None:
        self._experiment_name = experiment_name
        self._db_path = Path(db)
        self._config = config
        self._run_name = run_name
        self._strict = strict
        self._conn: sqlite3.Connection | None = None
        self._run_info: RunInfo | None = None
        self._buffer: MetricBuffer | None = None
        self._step_counter = 0

    @property
    def id(self) -> str:
        """Return the run ID."""
        if self._run_info is None:
            raise RuntimeError("Run has not been started. Use as a context manager.")
        return self._run_info.id

    @property
    def experiment_id(self) -> str:
        """Return the experiment ID."""
        if self._run_info is None:
            raise RuntimeError("Run has not been started. Use as a context manager.")
        return self._run_info.experiment_id

    def start(self) -> Run:
        """Initialize the run: create DB, experiment, run record, and start buffer.

        Returns:
            Self for chaining.
        """
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = create_connection(self._db_path)
        initialize_db(self._conn)

        experiment = create_experiment(self._conn, self._experiment_name)
        self._run_info = create_run(
            self._conn,
            experiment_id=experiment.id,
            name=self._run_name,
            config=self._config,
        )

        self._buffer = MetricBuffer(
            flush_fn=self._flush_metrics,
            strict=self._strict,
        )
        self._buffer.start()

        logger.info(f"Started run {self._run_info.id} in experiment '{self._experiment_name}'")
        return self

    def log(self, metrics: dict[str, int | float], step: int | None = None) -> None:
        """Log metrics for the current step.

        Args:
            metrics: Dictionary mapping metric names to numeric values.
            step: Optional step number. Auto-increments if not provided.
        """
        if self._buffer is None:
            raise RuntimeError("Run has not been started. Use as a context manager.")

        if step is None:
            step = self._step_counter
            self._step_counter += 1
        else:
            self._step_counter = step + 1

        try:
            self._buffer.add(metrics, step)
        except Exception:
            if self._strict:
                raise
            logger.exception(f"Failed to log metrics at step {step}")

    def log_config(self, config: dict) -> None:
        """Update the run's hyperparameter configuration.

        Args:
            config: Configuration dictionary to store.
        """
        if self._conn is None or self._run_info is None:
            raise RuntimeError("Run has not been started. Use as a context manager.")

        if self._config is None:
            self._config = {}
        self._config.update(config)
        update_run_config(self._conn, self._run_info.id, self._config)

    def flush(self) -> None:
        """Flush all buffered metrics to the database."""
        if self._buffer is not None:
            self._buffer.flush()

    def finish(self, status: str = "completed") -> None:
        """Finish the run, flushing all buffered data.

        Args:
            status: Final status (completed, failed, interrupted).
        """
        if self._buffer is not None:
            self._buffer.stop()
            self._buffer = None

        if self._conn is not None and self._run_info is not None:
            finish_run(self._conn, self._run_info.id, status)
            logger.info(f"Finished run {self._run_info.id} with status '{status}'")

        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _flush_metrics(self, batch: list[tuple[str, float | None, int, float]]) -> None:
        """Flush a batch of metrics to SQLite.

        Args:
            batch: List of (key, value, step, timestamp) tuples.
        """
        if self._conn is None or self._run_info is None:
            return
        insert_metrics(self._conn, self._run_info.id, batch)
        update_heartbeat(self._conn, self._run_info.id)

    def __enter__(self) -> Run:
        """Enter the context manager, starting the run."""
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context manager, finishing the run."""
        if exc_type is KeyboardInterrupt:
            self.finish("interrupted")
        elif exc_type is not None:
            self.finish("failed")
        else:
            self.finish("completed")
