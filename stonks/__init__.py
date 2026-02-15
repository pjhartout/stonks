"""Stonks - Lightweight ML experiment tracking."""

from __future__ import annotations

from pathlib import Path

from stonks.config import resolve_db_path
from stonks.models import Experiment, MetricPoint, MetricSeries, RunInfo
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
    "Database",
    "Experiment",
    "MetricPoint",
    "MetricSeries",
    "Run",
    "RunInfo",
    "open",
    "start_run",
]


def start_run(
    experiment: str,
    config: dict | None = None,
    db: str | None = None,
    run_name: str | None = None,
    strict: bool = False,
) -> Run:
    """Start a new training run.

    Args:
        experiment: Name of the experiment to log under.
        config: Optional hyperparameter configuration.
        db: Path to the database file. Defaults to ./stonks.db or STONKS_DB env var.
        run_name: Optional display name for the run.
        strict: If True, raise on logging errors instead of swallowing them.

    Returns:
        A Run instance (use as context manager or call .start() manually).
    """
    db_path = resolve_db_path(db)
    return Run(
        experiment_name=experiment,
        db=db_path,
        config=config,
        run_name=run_name,
        strict=strict,
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
