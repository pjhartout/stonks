"""PyTorch Lightning logger integration for stonks."""

from __future__ import annotations

import warnings
from typing import Any, Literal

from loguru import logger as log

try:
    import torch.distributed as torch_dist
    from lightning.pytorch.callbacks import Callback
    from lightning.pytorch.loggers.logger import Logger, rank_zero_experiment
    from lightning.pytorch.utilities import rank_zero_only
except ImportError as e:
    raise ImportError(
        "PyTorch Lightning is required for StonksLogger. Install it with: uv add stonks[lightning]"
    ) from e

from stonks.config import resolve_db_path
from stonks.distributed import get_distributed_info
from stonks.hardware import collect_hardware_snapshot
from stonks.run import Run


class StonksLogger(Logger):
    """PyTorch Lightning logger that writes to a stonks SQLite database.

    All parameters are optional with sensible defaults.

    Args:
        project: Top-level project name for grouping experiments.
        experiment: Experiment name. Defaults to "default".
        name: Optional display name for this run.
        id: Optional run ID for resume.
        resume: If True, resume existing run. If "must", raise if not found.
        group: Optional grouping key (e.g. k-fold, sweep).
        job_type: Optional run type (e.g. train, eval).
        tags: Optional list of tags.
        notes: Optional run description.
        config: Optional hyperparameters dict to log at start.
        prefix: Metric key prefix prepended to all logged keys.
        save_dir: DB path. Defaults to ./stonks.db or STONKS_DB env var.
        hardware: If True, enable background hardware monitoring.
        hardware_interval: Seconds between hardware polls (minimum 1.0).
        hardware_gpu: Whether to attempt GPU monitoring via pynvml.
        strict: If True, raise on logging errors.
        experiment_name: Deprecated. Use experiment instead.
        db: Deprecated. Use save_dir instead.
        run_name: Deprecated. Use name instead.

    Example::

        from stonks.lightning import StonksLogger
        logger = StonksLogger(project="nlp", experiment="bert", hardware=True)
        trainer = pl.Trainer(logger=logger)
        trainer.fit(model)
    """

    def __init__(
        self,
        experiment: str | None = None,
        *,
        # Organizational.
        project: str | None = None,
        name: str | None = None,
        id: str | None = None,
        resume: bool | Literal["must"] | None = None,
        group: str | None = None,
        job_type: str | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
        config: dict | None = None,
        prefix: str = "",
        # Storage.
        save_dir: str | None = None,
        # Monitoring.
        hardware: bool = False,
        hardware_interval: float = 5.0,
        hardware_gpu: bool = True,
        # Behavior.
        strict: bool = False,
        # Deprecated parameter names.
        experiment_name: str | None = None,
        db: str | None = None,
        run_name: str | None = None,
    ) -> None:
        super().__init__()

        # Handle deprecated parameter names.
        if experiment_name is not None:
            warnings.warn(
                "The 'experiment_name' parameter is deprecated. Use 'experiment' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            if experiment is None:
                experiment = experiment_name

        if db is not None:
            warnings.warn(
                "The 'db' parameter is deprecated. Use 'save_dir' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            if save_dir is None:
                save_dir = db

        if run_name is not None:
            warnings.warn(
                "The 'run_name' parameter is deprecated. Use 'name' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            if name is None:
                name = run_name

        # Resolve experiment name immediately (Lightning reads logger.name early).
        self._experiment_name = experiment or "default"
        self._project = project
        self._name = name
        self._id = id
        self._resume = resume
        self._group = group
        self._job_type = job_type
        self._tags = tags
        self._notes = notes
        self._config = config
        self._prefix = prefix
        self._db_path = str(resolve_db_path(save_dir))
        self._hardware = hardware
        self._hardware_interval = hardware_interval
        self._hardware_gpu = hardware_gpu
        self._strict = strict
        self._run: Run | None = None

    def _ensure_run(self) -> Run:
        """Lazily initialize the Run on first use.

        Returns:
            The active Run instance.
        """
        if self._run is None:
            self._run = Run(
                experiment_name=self._experiment_name,
                db=self._db_path,
                run_name=self._name,
                strict=self._strict,
                hardware=self._hardware,
                hardware_interval=self._hardware_interval,
                hardware_gpu=self._hardware_gpu,
                project=self._project,
                run_id=self._id,
                resume=self._resume,
                group=self._group,
                job_type=self._job_type,
                tags=self._tags,
                notes=self._notes,
                prefix=self._prefix,
            )
            self._run.start()
            # Log initial config if provided.
            if self._config:
                self._run.log_config(self._config)
            log.debug(f"StonksLogger initialized run {self._run.id}")
        return self._run

    @property
    def name(self) -> str:
        """Return the experiment name."""
        return self._experiment_name

    @property
    def version(self) -> str | int:
        """Return the run ID as the version."""
        if self._run is None:
            return "0"
        return self._run.id

    @property
    @rank_zero_experiment
    def experiment(self) -> Run:
        """Return the underlying Run object."""
        return self._ensure_run()

    @rank_zero_only
    def log_hyperparams(self, params: dict[str, Any] | Any) -> None:
        """Log hyperparameters.

        Args:
            params: Dictionary or Namespace of hyperparameters.
        """
        run = self._ensure_run()
        if hasattr(params, "__dict__"):
            params = vars(params)
        if not isinstance(params, dict):
            params = dict(params)
        run.log_config(params)
        log.debug(f"Logged {len(params)} hyperparameters")

    @rank_zero_only
    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        """Log metrics.

        Args:
            metrics: Dictionary mapping metric names to float values.
            step: The global step number.
        """
        run = self._ensure_run()
        run.log(metrics, step=step)

    @rank_zero_only
    def save(self) -> None:
        """Flush buffered metrics to disk."""
        if self._run is not None:
            self._run.flush()

    @rank_zero_only
    def finalize(self, status: str) -> None:
        """Finalize the logger when training ends.

        Args:
            status: One of "success", "failed", "finished".
        """
        if self._run is not None:
            mapped_status = "completed" if status == "success" else status
            self._run.finish(mapped_status)
            self._run = None
            log.info(f"StonksLogger finalized with status '{mapped_status}'")


class StonksDistributedCallback(Callback):
    """Lightning Callback for multi-rank metric and hardware gathering.

    Collects per-rank metrics and hardware stats from all distributed
    processes and logs them through the StonksLogger on rank 0.

    Use alongside StonksLogger in distributed training::

        logger = StonksLogger(experiment="distributed-run")
        callback = StonksDistributedCallback(
            metric_keys=["train_loss", "val_loss"],
            hardware=True,
        )
        trainer = pl.Trainer(logger=logger, callbacks=[callback])

    Args:
        metric_keys: Metric keys to gather per-rank. If None, gathers all
            metrics from trainer.callback_metrics.
        gather_interval: Gather per-rank metrics every N training steps.
            Set higher to reduce communication overhead.
        hardware: If True, gather hardware snapshots from all ranks.
        hardware_interval: Gather hardware every N training steps.
        hardware_gpu: Whether to collect GPU metrics in hardware snapshots.
    """

    def __init__(
        self,
        metric_keys: list[str] | None = None,
        gather_interval: int = 1,
        hardware: bool = True,
        hardware_interval: int = 10,
        hardware_gpu: bool = True,
    ) -> None:
        super().__init__()
        self._metric_keys = metric_keys
        self._gather_interval = max(1, gather_interval)
        self._hardware = hardware
        self._hardware_interval = max(1, hardware_interval)
        self._hardware_gpu = hardware_gpu

    def setup(
        self,
        trainer: Any,
        pl_module: Any,
        stage: str | None = None,
    ) -> None:
        """Log distributed metadata on rank 0 when training starts.

        Args:
            trainer: The Lightning Trainer.
            pl_module: The LightningModule.
            stage: Current stage (fit, validate, test, predict).
        """
        if not torch_dist.is_initialized():
            log.warning(
                "StonksDistributedCallback: torch.distributed not initialized, "
                "callback will be inactive"
            )
            return

        if torch_dist.get_rank() == 0:
            stonks_logger = self._get_stonks_logger(trainer)
            if stonks_logger is not None:
                info = get_distributed_info()
                run = stonks_logger._ensure_run()
                run.log_config({"distributed": info})
                log.info(
                    f"Logged distributed metadata: "
                    f"world_size={info['world_size']}, num_nodes={info['num_nodes']}"
                )

    def on_train_batch_end(
        self,
        trainer: Any,
        pl_module: Any,
        outputs: Any,
        batch: Any,
        batch_idx: int,
    ) -> None:
        """Gather per-rank metrics and hardware after each training batch.

        Args:
            trainer: The Lightning Trainer.
            pl_module: The LightningModule.
            outputs: Output of training_step.
            batch: The current batch.
            batch_idx: Index of the current batch.
        """
        if not torch_dist.is_initialized():
            return

        step = trainer.global_step

        if step % self._gather_interval == 0:
            self._gather_and_log_metrics(trainer, step)

        if self._hardware and step % self._hardware_interval == 0:
            self._gather_and_log_hardware(trainer, step)

    def _gather_and_log_metrics(self, trainer: Any, step: int) -> None:
        """Gather per-rank metrics from all processes and log on rank 0.

        Args:
            trainer: The Lightning Trainer.
            step: Current global step.
        """
        world_size = torch_dist.get_world_size()
        rank = torch_dist.get_rank()

        local_metrics: dict[str, float] = {}
        if self._metric_keys:
            for key in self._metric_keys:
                if key in trainer.callback_metrics:
                    val = trainer.callback_metrics[key]
                    local_metrics[key] = val.item() if hasattr(val, "item") else float(val)
        else:
            for key, val in trainer.callback_metrics.items():
                local_metrics[key] = val.item() if hasattr(val, "item") else float(val)

        gathered: list[dict[str, float] | None] = [None] * world_size
        torch_dist.all_gather_object(gathered, local_metrics)

        if rank == 0:
            stonks_logger = self._get_stonks_logger(trainer)
            if stonks_logger is not None:
                per_rank_metrics: dict[str, float] = {}
                for r, metrics in enumerate(gathered):
                    if metrics:
                        for k, v in metrics.items():
                            per_rank_metrics[f"rank_{r}/{k}"] = v
                if per_rank_metrics:
                    stonks_logger.log_metrics(per_rank_metrics, step=step)

    def _gather_and_log_hardware(self, trainer: Any, step: int) -> None:
        """Gather hardware snapshots from all ranks and log on rank 0.

        Args:
            trainer: The Lightning Trainer.
            step: Current global step.
        """
        world_size = torch_dist.get_world_size()
        rank = torch_dist.get_rank()

        local_hw = collect_hardware_snapshot(enable_gpu=self._hardware_gpu)

        gathered: list[dict[str, float] | None] = [None] * world_size
        torch_dist.all_gather_object(gathered, local_hw)

        if rank == 0:
            stonks_logger = self._get_stonks_logger(trainer)
            if stonks_logger is not None:
                hw_metrics: dict[str, float] = {}
                for r, metrics in enumerate(gathered):
                    if metrics:
                        for k, v in metrics.items():
                            hw_metrics[f"rank_{r}/{k}"] = v
                if hw_metrics:
                    stonks_logger.log_metrics(hw_metrics, step=step)

    def _get_stonks_logger(self, trainer: Any) -> StonksLogger | None:
        """Find the StonksLogger in the trainer's loggers.

        Args:
            trainer: The Lightning Trainer.

        Returns:
            The StonksLogger instance, or None if not found.
        """
        if isinstance(trainer.logger, StonksLogger):
            return trainer.logger
        if hasattr(trainer, "loggers"):
            for lg in trainer.loggers:
                if isinstance(lg, StonksLogger):
                    return lg
        return None
