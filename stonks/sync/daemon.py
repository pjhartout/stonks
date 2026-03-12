"""Sync daemon for pulling and merging remote stonks databases."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

from loguru import logger

from stonks.exceptions import StonksError
from stonks.store.connection import create_connection, initialize_db
from stonks.sync.config import RemoteConfig, parse_remotes_config
from stonks.sync.merge import MergeError, MergeStats, check_integrity, merge_remote_db

DEFAULT_INTERVAL = 10
LOCK_FILE = Path.home() / ".stonks" / "sync.lock"


class SyncError(StonksError):
    """Error during sync operation."""


def _build_rsync_command(remote: RemoteConfig) -> list[str]:
    """Build the rsync command for a remote.

    Args:
        remote: Remote configuration.

    Returns:
        List of command-line arguments for subprocess.
    """
    ssh_opts = (
        f"ssh -o StrictHostKeyChecking=accept-new "
        f"-o ConnectTimeout=10 -o BatchMode=yes "
        f"-p {remote.port}"
    )
    if remote.ssh_key:
        ssh_opts += f" -i {remote.ssh_key}"

    return [
        "rsync",
        "-az",
        "--whole-file",
        "-e",
        ssh_opts,
        remote.rsync_source,
        str(remote.staging_path),
    ]


def pull_remote(remote: RemoteConfig) -> bool:
    """Pull a remote database via rsync.

    Creates the staging directory if needed and runs rsync.

    Args:
        remote: Remote configuration.

    Returns:
        True if the pull succeeded, False otherwise.
    """
    remote.staging_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = _build_rsync_command(remote)
    logger.debug(f"Running rsync for '{remote.name}': {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning(
                f"rsync failed for '{remote.name}' (exit {result.returncode}): "
                f"{result.stderr.strip()}"
            )
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.warning(f"rsync timed out for '{remote.name}'")
        return False
    except FileNotFoundError:
        logger.error("rsync not found. Install rsync to use sync feature.")
        return False


def sync_remote(
    remote: RemoteConfig,
    target_db_path: Path,
) -> MergeStats | None:
    """Pull and merge a single remote.

    Args:
        remote: Remote configuration.
        target_db_path: Path to the local target database.

    Returns:
        MergeStats if successful, None if the pull or merge failed.
    """
    if not pull_remote(remote):
        return None

    if not remote.staging_path.exists():
        logger.warning(f"No database found after pull for '{remote.name}'")
        return None

    if not check_integrity(remote.staging_path):
        logger.warning(f"Integrity check failed for '{remote.name}', skipping merge")
        return None

    target_conn = create_connection(target_db_path)
    initialize_db(target_conn)
    try:
        return merge_remote_db(
            source_path=remote.staging_path,
            target_conn=target_conn,
            remote_name=remote.name,
        )
    except MergeError as e:
        logger.error(f"Merge failed for '{remote.name}': {e}")
        return None
    finally:
        target_conn.close()


def sync_all(
    remotes: list[RemoteConfig],
    target_db_path: Path,
) -> list[MergeStats]:
    """Sync all remotes in sequence.

    Args:
        remotes: List of remote configurations.
        target_db_path: Path to the local target database.

    Returns:
        List of MergeStats for successful syncs.
    """
    results: list[MergeStats] = []
    for remote in remotes:
        stats = sync_remote(remote, target_db_path)
        if stats is not None:
            results.append(stats)
    return results


def _acquire_lock() -> bool:
    """Acquire the sync lock file.

    Uses a PID-based lock. If the lock file exists but the PID is dead,
    the lock is reclaimed.

    Returns:
        True if the lock was acquired, False if another sync is running.
    """
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            # Check if the process is still alive
            os.kill(pid, 0)
            logger.error(f"Another sync process is running (PID {pid})")
            return False
        except (ValueError, ProcessLookupError, PermissionError):
            # PID is invalid or process is dead, reclaim lock
            logger.debug("Reclaiming stale lock file")

    LOCK_FILE.write_text(str(os.getpid()))
    return True


def _release_lock() -> None:
    """Release the sync lock file."""
    try:
        if LOCK_FILE.exists():
            pid = int(LOCK_FILE.read_text().strip())
            if pid == os.getpid():
                LOCK_FILE.unlink()
    except (ValueError, OSError):
        pass


def run_sync_daemon(
    target_db_path: Path,
    config_path: Path | None = None,
    interval: int = DEFAULT_INTERVAL,
) -> None:
    """Run the sync daemon loop.

    Pulls and merges all configured remotes every `interval` seconds.
    Re-reads the config file each cycle. Handles SIGINT/SIGTERM gracefully.

    Args:
        target_db_path: Path to the local target database.
        config_path: Path to remotes.toml. Defaults to ~/.stonks/remotes.toml.
        interval: Seconds between sync cycles.
    """
    if not _acquire_lock():
        raise SyncError("Could not acquire sync lock. Is another sync process running?")

    stop_requested = False

    def _handle_signal(signum: int, frame: object) -> None:
        nonlocal stop_requested
        logger.info(f"Received signal {signum}, stopping after current cycle...")
        stop_requested = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    last_valid_remotes: list[RemoteConfig] | None = None

    logger.info(f"Sync daemon started (interval={interval}s, target={target_db_path})")

    try:
        while not stop_requested:
            # Re-read config each cycle
            try:
                remotes = parse_remotes_config(config_path)
                last_valid_remotes = remotes
            except Exception as e:
                if last_valid_remotes is not None:
                    logger.warning(f"Config error, using last valid config: {e}")
                    remotes = last_valid_remotes
                else:
                    logger.error(f"Config error and no previous valid config: {e}")
                    time.sleep(interval)
                    continue

            if not remotes:
                logger.debug("No remotes configured, sleeping")
                time.sleep(interval)
                continue

            results = sync_all(remotes, target_db_path)
            if results:
                total_new = sum(s.new_runs for s in results)
                total_updated = sum(s.updated_runs for s in results)
                total_metrics = sum(s.metrics_inserted for s in results)
                if total_new > 0 or total_updated > 0:
                    logger.info(
                        f"Sync cycle: {total_new} new runs, "
                        f"{total_updated} updated, {total_metrics} metrics"
                    )

            # Sleep in small increments to respond to signals faster
            elapsed = 0.0
            while elapsed < interval and not stop_requested:
                time.sleep(min(1.0, interval - elapsed))
                elapsed += 1.0
    finally:
        _release_lock()
        logger.info("Sync daemon stopped")
