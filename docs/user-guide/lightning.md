# PyTorch Lightning Integration

stonks provides a drop-in Lightning logger via `StonksLogger`.

## Installation

```bash
uv sync --extra lightning
```

## Basic Usage

```python
import lightning.pytorch as pl
from stonks.lightning import StonksLogger

logger = StonksLogger("my-experiment", run_name="baseline")
trainer = pl.Trainer(logger=logger, max_epochs=10)
trainer.fit(model, datamodule)
```

`StonksLogger` automatically:
- Creates the experiment and run on first use (lazy initialization)
- Logs hyperparameters from `trainer.fit()` via `log_hyperparams()`
- Logs all metrics reported by your `LightningModule` via `self.log()`
- Flushes and finalizes the run when training ends

## Constructor Parameters

`experiment_name`
: Name of the experiment.

`db` *(optional)*
: Path to the SQLite database. Defaults to `./stonks.db` or `STONKS_DB` env var.

`run_name` *(optional)*
: Display name for this run.

`strict` *(optional)*
: If `True`, raise on logging errors.

## Using Multiple Loggers

You can combine `StonksLogger` with other Lightning loggers:

```python
from lightning.pytorch.loggers import TensorBoardLogger

stonks_logger = StonksLogger("my-experiment")
tb_logger = TensorBoardLogger("tb_logs")

trainer = pl.Trainer(logger=[stonks_logger, tb_logger])
```

## Logging Custom Metrics

Your `LightningModule` logs metrics as usual with `self.log()`:

```python
class MyModel(pl.LightningModule):
    def training_step(self, batch, batch_idx):
        loss = self.compute_loss(batch)
        self.log("train/loss", loss)
        return loss

    def validation_step(self, batch, batch_idx):
        loss = self.compute_loss(batch)
        acc = self.compute_accuracy(batch)
        self.log("val/loss", loss)
        self.log("val/accuracy", acc)
```

## Distributed Training

`StonksLogger` respects Lightning's `rank_zero_only` decorators — only the rank-0 process logs metrics, preventing duplicate entries in multi-GPU training.

## Accessing the Underlying Run

You can access the raw `Run` object via the `.experiment` property:

```python
logger = StonksLogger("my-experiment")
trainer = pl.Trainer(logger=logger)
trainer.fit(model)

# After training, access run info
run = logger.experiment
print(f"Run ID: {run.id}")
```
