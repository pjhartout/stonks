# stonks

**Lightweight ML experiment tracking.**

stonks is a local-first, zero-config experiment tracker for machine learning. Log metrics from your training scripts, view them in a real-time dashboard, and query results programmatically — all backed by a single SQLite file.

- **Simple SDK** — two lines to start logging: `stonks.start_run()` + `run.log()`
- **PyTorch Lightning** — drop-in `StonksLogger` for Lightning trainers
- **Real-time dashboard** — `stonks serve` launches a web UI with live charts
- **Zero infrastructure** — no servers, databases, or accounts needed
- **Self-hostable** — share a dashboard with your team on any machine

## Quick Example

```python
import stonks

with stonks.start_run("my-experiment", config={"lr": 0.01}) as run:
    for step in range(100):
        loss = train_step()
        run.log({"train/loss": loss}, step=step)
```

Then view the results:

```bash
stonks serve
# Open http://127.0.0.1:8000
```

```{toctree}
:maxdepth: 2
:caption: User Guide

getting-started
user-guide/index
self-hosting
```

```{toctree}
:maxdepth: 2
:caption: Reference

rest-api
apidocs/index
```

```{toctree}
:maxdepth: 1
:caption: Development

contributing
```
