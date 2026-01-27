"""Unit tests for health check functionality.

Tests the health check file writing functionality in RadProBridge.
"""

import time
from unittest.mock import MagicMock, patch

from src.config import Config
from src.radpro_bridge import RadProBridge


class TestHealthCheck:
    """Test cases for health check functionality."""

    def test_write_health_check_success(self) -> None:
        """Test successful health check file writing.

        Verifies that _write_health_check() creates a file with a timestamp.

        Requirements: 6.6
        """
        # Create mock config with new attributes
        config = MagicMock(spec=Config)
        config.enable_pulse_tracking = False  # Disable to avoid PulseTracker initialization
        config.enable_advanced_sensors = False

        # Create bridge instance
        bridge = RadProBridge(config=config)

        # Patch the health file path
        with patch("builtins.open", create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            # Call _write_health_check
            bridge._write_health_check()

            # Verify file was opened for writing
            mock_open.assert_called_once_with("/tmp/health", "w")

            # Verify timestamp was written
            mock_file.write.assert_called_once()
            written_content = mock_file.write.call_args[0][0]

            # Verify content is a timestamp followed by newline
            assert written_content.endswith("\n")
            timestamp_str = written_content.strip()
            timestamp = float(timestamp_str)

            # Verify timestamp is recent (within last 5 seconds)
            current_time = time.time()
            assert abs(current_time - timestamp) < 5

    def test_write_health_check_error_handling(self) -> None:
        """Test health check error handling.

        Verifies that errors during health check file writing are logged
        but don't crash the application.

        Requirements: 6.6
        """
        # Create mock config with new attributes
        config = MagicMock(spec=Config)
        config.enable_pulse_tracking = False  # Disable to avoid PulseTracker initialization
        config.enable_advanced_sensors = False

        # Create bridge instance
        bridge = RadProBridge(config=config)

        # Patch open to raise an exception
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            # Call _write_health_check - should not raise exception
            bridge._write_health_check()

            # If we get here, the exception was handled correctly

    def test_health_check_called_after_poll(self) -> None:
        """Test that health check is called after successful poll.

        Verifies that _write_health_check() is called after poll_and_publish()
        completes successfully.

        Requirements: 6.6
        """
        # Create mock config with new attributes
        config = MagicMock(spec=Config)
        config.enable_pulse_tracking = False  # Disable to avoid PulseTracker initialization
        config.enable_advanced_sensors = False
        config.sync_device_time = False

        # Create bridge instance
        bridge = RadProBridge(config=config)

        # Set up device info
        bridge._device_info = MagicMock()
        bridge._device_info.device_id = "test-device"

        # Mock device methods to return valid data
        bridge.device.get_tube_rate = MagicMock(return_value=25.5)
        bridge.device.get_tube_pulse_count = MagicMock(return_value=1000)
        bridge.device.get_battery_voltage = MagicMock(return_value=1.5)
        bridge.device.get_tube_sensitivity = MagicMock(return_value=153.8)
        bridge.device.get_tube_lifetime = MagicMock(return_value=3600)

        # Mock publisher methods
        bridge.publisher.publish_sensor_state = MagicMock()

        # Mock _write_health_check
        bridge._write_health_check = MagicMock()

        # Call poll_and_publish
        bridge.poll_and_publish()

        # Verify _write_health_check was called
        bridge._write_health_check.assert_called_once()

    def test_health_check_not_called_on_poll_failure(self) -> None:
        """Test that health check is not called when poll fails.

        Verifies that _write_health_check() is not called if polling fails.

        Requirements: 6.6
        """
        # Create mock config with new attributes
        config = MagicMock(spec=Config)
        config.enable_pulse_tracking = False  # Disable to avoid PulseTracker initialization
        config.enable_advanced_sensors = False
        config.sync_device_time = False

        # Create bridge instance
        bridge = RadProBridge(config=config)

        # Set up device info
        bridge._device_info = MagicMock()
        bridge._device_info.device_id = "test-device"

        # Mock device methods to return None (failure)
        bridge.device.get_tube_rate = MagicMock(return_value=None)

        # Mock _write_health_check
        bridge._write_health_check = MagicMock()

        # Call poll_and_publish
        bridge.poll_and_publish()

        # Verify _write_health_check was NOT called
        bridge._write_health_check.assert_not_called()
