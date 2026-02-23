# stonks

Lightweight, self-hosted ML experiment tracking. No accounts, no SaaS, no nonsense — just a SQLite file and a dashboard.

Born out of frustration with the extortionate pricing of overleveraged ML experiment tracking companies and the hopeless clunkiness of `tensorboard`. 

## Install

```bash
git clone https://github.com/pjhartout/stonks.git && cd stonks
uv sync --all-extras
```

Or pick what you need:

```bash
uv sync                       # core SDK only
uv sync --extra lightning     # + PyTorch Lightning logger
uv sync --extra server        # + dashboard server
uv sync --extra gpu           # + NVIDIA GPU monitoring
uv sync --all-extras          # everything
```

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

## View the dashboard

```bash
stonks serve
# Open http://127.0.0.1:8000
```

Live metric charts, run comparison, config diffs — all updating in real time via SSE.

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
