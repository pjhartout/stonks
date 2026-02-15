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
# Environment variables (all optional):
#   STONKS_DB     Path to SQLite database (default: ./stonks.db)
#   STONKS_HOST   Bind address            (default: 127.0.0.1)
#   STONKS_PORT   Bind port               (default: 8000)
#   STONKS_VENV   Path to virtualenv      (default: .venv)

STONKS_DB="${STONKS_DB:-./stonks.db}"
STONKS_HOST="${STONKS_HOST:-127.0.0.1}"
STONKS_PORT="${STONKS_PORT:-8000}"
STONKS_VENV="${STONKS_VENV:-.venv}"

# Parse CLI flags (override env vars)
while [[ $# -gt 0 ]]; do
  case "$1" in
    --db)   STONKS_DB="$2";   shift 2 ;;
    --host) STONKS_HOST="$2"; shift 2 ;;
    --port) STONKS_PORT="$2"; shift 2 ;;
    --venv) STONKS_VENV="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: ./run.sh [--db PATH] [--host ADDR] [--port NUM] [--venv DIR]"
      echo ""
      echo "Options:"
      echo "  --db PATH    SQLite database path   (default: ./stonks.db, or \$STONKS_DB)"
      echo "  --host ADDR  Bind address            (default: 127.0.0.1, or \$STONKS_HOST)"
      echo "  --port NUM   Bind port               (default: 8000, or \$STONKS_PORT)"
      echo "  --venv DIR   Virtualenv directory     (default: .venv, or \$STONKS_VENV)"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

log() { echo "==> $*"; }

# --- Check Python ---
if command -v python3 &>/dev/null; then
  PYTHON=python3
elif command -v python &>/dev/null; then
  PYTHON=python
else
  echo "Error: Python 3.11+ is required but not found."
  exit 1
fi

PY_VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$($PYTHON -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$($PYTHON -c 'import sys; print(sys.version_info.minor)')

if [[ "$PY_MAJOR" -lt 3 ]] || [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 11 ]]; then
  echo "Error: Python 3.11+ required, found $PY_VERSION"
  exit 1
fi

# --- Set up virtualenv and install ---
if [[ ! -d "$STONKS_VENV" ]]; then
  log "Creating virtualenv at $STONKS_VENV (Python $PY_VERSION)"

  if command -v uv &>/dev/null; then
    uv venv "$STONKS_VENV"
  else
    $PYTHON -m venv "$STONKS_VENV"
  fi
fi

# Activate
source "$STONKS_VENV/bin/activate"

# Install stonks if not already present
if ! python -c "import stonks" &>/dev/null; then
  log "Installing stonks[server]..."

  if command -v uv &>/dev/null; then
    uv pip install "stonks[server]"
  else
    pip install --quiet "stonks[server]"
  fi
fi

# --- Run ---
export STONKS_DB
log "Database: $STONKS_DB"
log "Listening on http://$STONKS_HOST:$STONKS_PORT"

exec python -m uvicorn stonks.server.app:create_app \
  --factory \
  --host "$STONKS_HOST" \
  --port "$STONKS_PORT"
