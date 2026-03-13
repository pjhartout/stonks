"""Tests for sync merge logic."""

import os
import time

import pytest

from stonks.store.connection import create_connection, initialize_db
from stonks.store.experiments import create_experiment
from stonks.store.metrics import insert_metrics
from stonks.store.projects import create_project
from stonks.store.runs import create_run, finish_run
from stonks.sync.daemon import _merge_single_db
from stonks.sync.merge import MergeError, check_integrity, merge_remote_db


@pytest.fixture
def source_db(tmp_path):
    """Create and return a source (remote) database connection and path."""
    path = tmp_path / "source.db"
    conn = create_connection(str(path))
    initialize_db(conn)
    yield conn, path
    conn.close()


@pytest.fixture
def target_db(tmp_path):
    """Create and return a target (local) database connection and path."""
    path = tmp_path / "target.db"
    conn = create_connection(str(path))
    initialize_db(conn)
    yield conn, path
    conn.close()


def _add_metrics(conn, run_id, key, values):
    """Helper to add metrics to a database."""
    now = time.time()
    metrics = [(key, v, i, now + i) for i, v in enumerate(values)]
    insert_metrics(conn, run_id, metrics)


class TestCheckIntegrity:
    def test_valid_db(self, source_db):
        _, path = source_db
        assert check_integrity(path) is True

    def test_nonexistent_db(self, tmp_path):
        assert check_integrity(tmp_path / "nope.db") is False

    def test_corrupt_db(self, tmp_path):
        path = tmp_path / "corrupt.db"
        path.write_bytes(b"this is not a sqlite database")
        assert check_integrity(path) is False


class TestMergeNewRuns:
    def test_merge_single_new_run(self, source_db, target_db):
        src_conn, src_path = source_db
        tgt_conn, _ = target_db

        exp = create_experiment(src_conn, "my-experiment")
        run = create_run(src_conn, exp.id, name="run-1")
        _add_metrics(src_conn, run.id, "loss", [0.9, 0.7, 0.5])

        stats = merge_remote_db(src_path, tgt_conn, "test-remote")

        assert stats.new_experiments == 1
        assert stats.new_runs == 1
        assert stats.metrics_inserted == 3
        assert stats.updated_runs == 0
        assert stats.skipped_runs == 0

        # Verify data in target
        row = tgt_conn.execute("SELECT * FROM runs WHERE id = ?", (run.id,)).fetchone()
        assert row is not None
        assert row["name"] == "run-1"

        metrics = tgt_conn.execute(
            "SELECT COUNT(*) as cnt FROM metrics WHERE run_id = ?", (run.id,)
        ).fetchone()
        assert metrics["cnt"] == 3

    def test_merge_with_project(self, source_db, target_db):
        src_conn, src_path = source_db
        tgt_conn, _ = target_db

        project = create_project(src_conn, "my-project")
        exp = create_experiment(src_conn, "my-experiment", project_id=project.id)
        create_run(src_conn, exp.id, name="run-1")

        stats = merge_remote_db(src_path, tgt_conn, "test-remote")

        assert stats.new_projects == 1
        assert stats.new_experiments == 1
        assert stats.new_runs == 1

        # Verify project exists in target
        row = tgt_conn.execute("SELECT * FROM projects WHERE name = ?", ("my-project",)).fetchone()
        assert row is not None

    def test_merge_multiple_runs(self, source_db, target_db):
        src_conn, src_path = source_db
        tgt_conn, _ = target_db

        exp = create_experiment(src_conn, "exp")
        for i in range(5):
            run = create_run(src_conn, exp.id, name=f"run-{i}")
            _add_metrics(src_conn, run.id, "loss", [1.0 - i * 0.1])

        stats = merge_remote_db(src_path, tgt_conn, "test-remote")

        assert stats.new_runs == 5
        assert stats.metrics_inserted == 5


class TestMergeIdRemapping:
    def test_experiment_name_remapping(self, source_db, target_db):
        """When both DBs have the same experiment name but different UUIDs,
        runs from source should be remapped to the target's experiment."""
        src_conn, src_path = source_db
        tgt_conn, _ = target_db

        # Create same-named experiment in both DBs (different UUIDs)
        src_exp = create_experiment(src_conn, "shared-experiment")
        tgt_exp = create_experiment(tgt_conn, "shared-experiment")
        assert src_exp.id != tgt_exp.id

        src_run = create_run(src_conn, src_exp.id, name="remote-run")

        stats = merge_remote_db(src_path, tgt_conn, "test-remote")

        assert stats.new_experiments == 0  # Experiment already exists
        assert stats.new_runs == 1

        # The run should be remapped to the target's experiment ID
        row = tgt_conn.execute("SELECT * FROM runs WHERE id = ?", (src_run.id,)).fetchone()
        assert row["experiment_id"] == tgt_exp.id

    def test_project_name_remapping(self, source_db, target_db):
        """When both DBs have the same project name but different UUIDs,
        experiments should be remapped to the target's project."""
        src_conn, src_path = source_db
        tgt_conn, _ = target_db

        src_proj = create_project(src_conn, "shared-project")
        tgt_proj = create_project(tgt_conn, "shared-project")
        assert src_proj.id != tgt_proj.id

        src_exp = create_experiment(src_conn, "exp", project_id=src_proj.id)
        create_run(src_conn, src_exp.id, name="run-1")

        stats = merge_remote_db(src_path, tgt_conn, "test-remote")

        assert stats.new_projects == 0
        assert stats.new_experiments == 1

        # The new experiment should reference the target's project ID
        row = tgt_conn.execute("SELECT * FROM experiments WHERE name = ?", ("exp",)).fetchone()
        assert row["project_id"] == tgt_proj.id


class TestMergeUpdatedRuns:
    def test_run_status_update(self, source_db, target_db):
        """A run that transitions from running to completed should be updated."""
        src_conn, src_path = source_db
        tgt_conn, _ = target_db

        exp = create_experiment(src_conn, "exp")
        run = create_run(src_conn, exp.id, name="run-1")
        _add_metrics(src_conn, run.id, "loss", [0.9, 0.7])

        # First merge: run is "running"
        stats1 = merge_remote_db(src_path, tgt_conn, "test-remote")
        assert stats1.new_runs == 1

        # Complete the run on the source and add more metrics (steps 2, 3)
        finish_run(src_conn, run.id, "completed")
        now = time.time()
        insert_metrics(src_conn, run.id, [("loss", 0.5, 2, now), ("loss", 0.3, 3, now + 1)])

        # Second merge: run is now "completed" with more metrics
        stats2 = merge_remote_db(src_path, tgt_conn, "test-remote")
        assert stats2.updated_runs == 1
        assert stats2.new_runs == 0

        # Verify status updated
        row = tgt_conn.execute("SELECT * FROM runs WHERE id = ?", (run.id,)).fetchone()
        assert row["status"] == "completed"
        assert row["ended_at"] is not None

        # Verify incremental merge added only new metrics (2 original + 2 new = 4)
        count = tgt_conn.execute(
            "SELECT COUNT(*) as cnt FROM metrics WHERE run_id = ?", (run.id,)
        ).fetchone()["cnt"]
        assert count == 4

    def test_unchanged_run_skipped(self, source_db, target_db):
        """A run that hasn't changed since last sync should be skipped."""
        src_conn, src_path = source_db
        tgt_conn, _ = target_db

        exp = create_experiment(src_conn, "exp")
        run = create_run(src_conn, exp.id, name="run-1")
        finish_run(src_conn, run.id, "completed")
        _add_metrics(src_conn, run.id, "loss", [0.9])

        # First merge
        merge_remote_db(src_path, tgt_conn, "test-remote")

        # Second merge: nothing changed
        stats2 = merge_remote_db(src_path, tgt_conn, "test-remote")
        assert stats2.skipped_runs == 1
        assert stats2.new_runs == 0
        assert stats2.updated_runs == 0
        assert stats2.metrics_inserted == 0


class TestMergeIdempotency:
    def test_double_merge_is_idempotent(self, source_db, target_db):
        """Merging the same source twice should produce the same result."""
        src_conn, src_path = source_db
        tgt_conn, _ = target_db

        exp = create_experiment(src_conn, "exp")
        run = create_run(src_conn, exp.id, name="run-1")
        finish_run(src_conn, run.id, "completed")
        _add_metrics(src_conn, run.id, "loss", [0.9, 0.7, 0.5])

        merge_remote_db(src_path, tgt_conn, "test-remote")
        merge_remote_db(src_path, tgt_conn, "test-remote")

        # Should have exactly 3 metrics, not 6
        count = tgt_conn.execute(
            "SELECT COUNT(*) as cnt FROM metrics WHERE run_id = ?", (run.id,)
        ).fetchone()["cnt"]
        assert count == 3

        # Should have exactly 1 run
        run_count = tgt_conn.execute("SELECT COUNT(*) as cnt FROM runs").fetchone()["cnt"]
        assert run_count == 1

    def test_triple_merge_no_growth(self, source_db, target_db):
        """Three merges should not cause metric duplication."""
        src_conn, src_path = source_db
        tgt_conn, _ = target_db

        exp = create_experiment(src_conn, "exp")
        run = create_run(src_conn, exp.id, name="run-1")
        finish_run(src_conn, run.id, "completed")
        _add_metrics(src_conn, run.id, "loss", [0.9, 0.7, 0.5, 0.3, 0.1])

        for _ in range(3):
            merge_remote_db(src_path, tgt_conn, "test-remote")

        count = tgt_conn.execute(
            "SELECT COUNT(*) as cnt FROM metrics WHERE run_id = ?", (run.id,)
        ).fetchone()["cnt"]
        assert count == 5


class TestMergeEdgeCases:
    def test_empty_source_db(self, source_db, target_db):
        """Merging an empty source should do nothing."""
        _, src_path = source_db
        tgt_conn, _ = target_db

        stats = merge_remote_db(src_path, tgt_conn, "test-remote")
        assert stats.new_runs == 0
        assert stats.new_experiments == 0

    def test_nonexistent_source(self, target_db, tmp_path):
        """Merging a nonexistent source should raise MergeError."""
        tgt_conn, _ = target_db

        with pytest.raises(MergeError, match="not found"):
            merge_remote_db(tmp_path / "nope.db", tgt_conn, "test-remote")

    def test_merge_preserves_existing_local_data(self, source_db, target_db):
        """Merging should not affect runs that only exist locally."""
        src_conn, src_path = source_db
        tgt_conn, _ = target_db

        # Create a local-only run
        local_exp = create_experiment(tgt_conn, "local-exp")
        local_run = create_run(tgt_conn, local_exp.id, name="local-run")
        _add_metrics(tgt_conn, local_run.id, "loss", [0.5, 0.3])

        # Create a remote run
        remote_exp = create_experiment(src_conn, "remote-exp")
        create_run(src_conn, remote_exp.id, name="remote-run")

        merge_remote_db(src_path, tgt_conn, "test-remote")

        # Local run should be untouched
        row = tgt_conn.execute("SELECT * FROM runs WHERE id = ?", (local_run.id,)).fetchone()
        assert row is not None
        assert row["name"] == "local-run"

        local_metrics = tgt_conn.execute(
            "SELECT COUNT(*) as cnt FROM metrics WHERE run_id = ?", (local_run.id,)
        ).fetchone()["cnt"]
        assert local_metrics == 2

    def test_run_with_no_metrics(self, source_db, target_db):
        """A run with no metrics should merge fine."""
        src_conn, src_path = source_db
        tgt_conn, _ = target_db

        exp = create_experiment(src_conn, "exp")
        create_run(src_conn, exp.id, name="empty-run")

        stats = merge_remote_db(src_path, tgt_conn, "test-remote")
        assert stats.new_runs == 1
        assert stats.metrics_inserted == 0

    def test_run_with_tags_and_config(self, source_db, target_db):
        """Run metadata (tags, config, notes) should be preserved during merge."""
        src_conn, src_path = source_db
        tgt_conn, _ = target_db

        exp = create_experiment(src_conn, "exp")
        run = create_run(
            src_conn,
            exp.id,
            name="detailed-run",
            config={"lr": 0.001, "epochs": 100},
            tags=["baseline", "v2"],
            notes="First attempt with new architecture",
            group="sweep-1",
            job_type="train",
        )

        merge_remote_db(src_path, tgt_conn, "test-remote")

        row = tgt_conn.execute("SELECT * FROM runs WHERE id = ?", (run.id,)).fetchone()
        assert row["name"] == "detailed-run"
        assert row["group_name"] == "sweep-1"
        assert row["job_type"] == "train"
        assert row["notes"] == "First attempt with new architecture"
        assert "baseline" in row["tags"]
        assert "lr" in row["config"]


class TestFingerprintSkip:
    """Tests for file fingerprint-based skip logic in _merge_single_db."""

    def test_second_merge_skipped_when_unchanged(self, source_db, target_db):
        """Second merge of unchanged file should skip via fingerprint cache."""
        src_conn, src_path = source_db
        tgt_conn, _ = target_db

        exp = create_experiment(src_conn, "exp")
        run = create_run(src_conn, exp.id, name="run-1")
        _add_metrics(src_conn, run.id, "loss", [0.9, 0.7])

        fingerprints = {}

        # First merge: should actually merge
        stats1 = _merge_single_db(src_path, tgt_conn, "test-remote", "label", fingerprints)
        assert stats1 is not None
        assert stats1.new_runs == 1
        assert str(src_path) in fingerprints

        # Second merge: file unchanged, should skip
        stats2 = _merge_single_db(src_path, tgt_conn, "test-remote", "label", fingerprints)
        assert stats2 is not None
        assert stats2.new_runs == 0
        assert stats2.updated_runs == 0
        assert stats2.skipped_runs == 0
        assert stats2.metrics_inserted == 0

    def test_merge_runs_after_file_modified(self, source_db, target_db):
        """Merge should run again if the file is modified after caching."""
        src_conn, src_path = source_db
        tgt_conn, _ = target_db

        exp = create_experiment(src_conn, "exp")
        run = create_run(src_conn, exp.id, name="run-1")
        _add_metrics(src_conn, run.id, "loss", [0.9])

        fingerprints = {}
        _merge_single_db(src_path, tgt_conn, "test-remote", "label", fingerprints)

        # Modify the source DB and force mtime change
        now = time.time()
        insert_metrics(src_conn, run.id, [("loss", 0.7, 1, now)])
        finish_run(src_conn, run.id, "completed")
        os.utime(src_path, (now + 1, now + 1))

        # Should re-merge because fingerprint changed
        stats2 = _merge_single_db(src_path, tgt_conn, "test-remote", "label", fingerprints)
        assert stats2 is not None
        assert stats2.updated_runs == 1

    def test_no_fingerprint_cache_always_merges(self, source_db, target_db):
        """Without fingerprint cache (None), every call should merge."""
        src_conn, src_path = source_db
        tgt_conn, _ = target_db

        exp = create_experiment(src_conn, "exp")
        create_run(src_conn, exp.id, name="run-1")

        stats1 = _merge_single_db(src_path, tgt_conn, "test-remote", "label", None)
        assert stats1 is not None
        assert stats1.new_runs == 1

        stats2 = _merge_single_db(src_path, tgt_conn, "test-remote", "label", None)
        assert stats2 is not None
        assert stats2.skipped_runs == 1  # Run unchanged, but merge still ran

    def test_fingerprint_not_cached_on_failure(self, target_db, tmp_path):
        """Fingerprint should NOT be cached if integrity check fails."""
        tgt_conn, _ = target_db

        bad_path = tmp_path / "corrupt.db"
        bad_path.write_text("not a database")

        fingerprints = {}
        result = _merge_single_db(bad_path, tgt_conn, "test-remote", "label", fingerprints)
        assert result is None
        assert str(bad_path) not in fingerprints
