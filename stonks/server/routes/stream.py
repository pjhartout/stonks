"""Server-Sent Events (SSE) streaming for real-time metric updates."""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse

from stonks.server.dependencies import get_manager

router = APIRouter(tags=["stream"])

POLL_INTERVAL = 1.0

_LIGHTWEIGHT_RUNS_QUERY = (
    "SELECT id, status, name, created_at, ended_at, last_heartbeat "
    "FROM runs WHERE experiment_id = ? ORDER BY created_at DESC"
)


@router.get("/events")
async def stream_events(
    experiment_id: str = Query(..., description="Experiment ID to stream events for"),
) -> EventSourceResponse:
    """Stream run status changes and metric heartbeats via SSE.

    Clients receive `run_update` events when runs change status, and
    `metrics_update` events when running runs have new data (signaled by
    heartbeat updates). The client should refetch metrics via REST on
    receiving a `metrics_update` event.

    Args:
        experiment_id: The experiment UUID to watch.

    Returns:
        EventSourceResponse with real-time updates.
    """

    async def event_generator():
        manager = get_manager()
        conn = manager.connect()
        try:
            last_check = time.time()
            known_run_statuses: dict[str, str] = {}

            while True:
                rows = conn.execute(_LIGHTWEIGHT_RUNS_QUERY, (experiment_id,)).fetchall()
                current_time = time.time()

                for row in rows:
                    run_id = row["id"]
                    status = row["status"]
                    old_status = known_run_statuses.get(run_id)

                    if old_status is None or old_status != status:
                        known_run_statuses[run_id] = status
                        yield {
                            "event": "run_update",
                            "data": json.dumps(
                                {
                                    "run_id": run_id,
                                    "status": status,
                                    "name": row["name"],
                                    "created_at": row["created_at"],
                                    "ended_at": row["ended_at"],
                                }
                            ),
                        }

                    last_heartbeat = row["last_heartbeat"]
                    if status == "running" and last_heartbeat and last_heartbeat > last_check:
                        yield {
                            "event": "metrics_update",
                            "data": json.dumps(
                                {
                                    "run_id": run_id,
                                    "last_heartbeat": last_heartbeat,
                                }
                            ),
                        }

                last_check = current_time
                await asyncio.sleep(POLL_INTERVAL)
        finally:
            conn.close()

    return EventSourceResponse(event_generator())
