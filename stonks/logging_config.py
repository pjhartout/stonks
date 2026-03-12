"""Loguru logging configuration for stonks."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger

_configured = False

_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


def _resolve_stdout_level() -> str:
    """Resolve the stdout log level from STONKS_LOG_LEVEL env var.

    Returns:
        A valid log level string (DEBUG, INFO, WARNING, or ERROR).
    """
    env_level = os.environ.get("STONKS_LOG_LEVEL")
    if env_level is None:
        return "WARNING"

    normalized = env_level.upper().strip()
    if normalized in _VALID_LEVELS:
        return normalized

    logger.warning(
        f"Invalid STONKS_LOG_LEVEL '{env_level}', "
        f"expected one of {sorted(_VALID_LEVELS)}. Falling back to WARNING."
    )
    return "WARNING"


def setup_logging(log_dir: str = "logs") -> None:
    """Configure loguru for stdout + file logging with 1-week retention.

    The stdout log level can be controlled via the STONKS_LOG_LEVEL
    environment variable. Accepted values: DEBUG, INFO, WARNING, ERROR.
    Invalid values log a warning and fall back to WARNING. The file log
    level is always WARNING regardless of the env var.

    Args:
        log_dir: Directory to store log files.
    """
    global _configured  # noqa: PLW0603
    if _configured:
        return

    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    logger.remove()

    stdout_level = _resolve_stdout_level()

    logger.add(
        sys.stdout,
        level=stdout_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    logger.add(
        str(log_path / "stonks_{time}.log"),
        level="WARNING",
        format=("{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"),
        rotation="1 day",
        retention="1 week",
        compression="zip",
        encoding="utf-8",
    )

    _configured = True
