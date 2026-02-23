"""Stonks - Lightweight ML experiment tracking."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Literal

from stonks.config import resolve_db_path

__version__ = "0.1.0"
from stonks.models import Experiment, MetricPoint, MetricSeries, Project, RunInfo
from stonks.run import Run
from stonks.store import (
    create_connection,
    get_metric_keys,
    get_metrics,
    initialize_db,
    list_experiments,
    list_runs,
)

__all__ = [
    "__version__",
    "Database",
    "Experiment",
    "MetricPoint",
    "MetricSeries",
    "Project",
    "Run",
    "RunInfo",
    "open",
    "start_run",
]


def start_run(
    experiment: str | None = None,
    *,
    project: str | None = None,
    name: str | None = None,
    id: str | None = None,
    resume: bool | Literal["must"] | None = None,
    group: str | None = None,
    job_type: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
    config: dict | None = None,
    prefix: str = "",
    save_dir: str | None = None,
    hardware: bool = False,
    hardware_interval: float = 5.0,
    hardware_gpu: bool = True,
    strict: bool = False,
    # Deprecated parameter names.
    db: str | None = None,
    run_name: str | None = None,
) -> Run:
    """Start a new training run.

    Args:
        experiment: Name of the experiment to log under. Defaults to "default".
        project: Optional project name for top-level grouping.
        name: Optional display name for the run.
        id: Optional run ID. Used with resume to resume a specific run.
        resume: If True, resume existing run. If "must", raise if not found.
        group: Optional grouping key (e.g. k-fold, sweep).
        job_type: Optional run type (e.g. train, eval).
        tags: Optional list of tags.
        notes: Optional run description.
        config: Optional hyperparameter configuration.
        prefix: Metric key prefix prepended to all logged keys.
        save_dir: Path to the database file. Defaults to ./stonks.db or STONKS_DB.
        hardware: If True, enable background hardware monitoring.
        hardware_interval: Seconds between hardware polls (minimum 1.0).
        hardware_gpu: Whether to attempt GPU monitoring via pynvml.
        strict: If True, raise on logging errors instead of swallowing them.
        db: Deprecated. Use save_dir instead.
        run_name: Deprecated. Use name instead.

    Returns:
        A Run instance (use as context manager or call .start() manually).
    """
    # Handle deprecated parameter names.
    if db is not None:
        warnings.warn(
            "The 'db' parameter is deprecated. Use 'save_dir' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if save_dir is None:
            save_dir = db

    if run_name is not None:
        warnings.warn(
            "The 'run_name' parameter is deprecated. Use 'name' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if name is None:
            name = run_name

    if experiment is None:
        experiment = "default"

    db_path = resolve_db_path(save_dir)
    return Run(
        experiment_name=experiment,
        db=db_path,
        config=config,
        run_name=name,
        strict=strict,
        hardware=hardware,
        hardware_interval=hardware_interval,
        hardware_gpu=hardware_gpu,
        project=project,
        run_id=id,
        resume=resume,
        group=group,
        job_type=job_type,
        tags=tags,
        notes=notes,
        prefix=prefix,
    )


class Database:
    """Read-only interface to a stonks database.

    Args:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._conn = create_connection(db_path)
        initialize_db(self._conn)

    def list_experiments(self) -> list[Experiment]:
        """List all experiments.

        Returns:
            List of Experiment objects.
        """
        return list_experiments(self._conn)

    def list_runs(self, experiment_id: str | None = None) -> list[RunInfo]:
        """List runs, optionally filtered by experiment.

        Args:
            experiment_id: Optional experiment ID to filter by.

        Returns:
            List of RunInfo objects.
        """
        return list_runs(self._conn, experiment_id=experiment_id)

    def get_metric_keys(self, run_id: str) -> list[str]:
        """Get all metric keys for a run.

        Args:
            run_id: The run to query.

        Returns:
            List of metric key strings.
        """
        return get_metric_keys(self._conn, run_id)

    def get_metrics(self, run_id: str, key: str) -> MetricSeries:
        """Get a metric time series for a run.

        Args:
            run_id: The run to query.
            key: The metric key to retrieve.

        Returns:
            MetricSeries with steps, values, and timestamps.
        """
        return get_metrics(self._conn, run_id, key)

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> Database:
        """Enter context manager."""
        return self

    def __exit__(self, *args: object) -> None:
        """Exit context manager."""
        self.close()


def open(db: str | None = None) -> Database:
    """Open a stonks database for querying.

    Args:
        db: Path to the database file. Defaults to ./stonks.db or STONKS_DB env var.

    Returns:
        A Database instance for querying experiments and metrics.
    """
    db_path = resolve_db_path(db)
    return Database(db_path)
