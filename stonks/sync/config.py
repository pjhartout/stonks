"""Configuration for remote stonks databases."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from stonks.exceptions import StonksError

DEFAULT_CONFIG_PATH = Path.home() / ".stonks" / "remotes.toml"
DEFAULT_SYNC_DIR = Path.home() / ".stonks" / "sync"


class SyncConfigError(StonksError):
    """Error parsing or validating sync configuration."""


@dataclass(frozen=True)
class RemoteConfig:
    """Configuration for a single remote stonks database.

    Attributes:
        name: Alias for this remote (from TOML section key).
        host: SSH host string (e.g. "user@hostname" or "hostname").
        db_path: Absolute path to stonks.db on the remote machine.
        ssh_key: Optional path to SSH private key.
        port: SSH port (default 22).
    """

    name: str
    host: str
    db_path: str
    ssh_key: str | None = None
    port: int = 22

    @property
    def staging_path(self) -> Path:
        """Local staging path for this remote's synced database."""
        return DEFAULT_SYNC_DIR / self.name / "stonks.db"

    @property
    def rsync_source(self) -> str:
        """Full rsync source string (host:path)."""
        return f"{self.host}:{self.db_path}"


def parse_remotes_config(config_path: Path | None = None) -> list[RemoteConfig]:
    """Parse the remotes configuration file.

    Args:
        config_path: Path to remotes.toml. Defaults to ~/.stonks/remotes.toml.

    Returns:
        List of RemoteConfig objects.

    Raises:
        SyncConfigError: If the config file is missing, malformed, or has invalid entries.
    """
    path = config_path or DEFAULT_CONFIG_PATH

    if not path.exists():
        raise SyncConfigError(f"Config file not found: {path}")

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise SyncConfigError(f"Invalid TOML in {path}: {e}") from e

    remotes_section = data.get("remotes")
    if remotes_section is None:
        raise SyncConfigError(f"No [remotes] section found in {path}")

    if not isinstance(remotes_section, dict):
        raise SyncConfigError(f"[remotes] must be a table in {path}")

    remotes: list[RemoteConfig] = []
    for name, entry in remotes_section.items():
        if not isinstance(entry, dict):
            raise SyncConfigError(f"Remote '{name}' must be a table")

        host = entry.get("host")
        if not host or not isinstance(host, str):
            raise SyncConfigError(f"Remote '{name}' is missing required 'host' field")

        db_path = entry.get("db_path")
        if not db_path or not isinstance(db_path, str):
            raise SyncConfigError(f"Remote '{name}' is missing required 'db_path' field")

        ssh_key = entry.get("ssh_key")
        if ssh_key is not None:
            ssh_key = str(Path(ssh_key).expanduser())

        port = entry.get("port", 22)
        if not isinstance(port, int):
            raise SyncConfigError(f"Remote '{name}' has invalid 'port': must be an integer")

        remotes.append(
            RemoteConfig(
                name=name,
                host=host,
                db_path=db_path,
                ssh_key=ssh_key,
                port=port,
            )
        )

    logger.debug(f"Loaded {len(remotes)} remote(s) from {path}")
    return remotes
