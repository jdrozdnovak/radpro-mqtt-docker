"""Unit tests for health check functionality.

Tests the health check file written by RadProBridge and the container health
check that reads it.
"""

import time
from unittest.mock import MagicMock, patch

from src.config import Config
from src.healthcheck import check_health, read_health_timestamp
from src.radpro_bridge import RadProBridge


def make_config(health_file: str) -> MagicMock:
    """Create a mock Config that is usable by RadProBridge."""
    config = MagicMock(spec=Config)
    config.enable_pulse_tracking = False  # Disable to avoid PulseTracker initialization
    config.enable_advanced_sensors = False
    config.sync_device_time = False
    config.health_file = health_file
    return config


class TestHealthCheck:
    """Test cases for health check functionality."""

    def test_write_health_check_success(self, tmp_path) -> None:
        """Test successful health check file writing.

        Verifies that _write_health_check() creates a file with a timestamp.

        Requirements: 6.6
        """
        health_file = tmp_path / "health"
        bridge = RadProBridge(config=make_config(str(health_file)))

        bridge._write_health_check()

        # Verify content is a recent timestamp followed by a newline
        written_content = health_file.read_text()
        assert written_content.endswith("\n")
        timestamp = float(written_content.strip())
        assert abs(time.time() - timestamp) < 5

    def test_write_health_check_is_atomic(self, tmp_path) -> None:
        """Test that the health file is never left half written.

        The container health check can read the file at any moment, and a
        truncated timestamp would look like a failure.

        Requirements: 6.6
        """
        health_file = tmp_path / "health"
        bridge = RadProBridge(config=make_config(str(health_file)))

        with patch("src.radpro_bridge.os.replace") as mock_replace:
            bridge._write_health_check()

        # The real file is only swapped in once the timestamp is fully written
        mock_replace.assert_called_once_with(f"{health_file}.tmp", str(health_file))
        assert not health_file.exists()

    def test_write_health_check_error_handling(self, tmp_path) -> None:
        """Test health check error handling.

        Verifies that errors during health check file writing are logged
        but don't crash the application.

        Requirements: 6.6
        """
        bridge = RadProBridge(config=make_config(str(tmp_path / "health")))

        # Patch open to raise an exception
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            # Call _write_health_check - should not raise exception
            bridge._write_health_check()

            # If we get here, the exception was handled correctly

    def test_clear_health_check_removes_stale_file(self, tmp_path) -> None:
        """Test that a stale health file from a previous run is removed.

        A restarted container keeps its filesystem, so an old timestamp must
        not make a bridge that never started up look healthy.
        """
        health_file = tmp_path / "health"
        health_file.write_text("1.0\n")
        bridge = RadProBridge(config=make_config(str(health_file)))

        bridge._clear_health_check()

        assert not health_file.exists()

    def test_clear_health_check_without_file(self, tmp_path) -> None:
        """Test that clearing a missing health file is not an error."""
        bridge = RadProBridge(config=make_config(str(tmp_path / "health")))

        bridge._clear_health_check()

    def test_health_check_called_after_poll(self) -> None:
        """Test that health check is called after successful poll.

        Verifies that _write_health_check() is called after poll_and_publish()
        completes successfully.

        Requirements: 6.6
        """
        bridge = RadProBridge(config=make_config("/tmp/health"))

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
        bridge.publisher.publish_sensor_state = MagicMock(return_value=True)
        bridge.publisher.wait_for_delivery = MagicMock(return_value=True)

        # Mock _write_health_check
        bridge._write_health_check = MagicMock()

        # Call poll_and_publish
        assert bridge.poll_and_publish() is True

        # Verify _write_health_check was called
        bridge._write_health_check.assert_called_once()

    def test_health_check_not_called_on_poll_failure(self) -> None:
        """Test that health check is not called when poll fails.

        Verifies that _write_health_check() is not called if polling fails.

        Requirements: 6.6
        """
        bridge = RadProBridge(config=make_config("/tmp/health"))

        # Set up device info
        bridge._device_info = MagicMock()
        bridge._device_info.device_id = "test-device"

        # Mock device methods to return None (failure)
        bridge.device.get_tube_rate = MagicMock(return_value=None)

        # Mock _write_health_check
        bridge._write_health_check = MagicMock()

        # Call poll_and_publish
        assert bridge.poll_and_publish() is False

        # Verify _write_health_check was NOT called
        bridge._write_health_check.assert_not_called()


class TestContainerHealthCheck:
    """Test cases for the health check the container runtime executes."""

    def test_healthy_when_recently_published(self, tmp_path) -> None:
        """Test that a fresh timestamp is reported as healthy."""
        health_file = tmp_path / "health"
        health_file.write_text(f"{time.time()}\n")
        config = Config(mqtt_host="localhost", health_file=str(health_file))

        healthy, reason = check_health(config)

        assert healthy is True
        assert "ago" in reason

    def test_unhealthy_when_data_stopped_flowing(self, tmp_path) -> None:
        """Test that a stale timestamp is reported as unhealthy.

        This is the state the bridge used to sit in indefinitely: process up,
        logs quiet, nothing arriving at the broker.
        """
        health_file = tmp_path / "health"
        config = Config(mqtt_host="localhost", health_file=str(health_file), poll_interval=60)
        stale = time.time() - (config.effective_watchdog_timeout + config.poll_interval + 60)
        health_file.write_text(f"{stale}\n")

        healthy, reason = check_health(config)

        assert healthy is False
        assert "Last successful publish" in reason

    def test_unhealthy_when_file_missing(self, tmp_path) -> None:
        """Test that a bridge which never published is reported as unhealthy."""
        config = Config(mqtt_host="localhost", health_file=str(tmp_path / "missing"))

        healthy, reason = check_health(config)

        assert healthy is False
        assert "has not published yet" in reason

    def test_threshold_follows_poll_interval(self, tmp_path) -> None:
        """Test that a slow polling interval does not report false failures."""
        health_file = tmp_path / "health"
        health_file.write_text(f"{time.time() - 900}\n")
        config = Config(mqtt_host="localhost", health_file=str(health_file), poll_interval=600)

        # 15 minutes of silence is normal with a 10 minute poll interval
        healthy, _ = check_health(config)

        assert healthy is True

    def test_read_timestamp_falls_back_to_mtime(self, tmp_path) -> None:
        """Test that an unparseable health file falls back to its mtime."""
        health_file = tmp_path / "health"
        health_file.write_text("not-a-timestamp")

        timestamp = read_health_timestamp(str(health_file))

        assert timestamp is not None
        assert abs(time.time() - timestamp) < 5

    def test_read_timestamp_for_missing_file(self, tmp_path) -> None:
        """Test that a missing health file yields no timestamp."""
        assert read_health_timestamp(str(tmp_path / "missing")) is None
