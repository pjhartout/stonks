# Querying Data

stonks provides a Python API for reading experiment data programmatically.

## Opening a Database

```python
import stonks

with stonks.open() as db:
    experiments = db.list_experiments()
```

The `db` parameter follows the same resolution rules as `start_run()` — see {doc}`configuration`.

## Listing Experiments

```python
with stonks.open() as db:
    for exp in db.list_experiments():
        print(f"{exp.name} (created {exp.created_at})")
```

Each `Experiment` has:
- `id` — UUID string
- `name` — experiment name (unique)
- `created_at` — Unix timestamp
- `description` — optional description

## Listing Runs

```python
with stonks.open() as db:
    # All runs across all experiments
    all_runs = db.list_runs()

    # Runs for a specific experiment
    runs = db.list_runs(experiment_id="abc-123")
```

Each `RunInfo` has:
- `id` — UUID string
- `experiment_id` — parent experiment ID
- `status` — "running", "completed", "failed", or "interrupted"
- `created_at` — Unix timestamp
- `name` — optional display name
- `config` — hyperparameter dictionary (or `None`)
- `ended_at` — Unix timestamp (or `None` if still running)

## Retrieving Metrics

```python
with stonks.open() as db:
    runs = db.list_runs()
    run = runs[0]

    # Get available metric keys
    keys = db.get_metric_keys(run.id)
    # e.g. ["train/loss", "train/accuracy", "val/loss"]

    # Get a metric series
    series = db.get_metrics(run.id, "train/loss")
    print(f"Steps: {series.steps}")
    print(f"Values: {series.values}")
    print(f"Timestamps: {series.timestamps}")
```

`MetricSeries` contains parallel lists:
- `key` — the metric name
- `steps` — list of step numbers
- `values` — list of metric values
- `timestamps` — list of Unix timestamps

## Example: Export to Pandas

```python
import pandas as pd
import stonks

with stonks.open() as db:
    runs = db.list_runs()
    run = runs[0]
    series = db.get_metrics(run.id, "train/loss")

    df = pd.DataFrame({
        "step": series.steps,
        "loss": series.values,
    })
    print(df.describe())
```
