"""End-to-end tests for stonks Lightning integration with a full Trainer loop."""

import os

import torch
import torch.nn as nn

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import lightning.pytorch as pl
import pytest

from stonks.lightning import StonksLogger
from stonks.store import create_connection, get_metric_keys, get_metrics, list_runs

from omegaconf import DictConfig, ListConfig


class DummyModel(pl.LightningModule):
    """Minimal model for e2e Lightning tests."""

    def __init__(self, in_features: int = 4, lr: float = 1e-3):
        super().__init__()
        self.save_hyperparameters()
        self.net = nn.Linear(in_features, 1)

    def forward(self, x):
        return self.net(x)

    def training_step(self, batch, batch_idx):
        x, y = batch
        loss = nn.functional.mse_loss(self(x).squeeze(), y)
        self.log("train_loss", loss, on_step=True, on_epoch=True)
        return loss

    def validation_step(self, batch, batch_idx):
        x, y = batch
        loss = nn.functional.mse_loss(self(x).squeeze(), y)
        self.log("val_loss", loss)

    def configure_optimizers(self):
        return torch.optim.SGD(self.parameters(), lr=self.hparams.lr)


class DummyDataModule(pl.LightningDataModule):
    """Minimal datamodule producing random regression data."""

    def __init__(self, n_samples: int = 64, in_features: int = 4, batch_size: int = 16):
        super().__init__()
        self.n_samples = n_samples
        self.in_features = in_features
        self.batch_size = batch_size

    def setup(self, stage=None):
        x = torch.randn(self.n_samples, self.in_features)
        y = torch.randn(self.n_samples)
        self.train_ds = torch.utils.data.TensorDataset(x, y)
        self.val_ds = torch.utils.data.TensorDataset(x[:16], y[:16])

    def train_dataloader(self):
        return torch.utils.data.DataLoader(self.train_ds, batch_size=self.batch_size)

    def val_dataloader(self):
        return torch.utils.data.DataLoader(self.val_ds, batch_size=self.batch_size)


@pytest.fixture
def stonks_logger(db_path):
    """Provide a StonksLogger writing to a temporary database."""
    return StonksLogger(experiment="e2e-test", save_dir=str(db_path))


@pytest.fixture
def dummy_data():
    """Provide a DummyDataModule."""
    return DummyDataModule()


@pytest.fixture
def trainer_kwargs():
    """Base Trainer keyword arguments for fast local tests."""
    return {
        "accelerator": "cpu",
        "max_epochs": 2,
        "enable_checkpointing": False,
        "enable_progress_bar": False,
        "enable_model_summary": False,
        "log_every_n_steps": 1,
    }


class TestLightningE2E:
    """Full trainer loop with StonksLogger."""

    def test_fit_logs_train_and_val_metrics(self, stonks_logger, dummy_data, trainer_kwargs, db_path):
        trainer = pl.Trainer(logger=stonks_logger, **trainer_kwargs)
        model = DummyModel()
        trainer.fit(model, datamodule=dummy_data)

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert len(runs) == 1

        keys = get_metric_keys(conn, runs[0].id)
        assert "train_loss_step" in keys or "train_loss" in keys
        conn.close()

    def test_fit_logs_hyperparameters(self, stonks_logger, dummy_data, trainer_kwargs, db_path):
        trainer = pl.Trainer(logger=stonks_logger, **trainer_kwargs)
        model = DummyModel(in_features=8, lr=0.01)
        trainer.fit(model, datamodule=DummyDataModule(in_features=8))

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert len(runs) == 1
        assert runs[0].config["in_features"] == 8
        assert runs[0].config["lr"] == 0.01
        conn.close()

    def test_fit_finalizes_run_as_completed(self, stonks_logger, dummy_data, trainer_kwargs, db_path):
        trainer = pl.Trainer(logger=stonks_logger, **trainer_kwargs)
        trainer.fit(DummyModel(), datamodule=dummy_data)

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert len(runs) == 1
        assert runs[0].status == "completed"
        conn.close()

    def test_validate_before_fit_logs_hyperparams(self, stonks_logger, dummy_data, trainer_kwargs, db_path):
        """validate() before fit() triggers log_hyperparams — must not crash."""
        trainer = pl.Trainer(logger=stonks_logger, **trainer_kwargs)
        model = DummyModel()
        trainer.validate(model, datamodule=dummy_data)

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert len(runs) == 1
        conn.close()

    def test_multiple_loggers(self, db_path, dummy_data, trainer_kwargs):
        """StonksLogger works alongside other loggers."""
        from lightning.pytorch.loggers import CSVLogger

        stonks = StonksLogger(experiment="multi-logger", save_dir=str(db_path))
        csv = CSVLogger(save_dir=str(db_path.parent / "csv"))
        trainer = pl.Trainer(logger=[csv, stonks], **trainer_kwargs)
        trainer.fit(DummyModel(), datamodule=dummy_data)

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert len(runs) == 1
        conn.close()

    def test_max_steps_mode(self, stonks_logger, dummy_data, trainer_kwargs, db_path):
        """Step-based training (max_epochs=-1, max_steps=N) works."""
        trainer_kwargs["max_epochs"] = -1
        trainer_kwargs["max_steps"] = 5
        trainer = pl.Trainer(logger=stonks_logger, **trainer_kwargs)
        trainer.fit(DummyModel(), datamodule=dummy_data)

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert len(runs) == 1
        assert runs[0].status == "completed"
        conn.close()


class TestHyperparamSerialization:
    """Ensure log_hyperparams handles non-plain-dict types from frameworks."""

    def test_omegaconf_listconfig_in_hparams(self, db_path, dummy_data, trainer_kwargs):
        """Hydra ListConfig in model hparams must not crash log_hyperparams."""

        class ModelWithListConfig(pl.LightningModule):
            def __init__(self):
                super().__init__()
                self.save_hyperparameters({"lr": 0.001, "betas": ListConfig([0.9, 0.999])})
                self.net = nn.Linear(4, 1)

            def training_step(self, batch, batch_idx):
                x, y = batch
                return nn.functional.mse_loss(self.net(x).squeeze(), y)

            def configure_optimizers(self):
                return torch.optim.SGD(self.parameters(), lr=0.001)

        logger = StonksLogger(experiment="listconfig-test", save_dir=str(db_path))
        trainer = pl.Trainer(logger=logger, **trainer_kwargs)
        trainer.fit(ModelWithListConfig(), datamodule=dummy_data)

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert len(runs) == 1
        assert runs[0].config["betas"] == [0.9, 0.999]
        conn.close()

    def test_omegaconf_dictconfig_in_hparams(self, db_path, dummy_data, trainer_kwargs):
        """Hydra DictConfig in model hparams must not crash log_hyperparams."""

        class ModelWithDictConfig(pl.LightningModule):
            def __init__(self):
                super().__init__()
                self.save_hyperparameters(
                    {"optimizer": DictConfig({"type": "adam", "lr": 0.001, "betas": [0.9, 0.999]})}
                )
                self.net = nn.Linear(4, 1)

            def training_step(self, batch, batch_idx):
                x, y = batch
                return nn.functional.mse_loss(self.net(x).squeeze(), y)

            def configure_optimizers(self):
                return torch.optim.SGD(self.parameters(), lr=0.001)

        logger = StonksLogger(experiment="dictconfig-test", save_dir=str(db_path))
        trainer = pl.Trainer(logger=logger, **trainer_kwargs)
        trainer.fit(ModelWithDictConfig(), datamodule=dummy_data)

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert len(runs) == 1
        assert runs[0].config["optimizer"]["type"] == "adam"
        conn.close()

    def test_nested_listconfig_in_hparams(self, db_path, dummy_data, trainer_kwargs):
        """Deeply nested ListConfig/DictConfig must serialize cleanly."""

        class ModelWithNestedConfig(pl.LightningModule):
            def __init__(self):
                super().__init__()
                self.save_hyperparameters(
                    {
                        "model": DictConfig(
                            {
                                "layers": ListConfig([64, 128, 256]),
                                "activations": ListConfig(["relu", "gelu"]),
                                "nested": DictConfig({"a": ListConfig([1, 2, 3])}),
                            }
                        )
                    }
                )
                self.net = nn.Linear(4, 1)

            def training_step(self, batch, batch_idx):
                x, y = batch
                return nn.functional.mse_loss(self.net(x).squeeze(), y)

            def configure_optimizers(self):
                return torch.optim.SGD(self.parameters(), lr=0.001)

        logger = StonksLogger(experiment="nested-test", save_dir=str(db_path))
        trainer = pl.Trainer(logger=logger, **trainer_kwargs)
        trainer.fit(ModelWithNestedConfig(), datamodule=dummy_data)

        conn = create_connection(str(db_path))
        runs = list_runs(conn)
        assert len(runs) == 1
        assert runs[0].config["model"]["layers"] == [64, 128, 256]
        assert runs[0].config["model"]["nested"]["a"] == [1, 2, 3]
        conn.close()
