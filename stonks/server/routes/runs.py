"""Run API routes."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from stonks.server.dependencies import get_db
from stonks.store import get_run_by_id, list_runs

router = APIRouter(tags=["runs"])


def _run_to_dict(run) -> dict:
    """Convert a RunInfo to a serializable dict.

    Args:
        run: RunInfo instance.

    Returns:
        Dictionary representation.
    """
    return {
        "id": run.id,
        "experiment_id": run.experiment_id,
        "name": run.name,
        "status": run.status,
        "config": run.config,
        "created_at": run.created_at,
        "ended_at": run.ended_at,
        "last_heartbeat": run.last_heartbeat,
        "group": run.group,
        "job_type": run.job_type,
        "tags": run.tags,
        "notes": run.notes,
    }


@router.get("/experiments/{experiment_id}/runs")
def get_experiment_runs(
    experiment_id: str, conn: sqlite3.Connection = Depends(get_db)
) -> list[dict]:
    """List all runs in an experiment.

    Args:
        experiment_id: The experiment UUID.

    Returns:
        List of run dicts.
    """
    runs = list_runs(conn, experiment_id=experiment_id)
    return [_run_to_dict(r) for r in runs]


@router.get("/runs/{run_id}")
def get_run(run_id: str, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """Get run details by ID.

    Args:
        run_id: The run UUID.

    Returns:
        Run dict with full details.

    Raises:
        HTTPException: If run not found.
    """
    run = get_run_by_id(conn, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_to_dict(run)
