"""Min-max decimation for downsampling metric series."""

from __future__ import annotations

from stonks.models import MetricSeries


def downsample_minmax(series: MetricSeries, target_points: int) -> MetricSeries:
    """Downsample a metric series using min-max decimation.

    Preserves the first and last points. For each bucket between them,
    keeps the min and max values to preserve the visual shape of the data.

    Args:
        series: The full-resolution MetricSeries.
        target_points: Desired number of output points.

    Returns:
        A new MetricSeries with at most target_points entries.
    """
    n = len(series.steps)
    if n <= target_points or target_points < 2:
        return series

    result = MetricSeries(key=series.key)

    # Always include first point
    result.steps.append(series.steps[0])
    result.values.append(series.values[0])
    result.timestamps.append(series.timestamps[0])

    # Number of interior buckets (excluding first and last points)
    num_buckets = target_points - 2
    interior_points = n - 2

    if num_buckets > 0 and interior_points > 0:
        bucket_size = interior_points / num_buckets

        for i in range(num_buckets):
            start = int(1 + i * bucket_size)
            end = int(1 + (i + 1) * bucket_size)
            end = min(end, n - 1)

            if start >= end:
                continue

            min_idx = start
            max_idx = start
            min_val = series.values[start]
            max_val = series.values[start]

            for j in range(start, end):
                val = series.values[j]
                if val is None:
                    continue
                if min_val is None or val < min_val:
                    min_val = val
                    min_idx = j
                if max_val is None or val > max_val:
                    max_val = val
                    max_idx = j

            # Add min and max in step order
            if min_idx <= max_idx:
                indices = [min_idx, max_idx]
            else:
                indices = [max_idx, min_idx]

            # Deduplicate if min and max are the same point
            seen = set()
            for idx in indices:
                if idx not in seen:
                    seen.add(idx)
                    result.steps.append(series.steps[idx])
                    result.values.append(series.values[idx])
                    result.timestamps.append(series.timestamps[idx])

    # Always include last point
    result.steps.append(series.steps[-1])
    result.values.append(series.values[-1])
    result.timestamps.append(series.timestamps[-1])

    return result
