# Contributing

## Development Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [bun](https://bun.sh/) (for frontend development)

### Clone and Install

```bash
git clone https://github.com/pjhartout/stonks.git
cd stonks

# Install all Python dependencies (including optional extras)
uv sync --all-extras

# Install frontend dependencies
cd ui && bun install && cd ..

# Install pre-commit hooks
uv run pre-commit install
```

### Running Tests

```bash
# Python tests
uv run pytest

# Frontend type checking
cd ui && bun run check
```

The Python test suite includes unit tests (`tests/unit/`) and integration tests (`tests/integration/`). Tests should run in under 20 seconds.

### Linting and Formatting

```bash
# Format Python code
uv run ruff format .

# Lint Python code
uv run ruff check --fix .

# Type checking
uv run ty check stonks/
```

Pre-commit hooks run `ruff format`, `ruff check`, and `ty check` automatically on each commit.

### Frontend Development

The frontend is a Svelte 5 + TypeScript app built with Vite:

```bash
cd ui

# Start dev server (proxies /api to localhost:8000)
bun run dev

# Type check
bun run check

# Build for production (outputs to stonks/server/static/)
bun run build
```

During development, run the backend and frontend separately:

```bash
# Terminal 1: backend
stonks serve

# Terminal 2: frontend dev server
cd ui && bun run dev
# Open http://localhost:5173 (Vite dev server with API proxy)
```

### Building Documentation

```bash
# Install doc dependencies
uv sync --group docs

# Build HTML docs
uv run sphinx-build -b html docs docs/_build/html

# Preview locally
python -m http.server -d docs/_build/html 8080
```

## Project Structure

```
stonks/             # Python package
  __init__.py       # Public API: start_run(), open(), Database
  run.py            # Run context manager
  store.py          # SQLite data access layer
  buffer.py         # Thread-safe metric buffer
  models.py         # Data classes
  config.py         # DB path resolution
  lightning.py      # PyTorch Lightning logger
  cli.py            # CLI entry point
  server/           # FastAPI dashboard server
    app.py          # App factory
    routes/         # API endpoints
ui/                 # Svelte 5 frontend
tests/              # Python test suite
  unit/             # Unit tests
  integration/      # Integration tests
docs/               # Sphinx documentation
```

## Code Style

- Python formatting: [ruff](https://docs.astral.sh/ruff/)
- Line length: 100
- Docstrings: Google style
- All imports at the top of the file (no inline imports except in `cli.py` and tests)
- Use f-strings for log messages
