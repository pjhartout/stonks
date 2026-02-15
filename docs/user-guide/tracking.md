# Tracking Experiments

## Starting a Run

Use `stonks.start_run()` to create a new run under an experiment:

```python
import stonks

with stonks.start_run("resnet-cifar10", config={"lr": 0.1}) as run:
    for step in range(1000):
        loss = train_step()
        run.log({"train/loss": loss}, step=step)
```

### Parameters

`experiment`
: Name of the experiment. If the experiment doesn't exist, it's created automatically. If it does exist, the run is added to it.

`config` *(optional)*
: Dictionary of hyperparameters to store with the run.

`db` *(optional)*
: Path to the SQLite database file. See {doc}`configuration` for resolution rules.

`run_name` *(optional)*
: Human-readable name for this run. Shown in the dashboard.

`strict` *(optional)*
: If `True`, logging errors raise exceptions. If `False` (default), errors are logged as warnings and swallowed.

## Logging Metrics

Call `run.log()` with a dictionary of metric names and values:

```python
run.log({"train/loss": 0.45, "train/accuracy": 0.82}, step=10)
```

### Metric Key Naming

Use slash-separated namespaces to group related metrics:

```python
run.log({
    "train/loss": train_loss,
    "train/accuracy": train_acc,
    "val/loss": val_loss,
    "val/accuracy": val_acc,
})
```

The dashboard groups charts by prefix (e.g., all `train/*` metrics appear together).

### Step Numbers

If you provide `step`, that value is recorded. If you omit it, stonks auto-increments from 0:

```python
# Explicit steps
run.log({"loss": 0.5}, step=0)
run.log({"loss": 0.3}, step=1)

# Auto-incrementing (starts at 0)
run.log({"loss": 0.5})  # step=0
run.log({"loss": 0.3})  # step=1
```

## Updating Config After Creation

You can add or update hyperparameters at any point during the run:

```python
with stonks.start_run("my-exp") as run:
    run.log_config({"lr": 0.01, "optimizer": "adam"})
    # ... training ...
    run.log_config({"early_stopped_at": 50})  # merges with existing config
```

## Context Manager vs Manual Lifecycle

### Context Manager (Recommended)

The context manager automatically handles start/finish and sets the status based on how the block exits:

```python
with stonks.start_run("my-exp") as run:
    run.log({"loss": 0.5})
    # Status: "completed" on normal exit
    # Status: "failed" on exception
    # Status: "interrupted" on KeyboardInterrupt
```

### Manual Lifecycle

For cases where a context manager doesn't fit:

```python
run = stonks.start_run("my-exp")
run.start()
try:
    run.log({"loss": 0.5})
    run.finish("completed")
except Exception:
    run.finish("failed")
```

## Error Handling

By default, logging errors are swallowed and logged as warnings. This prevents experiment tracking from crashing your training script:

```python
# Default: errors are swallowed
with stonks.start_run("my-exp") as run:
    run.log({"loss": float("nan")})  # warning logged, training continues

# Strict mode: errors raise
with stonks.start_run("my-exp", strict=True) as run:
    run.log({"loss": float("nan")})  # raises InvalidMetricError
```

## Buffered Writes

Metrics are buffered in memory and flushed to SQLite periodically in a background thread. This keeps logging fast and non-blocking. You can force a flush at any time:

```python
run.flush()
```

The buffer flushes automatically when:
- It reaches 100 entries
- Every 5 seconds (background timer)
- The run finishes
