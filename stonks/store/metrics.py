"""Metric data access operations."""

from __future__ import annotations

import sqlite3

from stonks.models import MetricSeries


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


def count_metrics(conn: sqlite3.Connection) -> int:
    """Count total number of metric data points.

    Args:
        conn: Active database connection.

    Returns:
        Total metric count.
    """
    row = conn.execute("SELECT COUNT(*) AS cnt FROM metrics").fetchone()
    return row["cnt"]
