"""Data models for stonks experiment tracking."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Project:
    """A project groups related experiments."""

    id: str
    name: str
    created_at: float


@dataclass
class Experiment:
    """An experiment groups related training runs."""

    id: str
    name: str
    created_at: float
    description: str | None = None
    metadata: dict | None = None
    project_id: str | None = None


@dataclass
class RunInfo:
    """Metadata about a training run."""

    id: str
    experiment_id: str
    status: str
    created_at: float
    name: str | None = None
    config: dict | None = None
    ended_at: float | None = None
    last_heartbeat: float | None = None
    group: str | None = None
    job_type: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
    prefix: str = ""


@dataclass
class MetricPoint:
    """A single metric data point."""

    key: str
    value: float | None
    step: int
    timestamp: float


@dataclass
class MetricSeries:
    """A series of metric data points for a single key."""

    key: str
    steps: list[int] = field(default_factory=list)
    values: list[float | None] = field(default_factory=list)
    timestamps: list[float] = field(default_factory=list)


def config_to_json(config: dict | None) -> str | None:
    """Serialize config dict to JSON string.

    Args:
        config: Dictionary of configuration values.

    Returns:
        JSON string or None.
    """
    if config is None:
        return None
    return json.dumps(config)


def config_from_json(json_str: str | None) -> dict | None:
    """Deserialize JSON string to config dict.

    Args:
        json_str: JSON string or None.

    Returns:
        Dictionary or None.
    """
    if json_str is None:
        return None
    return json.loads(json_str)


def tags_to_json(tags: list[str] | None) -> str | None:
    """Serialize tags list to JSON string.

    Args:
        tags: List of tag strings.

    Returns:
        JSON string or None.
    """
    if tags is None:
        return None
    return json.dumps(tags)


def tags_from_json(json_str: str | None) -> list[str] | None:
    """Deserialize JSON string to tags list.

    Args:
        json_str: JSON string or None.

    Returns:
        List of strings or None.
    """
    if json_str is None:
        return None
    return json.loads(json_str)
