# Stage 1: Build frontend
FROM node:22-slim AS ui-build
WORKDIR /app
COPY ui/ ui/
COPY stonks/server/ stonks/server/
WORKDIR /app/ui
RUN npm install && npm run build

# Stage 2: Python runtime
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --extra server --no-dev --no-install-project

# Copy source code
COPY stonks/ stonks/
COPY README.md ./

# Copy built frontend from stage 1
COPY --from=ui-build /app/stonks/server/static/ stonks/server/static/

# Install the project itself
RUN uv sync --frozen --extra server --no-dev

ENV STONKS_DB=/data/stonks.db
EXPOSE 8000

ENTRYPOINT ["uv", "run", "stonks", "serve", "--host", "0.0.0.0"]
