---
title: "feat: Stable API surface"
type: feat
status: completed
date: 2026-02-23
---

# feat: Stable API surface

## Overview

Define the complete `StonksLogger`, `start_run()`, and CLI API surface **now** so the declaration in ML pipelines never needs to change as the package evolves internally.

The principle: **declare once, never refactor your training scripts.**

## Problem Statement / Motivation

ML experiment trackers typically expose organizational primitives like `project`, `name`, `tags`, `group`, `notes`, `resume`. Today's `StonksLogger` only exposes `experiment_name`, `db`, `run_name`, and hardware flags — any future addition (tags, resume, groups) would be a breaking API change that forces users to update every training script.

Similarly, the CLI is just `stonks serve` today. As the dashboard evolves and features get added (listing runs, exporting data, cleanup), the CLI needs to be stable enough that users' scripts and CI pipelines don't break.

**Goal:** Ship the full parameter surface now. Parameters can be accepted-but-not-yet-implemented (stored in the DB, surfaced later in the UI). The API contract is set; internals evolve freely behind it.

## Proposed Solution

### Parameter surface

| Concept | Stonks parameter | Status |
|---|---|---|
| Top-level grouping | `project` | **New** |
| Experiment / run group | `experiment` | Exists (rename semantics) |
| Run display name | `name` | Exists as `run_name` |
| Run identifier for resume | `id` | **New** |
| Resume behavior | `resume` | **New** |
| Tags | `tags` | **New** |
| Notes / description | `notes` | **New** |
| Group (e.g. k-fold, sweep) | `group` | **New** |
| Job type | `job_type` | **New** |
| Hyperparameters | `config` | Exists |
| Metric prefix | `prefix` | **New** |
| Storage location | `save_dir` | Rename from `db` |
| Hardware monitoring | `hardware` | Exists (stonks-specific) |
| Strict error mode | `strict` | Exists (stonks-specific) |

### Target API: `StonksLogger`

```python
class StonksLogger(Logger):
    def __init__(
        self,
        # --- Organizational ---
        project: str | None = None,          # top-level project name (new)
        experiment: str | None = None,       # experiment name (was: experiment_name, required)
        name: str | None = None,             # run display name (was: run_name)
        id: str | None = None,               # run ID for resume (new)
        resume: bool | Literal["must"] | None = None,  # resume behavior (new)
        group: str | None = None,            # run grouping key (new)
        job_type: str | None = None,         # run type: train, eval, etc. (new)
        tags: list[str] | None = None,       # run tags (new)
        notes: str | None = None,            # run description (new)
        config: dict | None = None,          # hyperparameters (new on logger)
        prefix: str = "",                    # metric key prefix (new)
        # --- Storage ---
        save_dir: str | None = None,         # DB path (was: db)
        # --- Monitoring ---
        hardware: bool = False,              # hardware monitoring
        hardware_interval: float = 5.0,      # poll interval
        hardware_gpu: bool = True,           # GPU monitoring
        # --- Behavior ---
        strict: bool = False,                # raise on errors
    ) -> None:
```

### Target API: `start_run()`

```python
def start_run(
    # --- Organizational ---
    project: str | None = None,
    experiment: str | None = None,
    name: str | None = None,
    id: str | None = None,
    resume: bool | Literal["must"] | None = None,
    group: str | None = None,
    job_type: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
    config: dict | None = None,
    prefix: str = "",
    # --- Storage ---
    save_dir: str | None = None,
    # --- Monitoring ---
    hardware: bool = False,
    hardware_interval: float = 5.0,
    hardware_gpu: bool = True,
    # --- Behavior ---
    strict: bool = False,
) -> Run:
```

### Target API: `Run`

```python
class Run:
    # Properties
    run.id -> str
    run.experiment_id -> str
    run.project -> str | None
    run.name -> str | None
    run.tags -> list[str]
    run.group -> str | None
    run.job_type -> str | None
    run.notes -> str | None
    run.config -> dict | None

    # Methods
    run.log(metrics, step=None)           # existing
    run.log_config(config)                # existing
    run.flush()                           # existing
    run.finish(status="completed")        # existing
    run.set_tags(tags)                    # new: update tags after creation
    run.set_notes(notes)                  # new: update notes after creation
```

### Target CLI

The CLI should expose data operations so users never need to write Python to inspect or manage their data. The `serve` command stays as-is. New commands are additive.

```
stonks serve [--db] [--host] [--port] [--reload]     # existing
stonks ls [--db]                                       # list experiments
stonks runs <experiment> [--db] [--status] [--tag]     # list runs
stonks info [--db]                                     # DB stats
stonks delete <run-id|experiment> [--db] [--force]     # delete run or experiment
stonks export <run-id> [--db] [--format csv|json]      # export metrics
stonks gc [--db] [--before] [--status failed,interrupted]  # cleanup
```

All commands accept `--db` with the same resolution as the SDK: explicit > `STONKS_DB` env var > `./stonks.db`.

### Backward Compatibility

The old parameter names must keep working during a deprecation period:

| Old | New | Strategy |
|---|---|---|
| `experiment_name=` (StonksLogger) | `experiment=` | Accept both, warn on old |
| `run_name=` (start_run) | `name=` | Accept both, warn on old |
| `db=` (start_run, StonksLogger) | `save_dir=` | Accept both, warn on old |

Use `warnings.warn(..., DeprecationWarning, stacklevel=2)` for each. Remove old names in the next major version.

## Technical Approach

### Architecture

```
Before:
  experiments (name)  ->  runs (name, config, status)  ->  metrics

After:
  projects (name)  ->  experiments (name)  ->  runs (name, group, job_type,
                                                     tags, notes, config,
                                                     status, prefix)  ->  metrics
```

The `project` level is optional — when omitted, runs go under a default project.

### Implementation Phases

#### Phase 1: Schema migration + models

Add new columns and table. Use `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ADD COLUMN` with existence checks (SQLite-friendly, no migration framework needed).

**Schema changes:**

```sql
-- New table
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL
);

-- New columns on experiments
ALTER TABLE experiments ADD COLUMN project_id TEXT REFERENCES projects(id);

-- New columns on runs
ALTER TABLE runs ADD COLUMN group_name TEXT;
ALTER TABLE runs ADD COLUMN job_type TEXT;
ALTER TABLE runs ADD COLUMN tags TEXT;        -- JSON array
ALTER TABLE runs ADD COLUMN notes TEXT;
ALTER TABLE runs ADD COLUMN prefix TEXT DEFAULT '';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_runs_group ON runs(group_name);
CREATE INDEX IF NOT EXISTS idx_runs_job_type ON runs(job_type);
CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);
CREATE INDEX IF NOT EXISTS idx_experiments_project ON experiments(project_id);
```

**`tags` storage:** JSON array in a TEXT column (`'["baseline","v2"]'`). Simple, queryable with `json_each()` in SQLite, avoids a join table for what is fundamentally a small list.

**Model changes (`stonks/models.py`):**

```python
@dataclass
class Project:
    id: str
    name: str
    created_at: float

@dataclass
class Experiment:
    # ... existing fields ...
    project_id: str | None = None        # new

@dataclass
class RunInfo:
    # ... existing fields ...
    group: str | None = None             # new
    job_type: str | None = None          # new
    tags: list[str] | None = None        # new
    notes: str | None = None             # new
    prefix: str = ""                     # new
```

**Tasks:**

- [x]Add `Project` dataclass to `stonks/models.py`
- [x]Add new fields to `Experiment` and `RunInfo` in `stonks/models.py`
- [x]Add `projects` table creation to `stonks/store.py` schema
- [x]Add `ALTER TABLE` migration statements (with `try/except` for idempotency) to `initialize_db()`
- [x]Add `create_project()`, `get_or_create_project()` to `stonks/store.py`
- [x]Update `create_run()` to accept and store `group`, `job_type`, `tags`, `notes`, `prefix`
- [x]Add `update_run_tags()`, `update_run_notes()` to `stonks/store.py`
- [x]Update `list_runs()` and `get_run_by_id()` to return new fields
- [x]Update `create_experiment()` to accept optional `project_id`

#### Phase 2: Run + resume logic

Update `Run` class to accept all new parameters and implement resume.

**Resume semantics:**

| `id` | `resume` | Behavior |
|---|---|---|
| None | None | Create new run (current behavior) |
| `"abc"` | None | Create new run with that specific ID |
| `"abc"` | `True` | Resume if exists, create if not |
| `"abc"` | `"must"` | Resume existing, raise if not found |
| None | `True` | Resume latest run in experiment, create if none |

**Resume implementation in `Run.start()`:**

```python
if self._id and self._resume:
    existing = get_run_by_id(self._conn, self._id)
    if existing:
        self._run_info = existing
        # re-open: set status back to 'running', update heartbeat
        reopen_run(self._conn, self._id)
        self._step_counter = get_max_step(self._conn, self._id) + 1
        return self
    elif self._resume == "must":
        raise StonksError(f"Run '{self._id}' not found and resume='must'")
# ... fall through to create_run()
```

**New store functions needed:**

- `reopen_run(conn, run_id)` — set status='running', update heartbeat
- `get_max_step(conn, run_id)` — `SELECT MAX(step) FROM metrics WHERE run_id = ?`
- `get_latest_run(conn, experiment_id)` — most recent run for resume=True without id

**`prefix` implementation:**

Applied in `Run.log()` — prepend `f"{prefix}/"` to each metric key before buffering. This is a one-line change in the log method. The prefix is stored on the run record so the dashboard can strip it for display if needed.

**Tasks:**

- [x]Update `Run.__init__()` to accept `project`, `id`, `resume`, `group`, `job_type`, `tags`, `notes`, `prefix`
- [x]Add resume branch to `Run.start()`
- [x]Add `run.set_tags()` and `run.set_notes()` methods
- [x]Add prefix application in `Run.log()`
- [x]Expose new properties: `project`, `tags`, `group`, `job_type`, `notes`
- [x]Add `reopen_run()`, `get_max_step()`, `get_latest_run()` to `stonks/store.py`

#### Phase 3: Public API + StonksLogger

Update `start_run()` and `StonksLogger` to expose the full parameter surface.

**`start_run()` (`stonks/__init__.py`):**

- Accept all new parameters
- Wire through to `Run()`
- Handle `save_dir` / `db` alias with deprecation warning
- Handle `name` / `run_name` alias with deprecation warning
- Default `experiment` to project name or `"default"` when omitted

**`StonksLogger` (`stonks/lightning.py`):**

- Accept all new parameters
- Handle `experiment_name` / `experiment` alias with deprecation warning
- Resolve everything at `__init__` time (Lightning reads `logger.name` before training)
- Pass `config` to `Run.log_config()` on first use
- Apply `prefix` to all `log_metrics()` calls

**Tasks:**

- [x]Rewrite `start_run()` with full parameter surface
- [x]Add deprecation handling for `db`, `run_name`, `experiment_name`
- [x]Rewrite `StonksLogger.__init__()` with full parameter surface
- [x]Update `StonksLogger.name` to return experiment name
- [x]Update `StonksLogger.version` to return run ID
- [x]Pass `config` through to run in `_ensure_run()`

#### Phase 4: CLI commands

Add the stable CLI surface. Each command is a thin wrapper over the existing `Database` / store layer.

**Commands to add:**

- [x]`stonks ls` — list experiments (uses `list_experiments_with_run_counts()`)
- [x]`stonks runs <experiment>` — list runs with optional `--status`, `--tag` filters
- [x]`stonks info` — DB stats (experiment count, run count, DB file size, metrics count)
- [x]`stonks delete <id>` — delete a run or experiment with `--force` confirmation
- [x]`stonks export <run-id>` — export metrics as CSV or JSON
- [x]`stonks gc` — garbage collect runs by status/age

Each command uses the same `--db` resolution as `stonks serve`.

**Output format:** Plain text tables for TTY, JSON with `--json` flag for scripting.

#### Phase 5: Server API + Dashboard support

Expose the new fields through the FastAPI endpoints so the dashboard can display them.

**API changes:**

- [x]Update `/api/experiments` response to include `project` info
- [x]Update `/api/runs` response to include `group`, `job_type`, `tags`, `notes`
- [x]Add `?tag=`, `?group=`, `?job_type=` query filters to `GET /api/runs`
- [x]Add `GET /api/projects` endpoint

**Dashboard changes** (deferred to separate PR — the API contract is what matters here):

- Tags displayed as chips on run cards
- Group column in runs table
- Filter sidebar for tags/groups
- Notes shown in run detail view

#### Phase 6: Tests

**Unit tests (`tests/unit/`):**

- [x]`test_store.py` — new schema columns present, `create_project()`, `create_run()` with new fields, `reopen_run()`, `get_max_step()`, `get_latest_run()`
- [x]`test_run.py` — resume scenarios (all 5 from the matrix), prefix application, `set_tags()`, `set_notes()`, new properties
- [x]`test_config.py` — deprecation warnings for old parameter names
- [x]`test_models.py` — new dataclasses serialize/deserialize correctly

**Integration tests (`tests/integration/`):**

- [x]`test_full_workflow.py` — start_run with all new params -> log -> finish -> query back, verify all fields stored
- [x]`test_resume.py` — create run -> finish -> resume by id -> log more -> verify step continuity
- [x]`test_lightning.py` — StonksLogger with full params, verify deprecated params warn
- [x]`test_server_api.py` — new API endpoints return new fields, filter params work
- [x]`test_backward_compat.py` — existing code with old param names still works, emits warnings

## Alternative Approaches Considered

### Add parameters incrementally as needed

**Rejected:** This is exactly what the user wants to avoid. Every addition would be a potentially breaking change to training scripts, and users would need to update their code.

### Use `**kwargs` pass-through

Accept `**kwargs` and forward them to underlying init functions. We could do `StonksLogger(**kwargs)` and accept anything.

**Rejected:** Stonks has no underlying service to forward to. Explicit parameters with type hints are better for a library that owns its entire stack — they provide autocomplete, type checking, and clear documentation.

### Skip the `project` level entirely

Just use `experiment` as the top-level grouping (current behavior) and add all new fields to runs.

**Considered but rejected:** Most experiment trackers have `project` as the organizational root. Users expect `project` -> `experiment` -> `run` hierarchy. Adding it now (even if the dashboard doesn't use it yet) prevents a future breaking change.

## Acceptance Criteria

### Functional Requirements

- [x]`StonksLogger` and `start_run()` accept all parameters from the target API
- [x]Old parameter names (`experiment_name`, `run_name`, `db`) still work with deprecation warnings
- [x]`resume=True` with `id=` resumes an existing run and appends metrics
- [x]`resume="must"` raises `StonksError` when run not found
- [x]`tags`, `notes`, `group`, `job_type` are stored and queryable
- [x]`prefix` is prepended to metric keys
- [x]`project` creates/gets a project record and links experiments to it
- [x]CLI commands (`ls`, `runs`, `info`, `delete`, `export`, `gc`) work
- [x]All existing tests pass without modification
- [x]New fields appear in API responses

### Non-Functional Requirements

- [x]No new Python dependencies (tags as JSON, no tagging library)
- [x]Schema migration is idempotent (safe to run on existing DBs)
- [x]Test suite stays under 20 seconds
- [x]All imports hoisted (PLC0415)

## Dependencies & Prerequisites

- None. All changes use stdlib (`json`, `warnings`, `sqlite3`). No new packages.

## Risk Analysis & Mitigation

| Risk | Mitigation |
|---|---|
| Schema migration breaks existing DBs | `ALTER TABLE ADD COLUMN` with `try/except OperationalError` — idempotent, safe |
| `project` adds complexity users don't need yet | Optional, defaults to None. No project = flat experiment list (current behavior) |
| Resume logic has edge cases (concurrent access, WAL) | SQLite WAL handles concurrent reads. Resume sets status atomically. Test all 5 resume scenarios. |
| Deprecation warnings annoy users | Only emit on actual use of old names. Clear migration path in warning message. |

## Future Considerations

These are explicitly **out of scope** but the API surface accommodates them without changes:

- **Dashboard**: tags/groups/notes rendering (separate PR, no API change needed)
- **Auto-config capture** (`config="auto"`): detect argparse/Hydra automatically
- **pyproject.toml defaults**: read `[tool.stonks]` for project-level defaults like `save_dir`
- **Artifact logging**: if ever added, would be a new method on `Run`, not a constructor change
- **Remote sync**: if ever added, would be config/env-driven, not a parameter change

## Sources & References

### Internal References

- Current logger: `stonks/lightning.py:41-59`
- Current Run: `stonks/run.py:26-211`
- Current store: `stonks/store.py` (full file — schema + DAL)
- Current models: `stonks/models.py` (full file)
- Current CLI: `stonks/cli.py` (full file)
- Current public API: `stonks/__init__.py:31-66`

### External References

- PyTorch Lightning Logger interface: `lightning.pytorch.loggers.Logger`
