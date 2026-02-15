# REST API Reference

The stonks server exposes a REST API at `/api`. All endpoints return JSON.

## Experiments

### List Experiments

```
GET /api/experiments
```

Returns all experiments with their run counts.

**Response:**

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "resnet-cifar10",
    "description": null,
    "created_at": 1700000000.0,
    "run_count": 3
  }
]
```

### Get Experiment

```
GET /api/experiments/{experiment_id}
```

**Response:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "resnet-cifar10",
  "description": null,
  "created_at": 1700000000.0,
  "run_count": 3
}
```

**Errors:** `404` if experiment not found.

## Runs

### List Runs for Experiment

```
GET /api/experiments/{experiment_id}/runs
```

Returns all runs for the specified experiment, ordered by creation time (newest first).

**Response:**

```json
[
  {
    "id": "run-uuid",
    "experiment_id": "exp-uuid",
    "name": "lr=0.01",
    "status": "completed",
    "config": {"lr": 0.01, "batch_size": 128},
    "created_at": 1700000000.0,
    "ended_at": 1700003600.0,
    "last_heartbeat": 1700003600.0
  }
]
```

### Get Run

```
GET /api/runs/{run_id}
```

**Response:** Same shape as a single run in the list above.

**Errors:** `404` if run not found.

## Metrics

### List Metric Keys

```
GET /api/runs/{run_id}/metric-keys
```

Returns all metric keys logged for a run.

**Response:**

```json
["train/loss", "train/accuracy", "val/loss", "val/accuracy"]
```

**Errors:** `404` if run not found.

### Get Metric Series

```
GET /api/runs/{run_id}/metrics?key={metric_key}&downsample={n}
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `key` | string | yes | Metric key to retrieve |
| `downsample` | integer | no | Target number of data points (min: 2) |

**Response:**

```json
{
  "key": "train/loss",
  "steps": [0, 1, 2, 3, 4],
  "values": [2.3, 1.8, 1.2, 0.9, 0.7],
  "timestamps": [1700000000.0, 1700000001.0, 1700000002.0, 1700000003.0, 1700000004.0]
}
```

When `downsample` is provided, the series is reduced to approximately that many points using a min-max decimation algorithm that preserves peaks and valleys.

**Errors:** `404` if run not found.

## Server-Sent Events (SSE)

### Stream Events

```
GET /api/events?experiment_id={experiment_id}
```

Opens a persistent SSE connection for real-time updates. The server sends two event types:

**`run_update`** — when a run changes status:

```json
{
  "run_id": "run-uuid",
  "status": "completed",
  "name": "lr=0.01",
  "created_at": 1700000000.0,
  "ended_at": 1700003600.0
}
```

**`metrics_update`** — when a running run has new data:

```json
{
  "run_id": "run-uuid",
  "last_heartbeat": 1700003600.0
}
```

On receiving a `metrics_update`, clients should refetch metrics via the REST API.
