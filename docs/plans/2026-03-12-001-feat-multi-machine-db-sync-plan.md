---
title: "feat: Add multi-machine DB sync via rsync + merge"
type: feat
status: completed
date: 2026-03-12
origin: docs/brainstorms/2026-03-12-multi-machine-sync-brainstorm.md
---

# feat: Add multi-machine DB sync via rsync + merge

## Overview

Add a `stonks sync` CLI command that pulls `stonks.db` files from remote training machines via rsync/SSH and merges them into the local database. This gives users a unified dashboard view of all runs across machines, with no changes to the SDK's write path.

## Problem Statement / Motivation

Training runs happen on remote GPU servers and cloud VMs. Each machine writes to its own local `stonks.db`. Currently there's no way to view all runs in one place without manually copying files. Users want a near real-time unified view on their laptop's dashboard.

(see brainstorm: `docs/brainstorms/2026-03-12-multi-machine-sync-brainstorm.md`)

## Proposed Solution

Three new components:

1. **Config file** (`~/.stonks/remotes.toml`) — defines remote machines with SSH host and DB path
2. **Sync engine** — rsync pulls remote `.db` files to a local staging area, then merges into the local `stonks.db`
3. **CLI commands** — `stonks sync` (one-shot + `--watch` daemon mode) and `stonks remote` (list/validate remotes)

### Merge Strategy

The merge uses SQLite's `ATTACH DATABASE` to open the remote DB alongside the local DB. For each run in the remote:

- **New run** (UUID not in local DB): Insert project/experiment (upsert by name), insert run, bulk-insert all metrics
- **Changed run** (exists locally but remote has newer `last_heartbeat` or `ended_at`): Update run record, delete local metrics for that run, re-insert all metrics from remote
- **Unchanged run**: Skip entirely

This avoids the metric deduplication problem identified in analysis — metrics have no natural unique key (`id` is autoincrement), so rather than attempting `INSERT OR IGNORE`, we do a clean delete+reinsert for changed runs and skip unchanged ones.

**ID remapping**: Experiments and projects have UNIQUE name constraints but different UUIDs across machines. During merge, we resolve by name:
- Look up experiment by name in local DB → if found, use local ID; if not, insert with remote's ID
- Remap `experiment_id` on runs and `project_id` on experiments accordingly

**Merge order** (respecting foreign keys): projects → experiments → runs → metrics

**Transaction boundary**: One transaction per remote merge. Failure rolls back cleanly.

## Technical Considerations

### Architecture

New module `stonks/sync/` with three files:
- `config.py` — parse and validate `~/.stonks/remotes.toml`
- `merge.py` — ATTACH-based merge logic
- `daemon.py` — watch loop with signal handling

New CLI commands in `stonks/cli.py`:
- `sync` subcommand (one-shot + `--watch` + `--interval`)
- `remote` subcommand (`list`, `check`)

### Critical Design Decisions

**1. Metric dedup via delete+reinsert (not INSERT OR IGNORE)**

The metrics table has `id INTEGER PRIMARY KEY AUTOINCREMENT` with no unique constraint on `(run_id, key, step)`. `INSERT OR IGNORE` would do nothing since every row gets a new ID. Instead:
- For new runs: straight insert (all metrics are new)
- For changed runs: `DELETE FROM metrics WHERE run_id = ?` then bulk insert from remote
- For unchanged runs: skip entirely (zero cost)

This is simple, correct, and idempotent. Trade-off: for very large changed runs, the delete+reinsert is expensive, but this is the minority case (most runs complete once and never change again).

**2. Run upsert semantics: remote wins for all fields**

Since these are remote-origin runs, the remote copy is authoritative. All fields (status, ended_at, config, tags, notes) are overwritten from the remote on update. Local dashboard edits to synced runs would be lost on next sync — this is acceptable for v1.

**3. Integrity check before merge**

Run `PRAGMA integrity_check` on each staged remote DB before merging. Skip the remote (with warning) if the check fails. This guards against corrupt transfers from rsyncing a live SQLite file.

**4. Lock file to prevent concurrent sync**

A PID-based lock file at `~/.stonks/sync.lock` prevents two sync processes from running simultaneously. On startup, check if the PID in the lock file is still alive. If not, claim the lock.

**5. Config re-read every cycle in daemon mode**

The `--watch` daemon re-reads `remotes.toml` on each cycle. Config parse errors are logged and the last valid config is retained.

**6. Rsync flags**

```
rsync -az --whole-file -e "ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o BatchMode=yes"
```

- `--whole-file`: skip delta algorithm (inefficient for binary SQLite files)
- `-az`: archive mode + compression
- `BatchMode=yes`: never prompt for passwords (fail fast if key auth doesn't work)
- `ConnectTimeout=10`: don't hang on unreachable hosts

### Performance Implications

- 10-second sync interval means ~6 SSH connections per minute per remote. For a handful of remotes this is fine. For many (>10), consider increasing the interval.
- Full merge scans all runs in the remote DB each cycle, but skips unchanged runs quickly (just comparing `last_heartbeat`). The cost is proportional to the number of *changed* runs, not total runs.
- SQLite WAL mode allows the dashboard to read while the merge writes. Brief write locks during merge transactions are possible but the SSE polling (1s interval) will simply retry.

### Security Considerations

- SSH keys are the only supported auth method (`BatchMode=yes` rejects password prompts)
- `StrictHostKeyChecking=accept-new` accepts new hosts on first connect but rejects changed host keys (TOFU model)
- Remote DB paths are user-configured; no path traversal risk since rsync runs as the SSH user
- The config file at `~/.stonks/remotes.toml` could contain hostnames — permissions should be 600

## System-Wide Impact

- **SSE interaction**: When the merge bulk-inserts new runs, the SSE stream will emit `run_update` events. This is desirable — the dashboard shows new runs appearing. For large initial syncs, this could generate a burst of events, but the Svelte frontend handles incremental updates fine.
- **Error propagation**: rsync failure → skip remote, log warning, retry next cycle. Merge failure → rollback transaction, skip remote, log error. Neither crashes the daemon.
- **State lifecycle**: The lock file prevents partial state from concurrent sync processes. Per-remote transactions prevent cross-contamination.
- **API surface**: No changes to the public Python API (`stonks/__init__.py`). All new code is internal modules + CLI commands.

## Acceptance Criteria

- [x] `~/.stonks/remotes.toml` config file parsed and validated with clear error messages
- [x] `stonks remote list` shows configured remotes with connectivity status
- [x] `stonks remote check` validates SSH connectivity to all remotes
- [x] `stonks sync` performs one-shot sync from all configured remotes
- [x] `stonks sync --watch` runs as a daemon, syncing every 10s (configurable via `--interval`)
- [x] Merge correctly handles project/experiment name → ID remapping across machines
- [x] New runs from remotes appear in the local dashboard
- [x] Run status changes (running → completed) propagate from remote to local
- [x] Metrics for changed runs are correctly updated (no duplication)
- [x] Unchanged runs are skipped (idempotent merge)
- [x] Corrupt remote DB files are detected and skipped with warning
- [x] Unreachable remotes are skipped with warning, retried next cycle
- [x] Lock file prevents concurrent sync processes
- [x] Daemon handles SIGINT/SIGTERM gracefully (finish current transaction, clean up, exit)
- [x] Config changes during `--watch` are picked up on next cycle
- [x] Unit tests for merge logic (ID remapping, new/changed/unchanged runs, corrupt DB)
- [x] Integration test: two separate DBs with overlapping experiment names → merged correctly
- [x] Integration test: running merge twice produces same result (idempotency)

## Success Metrics

- All runs from remote machines visible in local dashboard within ~10-20 seconds
- Zero metric duplication after repeated sync cycles
- Sync daemon runs stably for hours without memory leaks or DB growth issues

## Dependencies & Risks

**Dependencies:**
- `tomllib` (stdlib in Python 3.11+) for config parsing — no new external dependency needed
- `rsync` and `ssh` must be installed on the local machine (standard on macOS/Linux)
- `sqlite3` CLI not required on remote machines (we don't run backup commands remotely)

**Risks:**
- **Corrupt transfers**: Rsyncing a live SQLite file without the WAL can produce a corrupt copy. Mitigated by integrity check before merge, and the fact that MetricBuffer flushes every 1s (so the WAL is checkpointed frequently).
- **Large DB merge performance**: For experiments with millions of metric rows where the run is still "running", each sync cycle deletes and re-inserts all metrics. For v1 this is acceptable; if it becomes a bottleneck, we can add watermark-based incremental sync later.
- **SSH overhead**: 10-second polling with many remotes could be noisy. The interval is configurable, and the `--whole-file` flag minimizes rsync overhead.

## Implementation Phases

### Phase 1: Config + Remote Management
- `stonks/sync/config.py` — parse `~/.stonks/remotes.toml`, validate schema, resolve paths
- `stonks remote list` and `stonks remote check` CLI commands
- Tests for config parsing and validation

### Phase 2: Merge Engine
- `stonks/sync/merge.py` — ATTACH-based merge with ID remapping
- Handle new/changed/unchanged runs
- Integrity check on source DB
- Unit tests with two synthetic DBs

### Phase 3: Sync Command + Daemon
- `stonks/sync/daemon.py` — rsync execution, watch loop, signal handling, lock file
- `stonks sync` and `stonks sync --watch` CLI commands
- Integration tests for full sync flow

### Phase 4: Polish
- Progress logging (which remotes synced, how many runs/metrics imported)
- Error message quality (SSH failures, config errors, corrupt DBs)
- Documentation in README

## New Files

```
stonks/sync/__init__.py
stonks/sync/config.py        # RemoteConfig dataclass, parse_remotes_config()
stonks/sync/merge.py          # merge_remote_db(source_path, target_conn)
stonks/sync/daemon.py          # SyncDaemon class, rsync execution, lock file
tests/unit/test_sync_config.py
tests/unit/test_sync_merge.py
tests/integration/test_sync.py
```

## Config File Schema

```toml
# ~/.stonks/remotes.toml

[remotes.gpu-server-1]
host = "user@192.168.1.100"         # required: SSH host (user@host or just host)
db_path = "/home/user/stonks.db"    # required: absolute path to stonks.db on remote
ssh_key = "~/.ssh/gpu_key"          # optional: SSH private key path
port = 22                            # optional: SSH port (default: 22)

[remotes.cloud-vm]
host = "trainer@ml-box.example.com"
db_path = "/data/experiments/stonks.db"
```

**Local staging path**: `~/.stonks/sync/<remote_name>/stonks.db`

## Sources & References

- **Origin brainstorm:** [docs/brainstorms/2026-03-12-multi-machine-sync-brainstorm.md](docs/brainstorms/2026-03-12-multi-machine-sync-brainstorm.md) — key decisions: DB file sync over HTTP, rsync pull model, full merge with INSERT OR IGNORE semantics (refined to delete+reinsert for changed runs), 10s interval, config file for remotes
- CLI pattern: `stonks/cli.py` — argparse dispatch dict for adding new commands
- Store upsert pattern: `stonks/store/experiments.py:32` — IntegrityError catch for name-based upsert
- Schema: `stonks/store/connection.py:10-57` — table definitions and foreign key relationships
- SSE: `stonks/server/routes/stream.py:42` — polling logic that will surface synced data
