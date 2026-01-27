"""Pulse tracking and moving average calculation for RadPro MQTT Bridge.

This module provides the PulseTracker class for tracking pulse count deltas
over time and calculating moving average CPM values.
"""

import logging
import time
from collections import deque
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PulseDataPoint:
    """A single pulse count measurement with timestamp.

    Attributes:
        timestamp: Unix timestamp when measurement was taken
        pulse_count: Total pulse count at this timestamp
    """

    timestamp: float
    pulse_count: int


class PulseTracker:
    """Tracks pulse counts over time and calculates moving averages.

    This class maintains a history of pulse count measurements and calculates
    CPM (counts per minute) over various time windows using moving averages.
    This provides more responsive and accurate radiation measurements compared
    to the device's internal averaging.

    Attributes:
        windows: Tuple of time windows in minutes for moving averages
        max_history_seconds: Maximum history to retain (seconds)
    """

    def __init__(self, windows: tuple[int, ...] = (1, 5, 15)):
        """Initialize PulseTracker with specified time windows.

        Args:
            windows: Tuple of time windows in minutes for calculating moving averages
        """
        self.windows = windows
        self.max_history_seconds = max(windows) * 60 + 60  # Longest window + buffer
        self._history: deque[PulseDataPoint] = deque()

        logger.info(f"PulseTracker initialized with windows: {windows} minutes")

    def add_measurement(self, pulse_count: int, timestamp: float | None = None) -> None:
        """Add a new pulse count measurement.

        Args:
            pulse_count: Total pulse count from device
            timestamp: Unix timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = time.time()

        data_point = PulseDataPoint(timestamp=timestamp, pulse_count=pulse_count)
        self._history.append(data_point)

        # Clean up old data points beyond max history
        cutoff_time = timestamp - self.max_history_seconds
        while self._history and self._history[0].timestamp < cutoff_time:
            self._history.popleft()

        logger.debug(
            f"Added pulse measurement: count={pulse_count}, " f"history_size={len(self._history)}"
        )

    def get_moving_average_cpm(self, window_minutes: int) -> float | None:
        """Calculate moving average CPM for a specific time window.

        Args:
            window_minutes: Time window in minutes

        Returns:
            Moving average CPM, or None if insufficient data
        """
        if len(self._history) < 2:
            logger.debug(f"Insufficient data for {window_minutes}min average (need 2+ points)")
            return None

        current_time = time.time()
        window_seconds = window_minutes * 60
        cutoff_time = current_time - window_seconds

        # Find the oldest data point within the window
        oldest_in_window: PulseDataPoint | None = None
        for point in self._history:
            if point.timestamp >= cutoff_time:
                oldest_in_window = point
                break

        if oldest_in_window is None:
            logger.debug(f"No data points within {window_minutes}min window")
            return None

        # Get the most recent data point
        newest = self._history[-1]

        # Calculate time difference and pulse difference
        time_diff = newest.timestamp - oldest_in_window.timestamp
        pulse_diff = newest.pulse_count - oldest_in_window.pulse_count

        # Need at least some time difference to calculate rate
        if time_diff < 1.0:
            logger.debug(f"Time difference too small for {window_minutes}min average")
            return None

        # Handle pulse count rollover (unlikely but possible)
        if pulse_diff < 0:
            logger.warning(
                f"Pulse count decreased (rollover?): "
                f"{oldest_in_window.pulse_count} -> {newest.pulse_count}"
            )
            return None

        # Calculate CPM: (pulses / seconds) * 60
        cpm = (pulse_diff / time_diff) * 60.0

        logger.debug(
            f"Calculated {window_minutes}min average: {cpm:.2f} CPM "
            f"(delta={pulse_diff} over {time_diff:.1f}s)"
        )

        return cpm

    def get_all_moving_averages(self) -> dict[int, float | None]:
        """Calculate moving average CPM for all configured windows.

        Returns:
            Dictionary mapping window size (minutes) to CPM value
        """
        averages = {}
        for window in self.windows:
            averages[window] = self.get_moving_average_cpm(window)

        return averages

    def get_instantaneous_cpm(self) -> float | None:
        """Calculate instantaneous CPM from the last two measurements.

        This provides the most responsive measurement but is also the noisiest.

        Returns:
            Instantaneous CPM, or None if insufficient data
        """
        if len(self._history) < 2:
            return None

        # Use last two points
        older = self._history[-2]
        newer = self._history[-1]

        time_diff = newer.timestamp - older.timestamp
        pulse_diff = newer.pulse_count - older.pulse_count

        if time_diff < 0.1:  # Avoid division by very small numbers
            return None

        if pulse_diff < 0:
            logger.warning("Pulse count decreased between last two measurements")
            return None

        cpm = (pulse_diff / time_diff) * 60.0
        return cpm

    def clear(self) -> None:
        """Clear all historical data."""
        self._history.clear()
        logger.info("Pulse tracker history cleared")

    def get_history_size(self) -> int:
        """Get the number of data points in history.

        Returns:
            Number of stored data points
        """
        return len(self._history)

    def get_history_duration(self) -> float | None:
        """Get the time span of stored history in seconds.

        Returns:
            Duration in seconds, or None if insufficient data
        """
        if len(self._history) < 2:
            return None

        return self._history[-1].timestamp - self._history[0].timestamp
