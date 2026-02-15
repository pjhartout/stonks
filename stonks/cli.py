"""CLI entry point for stonks."""

from __future__ import annotations

import argparse

from loguru import logger

from stonks.config import resolve_db_path
from stonks.logging_config import setup_logging


def serve_command(args: argparse.Namespace) -> None:
    """Run the stonks dashboard server.

    Args:
        args: Parsed CLI arguments with db, host, port.
    """
    import uvicorn

    from stonks.server.app import create_app

    db_path = str(resolve_db_path(args.db))
    app = create_app(db_path)
    logger.info(f"Starting stonks server on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


def main() -> None:
    """Main CLI entry point."""
    setup_logging()

    parser = argparse.ArgumentParser(
        prog="stonks",
        description="Lightweight ML experiment tracking",
    )
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Start the dashboard server")
    serve_parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to the SQLite database (default: ./stonks.db or STONKS_DB env var)",
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

    args = parser.parse_args()

    if args.command == "serve":
        serve_command(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
