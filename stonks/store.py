"""SQLite data access layer for stonks."""

from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path

from loguru import logger

from stonks.models import (
    Experiment,
    MetricSeries,
    RunInfo,
    config_from_json,
    config_to_json,
)

_SCHEMA_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS experiments (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        created_at REAL NOT NULL,
        metadata TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS runs (
        id TEXT PRIMARY KEY,
        experiment_id TEXT NOT NULL,
        name TEXT,
        status TEXT NOT NULL DEFAULT 'running',
        config TEXT,
        created_at REAL NOT NULL,
        ended_at REAL,
        last_heartbeat REAL,
        FOREIGN KEY (experiment_id) REFERENCES experiments(id)
    )""",
    """CREATE TABLE IF NOT EXISTS metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        key TEXT NOT NULL,
        value REAL,
        step INTEGER NOT NULL,
        timestamp REAL NOT NULL,
        FOREIGN KEY (run_id) REFERENCES runs(id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_metrics_run_key_step ON metrics(run_id, key, step)",
    "CREATE INDEX IF NOT EXISTS idx_metrics_run_timestamp ON metrics(run_id, timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_runs_experiment ON runs(experiment_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_experiments_created ON experiments(created_at DESC)",
]


def create_connection(db_path: str | Path) -> sqlite3.Connection:
    """Create an optimized SQLite connection.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Configured sqlite3.Connection.
    """
    conn = sqlite3.connect(str(db_path), timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def initialize_db(conn: sqlite3.Connection) -> None:
    """Create tables and indexes if they don't exist.

    Args:
        conn: Active database connection.
    """
    for statement in _SCHEMA_STATEMENTS:
        conn.execute(statement)
    conn.commit()
    logger.debug("Database schema initialized")


def create_experiment(
    conn: sqlite3.Connection,
    name: str,
    description: str | None = None,
) -> Experiment:
    """Create a new experiment or return existing one by name.

    Args:
        conn: Active database connection.
        name: Experiment name (unique).
        description: Optional description.

    Returns:
        The created or existing Experiment.
    """
    now = time.time()
    experiment_id = str(uuid.uuid4())

    try:
        conn.execute(
            "INSERT INTO experiments (id, name, description, created_at) VALUES (?, ?, ?, ?)",
            (experiment_id, name, description, now),
        )
        conn.commit()
        logger.debug(f"Created experiment '{name}' with id {experiment_id}")
        return Experiment(id=experiment_id, name=name, created_at=now, description=description)
    except sqlite3.IntegrityError:
        row = conn.execute("SELECT * FROM experiments WHERE name = ?", (name,)).fetchone()
        logger.debug(f"Experiment '{name}' already exists, returning existing")
        return Experiment(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            description=row["description"],
        )


def create_run(
    conn: sqlite3.Connection,
    experiment_id: str,
    name: str | None = None,
    config: dict | None = None,
) -> RunInfo:
    """Create a new run within an experiment.

    Args:
        conn: Active database connection.
        experiment_id: Parent experiment ID.
        name: Optional display name for the run.
        config: Optional hyperparameter configuration.

    Returns:
        The created RunInfo.
    """
    run_id = str(uuid.uuid4())
    now = time.time()
    config_json = config_to_json(config)

    conn.execute(
        "INSERT INTO runs (id, experiment_id, name, config, created_at, last_heartbeat) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (run_id, experiment_id, name, config_json, now, now),
    )
    conn.commit()
    logger.debug(f"Created run {run_id} in experiment {experiment_id}")
    return RunInfo(
        id=run_id,
        experiment_id=experiment_id,
        status="running",
        created_at=now,
        name=name,
        config=config,
        last_heartbeat=now,
    )


def insert_metrics(
    conn: sqlite3.Connection,
    run_id: str,
    metrics: list[tuple[str, float | None, int, float]],
) -> None:
    """Batch insert metrics into the database.

    Args:
        conn: Active database connection.
        run_id: The run these metrics belong to.
        metrics: List of (key, value, step, timestamp) tuples.
    """
    conn.executemany(
        "INSERT INTO metrics (run_id, key, value, step, timestamp) VALUES (?, ?, ?, ?, ?)",
        [(run_id, key, value, step, ts) for key, value, step, ts in metrics],
    )
    conn.commit()


def update_heartbeat(conn: sqlite3.Connection, run_id: str) -> None:
    """Update the last_heartbeat timestamp for a run.

    Args:
        conn: Active database connection.
        run_id: The run to update.
    """
    conn.execute(
        "UPDATE runs SET last_heartbeat = ? WHERE id = ?",
        (time.time(), run_id),
    )
    conn.commit()


def finish_run(conn: sqlite3.Connection, run_id: str, status: str) -> None:
    """Mark a run as finished with the given status.

    Args:
        conn: Active database connection.
        run_id: The run to finish.
        status: Final status (completed, failed, interrupted).
    """
    conn.execute(
        "UPDATE runs SET status = ?, ended_at = ? WHERE id = ?",
        (status, time.time(), run_id),
    )
    conn.commit()
    logger.debug(f"Run {run_id} finished with status '{status}'")


def update_run_config(conn: sqlite3.Connection, run_id: str, config: dict) -> None:
    """Update the config for a run.

    Args:
        conn: Active database connection.
        run_id: The run to update.
        config: New configuration dict.
    """
    conn.execute(
        "UPDATE runs SET config = ? WHERE id = ?",
        (config_to_json(config), run_id),
    )
    conn.commit()


def get_experiment_by_id(conn: sqlite3.Connection, experiment_id: str) -> Experiment | None:
    """Get a single experiment by ID.

    Args:
        conn: Active database connection.
        experiment_id: The experiment UUID.

    Returns:
        Experiment if found, None otherwise.
    """
    row = conn.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
    if row is None:
        return None
    return Experiment(
        id=row["id"],
        name=row["name"],
        created_at=row["created_at"],
        description=row["description"],
    )


def list_experiments(conn: sqlite3.Connection) -> list[Experiment]:
    """List all experiments ordered by creation time.

    Args:
        conn: Active database connection.

    Returns:
        List of Experiment objects.
    """
    rows = conn.execute("SELECT * FROM experiments ORDER BY created_at DESC").fetchall()
    return [
        Experiment(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            description=row["description"],
        )
        for row in rows
    ]


def list_experiments_with_run_counts(conn: sqlite3.Connection) -> list[dict]:
    """List all experiments with their run counts in a single query.

    Args:
        conn: Active database connection.

    Returns:
        List of dicts with experiment fields plus run_count.
    """
    rows = conn.execute(
        """SELECT e.*, COUNT(r.id) AS run_count
           FROM experiments e
           LEFT JOIN runs r ON r.experiment_id = e.id
           GROUP BY e.id
           ORDER BY e.created_at DESC""",
    ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "created_at": row["created_at"],
            "run_count": row["run_count"],
        }
        for row in rows
    ]


def count_runs(conn: sqlite3.Connection, experiment_id: str) -> int:
    """Count runs for an experiment.

    Args:
        conn: Active database connection.
        experiment_id: The experiment UUID.

    Returns:
        Number of runs.
    """
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM runs WHERE experiment_id = ?",
        (experiment_id,),
    ).fetchone()
    return row["cnt"]


def get_run_by_id(conn: sqlite3.Connection, run_id: str) -> RunInfo | None:
    """Get a single run by ID.

    Args:
        conn: Active database connection.
        run_id: The run UUID.

    Returns:
        RunInfo if found, None otherwise.
    """
    row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    return RunInfo(
        id=row["id"],
        experiment_id=row["experiment_id"],
        status=row["status"],
        created_at=row["created_at"],
        name=row["name"],
        config=config_from_json(row["config"]),
        ended_at=row["ended_at"],
        last_heartbeat=row["last_heartbeat"],
    )


def list_runs(
    conn: sqlite3.Connection,
    experiment_id: str | None = None,
) -> list[RunInfo]:
    """List runs, optionally filtered by experiment.

    Args:
        conn: Active database connection.
        experiment_id: Optional experiment ID to filter by.

    Returns:
        List of RunInfo objects.
    """
    if experiment_id is not None:
        rows = conn.execute(
            "SELECT * FROM runs WHERE experiment_id = ? ORDER BY created_at DESC",
            (experiment_id,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()

    return [
        RunInfo(
            id=row["id"],
            experiment_id=row["experiment_id"],
            status=row["status"],
            created_at=row["created_at"],
            name=row["name"],
            config=config_from_json(row["config"]),
            ended_at=row["ended_at"],
            last_heartbeat=row["last_heartbeat"],
        )
        for row in rows
    ]


def get_metric_keys(conn: sqlite3.Connection, run_id: str) -> list[str]:
    """Get all metric keys logged for a run.

    Args:
        conn: Active database connection.
        run_id: The run to query.

    Returns:
        List of metric key strings.
    """
    rows = conn.execute(
        "SELECT DISTINCT key FROM metrics WHERE run_id = ? ORDER BY key",
        (run_id,),
    ).fetchall()
    return [row["key"] for row in rows]


def get_metrics(
    conn: sqlite3.Connection,
    run_id: str,
    key: str,
) -> MetricSeries:
    """Get a metric time series for a run.

    Args:
        conn: Active database connection.
        run_id: The run to query.
        key: The metric key to retrieve.

    Returns:
        MetricSeries with steps, values, and timestamps.
    """
    rows = conn.execute(
        "SELECT step, value, timestamp FROM metrics WHERE run_id = ? AND key = ? ORDER BY step",
        (run_id, key),
    ).fetchall()

    series = MetricSeries(key=key)
    for row in rows:
        series.steps.append(row["step"])
        series.values.append(row["value"])
        series.timestamps.append(row["timestamp"])
    return series
