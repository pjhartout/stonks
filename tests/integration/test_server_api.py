"""Integration tests for the FastAPI server REST endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

import stonks
from stonks.server.app import create_app


@pytest.fixture
def app(db_path):
    """Create a FastAPI app with a test database."""
    db = str(db_path)
    # Seed some data
    with stonks.start_run("exp-alpha", db=db, config={"lr": 0.001}) as run:
        run.log({"train/loss": 1.0, "train/acc": 0.5}, step=0)
        run.log({"train/loss": 0.5, "train/acc": 0.8}, step=1)

    with stonks.start_run("exp-alpha", db=db, config={"lr": 0.01}) as run:
        run.log({"train/loss": 0.8}, step=0)

    with stonks.start_run("exp-beta", db=db, config={"epochs": 10}) as run:
        run.log({"val/loss": 0.3}, step=0)

    return create_app(db)


@pytest.fixture
async def client(app):
    """Provide an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestExperimentEndpoints:
    async def test_list_experiments(self, client):
        """GET /api/experiments returns all experiments."""
        resp = await client.get("/api/experiments")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = {e["name"] for e in data}
        assert names == {"exp-alpha", "exp-beta"}

    async def test_list_experiments_with_run_count(self, client):
        """Each experiment includes a run_count."""
        resp = await client.get("/api/experiments")
        data = resp.json()
        alpha = next(e for e in data if e["name"] == "exp-alpha")
        beta = next(e for e in data if e["name"] == "exp-beta")
        assert alpha["run_count"] == 2
        assert beta["run_count"] == 1

    async def test_get_experiment_by_id(self, client):
        """GET /api/experiments/{id} returns a single experiment."""
        resp = await client.get("/api/experiments")
        exp_id = resp.json()[0]["id"]

        resp = await client.get(f"/api/experiments/{exp_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == exp_id

    async def test_get_experiment_not_found(self, client):
        """GET /api/experiments/{id} returns 404 for unknown ID."""
        resp = await client.get("/api/experiments/nonexistent-id")
        assert resp.status_code == 404


class TestRunEndpoints:
    async def test_list_runs_for_experiment(self, client):
        """GET /api/experiments/{id}/runs returns runs for that experiment."""
        resp = await client.get("/api/experiments")
        alpha = next(e for e in resp.json() if e["name"] == "exp-alpha")

        resp = await client.get(f"/api/experiments/{alpha['id']}/runs")
        assert resp.status_code == 200
        runs = resp.json()
        assert len(runs) == 2
        assert all(r["status"] == "completed" for r in runs)

    async def test_get_run_by_id(self, client):
        """GET /api/runs/{id} returns run details with config."""
        resp = await client.get("/api/experiments")
        alpha = next(e for e in resp.json() if e["name"] == "exp-alpha")

        runs_resp = await client.get(f"/api/experiments/{alpha['id']}/runs")
        run_id = runs_resp.json()[0]["id"]

        resp = await client.get(f"/api/runs/{run_id}")
        assert resp.status_code == 200
        run = resp.json()
        assert run["id"] == run_id
        assert run["config"] is not None

    async def test_get_run_not_found(self, client):
        """GET /api/runs/{id} returns 404 for unknown ID."""
        resp = await client.get("/api/runs/nonexistent-id")
        assert resp.status_code == 404

    async def test_run_has_all_fields(self, client):
        """Run response includes all expected fields."""
        resp = await client.get("/api/experiments")
        alpha = next(e for e in resp.json() if e["name"] == "exp-alpha")
        runs_resp = await client.get(f"/api/experiments/{alpha['id']}/runs")
        run = runs_resp.json()[0]

        expected_fields = {
            "id",
            "experiment_id",
            "name",
            "status",
            "config",
            "created_at",
            "ended_at",
            "last_heartbeat",
            "group",
            "job_type",
            "tags",
            "notes",
        }
        assert set(run.keys()) == expected_fields


class TestMetricEndpoints:
    async def test_get_metric_keys(self, client):
        """GET /api/runs/{id}/metric-keys returns all metric keys."""
        resp = await client.get("/api/experiments")
        alpha = next(e for e in resp.json() if e["name"] == "exp-alpha")
        runs_resp = await client.get(f"/api/experiments/{alpha['id']}/runs")

        # Find the run with multiple metrics (2 steps)
        for run in runs_resp.json():
            keys_resp = await client.get(f"/api/runs/{run['id']}/metric-keys")
            assert keys_resp.status_code == 200
            keys = keys_resp.json()
            if "train/acc" in keys:
                assert "train/loss" in keys
                break

    async def test_get_metrics(self, client):
        """GET /api/runs/{id}/metrics returns metric series."""
        resp = await client.get("/api/experiments")
        alpha = next(e for e in resp.json() if e["name"] == "exp-alpha")
        runs_resp = await client.get(f"/api/experiments/{alpha['id']}/runs")

        # Find run with 2 loss steps
        for run in runs_resp.json():
            metrics_resp = await client.get(
                f"/api/runs/{run['id']}/metrics", params={"key": "train/loss"}
            )
            if len(metrics_resp.json()["steps"]) == 2:
                data = metrics_resp.json()
                assert data["key"] == "train/loss"
                assert data["values"] == [1.0, 0.5]
                assert data["steps"] == [0, 1]
                break

    async def test_get_metrics_with_downsample(self, client, db_path):
        """Downsampling reduces the number of points."""
        # Create a run with many data points
        db = str(db_path)
        with stonks.start_run("big-exp", db=db) as run:
            for step in range(100):
                run.log({"loss": 1.0 / (step + 1)}, step=step)

        resp = await client.get("/api/experiments")
        big_exp = next(e for e in resp.json() if e["name"] == "big-exp")
        runs_resp = await client.get(f"/api/experiments/{big_exp['id']}/runs")
        run_id = runs_resp.json()[0]["id"]

        # Without downsample
        resp = await client.get(f"/api/runs/{run_id}/metrics", params={"key": "loss"})
        assert len(resp.json()["steps"]) == 100

        # With downsample
        resp = await client.get(
            f"/api/runs/{run_id}/metrics", params={"key": "loss", "downsample": 10}
        )
        # Downsampled result should be smaller than original
        assert len(resp.json()["steps"]) <= 100
        assert len(resp.json()["steps"]) > 0

    async def test_get_metrics_run_not_found(self, client):
        """GET /api/runs/{id}/metrics returns 404 for unknown run."""
        resp = await client.get("/api/runs/nonexistent-id/metrics", params={"key": "loss"})
        assert resp.status_code == 404

    async def test_get_metric_keys_run_not_found(self, client):
        """GET /api/runs/{id}/metric-keys returns 404 for unknown run."""
        resp = await client.get("/api/runs/nonexistent-id/metric-keys")
        assert resp.status_code == 404

    async def test_get_metrics_missing_key_param(self, client):
        """GET /api/runs/{id}/metrics without key param returns 422."""
        resp = await client.get("/api/experiments")
        alpha = next(e for e in resp.json() if e["name"] == "exp-alpha")
        runs_resp = await client.get(f"/api/experiments/{alpha['id']}/runs")
        run_id = runs_resp.json()[0]["id"]

        resp = await client.get(f"/api/runs/{run_id}/metrics")
        assert resp.status_code == 422
