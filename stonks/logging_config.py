"""Loguru logging configuration for stonks."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

_configured = False


def setup_logging(log_dir: str = "logs") -> None:
    """Configure loguru for stdout + file logging with 1-week retention.

    Args:
        log_dir: Directory to store log files.
    """
    global _configured  # noqa: PLW0603
    if _configured:
        return

    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    logger.remove()

    logger.add(
        sys.stdout,
        level="INFO",
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
        level="DEBUG",
        format=("{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"),
        rotation="1 day",
        retention="1 week",
        compression="zip",
        encoding="utf-8",
    )

    _configured = True
