#!/usr/bin/env bash
set -euo pipefail

# stonks launcher — installs dependencies and starts the dashboard.
#
# Usage:
#   ./run.sh                          # defaults: ./stonks.db, 127.0.0.1:8000
#   ./run.sh --db /data/exp.db        # custom DB path
#   ./run.sh --host 0.0.0.0 --port 9000
#   STONKS_DB=/data/exp.db ./run.sh   # env var also works
#
# Requires: uv (https://docs.astral.sh/uv/)
#
# Environment variables (all optional):
#   STONKS_DB     Path to SQLite database (default: ./stonks.db)
#   STONKS_HOST   Bind address            (default: 127.0.0.1)
#   STONKS_PORT   Bind port               (default: 8000)

STONKS_DB="${STONKS_DB:-./stonks.db}"
STONKS_HOST="${STONKS_HOST:-127.0.0.1}"
STONKS_PORT="${STONKS_PORT:-8000}"

# Parse CLI flags (override env vars)
while [[ $# -gt 0 ]]; do
  case "$1" in
    --db)   STONKS_DB="$2";   shift 2 ;;
    --host) STONKS_HOST="$2"; shift 2 ;;
    --port) STONKS_PORT="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: ./run.sh [--db PATH] [--host ADDR] [--port NUM]"
      echo ""
      echo "Options:"
      echo "  --db PATH    SQLite database path   (default: ./stonks.db, or \$STONKS_DB)"
      echo "  --host ADDR  Bind address            (default: 127.0.0.1, or \$STONKS_HOST)"
      echo "  --port NUM   Bind port               (default: 8000, or \$STONKS_PORT)"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

log() { echo "==> $*"; }

# --- Check uv ---
if ! command -v uv &>/dev/null; then
  echo "Error: uv is required but not found. Install it from https://docs.astral.sh/uv/"
  exit 1
fi

# --- Sync dependencies ---
log "Syncing dependencies..."
uv sync --extra server

# --- Run ---
export STONKS_DB
log "Database: $STONKS_DB"
log "Listening on http://$STONKS_HOST:$STONKS_PORT"

exec uv run uvicorn stonks.server.app:create_app \
  --factory \
  --host "$STONKS_HOST" \
  --port "$STONKS_PORT"
