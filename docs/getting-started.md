# Getting Started

## Installation

Install stonks with pip (or uv):

```bash
# Core SDK only (logging metrics)
pip install stonks

# With PyTorch Lightning integration
pip install stonks[lightning]

# With dashboard server
pip install stonks[server]

# Everything
pip install stonks[all]
```

With uv:

```bash
uv add stonks           # core
uv add stonks[all]      # everything
```

## Quick Start

### 1. Log metrics from your training script

```python
import stonks

with stonks.start_run("my-experiment", config={"lr": 0.01, "epochs": 10}) as run:
    for epoch in range(10):
        loss = train_one_epoch()
        val_acc = evaluate()
        run.log({"train/loss": loss, "val/accuracy": val_acc}, step=epoch)
```

This creates a `stonks.db` file in your current directory containing all logged data.

### 2. View results in the dashboard

```bash
pip install stonks[server]  # if not already installed
stonks serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) to see your experiments, runs, and metric charts.

### 3. Query results programmatically

```python
import stonks

with stonks.open() as db:
    for exp in db.list_experiments():
        print(f"Experiment: {exp.name}")
        for run in db.list_runs(exp.id):
            print(f"  Run: {run.name} ({run.status})")
            keys = db.get_metric_keys(run.id)
            for key in keys:
                series = db.get_metrics(run.id, key)
                print(f"    {key}: {len(series.steps)} points")
```

## What's Next?

- {doc}`user-guide/tracking` — full SDK reference
- {doc}`user-guide/lightning` — PyTorch Lightning integration
- {doc}`user-guide/server` — dashboard features
- {doc}`self-hosting` — deploy the dashboard for your team
