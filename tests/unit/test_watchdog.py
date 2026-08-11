"""Unit tests for the bridge's self-healing behaviour.

These cover the failure the watchdog exists for: the bridge keeps running and
its logs look normal, but nothing is reaching the MQTT broker any more.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.config import Config
from src.radpro_bridge import (
    EXIT_OK,
    EXIT_SETUP_FAILED,
    EXIT_WATCHDOG_TRIPPED,
    RadProBridge,
)


@pytest.fixture
def bridge(tmp_path):
    """Create a bridge whose device and publisher are fully mocked."""
    config = Config(
        mqtt_host="localhost",
        poll_interval=1,
        watchdog_timeout=10,
        max_consecutive_failures=3,
        health_file=str(tmp_path / "health"),
    )
    bridge = RadProBridge(config=config)
    bridge.device = MagicMock()
    bridge.publisher = MagicMock()
    bridge._device_info = MagicMock(device_id="test-device")
    return bridge


def stub_successful_poll(bridge, *, published: bool = True, acknowledged: bool = True):
    """Make the mocked device return readings and the publisher behave as asked."""
    bridge.device.get_tube_rate.return_value = 25.5
    bridge.device.get_tube_pulse_count.return_value = 1000
    bridge.device.get_battery_voltage.return_value = 1.5
    bridge.device.get_tube_sensitivity.return_value = 153.8
    bridge.device.get_tube_lifetime.return_value = 3600
    bridge.device.get_tube_dead_time.return_value = 200.0
    bridge.device.get_tube_dead_time_compensation.return_value = 0.0
    bridge.device.get_tube_hv_duty_cycle.return_value = 50.0
    bridge.device.get_tube_hv_frequency.return_value = 9000.0
    bridge.publisher.publish_sensor_state.return_value = published
    bridge.publisher.wait_for_delivery.return_value = acknowledged


class TestPollResult:
    """Tests for what poll_and_publish reports back to the polling loop."""

    def test_successful_cycle_is_reported(self, bridge):
        """Test that a delivered cycle reports success."""
        stub_successful_poll(bridge)

        assert bridge.poll_and_publish() is True
        assert bridge._last_successful_publish > 0

    def test_failed_publish_is_not_success(self, bridge):
        """Test that a cycle whose publishes failed is not counted as success."""
        stub_successful_poll(bridge, published=False)

        assert bridge.poll_and_publish() is False

    def test_unacknowledged_publish_is_not_success(self, bridge):
        """Test that data the broker never acknowledged is not success.

        publish() only queues a message. Without waiting for the QoS 1
        acknowledgement, a client that has silently stopped delivering looks
        exactly like a healthy one.
        """
        stub_successful_poll(bridge, acknowledged=False)

        assert bridge.poll_and_publish() is False

    def test_success_requires_broker_acknowledgement(self, bridge):
        """Test that every cycle waits for the broker to confirm delivery."""
        stub_successful_poll(bridge)

        bridge.poll_and_publish()

        bridge.publisher.wait_for_delivery.assert_called_once_with(
            bridge.config.publish_ack_timeout
        )

    def test_failed_read_is_not_success(self, bridge):
        """Test that a device that stops answering is not counted as success."""
        stub_successful_poll(bridge)
        bridge.device.get_tube_rate.return_value = None

        assert bridge.poll_and_publish() is False


class TestPollingLoopRecovery:
    """Tests for recovery from repeated failures inside the polling loop."""

    def test_device_reconnect_after_repeated_failures(self, bridge):
        """Test that repeated failures force a device reconnect.

        A serial port can stay open while the device has stopped answering, so
        waiting for a disconnect that never comes means waiting forever.
        """
        bridge.device.is_connected.return_value = True
        bridge.device.reconnect.return_value = True
        bridge._consecutive_failures = bridge.config.max_consecutive_failures

        bridge._recover_connections()

        bridge.device.reconnect.assert_called_once()
        assert bridge._consecutive_failures == 0

    def test_recovery_refreshes_device_info(self, bridge):
        """Test that device info is refreshed after a successful reconnect."""
        bridge.device.reconnect.return_value = True
        new_info = MagicMock(device_id="new-device")
        bridge.device.get_device_id.return_value = new_info

        bridge._recover_connections()

        assert bridge._device_info is new_info

    def test_recovery_keeps_device_info_when_id_read_fails(self, bridge):
        """Test that a failed ID read does not wipe the known device info."""
        original_info = bridge._device_info
        bridge.device.reconnect.return_value = True
        bridge.device.get_device_id.return_value = None

        bridge._recover_connections()

        assert bridge._device_info is original_info

    def test_device_is_left_alone_while_mqtt_is_down(self, bridge):
        """Test that an MQTT outage does not cycle a healthy USB device.

        The failures are already explained by MQTT, and the client reconnects
        on its own; reopening the serial port would only add churn.
        """
        bridge.publisher.is_connected.return_value = False

        bridge._recover_connections()

        bridge.device.reconnect.assert_not_called()
        assert bridge._consecutive_failures == 0

    def test_recovery_uses_short_retries(self, bridge):
        """Test that recovery does not block the loop for minutes.

        A long backoff here would starve both the polling loop and the
        watchdog that is supposed to notice the bridge is stuck.
        """
        bridge.device.reconnect.return_value = False

        bridge._recover_connections()

        _, kwargs = bridge.device.reconnect.call_args
        assert kwargs["max_retries"] <= 3


class TestWatchdog:
    """Tests for the watchdog that asks for a container restart."""

    def test_exits_when_data_stops_reaching_the_broker(self, bridge):
        """Test that a stalled bridge exits with a restart-worthy code."""
        stub_successful_poll(bridge, acknowledged=False)
        bridge.setup = MagicMock(return_value=True)
        bridge._start_hard_watchdog = MagicMock()
        bridge._sleep_until_next_poll = MagicMock()

        # Last success is already older than the watchdog timeout
        bridge._last_successful_publish = time.time() - 1000

        exit_code = bridge.run()

        assert exit_code == EXIT_WATCHDOG_TRIPPED
        bridge.publisher.disconnect.assert_called_once()

    def test_keeps_running_while_data_flows(self, bridge):
        """Test that a healthy bridge is never restarted by the watchdog."""
        stub_successful_poll(bridge)
        bridge.setup = MagicMock(return_value=True)
        bridge._start_hard_watchdog = MagicMock()
        bridge._last_successful_publish = time.time()

        # Stop the loop after a single cycle
        def stop_after_one_cycle():
            bridge._shutdown_requested = True

        bridge._sleep_until_next_poll = MagicMock(side_effect=stop_after_one_cycle)

        assert bridge.run() == EXIT_OK

    def test_setup_failure_asks_for_a_restart(self, bridge):
        """Test that a failed startup exits non-zero.

        Exiting 0 would leave `restart: on-failure` deployments sitting idle
        with no bridge running.
        """
        bridge.setup = MagicMock(return_value=False)

        assert bridge.run() == EXIT_SETUP_FAILED

    def test_stale_health_file_is_cleared_on_start(self, bridge):
        """Test that a previous run's health file cannot mask a failed start."""
        health_file = bridge.config.health_file
        with open(health_file, "w") as f:
            f.write(f"{time.time()}\n")

        bridge.setup = MagicMock(return_value=False)
        bridge.run()

        import os

        assert not os.path.exists(health_file)

    def test_hard_watchdog_force_exits_a_wedged_bridge(self, bridge):
        """Test that the watchdog thread kills a process that cannot recover.

        The in-loop check only runs while the loop turns; this thread covers a
        main thread that is stuck for good, e.g. in a blocked USB read.
        """
        bridge._last_successful_publish = time.time() - 1000

        with (
            patch("src.radpro_bridge.os._exit") as mock_exit,
            patch("src.radpro_bridge.WATCHDOG_CHECK_INTERVAL", 0.01),
        ):
            bridge._start_hard_watchdog(timeout=10)
            time.sleep(0.2)
            bridge._shutdown_requested = True
            bridge._shutdown_event.set()

        mock_exit.assert_called_with(EXIT_WATCHDOG_TRIPPED)

    def test_hard_watchdog_leaves_a_healthy_bridge_alone(self, bridge):
        """Test that the watchdog thread does not kill a working bridge."""
        bridge._last_successful_publish = time.time()

        with (
            patch("src.radpro_bridge.os._exit") as mock_exit,
            patch("src.radpro_bridge.WATCHDOG_CHECK_INTERVAL", 0.01),
        ):
            bridge._start_hard_watchdog(timeout=10)
            time.sleep(0.2)
            bridge._shutdown_requested = True
            bridge._shutdown_event.set()

        mock_exit.assert_not_called()


class TestReconnectAnnouncement:
    """Tests for re-announcing the device after an MQTT reconnect."""

    def test_discovery_is_republished_after_reconnect(self, bridge):
        """Test that discovery and availability are re-sent on reconnect.

        A broker restart drops retained messages, which otherwise leaves the
        entities stuck as unavailable in Home Assistant.
        """
        bridge._on_mqtt_connected()

        bridge.publisher.publish_discovery.assert_called_once_with(bridge._device_info)
        bridge.publisher.publish_availability.assert_called_once_with("online")

    def test_no_announcement_before_the_device_is_known(self, bridge):
        """Test that nothing is announced before the device has been read."""
        bridge._device_info = None

        bridge._on_mqtt_connected()

        bridge.publisher.publish_discovery.assert_not_called()
