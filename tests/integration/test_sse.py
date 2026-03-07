"""Integration tests for SSE streaming endpoint."""

import asyncio
import json
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
        events = []
        gen = response.body_iterator

        async def collect_events():
            async for event in gen:
                if isinstance(event, dict) and event.get("event") == "run_update":
                    events.append(event)
                    return
                # sse_starlette may also yield raw text chunks
                if isinstance(event, (str, bytes)):
                    text = event if isinstance(event, str) else event.decode()
                    if "run_update" in text:
                        events.append({"raw": text})
                        return

        try:
            async with asyncio.timeout(2.0):
                await collect_events()
        except TimeoutError:
            pass

        # After first poll, the existing running run should produce a run_update
        assert len(events) >= 1

        if "raw" not in events[0]:
            data = json.loads(events[0]["data"])
            assert data["run_id"] == run_id
            assert data["status"] == "running"

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

        events = []
        saw_run_update = False

        async def collect_events():
            nonlocal saw_run_update
            async for event in gen:
                if isinstance(event, dict):
                    if event.get("event") == "run_update" and not saw_run_update:
                        saw_run_update = True
                        # Now update heartbeat so next poll picks it up
                        hb_conn = create_connection(db)
                        update_heartbeat(hb_conn, run_id)
                        hb_conn.close()
                    elif event.get("event") == "metrics_update":
                        events.append(event)
                        return

        try:
            async with asyncio.timeout(3.0):
                await collect_events()
        except TimeoutError:
            pass

        assert len(events) >= 1
        data = json.loads(events[0]["data"])
        assert data["run_id"] == run_id
        assert "last_heartbeat" in data

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
                if isinstance(event, dict) and event.get("event") == "run_update":
                    run_updates.append(event)
                    if not first_seen:
                        first_seen = True
                        # Change the run status
                        change_conn = create_connection(db)
                        finish_run(change_conn, run_id, "completed")
                        change_conn.close()
                    elif len(run_updates) >= 2:
                        return

        try:
            async with asyncio.timeout(3.0):
                await collect_events()
        except TimeoutError:
            pass

        assert len(run_updates) >= 2
        first_data = json.loads(run_updates[0]["data"])
        second_data = json.loads(run_updates[1]["data"])
        assert first_data["status"] == "running"
        assert second_data["status"] == "completed"
