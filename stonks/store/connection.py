"""Database connection and schema management."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from loguru import logger

_SCHEMA_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        created_at REAL NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS experiments (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        created_at REAL NOT NULL,
        metadata TEXT,
        project_id TEXT REFERENCES projects(id)
    )""",
    """CREATE TABLE IF NOT EXISTS runs (
        id TEXT PRIMARY KEY,
        experiment_id TEXT NOT NULL,
        name TEXT,
        status TEXT NOT NULL DEFAULT 'running',
        config TEXT,
        created_at REAL NOT NULL,
        ended_at REAL,
        last_heartbeat REAL,
        group_name TEXT,
        job_type TEXT,
        tags TEXT,
        notes TEXT,
        prefix TEXT DEFAULT '',
        FOREIGN KEY (experiment_id) REFERENCES experiments(id)
    )""",
    """CREATE TABLE IF NOT EXISTS metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        key TEXT NOT NULL,
        value REAL,
        step INTEGER NOT NULL,
        timestamp REAL NOT NULL,
        FOREIGN KEY (run_id) REFERENCES runs(id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_metrics_run_key_step ON metrics(run_id, key, step)",
    "CREATE INDEX IF NOT EXISTS idx_metrics_run_timestamp ON metrics(run_id, timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_runs_experiment ON runs(experiment_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_runs_group ON runs(group_name)",
    "CREATE INDEX IF NOT EXISTS idx_runs_job_type ON runs(job_type)",
    "CREATE INDEX IF NOT EXISTS idx_experiments_created ON experiments(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_experiments_project ON experiments(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name)",
]

# Migrations for existing databases that don't have the new columns yet.
_MIGRATION_COLUMNS = [
    (
        "projects",
        None,
        """CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, created_at REAL NOT NULL
    )""",
    ),
    (
        "experiments",
        "project_id",
        "ALTER TABLE experiments ADD COLUMN project_id TEXT REFERENCES projects(id)",
    ),
    ("runs", "group_name", "ALTER TABLE runs ADD COLUMN group_name TEXT"),
    ("runs", "job_type", "ALTER TABLE runs ADD COLUMN job_type TEXT"),
    ("runs", "tags", "ALTER TABLE runs ADD COLUMN tags TEXT"),
    ("runs", "notes", "ALTER TABLE runs ADD COLUMN notes TEXT"),
    ("runs", "prefix", "ALTER TABLE runs ADD COLUMN prefix TEXT DEFAULT ''"),
]


def create_connection(db_path: str | Path) -> sqlite3.Connection:
    """Create an optimized SQLite connection.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Configured sqlite3.Connection.
    """
    conn = sqlite3.connect(str(db_path), timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def initialize_db(conn: sqlite3.Connection) -> None:
    """Create tables and indexes if they don't exist.

    Also runs migrations for existing databases that predate new columns.

    Args:
        conn: Active database connection.
    """
    for statement in _SCHEMA_STATEMENTS:
        conn.execute(statement)
    conn.commit()

    # Migrate existing databases: add columns that may not exist yet.
    for table, column, sql in _MIGRATION_COLUMNS:
        if column is None:
            # Table creation (already handled by CREATE TABLE IF NOT EXISTS above)
            continue
        try:
            conn.execute(sql)
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists — expected for fresh or already-migrated DBs.
            pass

    logger.debug("Database schema initialized")
