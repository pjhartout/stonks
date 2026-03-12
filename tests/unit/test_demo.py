"""Tests for the demo data generation module."""

from __future__ import annotations

import stonks
from stonks.demo import EXPERIMENTS, generate_demo_data, get_default_demo_db


class TestDemoDataGeneration:
    """Tests for generate_demo_data."""

    def test_generates_all_experiments(self, tmp_path):
        """Demo generates the expected number of experiments."""
        db_path = str(tmp_path / "demo.db")
        generate_demo_data(db_path)

        db = stonks.open(db_path)
        experiments = db.list_experiments()
        db.close()

        assert len(experiments) == len(EXPERIMENTS)
        exp_names = {e.name for e in experiments}
        for exp_config in EXPERIMENTS:
            assert exp_config.name in exp_names

    def test_generates_correct_run_count(self, tmp_path):
        """Demo generates the expected number of runs per experiment."""
        db_path = str(tmp_path / "demo.db")
        generate_demo_data(db_path)

        db = stonks.open(db_path)
        experiments = db.list_experiments()

        total_expected = sum(len(exp.runs) for exp in EXPERIMENTS)
        total_actual = 0
        for exp in experiments:
            runs = db.list_runs(exp.id)
            total_actual += len(runs)
        db.close()

        assert total_actual == total_expected

    def test_runs_have_metrics(self, tmp_path):
        """Demo runs have logged metrics."""
        db_path = str(tmp_path / "demo.db")
        generate_demo_data(db_path)

        db = stonks.open(db_path)
        experiments = db.list_experiments()
        runs = db.list_runs(experiments[0].id)
        keys = db.get_metric_keys(runs[0].id)
        db.close()

        assert len(keys) > 0
        assert "train/loss" in keys
        assert "train/accuracy" in keys

    def test_runs_have_configs(self, tmp_path):
        """Demo runs have hyperparameter configurations."""
        db_path = str(tmp_path / "demo.db")
        generate_demo_data(db_path)

        db = stonks.open(db_path)
        experiments = db.list_experiments()
        runs = db.list_runs(experiments[0].id)
        db.close()

        for run in runs:
            assert run.config is not None
            assert "model" in run.config
            assert "learning_rate" in run.config

    def test_runs_have_tags(self, tmp_path):
        """Demo runs have tags assigned."""
        db_path = str(tmp_path / "demo.db")
        generate_demo_data(db_path)

        db = stonks.open(db_path)
        experiments = db.list_experiments()
        runs = db.list_runs(experiments[0].id)
        db.close()

        all_tags = set()
        for run in runs:
            if run.tags:
                all_tags.update(run.tags)

        assert "baseline" in all_tags
        assert "experiment" in all_tags

    def test_runs_have_groups(self, tmp_path):
        """Demo runs have groups assigned."""
        db_path = str(tmp_path / "demo.db")
        generate_demo_data(db_path)

        db = stonks.open(db_path)
        experiments = db.list_experiments()
        runs = db.list_runs(experiments[0].id)
        db.close()

        groups = {run.group for run in runs if run.group}
        assert len(groups) > 0

    def test_deterministic_with_seed(self, tmp_path):
        """Demo produces identical data with the same seed."""
        db_path1 = str(tmp_path / "demo1.db")
        db_path2 = str(tmp_path / "demo2.db")

        generate_demo_data(db_path1)
        generate_demo_data(db_path2)

        db1 = stonks.open(db_path1)
        db2 = stonks.open(db_path2)

        exps1 = db1.list_experiments()
        exps2 = db2.list_experiments()

        assert len(exps1) == len(exps2)

        runs1 = db1.list_runs(exps1[0].id)
        runs2 = db2.list_runs(exps2[0].id)
        keys1 = db1.get_metric_keys(runs1[0].id)
        keys2 = db2.get_metric_keys(runs2[0].id)
        assert keys1 == keys2

        series1 = db1.get_metrics(runs1[0].id, "train/loss")
        series2 = db2.get_metrics(runs2[0].id, "train/loss")
        assert series1.values == series2.values

        db1.close()
        db2.close()


class TestGetDefaultDemoDb:
    """Tests for get_default_demo_db."""

    def test_returns_temp_path(self):
        """Default demo db is in a temp directory."""
        path = get_default_demo_db()
        assert "stonks-demo.db" in path
        assert "/" in path
