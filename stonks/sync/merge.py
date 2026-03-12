"""Merge remote stonks databases into a local database."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from stonks.exceptions import StonksError
from stonks.store.connection import initialize_db


class MergeError(StonksError):
    """Error during database merge."""


@dataclass
class MergeStats:
    """Statistics from a merge operation.

    Attributes:
        remote_name: Name of the remote that was merged.
        new_projects: Number of new projects inserted.
        new_experiments: Number of new experiments inserted.
        new_runs: Number of new runs inserted.
        updated_runs: Number of existing runs updated.
        skipped_runs: Number of unchanged runs skipped.
        metrics_inserted: Number of metric rows inserted.
    """

    remote_name: str
    new_projects: int = 0
    new_experiments: int = 0
    new_runs: int = 0
    updated_runs: int = 0
    skipped_runs: int = 0
    metrics_inserted: int = 0


def check_integrity(db_path: Path) -> bool:
    """Run an integrity check on a SQLite database.

    Args:
        db_path: Path to the database file.

    Returns:
        True if the database passes integrity check, False otherwise.
    """
    if not db_path.exists():
        return False
    try:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        result = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        return result[0] == "ok"
    except (sqlite3.Error, OSError) as e:
        logger.warning(f"Integrity check failed for {db_path}: {e}")
        return False


def merge_remote_db(
    source_path: Path,
    target_conn: sqlite3.Connection,
    remote_name: str = "unknown",
) -> MergeStats:
    """Merge a remote stonks database into the local database.

    Uses ATTACH DATABASE to open the remote DB alongside the local DB.
    Merges in FK order: projects -> experiments -> runs -> metrics.

    For each run in the remote:
    - New run (UUID not in local): insert project/experiment (upsert by name),
      insert run, bulk-insert all metrics.
    - Changed run (local exists but remote has newer heartbeat/ended_at):
      update run record, delete local metrics, re-insert from remote.
    - Unchanged run: skip.

    Args:
        source_path: Path to the remote stonks.db file.
        target_conn: Connection to the local (target) database.
        remote_name: Name of the remote for logging.

    Returns:
        MergeStats with counts of what was merged.

    Raises:
        MergeError: If the merge fails.
    """
    stats = MergeStats(remote_name=remote_name)

    if not source_path.exists():
        raise MergeError(f"Source database not found: {source_path}")

    # Ensure target schema is up to date
    initialize_db(target_conn)

    # Attach the source database
    target_conn.execute("ATTACH DATABASE ? AS source", (str(source_path),))

    try:
        target_conn.execute("BEGIN")

        # Phase 1: Build project ID mapping (source_id -> target_id)
        project_map = _merge_projects(target_conn, stats)

        # Phase 2: Build experiment ID mapping (source_id -> target_id)
        experiment_map = _merge_experiments(target_conn, project_map, stats)

        # Phase 3: Merge runs and metrics
        _merge_runs_and_metrics(target_conn, experiment_map, stats)

        target_conn.execute("COMMIT")
    except Exception as e:
        target_conn.execute("ROLLBACK")
        raise MergeError(f"Merge failed for remote '{remote_name}': {e}") from e
    finally:
        target_conn.execute("DETACH DATABASE source")

    logger.info(
        f"Merged remote '{remote_name}': "
        f"{stats.new_runs} new, {stats.updated_runs} updated, "
        f"{stats.skipped_runs} skipped runs, {stats.metrics_inserted} metrics"
    )
    return stats


def _merge_projects(
    conn: sqlite3.Connection,
    stats: MergeStats,
) -> dict[str, str]:
    """Merge projects from source to target, building an ID mapping.

    Args:
        conn: Connection with source DB attached.
        stats: MergeStats to update.

    Returns:
        Dict mapping source project IDs to target project IDs.
    """
    project_map: dict[str, str] = {}

    source_projects = conn.execute("SELECT id, name, created_at FROM source.projects").fetchall()

    for row in source_projects:
        src_id, name, created_at = row[0], row[1], row[2]

        # Check if project exists in target by name
        existing = conn.execute("SELECT id FROM main.projects WHERE name = ?", (name,)).fetchone()

        if existing:
            project_map[src_id] = existing[0]
        else:
            # Insert new project with source's ID
            conn.execute(
                "INSERT INTO main.projects (id, name, created_at) VALUES (?, ?, ?)",
                (src_id, name, created_at),
            )
            project_map[src_id] = src_id
            stats.new_projects += 1

    return project_map


def _merge_experiments(
    conn: sqlite3.Connection,
    project_map: dict[str, str],
    stats: MergeStats,
) -> dict[str, str]:
    """Merge experiments from source to target, building an ID mapping.

    Args:
        conn: Connection with source DB attached.
        project_map: Mapping of source project IDs to target project IDs.
        stats: MergeStats to update.

    Returns:
        Dict mapping source experiment IDs to target experiment IDs.
    """
    experiment_map: dict[str, str] = {}

    source_experiments = conn.execute(
        "SELECT id, name, description, created_at, metadata, project_id FROM source.experiments"
    ).fetchall()

    for row in source_experiments:
        src_id = row[0]
        name = row[1]
        description = row[2]
        created_at = row[3]
        metadata = row[4]
        src_project_id = row[5]

        # Remap project_id
        target_project_id = project_map.get(src_project_id) if src_project_id else None

        # Check if experiment exists in target by name
        existing = conn.execute(
            "SELECT id FROM main.experiments WHERE name = ?", (name,)
        ).fetchone()

        if existing:
            experiment_map[src_id] = existing[0]
        else:
            # Insert new experiment with source's ID
            conn.execute(
                "INSERT INTO main.experiments "
                "(id, name, description, created_at, metadata, project_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (src_id, name, description, created_at, metadata, target_project_id),
            )
            experiment_map[src_id] = src_id
            stats.new_experiments += 1

    return experiment_map


def _merge_runs_and_metrics(
    conn: sqlite3.Connection,
    experiment_map: dict[str, str],
    stats: MergeStats,
) -> None:
    """Merge runs and their metrics from source to target.

    For each run:
    - New run: insert run + all metrics
    - Changed run: update run, delete old metrics, insert new metrics
    - Unchanged run: skip

    Args:
        conn: Connection with source DB attached.
        experiment_map: Mapping of source experiment IDs to target experiment IDs.
        stats: MergeStats to update.
    """
    source_runs = conn.execute(
        "SELECT id, experiment_id, name, status, config, created_at, ended_at, "
        "last_heartbeat, group_name, job_type, tags, notes, prefix "
        "FROM source.runs"
    ).fetchall()

    for run_row in source_runs:
        src_run_id = run_row[0]
        src_experiment_id = run_row[1]

        # Remap experiment_id
        target_experiment_id = experiment_map.get(src_experiment_id)
        if target_experiment_id is None:
            logger.warning(
                f"Skipping run {src_run_id}: experiment {src_experiment_id} not found in mapping"
            )
            continue

        # Check if run exists in target
        existing_run = conn.execute(
            "SELECT last_heartbeat, ended_at FROM main.runs WHERE id = ?",
            (src_run_id,),
        ).fetchone()

        if existing_run is None:
            # New run: insert run and all its metrics
            _insert_new_run(conn, run_row, target_experiment_id, stats)
        elif _run_has_changed(existing_run, run_row):
            # Changed run: update run, delete old metrics, insert new metrics
            _update_existing_run(conn, run_row, target_experiment_id, stats)
        else:
            # Unchanged: skip
            stats.skipped_runs += 1


def _run_has_changed(
    existing_row: sqlite3.Row | tuple,
    source_row: sqlite3.Row | tuple,
) -> bool:
    """Check if a run has changed since the last sync.

    Compares last_heartbeat and ended_at between local and remote.

    Args:
        existing_row: Local run row (last_heartbeat, ended_at).
        source_row: Source run row (full columns).

    Returns:
        True if the remote run has newer data.
    """
    local_heartbeat = existing_row[0] or 0.0
    local_ended_at = existing_row[1] or 0.0
    source_heartbeat = source_row[7] or 0.0  # last_heartbeat at index 7
    source_ended_at = source_row[6] or 0.0  # ended_at at index 6

    return source_heartbeat > local_heartbeat or source_ended_at > local_ended_at


def _insert_new_run(
    conn: sqlite3.Connection,
    run_row: sqlite3.Row | tuple,
    target_experiment_id: str,
    stats: MergeStats,
) -> None:
    """Insert a new run and all its metrics.

    Args:
        conn: Connection with source DB attached.
        run_row: Source run row.
        target_experiment_id: Remapped experiment ID for the target DB.
        stats: MergeStats to update.
    """
    src_run_id = run_row[0]

    conn.execute(
        "INSERT INTO main.runs "
        "(id, experiment_id, name, status, config, created_at, ended_at, "
        "last_heartbeat, group_name, job_type, tags, notes, prefix) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            src_run_id,
            target_experiment_id,
            run_row[2],  # name
            run_row[3],  # status
            run_row[4],  # config
            run_row[5],  # created_at
            run_row[6],  # ended_at
            run_row[7],  # last_heartbeat
            run_row[8],  # group_name
            run_row[9],  # job_type
            run_row[10],  # tags
            run_row[11],  # notes
            run_row[12],  # prefix
        ),
    )
    stats.new_runs += 1

    # Bulk insert all metrics for this run
    metrics_count = _copy_metrics_for_run(conn, src_run_id)
    stats.metrics_inserted += metrics_count


def _update_existing_run(
    conn: sqlite3.Connection,
    run_row: sqlite3.Row | tuple,
    target_experiment_id: str,
    stats: MergeStats,
) -> None:
    """Update an existing run and replace its metrics.

    Remote wins for all fields.

    Args:
        conn: Connection with source DB attached.
        run_row: Source run row.
        target_experiment_id: Remapped experiment ID for the target DB.
        stats: MergeStats to update.
    """
    src_run_id = run_row[0]

    # Update all run fields (remote wins)
    conn.execute(
        "UPDATE main.runs SET "
        "experiment_id = ?, name = ?, status = ?, config = ?, "
        "ended_at = ?, last_heartbeat = ?, group_name = ?, "
        "job_type = ?, tags = ?, notes = ?, prefix = ? "
        "WHERE id = ?",
        (
            target_experiment_id,
            run_row[2],  # name
            run_row[3],  # status
            run_row[4],  # config
            run_row[6],  # ended_at
            run_row[7],  # last_heartbeat
            run_row[8],  # group_name
            run_row[9],  # job_type
            run_row[10],  # tags
            run_row[11],  # notes
            run_row[12],  # prefix
            src_run_id,
        ),
    )

    # Delete old metrics and re-insert from remote
    conn.execute("DELETE FROM main.metrics WHERE run_id = ?", (src_run_id,))
    metrics_count = _copy_metrics_for_run(conn, src_run_id)

    stats.updated_runs += 1
    stats.metrics_inserted += metrics_count


def _copy_metrics_for_run(conn: sqlite3.Connection, run_id: str) -> int:
    """Copy all metrics for a run from source to target.

    Args:
        conn: Connection with source DB attached.
        run_id: The run ID to copy metrics for.

    Returns:
        Number of metrics copied.
    """
    conn.execute(
        "INSERT INTO main.metrics (run_id, key, value, step, timestamp) "
        "SELECT run_id, key, value, step, timestamp "
        "FROM source.metrics WHERE run_id = ?",
        (run_id,),
    )
    count = conn.execute(
        "SELECT COUNT(*) FROM source.metrics WHERE run_id = ?", (run_id,)
    ).fetchone()[0]
    return count
