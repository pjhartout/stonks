# Brainstorm: Multi-Machine Run Sync

**Date:** 2026-03-12
**Status:** Draft

## What We're Building

A way to collect experiment runs from multiple remote training machines into a single local stonks dashboard. Remote machines each produce their own `stonks.db` file. A sync mechanism pulls those files down over SSH and merges them into one local database, giving a unified view of all runs across machines.

## Context

- All training runs happen on remote machines (GPU servers, cloud VMs)
- Dashboard is viewed locally on a laptop (may move to a central server later)
- Near real-time preferred (seconds ideal, minutes acceptable)
- Minimal infrastructure complexity is a priority
- stonks currently has no network transport — SDK writes directly to local SQLite

## Why This Approach

We considered three approaches:

1. **HTTP Remote Logging** — Add ingest endpoints to the server, SDK sends metrics over HTTP. Simplest for real-time but requires the laptop to be reachable from remote machines (port forwarding, VPN, etc.) and loses data on network drops.

2. **DB File Sync (chosen)** — Pull SQLite files via rsync/scp, merge locally. No SDK or server changes needed for the core path. Works with existing SSH access. Trade-off is slightly higher latency and merge complexity.

3. **Hybrid (Local + Push)** — Write locally and push to server. Most resilient but significantly more complex (two write paths, dedup, retry queues).

**DB File Sync was chosen because:**
- It leverages existing SSH infrastructure with zero new networking requirements
- No changes needed to the SDK's write path — remote training scripts work exactly as they do today
- Keeps the local-first philosophy intact: each machine has a complete, self-contained DB
- Merge is a well-bounded problem since run IDs are UUIDs (no collision risk)

## Key Decisions

### 1. Sync mechanism: rsync over SSH (pull model)

A `stonks sync` command on the local machine pulls `stonks.db` files from configured remotes. Uses rsync for efficient delta transfers. Runs as a daemon with configurable interval (default: 10s).

### 2. Merge into one local DB (full merge, INSERT OR IGNORE)

A merge step (called automatically after each sync) imports data from pulled remote DBs into the local `stonks.db`. Deduplication uses `INSERT OR IGNORE` on primary keys — run IDs are UUIDs so collisions are not a concern. Metrics are deduplicated by the natural key (run_id + key + step). No watermark tracking; the full merge is re-run each cycle for simplicity.

### 3. Remote configuration via config file

Remotes are defined in `~/.stonks/remotes.toml`:

```toml
[remotes.gpu-server-1]
host = "user@192.168.1.100"
path = "/home/user/experiments/stonks.db"

[remotes.cloud-vm]
host = "user@training-box.example.com"
path = "/data/stonks.db"
ssh_key = "~/.ssh/training_key"  # optional, uses default if omitted
```

### 4. Automated daemon mode (10s default)

`stonks sync --watch` runs continuously, pulling from all configured remotes every 10 seconds. Can also be run as a one-shot `stonks sync` for manual pulls. The interval is configurable via `--interval`.

### 5. WAL handling: just sync the .db file

Don't attempt to copy WAL/SHM files or run remote backup commands. Just rsync the main `.db` file. The latest few seconds of buffered data may be missing until the next MetricBuffer flush on the remote machine, but it catches up on the next sync cycle. This keeps things simple and avoids requiring sqlite3 CLI on remotes.

### 6. Error handling: log and skip

If a remote machine is unreachable, log a warning and skip it. Retry on the next cycle. No dashboard indicator for now — keep it simple and rely on logs.

## Resolved Questions

1. **WAL file handling** — Just rsync the `.db` file. Accept brief data delay. Simplest approach.
2. **Incremental merge** — Full merge with `INSERT OR IGNORE` each cycle. Optimize later only if performance becomes an issue.
3. **Sync interval** — 10 seconds default. Balances responsiveness with SSH overhead.
4. **Unreachable machines** — Log warning, skip, retry next cycle. No dashboard surfacing for now.
