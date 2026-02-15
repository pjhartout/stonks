"""Tests for stonks Run context manager."""

import pytest

import stonks
from stonks.store import create_connection, get_metrics, list_runs


class TestRunLifecycle:
    def test_context_manager_creates_and_finishes(self, db_path):
        with stonks.start_run("test-exp", db=str(db_path)) as run:
            run_id = run.id
            assert run_id is not None

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert len(runs) == 1
        assert runs[0].id == run_id
        assert runs[0].status == "completed"
        conn.close()

    def test_context_manager_marks_failed_on_exception(self, db_path):
        with pytest.raises(ValueError, match="boom"):
            with stonks.start_run("test-exp", db=str(db_path)):
                raise ValueError("boom")

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert runs[0].status == "failed"
        conn.close()

    def test_context_manager_marks_interrupted_on_keyboard(self, db_path):
        with pytest.raises(KeyboardInterrupt):
            with stonks.start_run("test-exp", db=str(db_path)):
                raise KeyboardInterrupt()

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert runs[0].status == "interrupted"
        conn.close()

    def test_log_metrics(self, db_path):
        with stonks.start_run("test-exp", db=str(db_path)) as run:
            run.log({"loss": 1.0, "acc": 0.5}, step=0)
            run.log({"loss": 0.5, "acc": 0.8}, step=1)

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        series = get_metrics(conn, runs[0].id, "loss")
        assert series.values == [1.0, 0.5]
        assert series.steps == [0, 1]
        conn.close()

    def test_auto_increment_step(self, db_path):
        with stonks.start_run("test-exp", db=str(db_path)) as run:
            run.log({"loss": 1.0})
            run.log({"loss": 0.5})
            run.log({"loss": 0.3})

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        series = get_metrics(conn, runs[0].id, "loss")
        assert series.steps == [0, 1, 2]
        conn.close()

    def test_config_stored(self, db_path):
        config = {"lr": 0.001, "batch_size": 32}
        with stonks.start_run("test-exp", db=str(db_path), config=config):
            pass

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert runs[0].config == config
        conn.close()

    def test_log_config_updates(self, db_path):
        with stonks.start_run("test-exp", db=str(db_path), config={"lr": 0.001}) as run:
            run.log_config({"epochs": 10})

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert runs[0].config == {"lr": 0.001, "epochs": 10}
        conn.close()

    def test_experiment_reuse(self, db_path):
        with stonks.start_run("test-exp", db=str(db_path)) as run1:
            exp_id_1 = run1.experiment_id

        with stonks.start_run("test-exp", db=str(db_path)) as run2:
            exp_id_2 = run2.experiment_id

        assert exp_id_1 == exp_id_2

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert len(runs) == 2
        conn.close()

    def test_strict_mode_propagates_errors(self, db_path):
        with stonks.start_run("test-exp", db=str(db_path), strict=True) as run:
            with pytest.raises(Exception):
                run.log({"loss": float("inf")}, step=0)

    def test_lenient_mode_swallows_inf(self, db_path):
        with stonks.start_run("test-exp", db=str(db_path), strict=False) as run:
            run.log({"loss": float("inf")}, step=0)
            # Should not raise
