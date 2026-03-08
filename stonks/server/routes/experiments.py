"""Experiment API routes."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from stonks.server.dependencies import get_db
from stonks.store import (
    count_runs,
    delete_experiment,
    get_experiment_by_id,
    list_experiments_with_run_counts,
)

router = APIRouter(tags=["experiments"])


@router.get("/experiments")
def get_experiments(conn: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    """List all experiments with run counts.

    Returns:
        List of experiment dicts with run_count added.
    """
    return list_experiments_with_run_counts(conn)


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: str, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """Get experiment details by ID.

    Args:
        experiment_id: The experiment UUID.

    Returns:
        Experiment dict with run_count.

    Raises:
        HTTPException: If experiment not found.
    """
    exp = get_experiment_by_id(conn, experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    run_count = count_runs(conn, exp.id)
    return {
        "id": exp.id,
        "name": exp.name,
        "description": exp.description,
        "created_at": exp.created_at,
        "project_id": exp.project_id,
        "run_count": run_count,
    }


@router.delete("/experiments/{experiment_id}", status_code=204)
def delete_experiment_endpoint(
    experiment_id: str, conn: sqlite3.Connection = Depends(get_db)
) -> Response:
    """Delete an experiment, all its runs, and their metrics.

    Args:
        experiment_id: The experiment UUID.

    Returns:
        204 No Content on success.

    Raises:
        HTTPException: If experiment not found.
    """
    deleted = delete_experiment(conn, experiment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return Response(status_code=204)
