"""CLI entry point for stonks."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import UTC, datetime

import uvicorn
from loguru import logger

from stonks.config import resolve_db_path
from stonks.logging_config import setup_logging
from stonks.server.app import create_app
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

    args = parser.parse_args()

    commands = {
        "serve": serve_command,
        "ls": ls_command,
        "runs": runs_command,
        "info": info_command,
        "delete": delete_command,
        "export": export_command,
        "gc": gc_command,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
