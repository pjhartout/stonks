"""Configuration and path resolution for stonks."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DB_FILENAME = "stonks.db"
ENV_VAR_DB_PATH = "STONKS_DB"


def resolve_db_path(db: str | None = None) -> Path:
    """Resolve the database file path.

    Priority:
    1. Explicit `db` parameter
    2. STONKS_DB environment variable
    3. ./stonks.db in the current working directory

    Args:
        db: Explicit path to the database file.

    Returns:
        Resolved Path to the database file.
    """
    if db is not None:
        return Path(db)

    env_path = os.environ.get(ENV_VAR_DB_PATH)
    if env_path is not None:
        return Path(env_path)

    return Path.cwd() / DEFAULT_DB_FILENAME
