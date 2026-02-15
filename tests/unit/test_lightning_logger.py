"""Tests for stonks PyTorch Lightning logger."""

import argparse

from stonks.lightning import StonksLogger
from stonks.store import create_connection, get_metric_keys, get_metrics, list_runs


class TestStonksLogger:
    def test_lazy_initialization(self, db_path):
        """Run is not created until first log call."""
        logger = StonksLogger("test-exp", db=str(db_path))
        assert logger._run is None
        assert logger.version == "0"

    def test_log_metrics_initializes_run(self, db_path):
        """First log_metrics call creates the run."""
        logger = StonksLogger("test-exp", db=str(db_path))
        logger.log_metrics({"loss": 0.5}, step=0)
        assert logger._run is not None
        assert logger.version != "0"
        logger.finalize("success")

    def test_log_metrics(self, db_path):
        """Metrics are written to the database."""
        logger = StonksLogger("test-exp", db=str(db_path))
        logger.log_metrics({"loss": 1.0}, step=0)
        logger.log_metrics({"loss": 0.5}, step=1)
        logger.save()
        logger.finalize("success")

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert len(runs) == 1

        series = get_metrics(conn, runs[0].id, "loss")
        assert series.values == [1.0, 0.5]
        assert series.steps == [0, 1]
        conn.close()

    def test_log_hyperparams_dict(self, db_path):
        """Hyperparameters from a dict are stored as config."""
        logger = StonksLogger("test-exp", db=str(db_path))
        logger.log_hyperparams({"lr": 0.001, "batch_size": 32})
        logger.finalize("success")

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert runs[0].config["lr"] == 0.001
        assert runs[0].config["batch_size"] == 32
        conn.close()

    def test_log_hyperparams_namespace(self, db_path):
        """Hyperparameters from argparse.Namespace are converted to dict."""
        logger = StonksLogger("test-exp", db=str(db_path))
        ns = argparse.Namespace(lr=0.001, epochs=10)
        logger.log_hyperparams(ns)
        logger.finalize("success")

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert runs[0].config["lr"] == 0.001
        assert runs[0].config["epochs"] == 10
        conn.close()

    def test_finalize_success(self, db_path):
        """finalize("success") maps to status "completed"."""
        logger = StonksLogger("test-exp", db=str(db_path))
        logger.log_metrics({"loss": 0.5}, step=0)
        logger.finalize("success")

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert runs[0].status == "completed"
        conn.close()

    def test_finalize_failed(self, db_path):
        """finalize("failed") keeps status "failed"."""
        logger = StonksLogger("test-exp", db=str(db_path))
        logger.log_metrics({"loss": 0.5}, step=0)
        logger.finalize("failed")

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert runs[0].status == "failed"
        conn.close()

    def test_finalize_without_logging(self, db_path):
        """Finalizing a logger that was never used is a no-op."""
        logger = StonksLogger("test-exp", db=str(db_path))
        logger.finalize("success")  # Should not raise

    def test_save_flushes_buffer(self, db_path):
        """save() forces a flush of buffered metrics."""
        logger = StonksLogger("test-exp", db=str(db_path))
        logger.log_metrics({"loss": 0.5}, step=0)
        logger.save()

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        series = get_metrics(conn, runs[0].id, "loss")
        assert len(series.values) == 1
        conn.close()

        logger.finalize("success")

    def test_name_property(self, db_path):
        """name property returns the experiment name."""
        logger = StonksLogger("my-experiment", db=str(db_path))
        assert logger.name == "my-experiment"

    def test_experiment_reuse(self, db_path):
        """Multiple loggers with same experiment name share the experiment."""
        logger1 = StonksLogger("shared-exp", db=str(db_path))
        logger1.log_metrics({"loss": 1.0}, step=0)
        logger1.finalize("success")

        logger2 = StonksLogger("shared-exp", db=str(db_path))
        logger2.log_metrics({"loss": 0.5}, step=0)
        logger2.finalize("success")

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert len(runs) == 2
        # Both runs should belong to the same experiment
        assert runs[0].experiment_id == runs[1].experiment_id
        conn.close()

    def test_multiple_metric_keys(self, db_path):
        """Multiple metric keys are logged correctly."""
        logger = StonksLogger("test-exp", db=str(db_path))
        logger.log_metrics({"train/loss": 1.0, "train/acc": 0.5}, step=0)
        logger.log_metrics({"train/loss": 0.5, "train/acc": 0.8}, step=1)
        logger.save()
        logger.finalize("success")

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        keys = get_metric_keys(conn, runs[0].id)
        assert "train/loss" in keys
        assert "train/acc" in keys
        conn.close()
