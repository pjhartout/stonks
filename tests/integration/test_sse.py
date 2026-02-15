"""Integration tests for SSE streaming endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

import stonks
from stonks.server.app import create_app


@pytest.fixture
def sse_app(db_path):
    """Create a FastAPI app seeded with data for SSE tests."""
    db = str(db_path)
    with stonks.start_run("sse-exp", db=db) as run:
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
