"""Metrics API routes."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from stonks.server.dependencies import get_db
from stonks.server.downsampling import downsample_minmax
from stonks.store import get_metric_keys, get_metrics, get_run_by_id

router = APIRouter(tags=["metrics"])


@router.get("/runs/{run_id}/metric-keys")
def get_run_metric_keys(run_id: str, conn: sqlite3.Connection = Depends(get_db)) -> list[str]:
    """Get all metric keys for a run.

    Args:
        run_id: The run UUID.

    Returns:
        List of metric key strings.

    Raises:
        HTTPException: If run not found.
    """
    if get_run_by_id(conn, run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return get_metric_keys(conn, run_id)


@router.get("/runs/{run_id}/metrics")
def get_run_metrics(
    run_id: str,
    key: str = Query(..., description="Metric key to retrieve"),
    downsample: int | None = Query(None, ge=2, description="Target number of points"),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Get a metric time series for a run.

    Args:
        run_id: The run UUID.
        key: The metric key to retrieve.
        downsample: Optional target number of data points.

    Returns:
        Dict with key, steps, values, and timestamps.

    Raises:
        HTTPException: If run not found.
    """
    if get_run_by_id(conn, run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")

    series = get_metrics(conn, run_id, key)

    if downsample is not None:
        series = downsample_minmax(series, downsample)

    return {
        "key": series.key,
        "steps": series.steps,
        "values": series.values,
        "timestamps": series.timestamps,
    }
