"""Experiment data access operations."""

from __future__ import annotations

import sqlite3
import time
import uuid

from loguru import logger

from stonks.models import Experiment


def _row_to_experiment(row: sqlite3.Row) -> Experiment:
    """Convert a database row to an Experiment instance.

    Args:
        row: SQLite row from the experiments table.

    Returns:
        Experiment instance.
    """
    return Experiment(
        id=row["id"],
        name=row["name"],
        created_at=row["created_at"],
        description=row["description"],
        project_id=row["project_id"] if "project_id" in row.keys() else None,
    )


def create_experiment(
    conn: sqlite3.Connection,
    name: str,
    description: str | None = None,
    project_id: str | None = None,
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
            "INSERT INTO experiments (id, name, description, created_at, project_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (experiment_id, name, description, now, project_id),
        )
        conn.commit()
        logger.debug(f"Created experiment '{name}' with id {experiment_id}")
        return Experiment(
            id=experiment_id,
            name=name,
            created_at=now,
            description=description,
            project_id=project_id,
        )
    except sqlite3.IntegrityError:
        row = conn.execute("SELECT * FROM experiments WHERE name = ?", (name,)).fetchone()
        logger.debug(f"Experiment '{name}' already exists, returning existing")
        return Experiment(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            description=row["description"],
            project_id=row["project_id"],
        )


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
    return _row_to_experiment(row)


def list_experiments(conn: sqlite3.Connection) -> list[Experiment]:
    """List all experiments ordered by creation time.

    Args:
        conn: Active database connection.

    Returns:
        List of Experiment objects.
    """
    rows = conn.execute("SELECT * FROM experiments ORDER BY created_at DESC").fetchall()
    return [_row_to_experiment(row) for row in rows]


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
            "project_id": row["project_id"] if "project_id" in row.keys() else None,
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


def delete_experiment(conn: sqlite3.Connection, experiment_id: str) -> bool:
    """Delete an experiment, all its runs, and their metrics.

    Args:
        conn: Active database connection.
        experiment_id: The experiment to delete.

    Returns:
        True if the experiment was found and deleted, False otherwise.
    """
    row = conn.execute("SELECT id FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
    if row is None:
        return False
    run_rows = conn.execute(
        "SELECT id FROM runs WHERE experiment_id = ?", (experiment_id,)
    ).fetchall()
    for run_row in run_rows:
        conn.execute("DELETE FROM metrics WHERE run_id = ?", (run_row["id"],))
    conn.execute("DELETE FROM runs WHERE experiment_id = ?", (experiment_id,))
    conn.execute("DELETE FROM experiments WHERE id = ?", (experiment_id,))
    conn.commit()
    logger.debug(f"Deleted experiment {experiment_id}")
    return True
