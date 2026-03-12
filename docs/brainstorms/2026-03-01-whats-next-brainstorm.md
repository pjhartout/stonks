# What Should We Work On Next?

**Date:** 2026-03-01
**Status:** Draft

---

## Current State Summary

stonks is functional end-to-end: Python SDK, PyTorch Lightning integration, SQLite storage, real-time SSE dashboard, hardware monitoring, CLI tools, Docker deployment. The core loop (log -> store -> visualize) works well. Recent PRs added multi-run metric overlay, run renaming, and color pickers.

The codebase is clean — minimal TODOs, consistent style, good separation of concerns. But there are clear gaps between what the backend stores and what surfaces in the UI/API, plus growing test debt.

---

## Problems & Gaps

### 1. Test Debt (High Priority)

**96 deprecation warnings per test run.** Most tests in `test_run.py` and `test_full_workflow.py` still use the deprecated `db=` parameter instead of `save_dir=`. This is noise that masks real warnings.

**CLI has zero test coverage.** Seven commands (`ls`, `runs`, `info`, `delete`, `export`, `gc`, `serve`) totaling ~150 lines of logic are completely untested. Any refactor risks silent breakage.

**SSE coverage is minimal.** `test_sse.py` has a single test that checks a 422 on a missing parameter. The actual event delivery logic — polling, status comparison, heartbeat-triggered `metrics_update` events — is tested nowhere.

**Downsampling (`downsample_minmax`) is untested.** Edge cases like all-None values, single data point, and bucket deduplication have no coverage.

**`Run.start()` called manually** (outside context manager) is not tested.

**`strict=True` with actual DB failure** — the test uses `float("inf")` to trigger buffer rejection, but the actual strict-mode DB write failure path is untested.

### 2. Frontend-Backend Desync (High Priority)

**`types.ts` is out of sync with the API.** The frontend `Run` type omits `group`, `job_type`, `tags`, and `notes` even though the API returns them. This is a latent bug — anyone trying to display these fields will hit undefined values.

**Tags, notes, group, job_type are invisible in the dashboard.** All four are stored in the database, returned by the API, but the UI never renders them. This metadata is effectively write-only from the user's perspective.

**No filtering in the dashboard.** The runs table shows everything flat. As experiments grow to dozens or hundreds of runs, there's no way to filter by tag, group, status, or search by name.

### 3. API Incompleteness (Medium Priority)

**No REST delete endpoints.** `delete_run` and `delete_experiment` exist in the store layer and CLI, but no `DELETE /api/runs/{id}` or `DELETE /api/experiments/{id}` routes are exposed. The dashboard can't offer run deletion without these.

**No query filters on runs endpoint.** `GET /api/runs` doesn't support `?tag=`, `?group=`, or `?job_type=` filtering despite this being marked as done in an earlier plan.

**No run deletion from the dashboard.** Even if the REST endpoints existed, the UI has no delete button or confirmation flow.

### 4. Repo Hygiene (Low Priority, Easy Wins)

**Stray `AGENTS.md~` file** in the repo root — a tilde backup file that shouldn't be tracked.

**`stonks.db` is committed** to the repo root. This is likely development data that should be in `.gitignore`.

**`*.db` and `*~` patterns missing from `.gitignore`.**

**Hardcoded `level="DEBUG"`** in `stonks/logging_config.py:42`. Production log level should be `INFO` or configurable via environment variable.

### 5. Distribution (Medium Priority)

**No PyPI package.** Users must `git clone` to install. Publishing to PyPI (`pip install stonks`) would be the single biggest adoption unlock.

**README doesn't show screenshots.** For a dashboard tool, visual previews in the README would significantly help adoption.

### 6. Missing Features (Lower Priority, Future Work)

**No URL state / deep linking.** Selecting an experiment or run doesn't update the URL. You can't share a link to a specific view.

**No `pyproject.toml` defaults** (`[tool.stonks]`). Users can't set project-wide defaults for `save_dir`, `hardware`, etc.

**No artifact logging.** Can't attach files (model checkpoints, plots, configs) to runs.

**No pagination.** The runs table loads everything at once. Will become unusable with hundreds of runs.

**No dark/light mode toggle.** Currently hardcoded to Catppuccin Mocha dark theme.

**No project-level navigation.** The `project` field is stored but there's no project layer in the UI.

---

## Suggested Work Streams

### Stream A: Test Hygiene (1-2 days)

1. Migrate `test_run.py` and `test_full_workflow.py` from `db=` to `save_dir=` (kills 96 warnings)
2. Add CLI tests — call command functions directly with mock args, or use Click's test runner
3. Add at minimum one SSE test that verifies a client receives a `run_update` event
4. Add downsampling edge case tests
5. Delete `AGENTS.md~`, add `*.db` and `*~` to `.gitignore`
6. Make log level configurable (env var `STONKS_LOG_LEVEL`, default `INFO`)

### Stream B: Dashboard Metadata & Filtering (2-3 days)

1. Sync `types.ts` `Run` interface to include `group`, `job_type`, `tags`, `notes`
2. Render tags as chips in the runs table
3. Show group and job_type columns (toggleable)
4. Add a notes tooltip or expandable row
5. Add a filter sidebar: status, tags, groups, free-text search
6. Add `DELETE /api/runs/{id}` and `DELETE /api/experiments/{id}` REST endpoints
7. Add delete button in dashboard with confirmation dialog

### Stream C: PyPI Publishing (1 day)

1. Verify `pyproject.toml` metadata (description, classifiers, URLs, license)
2. Set up `trusted publishing` on PyPI via GitHub Actions
3. Add a `release.yml` workflow step that builds and uploads to PyPI on tag push
4. Test with `pip install stonks` from a clean venv

### Stream D: Polish & Adoption (1-2 days)

1. Add screenshots/GIFs to README showing the dashboard
2. Add a `stonks demo` CLI command that seeds sample data for quick evaluation
3. Add URL state so experiment/run selection persists in the browser URL
4. Make the Catppuccin theme configurable or add a light mode toggle

---

## Recommended Priority Order

1. **Stream A** — Fix test debt first. Everything else is riskier without solid test coverage.
2. **Stream B** — Make stored metadata visible. This is the biggest gap between what stonks captures and what users can see.
3. **Stream C** — PyPI publishing. Unlocks adoption beyond "people who git clone".
4. **Stream D** — Polish. Nice to have but not blocking anything.

---

## Open Questions

- Should CLI tests use Click's `CliRunner` or invoke functions directly? (Click runner is more realistic, direct calls are faster to write)
- For filtering, should it be a sidebar panel or inline filter chips above the table?
- Is PyPI the right distribution channel, or would conda-forge also be worth targeting?
- Should `stonks demo` generate realistic-looking training curves, or just random data?
- For URL state, should we use query params (`?exp=foo&run=bar`) or hash routing (`#/experiments/foo/runs/bar`)?
