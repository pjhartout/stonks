"""Project data access operations."""

from __future__ import annotations

import sqlite3
import time
import uuid

from loguru import logger

from stonks.models import Project


def create_project(
    conn: sqlite3.Connection,
    name: str,
) -> Project:
    """Create a new project or return existing one by name.

    Args:
        conn: Active database connection.
        name: Project name (unique).

    Returns:
        The created or existing Project.
    """
    now = time.time()
    project_id = str(uuid.uuid4())

    try:
        conn.execute(
            "INSERT INTO projects (id, name, created_at) VALUES (?, ?, ?)",
            (project_id, name, now),
        )
        conn.commit()
        logger.debug(f"Created project '{name}' with id {project_id}")
        return Project(id=project_id, name=name, created_at=now)
    except sqlite3.IntegrityError:
        row = conn.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
        logger.debug(f"Project '{name}' already exists, returning existing")
        return Project(id=row["id"], name=row["name"], created_at=row["created_at"])


def list_projects(conn: sqlite3.Connection) -> list[Project]:
    """List all projects ordered by creation time.

    Args:
        conn: Active database connection.

    Returns:
        List of Project objects.
    """
    rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    return [Project(id=row["id"], name=row["name"], created_at=row["created_at"]) for row in rows]
