"""FastAPI dependency injection for stonks server."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from typing import Any

from stonks.store import create_connection, initialize_db


class DatabaseManager:
    """Manages SQLite connections for the FastAPI server.

    Args:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        conn = create_connection(db_path)
        initialize_db(conn)
        conn.close()

    def connect(self) -> sqlite3.Connection:
        """Create a new connection for a request.

        Returns:
            Configured sqlite3.Connection.
        """
        return create_connection(self._db_path)


_manager: DatabaseManager | None = None


def init_db_manager(db_path: str) -> DatabaseManager:
    """Initialize the global database manager.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        The initialized DatabaseManager.
    """
    global _manager  # noqa: PLW0603
    _manager = DatabaseManager(db_path)
    return _manager


def get_manager() -> DatabaseManager:
    """Return the global database manager.

    Returns:
        The initialized DatabaseManager.

    Raises:
        RuntimeError: If init_db_manager() has not been called.
    """
    if _manager is None:
        raise RuntimeError("Database manager not initialized. Call init_db_manager() first.")
    return _manager


def get_db() -> Generator[sqlite3.Connection, Any, None]:
    """FastAPI dependency that provides a DB connection per request.

    Yields:
        sqlite3.Connection for the duration of the request.
    """
    manager = get_manager()
    conn = manager.connect()
    try:
        yield conn
    finally:
        conn.close()
