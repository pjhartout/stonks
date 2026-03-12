# stonks

Lightweight, self-hosted ML experiment tracking. No accounts, no SaaS, no nonsense — just a SQLite file and a dashboard.

Born out of frustration with the extortionate pricing of overleveraged ML experiment tracking companies and the hopeless clunkiness of `tensorboard`. 

## Install

### Development (recommended)

Clone the repo and install with [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/pjhartout/stonks.git
cd stonks
uv sync --all-extras

# Build the dashboard frontend
cd ui && bun install && bun run build && cd ..

# Start the dashboard
stonks serve
```

### From a release (easiest for non-developers)

Download a pre-built wheel from [GitHub Releases](https://github.com/pjhartout/stonks/releases)
(the wheel includes the pre-built dashboard frontend):

```bash
pip install https://github.com/pjhartout/stonks/releases/download/vX.Y.Z/stonks-X.Y.Z-py3-none-any.whl
```

### From Git (SDK only, no dashboard)

Install the latest `main` directly from Git:

```bash
pip install "stonks @ git+https://github.com/pjhartout/stonks.git"

# With the dashboard server:
pip install "stonks[server] @ git+https://github.com/pjhartout/stonks.git"
```

Note: Git installs do not include the pre-built dashboard frontend. To get the
dashboard, either use a release wheel or build the frontend yourself (see Development above).

### Optional extras

Pick what you need:

```bash
uv sync                       # core SDK only
uv sync --extra lightning     # + PyTorch Lightning logger
uv sync --extra server        # + dashboard server
uv sync --extra gpu           # + NVIDIA GPU monitoring
uv sync --all-extras          # everything
```

The same extras work with pip: `pip install "stonks[server,lightning]"`.

## Log metrics

```python
import stonks

with stonks.start_run("my-experiment", config={"lr": 0.01, "epochs": 10}) as run:
    for epoch in range(10):
        loss = train_one_epoch()
        val_acc = evaluate()
        run.log({"train/loss": loss, "val/accuracy": val_acc}, step=epoch)
```

All data is stored in a local `stonks.db` file. No network, no credentials.

## PyTorch Lightning

```python
from stonks.lightning import StonksLogger

logger = StonksLogger(experiment_name="resnet-cifar10")
trainer = Trainer(max_epochs=20, logger=logger)
trainer.fit(model, datamodule)
```

## Hardware monitoring

Track CPU, RAM, disk I/O, and network usage alongside your training metrics. Enable it with `hardware=True`:

```python
import stonks

with stonks.start_run("my-experiment", hardware=True) as run:
    for epoch in range(100):
        loss = train_one_epoch()
        run.log({"train/loss": loss}, step=epoch)
```

Hardware metrics are logged under `sys/` keys (e.g. `sys/cpu_percent`, `sys/ram_used_gb`) and appear in a dedicated "System Resources" panel in the dashboard.

For NVIDIA GPU monitoring, install the `gpu` extra (`uv sync --extra gpu`). GPU metrics are collected automatically when `pynvml` is available.

```python
# PyTorch Lightning
from stonks.lightning import StonksLogger

logger = StonksLogger("resnet-cifar10", hardware=True, hardware_interval=10.0)
trainer = Trainer(max_epochs=20, logger=logger)
```

Options:
- `hardware_interval` — seconds between polls (default 5.0, minimum 1.0)
- `hardware_gpu` — set to `False` to disable GPU monitoring even when pynvml is installed

## Organize runs

Group related runs, tag them, and add notes:

```python
with stonks.start_run(
    "my-experiment",
    config={"lr": 0.01},
    group="ablation-lr",
    job_type="train",
    tags=["baseline", "v2"],
    notes="Testing lower learning rate",
) as run:
    ...
```

## Resume a run

Pick up where you left off — useful for preempted jobs or multi-phase training:

```python
# Resume latest run in experiment
with stonks.start_run("my-experiment", resume="latest") as run:
    run.log({"train/loss": 0.3}, step=100)

# Resume a specific run by ID
with stonks.start_run("my-experiment", resume="run_abc123") as run:
    ...
```

## Agent-developed

This library is primarily developed with AI coding agents. I built stonks for my own ML workflow and use agents to move fast on features, tests, and maintenance. The codebase is structured to be agent-friendly (clear conventions, comprehensive tests, strict linting) but the design decisions and direction are mine.

## View the dashboard

```bash
stonks serve
# Open http://127.0.0.1:8000
```

The dashboard updates in real time via SSE and includes:

- **Multi-run metric overlay** — select up to 8 runs and compare metrics side by side on the same chart
- **Config comparison** — side-by-side table showing hyperparameter differences across selected runs
- **Run renaming** — double-click a run name to rename it inline
- **Custom run colors** — pick per-run colors for chart lines
- **Hardware monitoring panel** — collapsible view of CPU, RAM, disk I/O, network, and GPU metrics
- **Metric grouping** — charts are automatically grouped by prefix (e.g. `train/`, `val/`)

## CLI

```bash
stonks ls                           # list experiments
stonks runs <experiment>            # list runs (--status, --tag filters)
stonks info                         # database statistics
stonks export <run-id> -f csv      # export metrics as CSV or JSON
stonks delete <run-id>              # delete a run (-f to skip confirmation)
stonks gc --before 30 --status failed  # clean up old/failed runs
```

## Query results programmatically

```python
import stonks

with stonks.open() as db:
    for exp in db.list_experiments():
        for run in db.list_runs(exp.id):
            series = db.get_metrics(run.id, "val/accuracy")
            print(f"{run.name}: {max(series.values):.4f}")
```

## Deploy

**Docker:**

```bash
docker compose up
# or: docker run -v ./data:/data -e STONKS_DB=/data/stonks.db -p 8000:8000 stonks
```

**Bare metal:**

```bash
./run.sh --db /data/stonks.db --host 0.0.0.0
```

The wrapper script handles virtualenv creation and installation automatically. See `docs/self-hosting.md` for systemd, nginx, and team deployment guides.

## Development

```bash
git clone https://github.com/pjhartout/stonks.git && cd stonks
uv sync --all-extras          # Python deps
cd ui && bun install && cd .. # frontend deps

# Terminal 1: backend with auto-reload
stonks serve --reload

# Terminal 2: frontend with HMR
cd ui && bun run dev
# Open http://localhost:5173
```

## License

Apache-2.0
