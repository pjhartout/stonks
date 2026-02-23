"""Run data access operations."""

from __future__ import annotations

import sqlite3
import time
import uuid

from loguru import logger

from stonks.models import (
    RunInfo,
    config_from_json,
    config_to_json,
    tags_from_json,
    tags_to_json,
)


def _row_to_run_info(row: sqlite3.Row) -> RunInfo:
    """Convert a database row to a RunInfo instance.

    Args:
        row: SQLite row from the runs table.

    Returns:
        RunInfo instance.
    """
    return RunInfo(
        id=row["id"],
        experiment_id=row["experiment_id"],
        status=row["status"],
        created_at=row["created_at"],
        name=row["name"],
        config=config_from_json(row["config"]),
        ended_at=row["ended_at"],
        last_heartbeat=row["last_heartbeat"],
        group=row["group_name"],
        job_type=row["job_type"],
        tags=tags_from_json(row["tags"]),
        notes=row["notes"],
        prefix=row["prefix"] or "",
    )


def create_run(
    conn: sqlite3.Connection,
    experiment_id: str,
    name: str | None = None,
    config: dict | None = None,
    run_id: str | None = None,
    group: str | None = None,
    job_type: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
    prefix: str = "",
) -> RunInfo:
    """Create a new run within an experiment.

    Args:
        conn: Active database connection.
        experiment_id: Parent experiment ID.
        name: Optional display name for the run.
        config: Optional hyperparameter configuration.
        run_id: Optional specific run ID (for deterministic IDs).
        group: Optional grouping key (e.g. k-fold, sweep).
        job_type: Optional run type (e.g. train, eval).
        tags: Optional list of tags.
        notes: Optional run description.
        prefix: Metric key prefix (default empty).

    Returns:
        The created RunInfo.
    """
    if run_id is None:
        run_id = str(uuid.uuid4())
    now = time.time()
    config_json = config_to_json(config)
    tags_json = tags_to_json(tags)

    conn.execute(
        "INSERT INTO runs (id, experiment_id, name, config, created_at, last_heartbeat, "
        "group_name, job_type, tags, notes, prefix) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id,
            experiment_id,
            name,
            config_json,
            now,
            now,
            group,
            job_type,
            tags_json,
            notes,
            prefix,
        ),
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
        group=group,
        job_type=job_type,
        tags=tags,
        notes=notes,
        prefix=prefix,
    )


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
    return _row_to_run_info(row)


def get_latest_run(conn: sqlite3.Connection, experiment_id: str) -> RunInfo | None:
    """Get the most recently created run for an experiment.

    Args:
        conn: Active database connection.
        experiment_id: The experiment to query.

    Returns:
        Most recent RunInfo, or None if no runs exist.
    """
    row = conn.execute(
        "SELECT * FROM runs WHERE experiment_id = ? ORDER BY created_at DESC LIMIT 1",
        (experiment_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_run_info(row)


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

    return [_row_to_run_info(row) for row in rows]


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


def reopen_run(conn: sqlite3.Connection, run_id: str) -> None:
    """Reopen a finished run for resumed logging.

    Sets status back to 'running' and updates the heartbeat.

    Args:
        conn: Active database connection.
        run_id: The run to reopen.
    """
    conn.execute(
        "UPDATE runs SET status = 'running', ended_at = NULL, last_heartbeat = ? WHERE id = ?",
        (time.time(), run_id),
    )
    conn.commit()
    logger.debug(f"Reopened run {run_id}")


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


def get_max_step(conn: sqlite3.Connection, run_id: str) -> int:
    """Get the maximum step number for a run.

    Args:
        conn: Active database connection.
        run_id: The run to query.

    Returns:
        Maximum step number, or -1 if no metrics exist.
    """
    row = conn.execute(
        "SELECT MAX(step) AS max_step FROM metrics WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    if row["max_step"] is None:
        return -1
    return row["max_step"]


def update_run_tags(conn: sqlite3.Connection, run_id: str, tags: list[str]) -> None:
    """Update the tags for a run.

    Args:
        conn: Active database connection.
        run_id: The run to update.
        tags: New list of tags.
    """
    conn.execute(
        "UPDATE runs SET tags = ? WHERE id = ?",
        (tags_to_json(tags), run_id),
    )
    conn.commit()


def update_run_notes(conn: sqlite3.Connection, run_id: str, notes: str) -> None:
    """Update the notes for a run.

    Args:
        conn: Active database connection.
        run_id: The run to update.
        notes: New notes string.
    """
    conn.execute(
        "UPDATE runs SET notes = ? WHERE id = ?",
        (notes, run_id),
    )
    conn.commit()


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


def delete_run(conn: sqlite3.Connection, run_id: str) -> bool:
    """Delete a run and its metrics.

    Args:
        conn: Active database connection.
        run_id: The run to delete.

    Returns:
        True if the run was found and deleted, False otherwise.
    """
    row = conn.execute("SELECT id FROM runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        return False
    conn.execute("DELETE FROM metrics WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
    conn.commit()
    logger.debug(f"Deleted run {run_id}")
    return True
