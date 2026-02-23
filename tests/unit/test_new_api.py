"""Tests for the new stable API surface: resume, tags, notes, groups, prefix, deprecation."""

import warnings

import pytest

import stonks
from stonks.exceptions import StonksError
from stonks.lightning import StonksLogger
from stonks.store import (
    create_connection,
    get_metric_keys,
    get_metrics,
    get_run_by_id,
    list_runs,
)


class TestNewStartRunParams:
    def test_project_creates_project(self, db_path):
        """project= creates a project record and links the experiment."""
        with stonks.start_run("test-exp", project="my-project", save_dir=str(db_path)) as run:
            assert run.project == "my-project"

    def test_tags_stored(self, db_path):
        """tags= are stored on the run."""
        with stonks.start_run("test-exp", tags=["baseline", "v2"], save_dir=str(db_path)) as run:
            assert run.tags == ["baseline", "v2"]
            run_id = run.id

        conn = create_connection(str(db_path))
        r = get_run_by_id(conn, run_id)
        assert r.tags == ["baseline", "v2"]
        conn.close()

    def test_notes_stored(self, db_path):
        """notes= are stored on the run."""
        with stonks.start_run("test-exp", notes="Testing new LR", save_dir=str(db_path)) as run:
            run_id = run.id

        conn = create_connection(str(db_path))
        r = get_run_by_id(conn, run_id)
        assert r.notes == "Testing new LR"
        conn.close()

    def test_group_stored(self, db_path):
        """group= is stored on the run."""
        with stonks.start_run("test-exp", group="fold-3", save_dir=str(db_path)) as run:
            assert run.group == "fold-3"

    def test_job_type_stored(self, db_path):
        """job_type= is stored on the run."""
        with stonks.start_run("test-exp", job_type="train", save_dir=str(db_path)) as run:
            assert run.job_type == "train"

    def test_prefix_applied_to_metrics(self, db_path):
        """prefix= prepends to metric keys."""
        with stonks.start_run("test-exp", prefix="train", save_dir=str(db_path)) as run:
            run.log({"loss": 1.0, "acc": 0.5}, step=0)
            run_id = run.id

        conn = create_connection(str(db_path))
        keys = get_metric_keys(conn, run_id)
        assert "train/loss" in keys
        assert "train/acc" in keys
        assert "loss" not in keys
        conn.close()

    def test_name_param(self, db_path):
        """name= sets the run display name."""
        with stonks.start_run("test-exp", name="my-run", save_dir=str(db_path)) as run:
            assert run.name == "my-run"

    def test_default_experiment_name(self, db_path):
        """experiment defaults to 'default' when omitted."""
        with stonks.start_run(save_dir=str(db_path)):
            pass

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert len(runs) == 1
        conn.close()

    def test_config_param(self, db_path):
        """config= is stored."""
        with stonks.start_run("test-exp", config={"lr": 0.001}, save_dir=str(db_path)) as run:
            assert run.config == {"lr": 0.001}

    def test_all_params_together(self, db_path):
        """All new params work together."""
        with stonks.start_run(
            "test-exp",
            project="nlp",
            name="run-1",
            group="sweep-1",
            job_type="train",
            tags=["baseline"],
            notes="First run",
            config={"lr": 0.001},
            prefix="train",
            save_dir=str(db_path),
        ) as run:
            run.log({"loss": 1.0}, step=0)
            assert run.project == "nlp"
            assert run.name == "run-1"
            assert run.group == "sweep-1"
            assert run.job_type == "train"
            assert run.tags == ["baseline"]
            assert run.notes == "First run"


class TestSetTagsAndNotes:
    def test_set_tags_after_creation(self, db_path):
        """set_tags() updates tags on an active run."""
        with stonks.start_run("test-exp", save_dir=str(db_path)) as run:
            run.set_tags(["new-tag"])
            assert run.tags == ["new-tag"]
            run_id = run.id

        conn = create_connection(str(db_path))
        r = get_run_by_id(conn, run_id)
        assert r.tags == ["new-tag"]
        conn.close()

    def test_set_notes_after_creation(self, db_path):
        """set_notes() updates notes on an active run."""
        with stonks.start_run("test-exp", save_dir=str(db_path)) as run:
            run.set_notes("Updated notes")
            assert run.notes == "Updated notes"
            run_id = run.id

        conn = create_connection(str(db_path))
        r = get_run_by_id(conn, run_id)
        assert r.notes == "Updated notes"
        conn.close()


class TestResume:
    def test_resume_by_id(self, db_path):
        """resume=True with id= resumes an existing run."""
        db = str(db_path)
        with stonks.start_run("test-exp", save_dir=db) as run:
            run.log({"loss": 1.0}, step=0)
            run.log({"loss": 0.5}, step=1)
            original_id = run.id

        # Resume the run.
        with stonks.start_run("test-exp", id=original_id, resume=True, save_dir=db) as run:
            assert run.id == original_id
            run.log({"loss": 0.3}, step=2)

        conn = create_connection(db)
        series = get_metrics(conn, original_id, "loss")
        assert series.steps == [0, 1, 2]
        assert series.values == [1.0, 0.5, 0.3]

        runs = list_runs(conn)
        assert len(runs) == 1
        assert runs[0].status == "completed"
        conn.close()

    def test_resume_latest(self, db_path):
        """resume=True without id resumes the latest run."""
        db = str(db_path)
        with stonks.start_run("test-exp", save_dir=db) as run:
            run.log({"loss": 1.0}, step=0)
            original_id = run.id

        with stonks.start_run("test-exp", resume=True, save_dir=db) as run:
            assert run.id == original_id
            run.log({"loss": 0.5}, step=1)

        conn = create_connection(db)
        series = get_metrics(conn, original_id, "loss")
        assert series.steps == [0, 1]
        conn.close()

    def test_resume_must_raises_when_not_found(self, db_path):
        """resume="must" raises StonksError when no run exists."""
        db = str(db_path)
        with pytest.raises(StonksError, match="not found"):
            with stonks.start_run("test-exp", id="nonexistent", resume="must", save_dir=db):
                pass

    def test_resume_creates_new_when_not_found(self, db_path):
        """resume=True without id creates a new run if none exists."""
        db = str(db_path)
        with stonks.start_run("test-exp", resume=True, save_dir=db) as run:
            run.log({"loss": 1.0}, step=0)

        conn = create_connection(db)
        runs = list_runs(conn)
        assert len(runs) == 1
        conn.close()

    def test_resume_auto_increments_step(self, db_path):
        """Resumed run auto-increments from the last step."""
        db = str(db_path)
        with stonks.start_run("test-exp", save_dir=db) as run:
            run.log({"loss": 1.0}, step=0)
            run.log({"loss": 0.5}, step=5)
            run_id = run.id

        with stonks.start_run("test-exp", id=run_id, resume=True, save_dir=db) as run:
            # Auto-increment should start from 6 (max_step + 1).
            run.log({"loss": 0.3})

        conn = create_connection(db)
        series = get_metrics(conn, run_id, "loss")
        assert series.steps == [0, 5, 6]
        conn.close()

    def test_resume_merges_config(self, db_path):
        """Resumed run merges new config into existing."""
        db = str(db_path)
        with stonks.start_run("test-exp", config={"lr": 0.001}, save_dir=db) as run:
            run_id = run.id

        with stonks.start_run(
            "test-exp",
            id=run_id,
            resume=True,
            config={"epochs": 10},
            save_dir=db,
        ) as run:
            assert run.config == {"lr": 0.001, "epochs": 10}


class TestDeprecation:
    def test_db_param_deprecated(self, db_path):
        """Using db= emits DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with stonks.start_run("test-exp", db=str(db_path)):
                pass
            deprecation_msgs = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert any("db" in str(m.message) for m in deprecation_msgs)

    def test_run_name_param_deprecated(self, db_path):
        """Using run_name= emits DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with stonks.start_run("test-exp", run_name="my-run", save_dir=str(db_path)):
                pass
            deprecation_msgs = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert any("run_name" in str(m.message) for m in deprecation_msgs)

    def test_experiment_name_param_deprecated(self, db_path):
        """Using experiment_name= on StonksLogger emits DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            StonksLogger(experiment_name="test-exp", save_dir=str(db_path))
            deprecation_msgs = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert any("experiment_name" in str(m.message) for m in deprecation_msgs)

    def test_deprecated_db_on_logger(self, db_path):
        """Using db= on StonksLogger emits DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            StonksLogger("test-exp", db=str(db_path))
            deprecation_msgs = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert any("db" in str(m.message) for m in deprecation_msgs)

    def test_deprecated_params_still_work(self, db_path):
        """Deprecated params produce working behavior."""
        with stonks.start_run("test-exp", db=str(db_path), run_name="old-name") as run:
            assert run.name == "old-name"
            run.log({"loss": 1.0}, step=0)

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert len(runs) == 1
        assert runs[0].name == "old-name"
        conn.close()


class TestStonksLoggerNewParams:
    def test_logger_with_all_new_params(self, db_path):
        """StonksLogger accepts all new parameters."""
        logger = StonksLogger(
            "test-exp",
            project="nlp",
            name="run-1",
            group="sweep",
            job_type="train",
            tags=["baseline"],
            notes="Test",
            config={"lr": 0.001},
            prefix="train",
            save_dir=str(db_path),
        )
        assert logger.name == "test-exp"
        logger.log_metrics({"loss": 1.0}, step=0)
        logger.save()
        logger.finalize("success")

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert len(runs) == 1
        assert runs[0].group == "sweep"
        assert runs[0].job_type == "train"
        assert runs[0].tags == ["baseline"]
        assert runs[0].notes == "Test"
        assert runs[0].config == {"lr": 0.001}

        keys = get_metric_keys(conn, runs[0].id)
        assert "train/loss" in keys
        conn.close()

    def test_logger_default_experiment(self, db_path):
        """StonksLogger defaults experiment to 'default'."""
        logger = StonksLogger(save_dir=str(db_path))
        assert logger.name == "default"

    def test_logger_resume(self, db_path):
        """StonksLogger can resume a run."""
        db = str(db_path)
        logger1 = StonksLogger("test-exp", save_dir=db)
        logger1.log_metrics({"loss": 1.0}, step=0)
        logger1.save()
        run_id = logger1.version
        logger1.finalize("success")

        logger2 = StonksLogger("test-exp", id=run_id, resume=True, save_dir=db)
        logger2.log_metrics({"loss": 0.5}, step=1)
        logger2.save()
        assert logger2.version == run_id
        logger2.finalize("success")

        conn = create_connection(db)
        series = get_metrics(conn, run_id, "loss")
        assert series.steps == [0, 1]
        conn.close()
