# Project description

I want to build an app that allows for the easy tracking of machine learning experiments.  

## Start page

# Tech stack

- I want to manage python deps with uv
- I want easy to maintain typescript code for the UI. Use whatever library you want but I want the UI to be lightweight and ultra-responsive. So don't use React.
- I want a logger in pytorch lightning that allows me to log experiments easily. I want also to be able to use the library in a standalone way.

## Maintainability

I want a codebase that is easily maintainable. I want minimal coupling. If a pattern is particularly applicable in this project, apply it, otherwise focus on the functionality over the purity of how those patterns are applied.

## Testing

I want a full `pytest`-based test suite for the python part, and whatever testing is used for the framework you end up choosing. Document that choice here. I want to make extensive use of fixtures, instead of setup and teardowns.

I want to run this test suite on each push and opened PR on github workflows. I also want to have precommit hook to check for uv formatting and ty respecting the project rules.

Keep unit tests under `tests/unit/` and place integration/user-flow tests under `tests/integration/`. Integration tests should simulate user actions (e.g., via `app.run_test()`) and live alongside other integration helpers in that folder.

**Important**: Always run tests (`uv run pytest`) after making any code changes to ensure everything still works correctly.

**Performance**: The test suite must execute in under 20 seconds. To achieve this:
- Mock `_start_refresh_worker` and `check_slurm_available` in tests using `app.run_test()`
- Use `size=(80, 24)` for Textual app tests to reduce rendering overhead
- Avoid `await pilot.pause()` unless absolutely necessary
- Do not add `pytest-timeout` as a band-aid - fix slow tests at the root cause

## Logging

Use loguru for logging in python, and whatever equivalent exists for the UI, I want to use the logs for 1 week. I want the logs to be in a logs/ folders. I want the logs in the standard output and a file. Use f-strings for all log messages (e.g., `logger.info(f"Loaded {count} items")`) instead of loguru's deferred `{}` formatting or `%` style formatting.

## Docstrings

I want to use google-style docstrings.

## Documentation

I want to have mostly self-explanatory code. Use the Readme to show the user how to get started.

## Code structure

I want to have a clear code structure. In the end, I want the main source code for the package repository

## Code style

- **All imports must be hoisted to the top of the file** - no imports inside functions, methods, or conditional blocks. This is enforced by ruff rule PLC0415.

## Agent Auto-run Commands

**CRITICAL: You MUST automatically run these commands after making ANY code changes:**

1. **After editing Python files, ALWAYS run:**
   ```bash
   uv run ruff format .
   uv run ruff check --fix .
   uv run ty check stoei/
   ```

2. **After making ANY changes, ALWAYS run:**
   ```bash
   uv run pytest
   ```

3. **Before completing any task, verify with:**
   ```bash
   uv run ruff format --check .
   uv run ruff check .
   uv run ty check stoei/
   ```

**Do NOT ask the user - just run these commands automatically after code changes.**

## Pull Requests

PR descriptions should contain only a summary of the changes. Do not include a test plan, checklist, or any other sections beyond the summary.

## Commit Attribution

**IMPORTANT**: AI agents (Claude, Cursor, etc.) should NOT add themselves as co-authors in git commits. Do not use `Co-Authored-By` trailers or any other form of AI attribution in commit messages. Commits should only attribute human contributors.
