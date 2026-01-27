"""Unit tests for PulseTracker class.

Tests the pulse tracking and moving average calculation functionality.
"""

import time

import pytest

from src.pulse_tracker import PulseDataPoint, PulseTracker


class TestPulseDataPoint:
    """Test PulseDataPoint dataclass."""

    def test_pulse_data_point_creation(self) -> None:
        """Test creating a PulseDataPoint."""
        timestamp = time.time()
        pulse_count = 1000

        point = PulseDataPoint(timestamp=timestamp, pulse_count=pulse_count)

        assert point.timestamp == timestamp
        assert point.pulse_count == pulse_count


class TestPulseTrackerInitialization:
    """Test PulseTracker initialization."""

    def test_init_with_default_windows(self) -> None:
        """Test initialization with default time windows."""
        tracker = PulseTracker()

        assert tracker.windows == (1, 5, 15)
        assert tracker.max_history_seconds == 15 * 60 + 60  # 960 seconds
        assert tracker.get_history_size() == 0

    def test_init_with_custom_windows(self) -> None:
        """Test initialization with custom time windows."""
        tracker = PulseTracker(windows=(2, 10, 30))

        assert tracker.windows == (2, 10, 30)
        assert tracker.max_history_seconds == 30 * 60 + 60  # 1860 seconds
        assert tracker.get_history_size() == 0

    def test_init_with_single_window(self) -> None:
        """Test initialization with a single time window."""
        tracker = PulseTracker(windows=(5,))

        assert tracker.windows == (5,)
        assert tracker.max_history_seconds == 5 * 60 + 60  # 360 seconds


class TestPulseTrackerMeasurements:
    """Test adding measurements to PulseTracker."""

    def test_add_single_measurement(self) -> None:
        """Test adding a single measurement."""
        tracker = PulseTracker()
        timestamp = time.time()

        tracker.add_measurement(pulse_count=100, timestamp=timestamp)

        assert tracker.get_history_size() == 1

    def test_add_multiple_measurements(self) -> None:
        """Test adding multiple measurements."""
        tracker = PulseTracker()
        base_time = time.time()

        for i in range(5):
            tracker.add_measurement(pulse_count=100 + i * 10, timestamp=base_time + i * 60)

        assert tracker.get_history_size() == 5

    def test_add_measurement_with_auto_timestamp(self) -> None:
        """Test adding measurement without explicit timestamp."""
        tracker = PulseTracker()

        tracker.add_measurement(pulse_count=100)

        assert tracker.get_history_size() == 1

    def test_history_cleanup(self) -> None:
        """Test that old measurements are removed from history."""
        tracker = PulseTracker(windows=(1,))  # 1-minute window, max history ~120 seconds
        base_time = time.time()

        # Add measurements spanning 5 minutes
        for i in range(10):
            tracker.add_measurement(pulse_count=100 + i * 10, timestamp=base_time + i * 30)

        # Add a recent measurement that triggers cleanup
        tracker.add_measurement(pulse_count=200, timestamp=base_time + 300)

        # Old measurements should be cleaned up
        # Max history is 120 seconds, so measurements older than (base_time + 300 - 120) should be gone
        assert tracker.get_history_size() < 10


class TestMovingAverageCPM:
    """Test moving average CPM calculations."""

    def test_insufficient_data_returns_none(self) -> None:
        """Test that insufficient data returns None."""
        tracker = PulseTracker()

        # No data
        assert tracker.get_moving_average_cpm(5) is None

        # Only one data point
        tracker.add_measurement(pulse_count=100)
        assert tracker.get_moving_average_cpm(5) is None

    def test_simple_moving_average(self) -> None:
        """Test simple moving average calculation."""
        tracker = PulseTracker()
        base_time = time.time()

        # Add two measurements 60 seconds apart with 10 pulse difference
        tracker.add_measurement(pulse_count=100, timestamp=base_time)
        tracker.add_measurement(pulse_count=110, timestamp=base_time + 60)

        # CPM should be (10 pulses / 60 seconds) * 60 = 10 CPM
        cpm = tracker.get_moving_average_cpm(1)
        assert cpm is not None
        assert abs(cpm - 10.0) < 0.1

    def test_moving_average_with_multiple_points(self) -> None:
        """Test moving average with multiple data points."""
        tracker = PulseTracker()
        base_time = time.time()

        # Add measurements every 30 seconds with 5 pulses each
        for i in range(5):
            tracker.add_measurement(pulse_count=100 + i * 5, timestamp=base_time + i * 30)

        # CPM should be (20 pulses / 120 seconds) * 60 = 10 CPM
        cpm = tracker.get_moving_average_cpm(2)
        assert cpm is not None
        assert abs(cpm - 10.0) < 0.1

    def test_moving_average_outside_window(self) -> None:
        """Test moving average when data is outside the window."""
        tracker = PulseTracker()
        base_time = time.time()

        # Add old measurements
        tracker.add_measurement(pulse_count=100, timestamp=base_time - 600)
        tracker.add_measurement(pulse_count=110, timestamp=base_time - 540)

        # Request 1-minute window (60 seconds)
        # No data within the window
        cpm = tracker.get_moving_average_cpm(1)
        assert cpm is None

    def test_moving_average_handles_rollover(self) -> None:
        """Test that negative pulse differences are handled."""
        tracker = PulseTracker()
        base_time = time.time()

        # Add measurements with decreasing pulse count (simulating rollover)
        tracker.add_measurement(pulse_count=100, timestamp=base_time)
        tracker.add_measurement(pulse_count=90, timestamp=base_time + 60)

        # Should return None for negative pulse difference
        cpm = tracker.get_moving_average_cpm(1)
        assert cpm is None


class TestAllMovingAverages:
    """Test getting all moving averages at once."""

    def test_get_all_moving_averages(self) -> None:
        """Test getting all configured moving averages."""
        tracker = PulseTracker(windows=(1, 5, 15))
        base_time = time.time()

        # Add measurements spanning 15 minutes
        for i in range(16):
            tracker.add_measurement(pulse_count=100 + i * 10, timestamp=base_time + i * 60)

        averages = tracker.get_all_moving_averages()

        assert 1 in averages
        assert 5 in averages
        assert 15 in averages

        # All should have values
        assert averages[1] is not None
        assert averages[5] is not None
        assert averages[15] is not None

        # All should be approximately 10 CPM
        assert abs(averages[1] - 10.0) < 0.1
        assert abs(averages[5] - 10.0) < 0.1
        assert abs(averages[15] - 10.0) < 0.1

    def test_get_all_moving_averages_insufficient_data(self) -> None:
        """Test getting all averages with insufficient data."""
        tracker = PulseTracker(windows=(1, 5, 15))

        averages = tracker.get_all_moving_averages()

        assert averages[1] is None
        assert averages[5] is None
        assert averages[15] is None


class TestInstantaneousCPM:
    """Test instantaneous CPM calculation."""

    def test_instantaneous_cpm_insufficient_data(self) -> None:
        """Test instantaneous CPM with insufficient data."""
        tracker = PulseTracker()

        assert tracker.get_instantaneous_cpm() is None

        tracker.add_measurement(pulse_count=100)
        assert tracker.get_instantaneous_cpm() is None

    def test_instantaneous_cpm_calculation(self) -> None:
        """Test instantaneous CPM calculation."""
        tracker = PulseTracker()
        base_time = time.time()

        tracker.add_measurement(pulse_count=100, timestamp=base_time)
        tracker.add_measurement(pulse_count=110, timestamp=base_time + 60)

        cpm = tracker.get_instantaneous_cpm()
        assert cpm is not None
        assert abs(cpm - 10.0) < 0.1

    def test_instantaneous_cpm_handles_rollover(self) -> None:
        """Test instantaneous CPM with negative pulse difference."""
        tracker = PulseTracker()
        base_time = time.time()

        tracker.add_measurement(pulse_count=100, timestamp=base_time)
        tracker.add_measurement(pulse_count=90, timestamp=base_time + 60)

        cpm = tracker.get_instantaneous_cpm()
        assert cpm is None


class TestPulseTrackerUtilities:
    """Test utility methods."""

    def test_clear_history(self) -> None:
        """Test clearing history."""
        tracker = PulseTracker()
        base_time = time.time()

        # Add some measurements
        for i in range(5):
            tracker.add_measurement(pulse_count=100 + i * 10, timestamp=base_time + i * 60)

        assert tracker.get_history_size() == 5

        # Clear history
        tracker.clear()

        assert tracker.get_history_size() == 0

    def test_get_history_duration(self) -> None:
        """Test getting history duration."""
        tracker = PulseTracker()
        base_time = time.time()

        # No data
        assert tracker.get_history_duration() is None

        # One data point
        tracker.add_measurement(pulse_count=100, timestamp=base_time)
        assert tracker.get_history_duration() is None

        # Two data points 120 seconds apart
        tracker.add_measurement(pulse_count=110, timestamp=base_time + 120)
        duration = tracker.get_history_duration()
        assert duration is not None
        assert abs(duration - 120.0) < 0.1

    def test_get_history_size(self) -> None:
        """Test getting history size."""
        tracker = PulseTracker()

        assert tracker.get_history_size() == 0

        tracker.add_measurement(pulse_count=100)
        assert tracker.get_history_size() == 1

        tracker.add_measurement(pulse_count=110)
        assert tracker.get_history_size() == 2


class TestPulseTrackerEdgeCases:
    """Test edge cases and error conditions."""

    def test_very_small_time_difference(self) -> None:
        """Test handling of very small time differences."""
        tracker = PulseTracker()
        base_time = time.time()

        tracker.add_measurement(pulse_count=100, timestamp=base_time)
        tracker.add_measurement(pulse_count=101, timestamp=base_time + 0.01)

        # With 0.01 seconds, time_diff < 1.0 so should return None
        cpm = tracker.get_moving_average_cpm(1)
        assert cpm is None

    def test_zero_pulse_difference(self) -> None:
        """Test handling of zero pulse difference."""
        tracker = PulseTracker()
        base_time = time.time()

        tracker.add_measurement(pulse_count=100, timestamp=base_time)
        tracker.add_measurement(pulse_count=100, timestamp=base_time + 60)

        # Should return 0 CPM
        cpm = tracker.get_moving_average_cpm(1)
        assert cpm is not None
        assert abs(cpm - 0.0) < 0.1

    def test_large_pulse_count(self) -> None:
        """Test handling of large pulse counts."""
        tracker = PulseTracker()
        base_time = time.time()

        tracker.add_measurement(pulse_count=1000000, timestamp=base_time)
        tracker.add_measurement(pulse_count=1001000, timestamp=base_time + 60)

        # Should calculate correctly: (1000 pulses / 60 seconds) * 60 = 1000 CPM
        cpm = tracker.get_moving_average_cpm(1)
        assert cpm is not None
        assert abs(cpm - 1000.0) < 0.1
