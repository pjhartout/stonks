"""Integration tests for the full stonks workflow."""

import threading

import stonks


class TestFullWorkflow:
    def test_log_and_query(self, db_path):
        """End-to-end: start_run -> log -> finish -> open -> query."""
        db = str(db_path)

        # Log some training data
        with stonks.start_run("my-experiment", db=db, config={"lr": 0.001}) as run:
            for step in range(10):
                run.log({"train/loss": 1.0 / (step + 1), "train/acc": step * 0.1}, step=step)

        # Query the data back
        with stonks.open(db) as database:
            experiments = database.list_experiments()
            assert len(experiments) == 1
            assert experiments[0].name == "my-experiment"

            runs = database.list_runs(experiment_id=experiments[0].id)
            assert len(runs) == 1
            assert runs[0].status == "completed"
            assert runs[0].config == {"lr": 0.001}

            keys = database.get_metric_keys(runs[0].id)
            assert "train/loss" in keys
            assert "train/acc" in keys

            loss = database.get_metrics(runs[0].id, "train/loss")
            assert len(loss.steps) == 10
            assert loss.values[0] == 1.0
            assert loss.steps == list(range(10))

    def test_multiple_runs_same_experiment(self, db_path):
        """Multiple runs in the same experiment share the experiment record."""
        db = str(db_path)

        for i in range(3):
            with stonks.start_run("shared-exp", db=db, config={"run": i}) as run:
                run.log({"loss": 1.0 / (i + 1)}, step=0)

        with stonks.open(db) as database:
            experiments = database.list_experiments()
            assert len(experiments) == 1

            runs = database.list_runs()
            assert len(runs) == 3
            assert all(r.status == "completed" for r in runs)

    def test_concurrent_writes_from_threads(self, db_path):
        """Two threads logging to the same DB should not corrupt data."""
        db = str(db_path)

        # Pre-initialize DB to avoid PRAGMA race between threads
        with stonks.open(db):
            pass

        errors = []

        def log_run(name, experiment):
            try:
                with stonks.start_run(experiment, db=db, run_name=name) as run:
                    for step in range(50):
                        run.log({"loss": 1.0 / (step + 1)}, step=step)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=log_run, args=("run-1", "exp-a"))
        t2 = threading.Thread(target=log_run, args=("run-2", "exp-b"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0, f"Errors during concurrent writes: {errors}"

        with stonks.open(db) as database:
            runs = database.list_runs()
            assert len(runs) == 2
            for run in runs:
                loss = database.get_metrics(run.id, "loss")
                assert len(loss.steps) == 50

    def test_nan_values_roundtrip(self, db_path):
        """NaN values should be stored as NULL and returned as None."""
        db = str(db_path)

        with stonks.start_run("nan-test", db=db) as run:
            run.log({"loss": float("nan")}, step=0)
            run.log({"loss": 0.5}, step=1)

        with stonks.open(db) as database:
            runs = database.list_runs()
            loss = database.get_metrics(runs[0].id, "loss")
            assert loss.values[0] is None
            assert loss.values[1] == 0.5
