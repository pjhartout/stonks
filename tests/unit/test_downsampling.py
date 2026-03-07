"""Tests for min-max downsampling of metric series."""

from stonks.models import MetricSeries
from stonks.server.downsampling import downsample_minmax


def _make_series(values, key="loss"):
    """Create a MetricSeries with sequential steps and timestamps."""
    series = MetricSeries(key=key)
    for i, v in enumerate(values):
        series.steps.append(i)
        series.values.append(v)
        series.timestamps.append(float(i))
    return series


class TestDownsampleMinmax:
    def test_empty_series(self):
        """Empty series returns empty series."""
        series = MetricSeries(key="loss")
        result = downsample_minmax(series, target_points=10)
        assert result.key == "loss"
        assert result.steps == []
        assert result.values == []
        assert result.timestamps == []

    def test_single_data_point(self):
        """Single point series is returned as-is."""
        series = _make_series([1.0])
        result = downsample_minmax(series, target_points=10)
        assert result.steps == [0]
        assert result.values == [1.0]

    def test_all_none_values(self):
        """Series with all None values is handled without error."""
        series = _make_series([None, None, None, None, None])
        result = downsample_minmax(series, target_points=3)
        # Should not raise and should include first and last points
        assert len(result.steps) >= 2
        assert result.steps[0] == 0
        assert result.steps[-1] == 4

    def test_target_points_less_than_two(self):
        """target_points < 2 returns the original series unchanged."""
        series = _make_series([1.0, 2.0, 3.0])
        result = downsample_minmax(series, target_points=1)
        assert result.steps == series.steps
        assert result.values == series.values

    def test_target_points_zero(self):
        """target_points == 0 returns the original series."""
        series = _make_series([1.0, 2.0, 3.0])
        result = downsample_minmax(series, target_points=0)
        assert result.steps == series.steps

    def test_target_points_equals_two(self):
        """target_points == 2 returns first and last points only."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        series = _make_series(values)
        result = downsample_minmax(series, target_points=2)
        assert result.steps == [0, 4]
        assert result.values == [1.0, 5.0]

    def test_series_smaller_than_target(self):
        """Series with fewer points than target is returned as-is."""
        series = _make_series([1.0, 2.0, 3.0])
        result = downsample_minmax(series, target_points=10)
        assert result.steps == series.steps
        assert result.values == series.values

    def test_minmax_preservation(self):
        """Downsampling preserves min and max values from each bucket."""
        # Create series with clear min/max pattern
        values = [0.0, 10.0, 1.0, 9.0, 2.0, 8.0, 3.0, 7.0, 4.0, 6.0]
        series = _make_series(values)
        result = downsample_minmax(series, target_points=4)

        # First and last points always preserved
        assert result.steps[0] == 0
        assert result.values[0] == 0.0
        assert result.steps[-1] == 9
        assert result.values[-1] == 6.0

        # The result should contain min and max from interior buckets
        result_values = set(result.values)
        # The overall min (0.0) and max (10.0) should be in the result
        assert 0.0 in result_values

    def test_bucket_deduplication(self):
        """When min and max are the same point, it appears only once."""
        # All same values in interior - min_idx == max_idx
        values = [1.0, 5.0, 5.0, 5.0, 5.0, 5.0, 10.0]
        series = _make_series(values)
        result = downsample_minmax(series, target_points=4)

        # First and last are always included
        assert result.steps[0] == 0
        assert result.steps[-1] == 6

        # Interior points should be deduplicated (no repeated indices)
        assert len(result.steps) == len(set(result.steps))

    def test_preserves_key(self):
        """Downsampled series has the same key."""
        series = _make_series([1.0, 2.0, 3.0, 4.0, 5.0], key="train/loss")
        result = downsample_minmax(series, target_points=3)
        assert result.key == "train/loss"

    def test_timestamps_preserved(self):
        """Downsampled series has corresponding timestamps."""
        series = _make_series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = downsample_minmax(series, target_points=3)
        # Each step should have a matching timestamp
        assert len(result.steps) == len(result.timestamps)
        for step, ts in zip(result.steps, result.timestamps):
            # Our test timestamps equal step values
            assert ts == float(step)

    def test_large_series_reduces_size(self):
        """Large series is reduced to approximately target_points."""
        values = [float(i) for i in range(1000)]
        series = _make_series(values)
        result = downsample_minmax(series, target_points=20)

        # Should be significantly smaller than original
        assert len(result.steps) < 100
        assert len(result.steps) > 0
        # First and last always present
        assert result.steps[0] == 0
        assert result.steps[-1] == 999
