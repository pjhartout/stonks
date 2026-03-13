"""Tests for StonksDistributedCallback."""

import math
from unittest.mock import MagicMock, patch

import pytest

from stonks.lightning import StonksDistributedCallback, StonksLogger, _aggregate_across_ranks


@pytest.fixture
def mock_stonks_logger(db_path):
    """Create a StonksLogger for testing."""
    return StonksLogger("test-exp", save_dir=str(db_path))


@pytest.fixture
def callback():
    """Create a default callback."""
    return StonksDistributedCallback(
        metric_keys=["train_loss"],
        hardware=False,
    )


@pytest.fixture
def mock_trainer(mock_stonks_logger):
    """Create a mock trainer with a StonksLogger."""
    trainer = MagicMock()
    trainer.logger = mock_stonks_logger
    trainer.loggers = [mock_stonks_logger]
    trainer.global_step = 0
    trainer.callback_metrics = {"train_loss": MagicMock(item=lambda: 0.5)}
    return trainer


class TestAggregateAcrossRanks:
    def test_computes_mean_and_std(self):
        gathered = [
            {"loss": 1.0, "acc": 0.8},
            {"loss": 3.0, "acc": 0.6},
        ]
        result = _aggregate_across_ranks(gathered)
        assert result["avg/loss"] == pytest.approx(2.0)
        assert result["avg/acc"] == pytest.approx(0.7)
        assert result["std/loss"] == pytest.approx(math.sqrt(2.0))
        assert result["std/acc"] == pytest.approx(math.sqrt(0.02))

    def test_single_rank(self):
        gathered = [{"loss": 5.0}]
        result = _aggregate_across_ranks(gathered)
        assert result["avg/loss"] == pytest.approx(5.0)
        assert result["std/loss"] == 0.0

    def test_skips_none_entries(self):
        gathered = [None, {"loss": 4.0}, None, {"loss": 6.0}]
        result = _aggregate_across_ranks(gathered)
        assert result["avg/loss"] == pytest.approx(5.0)

    def test_empty_gathered(self):
        assert _aggregate_across_ranks([]) == {}
        assert _aggregate_across_ranks([None, None]) == {}

    def test_missing_keys_on_some_ranks(self):
        gathered = [
            {"loss": 1.0, "acc": 0.9},
            {"loss": 3.0},
        ]
        result = _aggregate_across_ranks(gathered)
        assert result["avg/loss"] == pytest.approx(2.0)
        assert result["avg/acc"] == pytest.approx(0.9)
        assert result["std/acc"] == 0.0


class TestCallbackInit:
    def test_default_params(self):
        cb = StonksDistributedCallback()
        assert cb._metric_keys is None
        assert cb._gather_interval == 1
        assert cb._hardware is True
        assert cb._hardware_interval == 10
        assert cb._hardware_gpu is True

    def test_custom_params(self):
        cb = StonksDistributedCallback(
            metric_keys=["loss", "acc"],
            gather_interval=5,
            hardware=False,
            hardware_interval=20,
            hardware_gpu=False,
        )
        assert cb._metric_keys == ["loss", "acc"]
        assert cb._gather_interval == 5
        assert cb._hardware is False
        assert cb._hardware_interval == 20
        assert cb._hardware_gpu is False

    def test_gather_interval_minimum(self):
        cb = StonksDistributedCallback(gather_interval=0)
        assert cb._gather_interval == 1

    def test_hardware_interval_minimum(self):
        cb = StonksDistributedCallback(hardware_interval=-1)
        assert cb._hardware_interval == 1


class TestGetStonksLogger:
    def test_finds_direct_logger(self, callback, mock_stonks_logger):
        trainer = MagicMock()
        trainer.logger = mock_stonks_logger
        assert callback._get_stonks_logger(trainer) is mock_stonks_logger

    def test_finds_logger_in_list(self, callback, mock_stonks_logger):
        trainer = MagicMock()
        trainer.logger = MagicMock()  # Not a StonksLogger
        trainer.loggers = [MagicMock(), mock_stonks_logger]
        assert callback._get_stonks_logger(trainer) is mock_stonks_logger

    def test_returns_none_when_not_found(self, callback):
        trainer = MagicMock()
        trainer.logger = MagicMock()
        trainer.loggers = [MagicMock()]
        assert callback._get_stonks_logger(trainer) is None


class TestCallbackSetup:
    @patch("stonks.lightning.torch_dist")
    def test_inactive_when_dist_not_initialized(self, mock_dist, callback, mock_trainer):
        """Callback is inactive when torch.distributed is not initialized."""
        mock_dist.is_initialized.return_value = False
        callback.setup(mock_trainer, MagicMock())
        # Should not crash, just log a warning

    @patch("stonks.lightning.torch_dist")
    def test_logs_metadata_on_rank_zero(self, mock_dist, callback, mock_trainer, db_path):
        """Callback logs distributed metadata on rank 0."""
        mock_dist.is_initialized.return_value = True
        mock_dist.get_rank.return_value = 0
        mock_dist.get_world_size.return_value = 4
        mock_dist.get_backend.return_value = "nccl"

        callback.setup(mock_trainer, MagicMock())

        # The logger should have been initialized and config logged
        assert mock_trainer.logger._run is not None
        config = mock_trainer.logger._run.config
        assert config is not None
        assert "distributed" in config
        mock_trainer.logger.finalize("success")

    @patch("stonks.lightning.torch_dist")
    def test_no_metadata_on_non_rank_zero(self, mock_dist, callback, mock_trainer):
        """Non-rank-0 processes do not log metadata."""
        mock_dist.is_initialized.return_value = True
        mock_dist.get_rank.return_value = 1
        callback.setup(mock_trainer, MagicMock())
        assert mock_trainer.logger._run is None


class TestCallbackOnTrainBatchEnd:
    @patch("stonks.lightning.torch_dist")
    def test_noop_when_dist_not_initialized(self, mock_dist, callback, mock_trainer):
        """No gather when dist is not initialized."""
        mock_dist.is_initialized.return_value = False
        callback.on_train_batch_end(mock_trainer, MagicMock(), None, None, 0)
        mock_dist.all_gather_object.assert_not_called()

    @patch("stonks.lightning.torch_dist")
    def test_respects_gather_interval(self, mock_dist, mock_trainer):
        """Metrics are only gathered at the specified interval."""
        mock_dist.is_initialized.return_value = True
        mock_dist.get_rank.return_value = 0
        mock_dist.get_world_size.return_value = 2

        cb = StonksDistributedCallback(
            metric_keys=["train_loss"],
            gather_interval=5,
            hardware=False,
        )

        # Step 0: should gather (0 % 5 == 0)
        mock_trainer.global_step = 0
        cb.on_train_batch_end(mock_trainer, MagicMock(), None, None, 0)
        assert mock_dist.all_gather_object.call_count == 1

        # Step 3: should not gather (3 % 5 != 0)
        mock_dist.all_gather_object.reset_mock()
        mock_trainer.global_step = 3
        cb.on_train_batch_end(mock_trainer, MagicMock(), None, None, 3)
        mock_dist.all_gather_object.assert_not_called()

        # Step 5: should gather (5 % 5 == 0)
        mock_trainer.global_step = 5
        cb.on_train_batch_end(mock_trainer, MagicMock(), None, None, 5)
        assert mock_dist.all_gather_object.call_count == 1
