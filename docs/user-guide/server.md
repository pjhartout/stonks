# Dashboard Server

The stonks dashboard is a web UI for browsing experiments, viewing metric charts, and comparing runs.

## Installation

```bash
uv sync --extra server
```

## Starting the Server

```bash
stonks serve
```

This serves the dashboard at [http://127.0.0.1:8000](http://127.0.0.1:8000).

### CLI Options

`--db PATH`
: Path to the SQLite database file. Defaults to `./stonks.db` or `STONKS_DB` env var.

`--host HOST`
: Host to bind to. Default: `127.0.0.1`.

`--port PORT`
: Port to bind to. Default: `8000`.

```bash
# Serve a specific database on all interfaces
stonks serve --db /data/experiments.db --host 0.0.0.0 --port 9000
```

## Dashboard Features

### Experiment List

The left sidebar shows all experiments with their run counts. Click an experiment to view its runs.

### Run Table

Shows all runs for the selected experiment with:
- Run name and ID
- Status (running, completed, failed, interrupted)
- Creation time
- Duration

Click a run to view its metrics.

### Metric Charts

Interactive charts rendered with [uPlot](https://github.com/leeoniya/uPlot). Charts are grouped by metric key prefix (e.g., `train/loss` and `train/accuracy` appear in a "train" group).

### Config Comparison

When a run is selected, the config comparison table shows the hyperparameters stored with that run.

### Live Updates

While training scripts are actively logging, the dashboard receives real-time updates via Server-Sent Events (SSE):
- Run status changes (running → completed) appear instantly
- New metric data triggers chart refreshes

No manual page refresh needed.

## Running in Production

For production deployments, see {doc}`/self-hosting`.
