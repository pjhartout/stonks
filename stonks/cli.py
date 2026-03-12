"""CLI entry point for stonks."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from stonks.config import resolve_db_path
from stonks.logging_config import setup_logging
from stonks.store import (
    count_metrics,
    create_connection,
    delete_experiment,
    delete_run,
    finish_run,
    get_metric_keys,
    get_metrics,
    get_run_by_id,
    initialize_db,
    list_experiments_with_run_counts,
    list_runs,
)


def _get_conn(args: argparse.Namespace):
    """Create a database connection from CLI args.

    Args:
        args: Parsed CLI arguments with db attribute.

    Returns:
        Initialized database connection.
    """
    db_path = str(resolve_db_path(args.db))
    conn = create_connection(db_path)
    initialize_db(conn)
    return conn


def serve_command(args: argparse.Namespace) -> None:
    """Run the stonks dashboard server.

    Args:
        args: Parsed CLI arguments with db, host, port.
    """
    try:
        import uvicorn

        from stonks.server.app import create_app
    except ImportError as e:
        print(f"Server dependencies not installed: {e}")
        print("Install with: uv add uvicorn fastapi")
        sys.exit(1)

    db_path = str(resolve_db_path(args.db))
    logger.info(f"Starting stonks server on {args.host}:{args.port}")

    if args.reload:
        # uvicorn reload requires factory string, not app instance
        uvicorn.run(
            "stonks.server.app:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=True,
            reload_dirs=["stonks"],
        )
    else:
        app = create_app(db_path)
        uvicorn.run(app, host=args.host, port=args.port)


def ls_command(args: argparse.Namespace) -> None:
    """List all experiments.

    Args:
        args: Parsed CLI arguments.
    """
    conn = _get_conn(args)
    experiments = list_experiments_with_run_counts(conn)
    conn.close()

    if args.json:
        print(json.dumps(experiments, indent=2))
        return

    if not experiments:
        print("No experiments found.")
        return

    # Table output.
    header = f"{'NAME':<30} {'RUNS':>6} {'CREATED':>26} {'ID':<36}"
    print(header)
    print("-" * len(header))
    for exp in experiments:
        created = datetime.fromtimestamp(exp["created_at"], tz=UTC)
        created_str = created.strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"{exp['name']:<30} {exp['run_count']:>6} {created_str:>26} {exp['id']:<36}")


def runs_command(args: argparse.Namespace) -> None:
    """List runs for an experiment.

    Args:
        args: Parsed CLI arguments.
    """
    conn = _get_conn(args)

    # Find experiment by name or ID.
    experiments = list_experiments_with_run_counts(conn)
    exp_match = None
    for exp in experiments:
        if exp["name"] == args.experiment or exp["id"] == args.experiment:
            exp_match = exp
            break

    if exp_match is None:
        print(f"Experiment '{args.experiment}' not found.")
        conn.close()
        sys.exit(1)

    runs = list_runs(conn, experiment_id=exp_match["id"])
    conn.close()

    # Apply filters.
    if args.status:
        statuses = {s.strip() for s in args.status.split(",")}
        runs = [r for r in runs if r.status in statuses]

    if args.tag:
        runs = [r for r in runs if r.tags and args.tag in r.tags]

    if args.json:
        run_dicts = [
            {
                "id": r.id,
                "name": r.name,
                "status": r.status,
                "group": r.group,
                "job_type": r.job_type,
                "tags": r.tags,
                "created_at": r.created_at,
            }
            for r in runs
        ]
        print(json.dumps(run_dicts, indent=2))
        return

    if not runs:
        print("No runs found.")
        return

    header = f"{'NAME':<20} {'STATUS':<12} {'GROUP':<15} {'TAGS':<20} {'ID':<36}"
    print(header)
    print("-" * len(header))
    for r in runs:
        name = r.name or ""
        group = r.group or ""
        tags_str = ",".join(r.tags) if r.tags else ""
        print(f"{name:<20} {r.status:<12} {group:<15} {tags_str:<20} {r.id:<36}")


def info_command(args: argparse.Namespace) -> None:
    """Show database statistics.

    Args:
        args: Parsed CLI arguments.
    """
    db_path = resolve_db_path(args.db)
    conn = _get_conn(args)

    experiments = list_experiments_with_run_counts(conn)
    total_runs = sum(e["run_count"] for e in experiments)
    total_metrics = count_metrics(conn)
    conn.close()

    db_size_mb = os.path.getsize(db_path) / (1024 * 1024) if db_path.exists() else 0

    if args.json:
        print(
            json.dumps(
                {
                    "db_path": str(db_path),
                    "db_size_mb": round(db_size_mb, 2),
                    "experiments": len(experiments),
                    "runs": total_runs,
                    "metrics": total_metrics,
                },
                indent=2,
            )
        )
        return

    print(f"Database:    {db_path}")
    print(f"Size:        {db_size_mb:.2f} MB")
    print(f"Experiments: {len(experiments)}")
    print(f"Runs:        {total_runs}")
    print(f"Metrics:     {total_metrics}")


def delete_command(args: argparse.Namespace) -> None:
    """Delete a run or experiment.

    Args:
        args: Parsed CLI arguments.
    """
    conn = _get_conn(args)

    # Try as run ID first.
    run = get_run_by_id(conn, args.id)
    if run is not None:
        if not args.force:
            answer = input(f"Delete run '{args.id}'? [y/N] ")
            if answer.lower() != "y":
                print("Aborted.")
                conn.close()
                return
        delete_run(conn, args.id)
        print(f"Deleted run {args.id}")
        conn.close()
        return

    # Try as experiment name or ID.
    experiments = list_experiments_with_run_counts(conn)
    exp_match = None
    for exp in experiments:
        if exp["name"] == args.id or exp["id"] == args.id:
            exp_match = exp
            break

    if exp_match is not None:
        if not args.force:
            answer = input(
                f"Delete experiment '{exp_match['name']}' "
                f"and {exp_match['run_count']} run(s)? [y/N] "
            )
            if answer.lower() != "y":
                print("Aborted.")
                conn.close()
                return
        delete_experiment(conn, exp_match["id"])
        print(f"Deleted experiment '{exp_match['name']}'")
        conn.close()
        return

    print(f"No run or experiment found with identifier '{args.id}'.")
    conn.close()
    sys.exit(1)


def export_command(args: argparse.Namespace) -> None:
    """Export metrics for a run.

    Args:
        args: Parsed CLI arguments.
    """
    conn = _get_conn(args)

    run = get_run_by_id(conn, args.run_id)
    if run is None:
        print(f"Run '{args.run_id}' not found.")
        conn.close()
        sys.exit(1)

    keys = get_metric_keys(conn, args.run_id)
    if not keys:
        print("No metrics found for this run.")
        conn.close()
        return

    # Build a merged table: step, key1, key2, ...
    all_series = {}
    all_steps = set()
    for key in keys:
        series = get_metrics(conn, args.run_id, key)
        all_series[key] = dict(zip(series.steps, series.values))
        all_steps.update(series.steps)
    conn.close()

    sorted_steps = sorted(all_steps)

    if args.format == "json":
        rows = []
        for step in sorted_steps:
            row = {"step": step}
            for key in keys:
                row[key] = all_series[key].get(step)
            rows.append(row)
        print(json.dumps(rows, indent=2))
    else:
        writer = csv.writer(sys.stdout)
        writer.writerow(["step", *keys])
        for step in sorted_steps:
            row = [step] + [all_series[key].get(step, "") for key in keys]
            writer.writerow(row)


def gc_command(args: argparse.Namespace) -> None:
    """Garbage collect runs by status or age.

    Args:
        args: Parsed CLI arguments.
    """
    conn = _get_conn(args)
    runs = list_runs(conn)

    statuses = {s.strip() for s in args.status.split(",")}
    candidates = [r for r in runs if r.status in statuses]

    if args.before:
        cutoff = time.time() - (args.before * 86400)
        candidates = [r for r in candidates if r.created_at < cutoff]

    if not candidates:
        print("No runs to clean up.")
        conn.close()
        return

    if not args.force:
        print(f"Will delete {len(candidates)} run(s):")
        for r in candidates[:10]:
            name = r.name or "(unnamed)"
            print(f"  {r.id}  {name}  [{r.status}]")
        if len(candidates) > 10:
            print(f"  ... and {len(candidates) - 10} more")
        answer = input("Proceed? [y/N] ")
        if answer.lower() != "y":
            print("Aborted.")
            conn.close()
            return

    deleted = 0
    for r in candidates:
        # Mark as finished first if still running.
        if r.status == "running":
            finish_run(conn, r.id, "interrupted")
        delete_run(conn, r.id)
        deleted += 1

    print(f"Deleted {deleted} run(s).")
    conn.close()


def remote_command(args: argparse.Namespace) -> None:
    """Manage remote stonks databases.

    Args:
        args: Parsed CLI arguments with remote_action.
    """
    from stonks.sync.config import SyncConfigError, parse_remotes_config

    config_path = Path(args.config) if args.config else None

    try:
        remotes = parse_remotes_config(config_path)
    except SyncConfigError as e:
        print(f"Config error: {e}")
        sys.exit(1)

    if not remotes:
        print("No remotes configured.")
        return

    if args.remote_action == "list":
        header = f"{'NAME':<20} {'HOST':<35} {'PATH':<40} {'MODE':<10}"
        print(header)
        print("-" * len(header))
        for r in remotes:
            path = r.scan_dir or r.db_path or ""
            mode = "scan" if r.is_scan_mode else "file"
            print(f"{r.name:<20} {r.host:<35} {path:<40} {mode:<10}")

    elif args.remote_action == "check":
        import subprocess

        for r in remotes:
            ssh_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5"]
            if r.ssh_key:
                ssh_cmd.extend(["-i", r.ssh_key])
            ssh_cmd.extend(["-p", str(r.port), r.host, "test", "-f", r.db_path])

            try:
                result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    print(f"  {r.name}: OK")
                else:
                    print(f"  {r.name}: FAILED (SSH ok, file not found)")
            except subprocess.TimeoutExpired:
                print(f"  {r.name}: FAILED (timeout)")
            except FileNotFoundError:
                print(f"  {r.name}: FAILED (ssh not found)")


def sync_command(args: argparse.Namespace) -> None:
    """Sync remote databases to local.

    Args:
        args: Parsed CLI arguments with watch, interval, config.
    """
    from stonks.sync.config import SyncConfigError, parse_remotes_config
    from stonks.sync.daemon import SyncError, run_sync_daemon, sync_all

    target_db_path = resolve_db_path(args.db)
    config_path = Path(args.config) if args.config else None

    if args.watch:
        try:
            run_sync_daemon(
                target_db_path=target_db_path,
                config_path=config_path,
                interval=args.interval,
            )
        except SyncError as e:
            print(f"Sync error: {e}")
            sys.exit(1)
    else:
        # One-shot sync
        try:
            remotes = parse_remotes_config(config_path)
        except SyncConfigError as e:
            print(f"Config error: {e}")
            sys.exit(1)

        if not remotes:
            print("No remotes configured.")
            return

        print(f"Syncing {len(remotes)} remote(s) to {target_db_path}...")
        results = sync_all(remotes, target_db_path)

        if not results:
            print("No remotes synced successfully.")
            sys.exit(1)

        for s in results:
            print(
                f"  {s.remote_name}: {s.new_runs} new, "
                f"{s.updated_runs} updated, {s.skipped_runs} skipped runs"
            )
        print("Done.")


def demo_command(args: argparse.Namespace) -> None:
    """Run the stonks demo with generated sample data.

    Args:
        args: Parsed CLI arguments with db, host, port, no_serve.
    """
    import webbrowser

    from stonks.demo import generate_demo_data, get_default_demo_db

    db_path = args.db or get_default_demo_db()
    generate_demo_data(db_path)

    if args.no_serve:
        print(f"Demo data written to: {db_path}")
        return

    try:
        import uvicorn

        from stonks.server.app import create_app
    except ImportError as e:
        print(f"Server dependencies not installed: {e}")
        print("Install with: uv add uvicorn fastapi")
        sys.exit(1)

    url = f"http://{args.host}:{args.port}"
    print(f"\nDemo database: {db_path}")
    print(f"Dashboard:     {url}")
    print("Press Ctrl+C to stop.\n")

    webbrowser.open(url)

    app = create_app(db_path)
    uvicorn.run(app, host=args.host, port=args.port)


def main() -> None:
    """Main CLI entry point."""
    setup_logging()

    parser = argparse.ArgumentParser(
        prog="stonks",
        description="Lightweight ML experiment tracking",
    )
    subparsers = parser.add_subparsers(dest="command")

    # serve
    serve_parser = subparsers.add_parser("serve", help="Start the dashboard server")
    serve_parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to the SQLite database (default: ./stonks.db or STONKS_DB)",
    )
    serve_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    serve_parser.add_argument(
        "--reload",
        action="store_true",
        default=False,
        help="Enable auto-reload for development",
    )

    # ls
    ls_parser = subparsers.add_parser("ls", help="List experiments")
    ls_parser.add_argument("--db", type=str, default=None, help="Database path")
    ls_parser.add_argument("--json", action="store_true", default=False, help="Output as JSON")

    # runs
    runs_parser = subparsers.add_parser("runs", help="List runs for an experiment")
    runs_parser.add_argument("experiment", help="Experiment name or ID")
    runs_parser.add_argument("--db", type=str, default=None, help="Database path")
    runs_parser.add_argument(
        "--status",
        type=str,
        default=None,
        help="Filter by status (comma-separated, e.g. completed,failed)",
    )
    runs_parser.add_argument("--tag", type=str, default=None, help="Filter by tag")
    runs_parser.add_argument("--json", action="store_true", default=False, help="Output as JSON")

    # info
    info_parser = subparsers.add_parser("info", help="Show database statistics")
    info_parser.add_argument("--db", type=str, default=None, help="Database path")
    info_parser.add_argument("--json", action="store_true", default=False, help="Output as JSON")

    # delete
    delete_parser = subparsers.add_parser("delete", help="Delete a run or experiment")
    delete_parser.add_argument("id", help="Run ID or experiment name/ID to delete")
    delete_parser.add_argument("--db", type=str, default=None, help="Database path")
    delete_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        default=False,
        help="Skip confirmation prompt",
    )

    # export
    export_parser = subparsers.add_parser("export", help="Export metrics for a run")
    export_parser.add_argument("run_id", help="Run ID to export")
    export_parser.add_argument("--db", type=str, default=None, help="Database path")
    export_parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
        help="Output format (default: csv)",
    )

    # gc
    gc_parser = subparsers.add_parser("gc", help="Garbage collect old or failed runs")
    gc_parser.add_argument("--db", type=str, default=None, help="Database path")
    gc_parser.add_argument(
        "--before",
        type=float,
        default=None,
        help="Only delete runs older than N days",
    )
    gc_parser.add_argument(
        "--status",
        type=str,
        default="failed,interrupted",
        help="Comma-separated statuses to clean (default: failed,interrupted)",
    )
    gc_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        default=False,
        help="Skip confirmation prompt",
    )

    # demo
    demo_parser = subparsers.add_parser("demo", help="Generate sample data and start dashboard")
    demo_parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Database path for demo data (default: temp directory)",
    )
    demo_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    demo_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    demo_parser.add_argument(
        "--no-serve",
        action="store_true",
        default=False,
        help="Only generate data, don't start the server",
    )

    # sync
    sync_parser = subparsers.add_parser("sync", help="Sync remote databases to local")
    sync_parser.add_argument("--db", type=str, default=None, help="Target database path")
    sync_parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to remotes.toml (default: ~/.stonks/remotes.toml)",
    )
    sync_parser.add_argument(
        "--watch",
        action="store_true",
        default=False,
        help="Run as daemon, syncing every --interval seconds",
    )
    sync_parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Seconds between sync cycles in watch mode (default: 10)",
    )

    # remote
    remote_parser = subparsers.add_parser("remote", help="Manage remote databases")
    remote_parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to remotes.toml (default: ~/.stonks/remotes.toml)",
    )
    remote_subparsers = remote_parser.add_subparsers(dest="remote_action")
    remote_subparsers.add_parser("list", help="List configured remotes")
    remote_subparsers.add_parser("check", help="Check SSH connectivity to remotes")

    args = parser.parse_args()

    commands = {
        "serve": serve_command,
        "ls": ls_command,
        "runs": runs_command,
        "info": info_command,
        "delete": delete_command,
        "export": export_command,
        "gc": gc_command,
        "demo": demo_command,
        "sync": sync_command,
        "remote": remote_command,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
