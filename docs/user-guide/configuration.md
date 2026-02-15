# Configuration

## Database Path Resolution

stonks resolves the database path with the following priority:

1. **Explicit parameter** — `stonks.start_run(..., db="/path/to/db")`
2. **Environment variable** — `STONKS_DB=/path/to/db`
3. **Default** — `./stonks.db` in the current working directory

This applies to `stonks.start_run()`, `stonks.open()`, and `stonks serve --db`.

## Environment Variables

`STONKS_DB`
: Path to the SQLite database file. Useful for setting a shared database location across training scripts.

```bash
export STONKS_DB=/shared/data/experiments.db
python train.py  # uses /shared/data/experiments.db
stonks serve     # serves /shared/data/experiments.db
```

## SQLite Configuration

stonks uses SQLite with the following optimizations:

- **WAL mode** — enables concurrent readers and a single writer without blocking
- **`synchronous=NORMAL`** — faster writes with minimal risk of corruption
- **Foreign keys enabled** — referential integrity enforced
- **64 MB page cache** — keeps frequently accessed data in memory
- **Temp store in memory** — temporary tables stored in RAM

These settings are applied automatically. No user configuration is needed.

## Logging

stonks uses [loguru](https://github.com/Delgan/loguru) for logging. Logs are written to both stdout and a rotating log file:

- **Log directory**: `./logs/`
- **Rotation**: 10 MB per file
- **Retention**: 1 week
- **Format**: `{time} | {level} | {name}:{function}:{line} - {message}`

Log output is configured automatically when using the SDK or CLI.
