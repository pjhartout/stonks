"""Tests for stonks data models."""

from stonks.models import (
    Experiment,
    MetricPoint,
    MetricSeries,
    RunInfo,
    config_from_json,
    config_to_json,
)


class TestConfigSerialization:
    def test_config_to_json(self):
        result = config_to_json({"lr": 0.001, "epochs": 10})
        assert '"lr": 0.001' in result
        assert '"epochs": 10' in result

    def test_config_to_json_none(self):
        assert config_to_json(None) is None

    def test_config_from_json(self):
        result = config_from_json('{"lr": 0.001, "epochs": 10}')
        assert result == {"lr": 0.001, "epochs": 10}

    def test_config_from_json_none(self):
        assert config_from_json(None) is None

    def test_roundtrip(self):
        original = {"lr": 0.001, "nested": {"a": 1, "b": [1, 2, 3]}}
        result = config_from_json(config_to_json(original))
        assert result == original


class TestDataclasses:
    def test_experiment(self):
        exp = Experiment(id="abc", name="test", created_at=1.0)
        assert exp.id == "abc"
        assert exp.name == "test"
        assert exp.description is None

    def test_run_info(self):
        run = RunInfo(id="abc", experiment_id="def", status="running", created_at=1.0)
        assert run.id == "abc"
        assert run.config is None
        assert run.ended_at is None

    def test_metric_point(self):
        point = MetricPoint(key="loss", value=0.5, step=1, timestamp=1.0)
        assert point.key == "loss"
        assert point.value == 0.5

    def test_metric_series(self):
        series = MetricSeries(key="loss")
        series.steps.append(0)
        series.values.append(1.0)
        series.timestamps.append(1.0)
        assert len(series.steps) == 1
        assert series.key == "loss"
