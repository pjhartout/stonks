"""Tests for stonks SQLite store layer."""

import time

from stonks.store import (
    create_experiment,
    create_run,
    finish_run,
    get_metric_keys,
    get_metrics,
    insert_metrics,
    list_experiments,
    list_runs,
    update_heartbeat,
    update_run_config,
)


class TestExperiments:
    def test_create_experiment(self, db_conn):
        exp = create_experiment(db_conn, "my-exp", description="test desc")
        assert exp.name == "my-exp"
        assert exp.description == "test desc"
        assert exp.id is not None

    def test_create_duplicate_returns_existing(self, db_conn):
        exp1 = create_experiment(db_conn, "my-exp")
        exp2 = create_experiment(db_conn, "my-exp")
        assert exp1.id == exp2.id

    def test_list_experiments(self, db_conn):
        create_experiment(db_conn, "exp-1")
        create_experiment(db_conn, "exp-2")
        exps = list_experiments(db_conn)
        assert len(exps) == 2
        names = {e.name for e in exps}
        assert names == {"exp-1", "exp-2"}


class TestRuns:
    def test_create_run(self, db_conn, sample_experiment):
        run = create_run(
            db_conn,
            experiment_id=sample_experiment.id,
            name="run-1",
            config={"lr": 0.01},
        )
        assert run.status == "running"
        assert run.name == "run-1"
        assert run.config == {"lr": 0.01}

    def test_list_runs_all(self, db_conn, sample_experiment):
        create_run(db_conn, experiment_id=sample_experiment.id)
        create_run(db_conn, experiment_id=sample_experiment.id)
        runs = list_runs(db_conn)
        assert len(runs) == 2

    def test_list_runs_filtered(self, db_conn):
        exp1 = create_experiment(db_conn, "exp-1")
        exp2 = create_experiment(db_conn, "exp-2")
        create_run(db_conn, experiment_id=exp1.id)
        create_run(db_conn, experiment_id=exp2.id)
        create_run(db_conn, experiment_id=exp2.id)

        runs_1 = list_runs(db_conn, experiment_id=exp1.id)
        runs_2 = list_runs(db_conn, experiment_id=exp2.id)
        assert len(runs_1) == 1
        assert len(runs_2) == 2

    def test_finish_run(self, db_conn, sample_run):
        finish_run(db_conn, sample_run.id, "completed")
        runs = list_runs(db_conn)
        assert runs[0].status == "completed"
        assert runs[0].ended_at is not None

    def test_update_run_config(self, db_conn, sample_run):
        update_run_config(db_conn, sample_run.id, {"lr": 0.1, "new_key": "value"})
        runs = list_runs(db_conn)
        assert runs[0].config["lr"] == 0.1
        assert runs[0].config["new_key"] == "value"

    def test_update_heartbeat(self, db_conn, sample_run):
        before = sample_run.last_heartbeat
        time.sleep(0.01)
        update_heartbeat(db_conn, sample_run.id)
        runs = list_runs(db_conn)
        assert runs[0].last_heartbeat > before


class TestMetrics:
    def test_insert_and_get_metrics(self, db_conn, sample_run):
        now = time.time()
        insert_metrics(
            db_conn,
            sample_run.id,
            [
                ("loss", 1.0, 0, now),
                ("loss", 0.5, 1, now + 1),
                ("loss", 0.3, 2, now + 2),
            ],
        )
        series = get_metrics(db_conn, sample_run.id, "loss")
        assert series.key == "loss"
        assert len(series.steps) == 3
        assert series.values == [1.0, 0.5, 0.3]
        assert series.steps == [0, 1, 2]

    def test_get_metric_keys(self, db_conn, sample_run):
        now = time.time()
        insert_metrics(
            db_conn,
            sample_run.id,
            [
                ("train/loss", 1.0, 0, now),
                ("train/acc", 0.5, 0, now),
                ("val/loss", 0.8, 0, now),
            ],
        )
        keys = get_metric_keys(db_conn, sample_run.id)
        assert keys == ["train/acc", "train/loss", "val/loss"]

    def test_nan_stored_as_none(self, db_conn, sample_run):
        now = time.time()
        insert_metrics(db_conn, sample_run.id, [("loss", None, 0, now)])
        series = get_metrics(db_conn, sample_run.id, "loss")
        assert series.values == [None]

    def test_empty_metrics(self, db_conn, sample_run):
        series = get_metrics(db_conn, sample_run.id, "nonexistent")
        assert len(series.steps) == 0
