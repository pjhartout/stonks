"""Run context manager for stonks experiment tracking."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Literal

from loguru import logger

from stonks.buffer import MetricBuffer
from stonks.exceptions import StonksError
from stonks.hardware import HardwareMonitor
from stonks.models import RunInfo
from stonks.store import (
    create_connection,
    create_experiment,
    create_project,
    create_run,
    finish_run,
    get_latest_run,
    get_max_step,
    get_run_by_id,
    initialize_db,
    insert_metrics,
    reopen_run,
    update_heartbeat,
    update_run_config,
    update_run_notes,
    update_run_tags,
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
        hardware: If True, enable background hardware monitoring.
        hardware_interval: Seconds between hardware polls (minimum 1.0).
        hardware_gpu: Whether to attempt GPU monitoring via pynvml.
        project: Optional project name for top-level grouping.
        run_id: Optional specific run ID. Used with resume to resume a run.
        resume: If True, resume existing run by id (or latest). If "must", raise if not found.
        group: Optional grouping key (e.g. k-fold, sweep).
        job_type: Optional run type (e.g. train, eval).
        tags: Optional list of tags.
        notes: Optional run description.
        prefix: Metric key prefix prepended to all logged metric keys.
    """

    def __init__(
        self,
        experiment_name: str,
        db: str | Path,
        config: dict | None = None,
        run_name: str | None = None,
        strict: bool = False,
        hardware: bool = False,
        hardware_interval: float = 5.0,
        hardware_gpu: bool = True,
        project: str | None = None,
        run_id: str | None = None,
        resume: bool | Literal["must"] | None = None,
        group: str | None = None,
        job_type: str | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
        prefix: str = "",
    ) -> None:
        self._experiment_name = experiment_name
        self._db_path = Path(db)
        self._config = config
        self._run_name = run_name
        self._strict = strict
        self._hardware = hardware
        self._hardware_interval = hardware_interval
        self._hardware_gpu = hardware_gpu
        self._project_name = project
        self._run_id = run_id
        self._resume = resume
        self._group = group
        self._job_type = job_type
        self._tags = tags
        self._notes = notes
        self._prefix = prefix
        self._conn: sqlite3.Connection | None = None
        self._run_info: RunInfo | None = None
        self._buffer: MetricBuffer | None = None
        self._hw_monitor: HardwareMonitor | None = None
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

    @property
    def project(self) -> str | None:
        """Return the project name."""
        return self._project_name

    @property
    def name(self) -> str | None:
        """Return the run display name."""
        return self._run_name

    @property
    def tags(self) -> list[str]:
        """Return the run tags."""
        if self._run_info is not None and self._run_info.tags is not None:
            return self._run_info.tags
        return self._tags or []

    @property
    def group(self) -> str | None:
        """Return the run group."""
        return self._group

    @property
    def job_type(self) -> str | None:
        """Return the run job type."""
        return self._job_type

    @property
    def notes(self) -> str | None:
        """Return the run notes."""
        if self._run_info is not None and self._run_info.notes is not None:
            return self._run_info.notes
        return self._notes

    @property
    def config(self) -> dict | None:
        """Return the run configuration."""
        return self._config

    def start(self) -> Run:
        """Initialize the run: create DB, experiment, run record, and start buffer.

        Returns:
            Self for chaining.
        """
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = create_connection(self._db_path)
        initialize_db(self._conn)

        # Create project if specified.
        project_id = None
        if self._project_name is not None:
            project = create_project(self._conn, self._project_name)
            project_id = project.id

        experiment = create_experiment(self._conn, self._experiment_name, project_id=project_id)

        # Resume logic.
        resumed = self._try_resume(experiment.id)
        if not resumed:
            self._run_info = create_run(
                self._conn,
                experiment_id=experiment.id,
                name=self._run_name,
                config=self._config,
                run_id=self._run_id,
                group=self._group,
                job_type=self._job_type,
                tags=self._tags,
                notes=self._notes,
                prefix=self._prefix,
            )

        self._buffer = MetricBuffer(
            flush_fn=self._flush_metrics,
            strict=self._strict,
        )
        self._buffer.start()

        if self._hardware:
            self._hw_monitor = HardwareMonitor(
                log_fn=self._buffer.add,
                interval=self._hardware_interval,
                enable_gpu=self._hardware_gpu,
            )
            self._hw_monitor.start()

        assert self._run_info is not None
        action = "Resumed" if resumed else "Started"
        logger.info(f"{action} run {self._run_info.id} in experiment '{self._experiment_name}'")
        return self

    def _try_resume(self, experiment_id: str) -> bool:
        """Attempt to resume an existing run.

        Args:
            experiment_id: The experiment to search for resumable runs.

        Returns:
            True if a run was resumed, False otherwise.

        Raises:
            StonksError: If resume="must" and no matching run is found.
        """
        if not self._resume:
            return False

        assert self._conn is not None
        existing: RunInfo | None = None

        if self._run_id is not None:
            existing = get_run_by_id(self._conn, self._run_id)
        else:
            existing = get_latest_run(self._conn, experiment_id)

        if existing is not None:
            self._run_info = existing
            reopen_run(self._conn, existing.id)
            self._step_counter = get_max_step(self._conn, existing.id) + 1
            # Merge any new config into existing.
            if self._config:
                merged = existing.config or {}
                merged.update(self._config)
                self._config = merged
                update_run_config(self._conn, existing.id, merged)
            else:
                self._config = existing.config
            return True

        if self._resume == "must":
            target = self._run_id or f"latest in '{self._experiment_name}'"
            raise StonksError(f"Cannot resume run {target}: not found and resume='must'")

        return False

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

        # Apply prefix if set.
        if self._prefix:
            metrics = {f"{self._prefix}/{k}": v for k, v in metrics.items()}

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

    def set_tags(self, tags: list[str]) -> None:
        """Update the run's tags.

        Args:
            tags: New list of tags.
        """
        if self._conn is None or self._run_info is None:
            raise RuntimeError("Run has not been started. Use as a context manager.")
        self._tags = tags
        self._run_info.tags = tags
        update_run_tags(self._conn, self._run_info.id, tags)

    def set_notes(self, notes: str) -> None:
        """Update the run's notes.

        Args:
            notes: New notes string.
        """
        if self._conn is None or self._run_info is None:
            raise RuntimeError("Run has not been started. Use as a context manager.")
        self._notes = notes
        self._run_info.notes = notes
        update_run_notes(self._conn, self._run_info.id, notes)

    def flush(self) -> None:
        """Flush all buffered metrics to the database."""
        if self._buffer is not None:
            self._buffer.flush()

    def finish(self, status: str = "completed") -> None:
        """Finish the run, flushing all buffered data.

        Args:
            status: Final status (completed, failed, interrupted).
        """
        if self._hw_monitor is not None:
            self._hw_monitor.stop()
            self._hw_monitor = None

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
