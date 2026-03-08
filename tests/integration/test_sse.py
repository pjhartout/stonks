"""Integration tests for SSE streaming endpoint."""

import asyncio
import json
import re
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

import stonks
from stonks.server.app import create_app
from stonks.store import (
    create_connection,
    create_experiment,
    create_run,
    finish_run,
    initialize_db,
    update_heartbeat,
)


def _parse_sse_event(event):
    """Parse an SSE event into a (event_type, data_dict) tuple.

    Handles both dict events (yielded by the generator) and raw text/bytes
    chunks (as formatted by sse_starlette). Returns None if the event cannot
    be parsed, ensuring tests always validate structured data rather than
    silently skipping assertions.

    Args:
        event: A dict, str, or bytes SSE event.

    Returns:
        A tuple of (event_type, data_dict) or None if unparseable.
    """
    if isinstance(event, dict) and "event" in event and "data" in event:
        return (event["event"], json.loads(event["data"]))

    if isinstance(event, (str, bytes)):
        text = event if isinstance(event, str) else event.decode()
        event_match = re.search(r"event:\s*(\S+)", text)
        data_match = re.search(r"data:\s*(.+)", text)
        if event_match and data_match:
            return (event_match.group(1), json.loads(data_match.group(1)))

    return None


@pytest.fixture
def sse_app(db_path):
    """Create a FastAPI app seeded with data for SSE tests."""
    db = str(db_path)
    with stonks.start_run("sse-exp", save_dir=db) as run:
        run.log({"loss": 1.0}, step=0)

    return create_app(db)


@pytest.fixture
async def sse_client(sse_app):
    """Provide an async test client for SSE tests."""
    transport = ASGITransport(app=sse_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestSSEEndpoint:
    async def test_events_requires_experiment_id(self, sse_client):
        """GET /api/events without experiment_id returns 422."""
        resp = await sse_client.get("/api/events")
        assert resp.status_code == 422

    @patch("stonks.server.routes.stream.POLL_INTERVAL", 0.05)
    async def test_run_update_event_on_status_change(self, db_path):
        """SSE generator emits run_update when a run's status changes."""
        db = str(db_path)

        conn = create_connection(db)
        initialize_db(conn)
        exp = create_experiment(conn, "sse-exp")
        run_info = create_run(conn, experiment_id=exp.id, name="run-1")
        run_id = run_info.id
        exp_id = exp.id
        conn.close()

        # Import the SSE internals so we can drive the generator
        from stonks.server.dependencies import init_db_manager

        init_db_manager(db)

        from stonks.server.routes.stream import stream_events

        # Call the endpoint handler to get the EventSourceResponse
        response = await stream_events(experiment_id=exp_id)

        # The response wraps an async generator. Extract events from it.
        parsed_events = []
        gen = response.body_iterator

        async def collect_events():
            async for event in gen:
                parsed = _parse_sse_event(event)
                if parsed is not None and parsed[0] == "run_update":
                    parsed_events.append(parsed)
                    return

        timed_out = False
        try:
            async with asyncio.timeout(2.0):
                await collect_events()
        except TimeoutError:
            timed_out = True

        # Fail loudly if no run_update events were collected
        assert len(parsed_events) >= 1, (
            f"Expected at least 1 run_update event, got {len(parsed_events)}. "
            f"Timed out: {timed_out}"
        )

        event_type, data = parsed_events[0]
        assert event_type == "run_update"
        assert data["run_id"] == run_id, f"Expected run_id={run_id!r}, got {data.get('run_id')!r}"
        assert data["status"] == "running", f"Expected status='running', got {data.get('status')!r}"

    @patch("stonks.server.routes.stream.POLL_INTERVAL", 0.05)
    async def test_metrics_update_event_on_heartbeat(self, db_path):
        """SSE generator emits metrics_update when heartbeat updates on a running run."""
        db = str(db_path)

        conn = create_connection(db)
        initialize_db(conn)
        exp = create_experiment(conn, "sse-exp")
        run_info = create_run(conn, experiment_id=exp.id, name="run-1")
        run_id = run_info.id
        exp_id = exp.id
        conn.close()

        from stonks.server.dependencies import init_db_manager

        init_db_manager(db)

        from stonks.server.routes.stream import stream_events

        response = await stream_events(experiment_id=exp_id)
        gen = response.body_iterator

        metrics_events = []
        saw_run_update = False

        async def collect_events():
            nonlocal saw_run_update
            async for event in gen:
                parsed = _parse_sse_event(event)
                if parsed is None:
                    continue
                event_type, data = parsed
                if event_type == "run_update" and not saw_run_update:
                    saw_run_update = True
                    # Now update heartbeat so next poll picks it up
                    hb_conn = create_connection(db)
                    update_heartbeat(hb_conn, run_id)
                    hb_conn.close()
                elif event_type == "metrics_update":
                    metrics_events.append((event_type, data))
                    return

        timed_out = False
        try:
            async with asyncio.timeout(3.0):
                await collect_events()
        except TimeoutError:
            timed_out = True

        assert saw_run_update, (
            "Never received initial run_update event before waiting for metrics_update. "
            f"Timed out: {timed_out}"
        )
        assert len(metrics_events) >= 1, (
            f"Expected at least 1 metrics_update event, got {len(metrics_events)}. "
            f"Timed out: {timed_out}"
        )

        event_type, data = metrics_events[0]
        assert event_type == "metrics_update"
        assert data["run_id"] == run_id, f"Expected run_id={run_id!r}, got {data.get('run_id')!r}"
        assert "last_heartbeat" in data, (
            f"Expected 'last_heartbeat' key in metrics_update data, got keys: {list(data.keys())}"
        )

    @patch("stonks.server.routes.stream.POLL_INTERVAL", 0.05)
    async def test_run_status_change_emits_update(self, db_path):
        """SSE generator emits a second run_update when status changes from running to completed."""
        db = str(db_path)

        conn = create_connection(db)
        initialize_db(conn)
        exp = create_experiment(conn, "sse-exp")
        run_info = create_run(conn, experiment_id=exp.id, name="run-1")
        run_id = run_info.id
        exp_id = exp.id
        conn.close()

        from stonks.server.dependencies import init_db_manager

        init_db_manager(db)

        from stonks.server.routes.stream import stream_events

        response = await stream_events(experiment_id=exp_id)
        gen = response.body_iterator

        run_updates = []
        first_seen = False

        async def collect_events():
            nonlocal first_seen
            async for event in gen:
                parsed = _parse_sse_event(event)
                if parsed is None:
                    continue
                event_type, data = parsed
                if event_type == "run_update":
                    run_updates.append((event_type, data))
                    if not first_seen:
                        first_seen = True
                        # Change the run status
                        change_conn = create_connection(db)
                        finish_run(change_conn, run_id, "completed")
                        change_conn.close()
                    elif len(run_updates) >= 2:
                        return

        timed_out = False
        try:
            async with asyncio.timeout(3.0):
                await collect_events()
        except TimeoutError:
            timed_out = True

        assert len(run_updates) >= 2, (
            f"Expected at least 2 run_update events, got {len(run_updates)}. Timed out: {timed_out}"
        )

        _, first_data = run_updates[0]
        _, second_data = run_updates[1]
        assert first_data["run_id"] == run_id, (
            f"First run_update: expected run_id={run_id!r}, got {first_data.get('run_id')!r}"
        )
        assert first_data["status"] == "running", (
            f"First run_update: expected status='running', got {first_data.get('status')!r}"
        )
        assert second_data["run_id"] == run_id, (
            f"Second run_update: expected run_id={run_id!r}, got {second_data.get('run_id')!r}"
        )
        assert second_data["status"] == "completed", (
            f"Second run_update: expected status='completed', got {second_data.get('status')!r}"
        )
