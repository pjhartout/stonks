"""Metrics API routes."""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query

from stonks.models import MetricSeries
from stonks.server.dependencies import get_db
from stonks.server.downsampling import downsample_minmax
from stonks.store import get_all_metrics, get_metric_keys, get_metrics, get_run_by_id

_RANK_PREFIX_RE = re.compile(r"^rank_\d+/")

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


def _aggregate_rank_series(
    rank_series: list[MetricSeries],
    base_key: str,
) -> dict:
    """Aggregate multiple rank series into mean/min/max per step.

    Args:
        rank_series: List of MetricSeries from different ranks.
        base_key: The key name without rank prefix.

    Returns:
        Dict with key, steps, values (mean), values_min, values_max, timestamps.
    """
    # Build step -> list of values across ranks
    step_values: dict[int, list[float]] = defaultdict(list)
    step_timestamps: dict[int, float] = {}
    for series in rank_series:
        for i, step in enumerate(series.steps):
            val = series.values[i]
            if val is not None:
                step_values[step].append(val)
            if step not in step_timestamps:
                step_timestamps[step] = series.timestamps[i]

    steps_sorted = sorted(step_values.keys())
    steps: list[int] = []
    values: list[float | None] = []
    values_min: list[float | None] = []
    values_max: list[float | None] = []
    timestamps: list[float] = []

    for step in steps_sorted:
        vals = step_values[step]
        if not vals:
            continue
        steps.append(step)
        values.append(sum(vals) / len(vals))
        values_min.append(min(vals))
        values_max.append(max(vals))
        timestamps.append(step_timestamps[step])

    return {
        "key": base_key,
        "steps": steps,
        "values": values,
        "values_min": values_min,
        "values_max": values_max,
        "timestamps": timestamps,
    }


@router.get("/runs/{run_id}/metrics/all")
def get_run_all_metrics(
    run_id: str,
    downsample: int | None = Query(None, ge=2, description="Target number of points per key"),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, dict]:
    """Get all metric time series for a run in one request.

    Per-rank keys (rank_N/foo) are aggregated into a single key (foo) with
    mean, min, and max values across ranks.

    Args:
        run_id: The run UUID.
        downsample: Optional target number of data points per key.

    Returns:
        Dict mapping metric key to {steps, values, timestamps, values_min?, values_max?}.

    Raises:
        HTTPException: If run not found.
    """
    if get_run_by_id(conn, run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")

    all_series = get_all_metrics(conn, run_id)

    # Separate rank keys from regular keys
    regular: dict[str, MetricSeries] = {}
    rank_groups: dict[str, list[MetricSeries]] = defaultdict(list)

    for key, series in all_series.items():
        m = _RANK_PREFIX_RE.match(key)
        if m:
            base_key = key[m.end() :]
            rank_groups[base_key].append(series)
        else:
            regular[key] = series

    result: dict[str, dict] = {}

    # Add regular keys
    for key, series in regular.items():
        if downsample is not None:
            series = downsample_minmax(series, downsample)
        result[key] = {
            "key": series.key,
            "steps": series.steps,
            "values": series.values,
            "timestamps": series.timestamps,
        }

    # Add aggregated rank keys (only if no regular key with same name exists)
    for base_key, rank_list in rank_groups.items():
        if base_key in result:
            continue
        agg = _aggregate_rank_series(rank_list, base_key)
        if downsample is not None:
            # Downsample the aggregated series
            tmp = MetricSeries(key=base_key)
            tmp.steps = agg["steps"]
            tmp.values = agg["values"]
            tmp.timestamps = agg["timestamps"]
            tmp = downsample_minmax(tmp, downsample)
            # Also downsample min/max in sync — use same indices
            tmp_min = MetricSeries(key=base_key)
            tmp_min.steps = agg["steps"]
            tmp_min.values = agg["values_min"]
            tmp_min.timestamps = agg["timestamps"]
            tmp_min = downsample_minmax(tmp_min, downsample)
            tmp_max = MetricSeries(key=base_key)
            tmp_max.steps = agg["steps"]
            tmp_max.values = agg["values_max"]
            tmp_max.timestamps = agg["timestamps"]
            tmp_max = downsample_minmax(tmp_max, downsample)
            agg = {
                "key": base_key,
                "steps": tmp.steps,
                "values": tmp.values,
                "values_min": tmp_min.values,
                "values_max": tmp_max.values,
                "timestamps": tmp.timestamps,
            }
        result[base_key] = agg

    return result
