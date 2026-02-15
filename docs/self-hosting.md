# Self-Hosting

stonks is designed to be self-hosted. The dashboard is a single Python process serving a static frontend — no external databases, message queues, or containers required.

## Quick Start

```bash
uv sync --extra server
stonks serve --db ./experiments.db
# Dashboard at http://127.0.0.1:8000
```

## Deployment Options

### Bare Metal / VM

Install stonks and run with uvicorn directly:

```bash
uv sync --extra server
uvicorn stonks.server.app:create_app --factory --host 0.0.0.0 --port 8000
```

Set the database path via environment variable:

```bash
export STONKS_DB=/data/experiments.db
uvicorn stonks.server.app:create_app --factory --host 0.0.0.0 --port 8000
```

### systemd Service

Create `/etc/systemd/system/stonks.service`:

```ini
[Unit]
Description=stonks experiment dashboard
After=network.target

[Service]
User=stonks
Environment=STONKS_DB=/data/experiments.db
ExecStart=/usr/local/bin/uvicorn stonks.server.app:create_app --factory --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now stonks
```

### Docker

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY . /app
WORKDIR /app
RUN uv sync --extra server --no-dev
EXPOSE 8000
ENV STONKS_DB=/data/stonks.db
CMD ["uv", "run", "uvicorn", "stonks.server.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:

```bash
docker build -t stonks .
docker run -d \
  -v /path/to/data:/data \
  -p 8000:8000 \
  stonks
```

Mount the directory containing your `stonks.db` file as a volume so the container can access it.

### Reverse Proxy (nginx)

If you're running stonks behind nginx, configure it to pass through SSE connections correctly:

```nginx
server {
    listen 80;
    server_name stonks.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SSE endpoint requires unbuffered proxying
    location /api/events {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header X-Accel-Buffering no;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
}
```

The key settings for SSE are:
- `proxy_buffering off` — prevents nginx from buffering the event stream
- `X-Accel-Buffering: no` — disables buffering at the application level
- `Connection: ''` — ensures the connection stays open

## Shared Team Usage

Multiple training scripts can write to the same SQLite database simultaneously. stonks uses WAL (Write-Ahead Logging) mode, which allows concurrent readers and a single writer without blocking.

### Setup

1. Store the database on a shared filesystem (NFS, CIFS, etc.):

   ```bash
   export STONKS_DB=/shared/ml/experiments.db
   ```

2. Point all training scripts to the same database:

   ```python
   import stonks

   with stonks.start_run("my-exp", db="/shared/ml/experiments.db") as run:
       run.log({"loss": 0.5})
   ```

3. Run the dashboard on a team-accessible machine:

   ```bash
   stonks serve --db /shared/ml/experiments.db --host 0.0.0.0
   ```

4. Access from any machine: `http://your-server:8000`

### Considerations

- **NFS/network filesystems**: SQLite works on network filesystems but performance may vary. For best results, run the dashboard server on the same machine as the database file.
- **Concurrent writes**: WAL mode handles concurrent writes well, but extremely high write rates from many processes may cause occasional `SQLITE_BUSY` errors. stonks uses a 10-second timeout to handle this.
- **Database size**: SQLite handles databases up to several GB easily. For very large experiments (millions of data points), consider using the `downsample` parameter in the REST API.
