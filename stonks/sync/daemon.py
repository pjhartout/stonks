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


def _build_ssh_command(remote: RemoteConfig) -> list[str]:
    """Build the base SSH command options for a remote.

    Args:
        remote: Remote configuration.

    Returns:
        List of SSH command-line arguments.
    """
    cmd = [
        "ssh",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "BatchMode=yes",
        "-p",
        str(remote.port),
    ]
    if remote.ssh_key:
        cmd.extend(["-i", remote.ssh_key])
    cmd.append(remote.host)
    return cmd


def _build_ssh_opts(remote: RemoteConfig) -> str:
    """Build the SSH options string for rsync -e flag.

    Args:
        remote: Remote configuration.

    Returns:
        SSH options string.
    """
    opts = (
        f"ssh -o StrictHostKeyChecking=accept-new "
        f"-o ConnectTimeout=10 -o BatchMode=yes "
        f"-p {remote.port}"
    )
    if remote.ssh_key:
        opts += f" -i {remote.ssh_key}"
    return opts


def _discover_remote_dbs(remote: RemoteConfig) -> list[str]:
    """Discover all stonks.db files under a remote scan_dir via SSH.

    Args:
        remote: Remote configuration with scan_dir set.

    Returns:
        List of absolute paths to stonks.db files on the remote.
    """
    assert remote.scan_dir is not None
    cmd: list[str] = _build_ssh_command(remote) + [
        "find",
        remote.scan_dir,
        "-name",
        "stonks.db",
        "-type",
        "f",
    ]
    logger.debug(f"Discovering DBs on '{remote.name}': {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.warning(
                f"DB discovery failed for '{remote.name}' (exit {result.returncode}): "
                f"{result.stderr.strip()}"
            )
            return []

        paths = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
        logger.debug(f"Found {len(paths)} database(s) on '{remote.name}'")
        return paths
    except subprocess.TimeoutExpired:
        logger.warning(f"DB discovery timed out for '{remote.name}'")
        return []
    except FileNotFoundError:
        logger.error("ssh not found.")
        return []


def _checkpoint_remote_wal(remote: RemoteConfig, remote_path: str) -> None:
    """Flush the WAL journal into the main database file on the remote.

    SQLite WAL mode writes to a separate -wal file. Without checkpointing,
    rsync only copies the main .db file and misses uncommitted WAL data.

    Uses PASSIVE mode so the checkpoint never blocks on active writers
    (e.g. a training script logging metrics). It flushes whatever WAL
    frames it can; the next sync cycle catches up with the rest.

    Args:
        remote: Remote configuration.
        remote_path: Absolute path to the database on the remote.
    """
    cmd = _build_ssh_command(remote)[:-1]  # Remove the trailing host arg
    # Pass the full sqlite3 command as a single string so the remote shell
    # doesn't interpret parentheses in the PRAGMA as subshell syntax.
    cmd.extend(
        [
            remote.host,
            f"sqlite3 '{remote_path}' 'PRAGMA wal_checkpoint(PASSIVE);'",
        ]
    )
    logger.debug(f"Checkpointing WAL on '{remote.name}': {remote_path}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.warning(
                f"WAL checkpoint failed for '{remote.name}' ({remote_path}): "
                f"{result.stderr.strip()}"
            )
    except subprocess.TimeoutExpired:
        logger.warning(f"WAL checkpoint timed out for '{remote.name}' ({remote_path})")
    except FileNotFoundError:
        logger.warning("ssh not found for WAL checkpoint")


def _format_bytes(n: float) -> str:
    """Format a byte count as a human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def _rsync_file(remote: RemoteConfig, remote_path: str, local_path: Path) -> bool:
    """Rsync a single file from a remote with progress logging.

    Checkpoints the WAL journal before transfer to ensure all written
    data is flushed into the main database file. Logs transfer progress
    every 10 seconds.

    Args:
        remote: Remote configuration.
        remote_path: Absolute path on the remote.
        local_path: Local destination path.

    Returns:
        True if successful.
    """
    local_path.parent.mkdir(parents=True, exist_ok=True)

    _checkpoint_remote_wal(remote, remote_path)

    cmd = [
        "rsync",
        "-az",
        "--info=progress2",
        "-e",
        _build_ssh_opts(remote),
        f"{remote.host}:{remote_path}",
        str(local_path),
    ]

    short_path = Path(remote_path).name
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        last_log_time = time.monotonic()
        last_progress = ""

        assert proc.stdout is not None
        # rsync --info=progress2 writes progress lines with \r to stdout
        buf = ""
        while True:
            chunk = proc.stdout.read(256)
            if not chunk:
                break
            buf += chunk
            # Extract the latest progress line (rsync uses \r for updates)
            lines = buf.replace("\r", "\n").split("\n")
            for line in lines:
                stripped = line.strip()
                if stripped and "%" in stripped:
                    last_progress = stripped
            buf = lines[-1]

            now = time.monotonic()
            if now - last_log_time >= 10 and last_progress:
                logger.info(f"rsync '{remote.name}' {short_path}: {last_progress}")
                last_log_time = now

        proc.wait()
        if proc.returncode != 0:
            stderr = proc.stderr.read() if proc.stderr else ""
            logger.warning(f"rsync failed for '{remote.name}' ({remote_path}): {stderr.strip()}")
            return False

        # Log final size
        if local_path.exists():
            size = _format_bytes(local_path.stat().st_size)
            logger.info(f"rsync '{remote.name}' {short_path}: done ({size})")
        return True
    except FileNotFoundError:
        logger.error("rsync not found. Install rsync to use sync feature.")
        return False


def pull_remote(remote: RemoteConfig) -> bool:
    """Pull a remote database via rsync (single-file mode).

    Args:
        remote: Remote configuration with db_path set.

    Returns:
        True if the pull succeeded.
    """
    assert remote.db_path is not None
    return _rsync_file(remote, remote.db_path, remote.staging_path)


def pull_remote_scan(remote: RemoteConfig) -> list[Path]:
    """Discover and pull all stonks.db files from a remote scan_dir.

    Args:
        remote: Remote configuration with scan_dir set.

    Returns:
        List of local paths to successfully pulled database files.
    """
    remote_paths = _discover_remote_dbs(remote)
    if not remote_paths:
        return []

    pulled: list[Path] = []
    for i, remote_path in enumerate(remote_paths):
        logger.info(f"Pulling '{remote.name}' [{i + 1}/{len(remote_paths)}]: {remote_path}")
        # Stage each DB in a unique subfolder to avoid collisions
        local_path = remote.staging_dir / f"db_{i}" / "stonks.db"
        if _rsync_file(remote, remote_path, local_path):
            pulled.append(local_path)

    logger.info(f"Pulled {len(pulled)}/{len(remote_paths)} databases from '{remote.name}'")
    return pulled


def _merge_single_db(
    source_path: Path,
    target_conn,
    remote_name: str,
    label: str,
) -> MergeStats | None:
    """Merge a single source DB into the target, with integrity check.

    Args:
        source_path: Path to the source database.
        target_conn: Target database connection.
        remote_name: Name of the remote for stats.
        label: Label for logging.

    Returns:
        MergeStats if successful, None otherwise.
    """
    if not check_integrity(source_path):
        logger.warning(f"Integrity check failed for '{label}', skipping")
        return None

    try:
        return merge_remote_db(
            source_path=source_path,
            target_conn=target_conn,
            remote_name=remote_name,
        )
    except MergeError as e:
        logger.error(f"Merge failed for '{label}': {e}")
        return None


def sync_remote(
    remote: RemoteConfig,
    target_db_path: Path,
) -> list[MergeStats]:
    """Pull and merge a single remote.

    Handles both single-file and scan_dir modes.

    Args:
        remote: Remote configuration.
        target_db_path: Path to the local target database.

    Returns:
        List of MergeStats for successful merges.
    """
    results: list[MergeStats] = []

    target_conn = create_connection(target_db_path)
    initialize_db(target_conn)

    try:
        if remote.is_scan_mode:
            pulled_paths = pull_remote_scan(remote)
            for i, path in enumerate(pulled_paths):
                label = f"{remote.name}[{i}]"
                size = _format_bytes(path.stat().st_size) if path.exists() else "?"
                logger.info(f"Merging '{label}' [{i + 1}/{len(pulled_paths)}] ({size})")
                stats = _merge_single_db(path, target_conn, remote.name, label)
                if stats is not None:
                    results.append(stats)
        else:
            if not pull_remote(remote):
                return results
            if not remote.staging_path.exists():
                logger.warning(f"No database found after pull for '{remote.name}'")
                return results
            stats = _merge_single_db(remote.staging_path, target_conn, remote.name, remote.name)
            if stats is not None:
                results.append(stats)
    finally:
        target_conn.close()

    return results


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
        results.extend(sync_remote(remote, target_db_path))
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

            cycle_start = time.monotonic()
            logger.info(f"Sync cycle starting ({len(remotes)} remote(s))")
            results = sync_all(remotes, target_db_path)
            elapsed_s = time.monotonic() - cycle_start
            total_new = sum(s.new_runs for s in results)
            total_updated = sum(s.updated_runs for s in results)
            total_skipped = sum(s.skipped_runs for s in results)
            total_metrics = sum(s.metrics_inserted for s in results)
            logger.info(
                f"Sync cycle done in {elapsed_s:.1f}s: "
                f"{total_new} new, {total_updated} updated, "
                f"{total_skipped} skipped runs, {total_metrics} metrics"
            )

            # Sleep in small increments to respond to signals faster
            elapsed = 0.0
            while elapsed < interval and not stop_requested:
                time.sleep(min(1.0, interval - elapsed))
                elapsed += 1.0
    finally:
        _release_lock()
        logger.info("Sync daemon stopped")
