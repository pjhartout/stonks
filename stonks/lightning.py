"""PyTorch Lightning logger integration for stonks."""

from __future__ import annotations

from typing import Any

from loguru import logger as log

try:
    from lightning.pytorch.loggers.logger import Logger, rank_zero_experiment
    from lightning.pytorch.utilities import rank_zero_only
except ImportError as e:
    raise ImportError(
        "PyTorch Lightning is required for StonksLogger. Install it with: uv add stonks[lightning]"
    ) from e

from stonks.config import resolve_db_path
from stonks.run import Run


class StonksLogger(Logger):
    """PyTorch Lightning logger that writes to a stonks SQLite database.

    Args:
        experiment_name: Name of the experiment.
        db: Path to the SQLite database. Defaults to ./stonks.db or STONKS_DB env var.
        run_name: Optional display name for this run.
        strict: If True, raise on logging errors. If False, swallow and warn.

    Example::

        from stonks.lightning import StonksLogger
        logger = StonksLogger("my-experiment")
        trainer = pl.Trainer(logger=logger)
        trainer.fit(model)
    """

    def __init__(
        self,
        experiment_name: str,
        db: str | None = None,
        run_name: str | None = None,
        strict: bool = False,
    ) -> None:
        super().__init__()
        self._experiment_name = experiment_name
        self._db_path = str(resolve_db_path(db))
        self._run_name = run_name
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
                run_name=self._run_name,
                strict=self._strict,
            )
            self._run.start()
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
