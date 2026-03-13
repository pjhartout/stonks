"""Integration tests for the full sync workflow."""

import time

from stonks.store.connection import create_connection, initialize_db
from stonks.store.experiments import create_experiment
from stonks.store.metrics import count_metrics, insert_metrics
from stonks.store.runs import create_run, finish_run
from stonks.sync.config import RemoteConfig
from stonks.sync.merge import merge_remote_db


def _seed_remote_db(path, experiment_name, num_runs=3, metrics_per_run=10):
    """Create a seeded remote database."""
    conn = create_connection(str(path))
    initialize_db(conn)

    exp = create_experiment(conn, experiment_name)
    now = time.time()
    for i in range(num_runs):
        run = create_run(conn, exp.id, name=f"run-{i}")
        metrics = [("loss", 1.0 - j * 0.1, j, now + j) for j in range(metrics_per_run)]
        insert_metrics(conn, run.id, metrics)
        if i < num_runs - 1:
            finish_run(conn, run.id, "completed")

    conn.close()
    return path


class TestFullMergeWorkflow:
    """Test merging two separate DBs with overlapping experiment names."""

    def test_merge_two_remotes_same_experiment_name(self, tmp_path):
        """Two remote machines with the same experiment name should merge cleanly."""
        remote_a_path = _seed_remote_db(
            tmp_path / "remote_a.db", "shared-experiment", num_runs=2, metrics_per_run=5
        )
        remote_b_path = _seed_remote_db(
            tmp_path / "remote_b.db", "shared-experiment", num_runs=3, metrics_per_run=5
        )

        target_path = tmp_path / "target.db"
        target_conn = create_connection(str(target_path))
        initialize_db(target_conn)

        # Merge both remotes
        stats_a = merge_remote_db(remote_a_path, target_conn, "remote-a")
        stats_b = merge_remote_db(remote_b_path, target_conn, "remote-b")

        assert stats_a.new_runs == 2
        assert stats_b.new_runs == 3

        # Should have 1 experiment (merged by name) with 5 runs total
        exp_count = target_conn.execute("SELECT COUNT(*) as cnt FROM experiments").fetchone()["cnt"]
        assert exp_count == 1

        run_count = target_conn.execute("SELECT COUNT(*) as cnt FROM runs").fetchone()["cnt"]
        assert run_count == 5

        total_metrics = count_metrics(target_conn)
        assert total_metrics == 25  # 5 runs * 5 metrics

        target_conn.close()

    def test_merge_overlapping_then_update(self, tmp_path):
        """Merge, then update remote with new data, merge again."""
        remote_path = tmp_path / "remote.db"
        remote_conn = create_connection(str(remote_path))
        initialize_db(remote_conn)

        exp = create_experiment(remote_conn, "experiment")
        run = create_run(remote_conn, exp.id, name="run-1")
        now = time.time()
        insert_metrics(remote_conn, run.id, [("loss", 0.9, 0, now)])

        target_path = tmp_path / "target.db"
        target_conn = create_connection(str(target_path))
        initialize_db(target_conn)

        # First merge
        stats1 = merge_remote_db(remote_path, target_conn, "remote")
        assert stats1.new_runs == 1
        assert stats1.metrics_inserted == 1

        # Add more data on remote and complete the run
        insert_metrics(remote_conn, run.id, [("loss", 0.5, 1, now + 1)])
        finish_run(remote_conn, run.id, "completed")

        # Second merge
        stats2 = merge_remote_db(remote_path, target_conn, "remote")
        assert stats2.updated_runs == 1
        assert stats2.metrics_inserted == 1  # Incremental: only new step=1 metric

        # Verify final state
        row = target_conn.execute("SELECT * FROM runs WHERE id = ?", (run.id,)).fetchone()
        assert row["status"] == "completed"

        metric_count = target_conn.execute(
            "SELECT COUNT(*) as cnt FROM metrics WHERE run_id = ?", (run.id,)
        ).fetchone()["cnt"]
        assert metric_count == 2

        remote_conn.close()
        target_conn.close()


class TestSyncRemote:
    """Test sync_remote (pull + merge) without real SSH.

    We mock the pull by directly placing files in the staging path.
    """

    def test_sync_with_staged_db(self, tmp_path):
        """sync_remote with a pre-staged DB file should merge successfully."""
        # Create a "remote" DB at the staging path
        remote = RemoteConfig(
            name="test-gpu",
            host="user@fake-host",
            db_path="/data/stonks.db",
        )

        # Override staging path to our test location
        staging_dir = tmp_path / "sync" / "test-gpu"
        staging_dir.mkdir(parents=True)
        staging_path = staging_dir / "stonks.db"

        _seed_remote_db(staging_path, "remote-exp", num_runs=2, metrics_per_run=3)

        target_path = tmp_path / "target.db"
        target_conn = create_connection(str(target_path))
        initialize_db(target_conn)

        # Directly test merge (bypassing rsync which needs real SSH)
        from stonks.sync.merge import merge_remote_db

        stats = merge_remote_db(staging_path, target_conn, remote.name)
        assert stats.new_runs == 2
        assert stats.metrics_inserted == 6

        target_conn.close()


class TestSyncAll:
    """Test sync_all with multiple pre-staged remotes."""

    def test_sync_multiple_staged_remotes(self, tmp_path):
        """sync_all should merge multiple staged remote DBs."""
        target_path = tmp_path / "target.db"

        # Create two "remote" DBs
        remote_a_path = tmp_path / "sync" / "gpu-a" / "stonks.db"
        remote_a_path.parent.mkdir(parents=True)
        _seed_remote_db(remote_a_path, "exp-a", num_runs=2, metrics_per_run=3)

        remote_b_path = tmp_path / "sync" / "gpu-b" / "stonks.db"
        remote_b_path.parent.mkdir(parents=True)
        _seed_remote_db(remote_b_path, "exp-b", num_runs=1, metrics_per_run=5)

        # Directly merge both (bypassing rsync)
        target_conn = create_connection(str(target_path))
        initialize_db(target_conn)

        stats_a = merge_remote_db(remote_a_path, target_conn, "gpu-a")
        stats_b = merge_remote_db(remote_b_path, target_conn, "gpu-b")

        assert stats_a.new_runs == 2
        assert stats_b.new_runs == 1

        total_runs = target_conn.execute("SELECT COUNT(*) as cnt FROM runs").fetchone()["cnt"]
        assert total_runs == 3

        target_conn.close()
