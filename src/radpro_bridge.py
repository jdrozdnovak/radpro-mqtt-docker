"""Main application orchestrator for RadPro MQTT Bridge.

This module provides the RadProBridge class that orchestrates all components
of the bridge application, including USB serial communication, MQTT publishing,
pulse tracking, and the main polling loop.
"""

import logging
import os
import signal
import threading
import time
from datetime import datetime

from src.config import Config
from src.models import DeviceInfo, RadiationMeasurement
from src.mqtt_publisher import MQTTPublisher
from src.pulse_tracker import PulseTracker
from src.radpro_device import RadProDevice

logger = logging.getLogger(__name__)

# Process exit codes. Anything non-zero tells the container supervisor
# (docker restart policy / systemd) to restart the bridge.
EXIT_OK = 0
EXIT_SETUP_FAILED = 1
EXIT_WATCHDOG_TRIPPED = 2

# Retries used when recovering the device mid-run. Deliberately small: a
# recovery attempt that blocks for minutes would starve the polling loop and
# the watchdog, and the next cycle retries anyway.
RECOVERY_RETRIES = 2

# How often the hard watchdog thread checks for progress, and how much longer
# than the polling-loop watchdog it waits before force-exiting the process.
WATCHDOG_CHECK_INTERVAL = 15.0
HARD_WATCHDOG_FACTOR = 2


class RadProBridge:
    """Main application class that orchestrates the RadPro MQTT Bridge.

    This class manages the lifecycle of the bridge application, coordinating
    between the RadPro device, MQTT publisher, and the main polling loop.

    Attributes:
        config: Configuration object with all application settings
        device: RadProDevice instance for USB serial communication
        publisher: MQTTPublisher instance for MQTT operations
    """

    def __init__(self, config: Config):
        """Initialize RadProBridge with configuration.

        Creates instances of Config, RadProDevice, MQTTPublisher, and optionally
        PulseTracker components. The components are not connected until setup() is called.

        Args:
            config: Configuration object containing all application settings

        Requirements: 6.1
        """
        self.config = config
        self._device_info: DeviceInfo | None = None
        self._shutdown_requested = False
        # Set alongside _shutdown_requested so sleeping threads wake up at
        # once instead of running out their timeout
        self._shutdown_event = threading.Event()
        self._last_time_sync: float = 0.0
        self._last_successful_publish: float = 0.0
        self._consecutive_failures = 0

        # Create RadProDevice instance (Requirement 6.1)
        self.device = RadProDevice(
            device_path=config.device_path,
            baudrate=config.serial_baudrate,
            timeout=config.serial_timeout,
        )

        # Create MQTTPublisher instance (Requirement 6.1)
        self.publisher = MQTTPublisher(config=config)

        # Create PulseTracker if enabled
        self.pulse_tracker: PulseTracker | None = None
        if config.enable_pulse_tracking:
            self.pulse_tracker = PulseTracker(windows=config.pulse_tracking_windows)
            logger.info(f"Pulse tracking enabled with windows: {config.pulse_tracking_windows}")

        logger.info("RadProBridge initialized")
        logger.debug(
            f"Configuration: device={config.device_path}, "
            f"mqtt_host={config.mqtt_host}:{config.mqtt_port}, "
            f"poll_interval={config.poll_interval}s, "
            f"advanced_sensors={config.enable_advanced_sensors}, "
            f"pulse_tracking={config.enable_pulse_tracking}"
        )

    def setup(self) -> bool:
        """Initialize USB and MQTT connections.

        Performs the complete setup sequence:
        1. Connect to RadPro device
        2. Retrieve device information
        3. Connect to MQTT broker
        4. Publish discovery payloads
        5. Publish online availability

        Returns:
            bool: True if setup successful, False otherwise

        Requirements: 1.1, 1.2, 3.1, 3.2, 4.1, 5.1
        """
        logger.info("Starting bridge setup...")

        # Step 1: Connect to RadPro device (Requirements 1.1, 1.2)
        logger.info("Connecting to RadPro device...")
        if not self.device.connect():
            logger.error("Failed to connect to RadPro device")
            return False

        # Step 2: Retrieve device information (Requirement 5.1)
        logger.info("Retrieving device information...")
        self._device_info = self.device.get_device_id()
        if self._device_info is None:
            logger.error("Failed to retrieve device information")
            self.device.disconnect()
            return False

        logger.info(
            f"Device connected: {self._device_info.hardware_id} "
            f"(ID: {self._device_info.device_id}, "
            f"SW: {self._device_info.software_id})"
        )

        # Step 2.5: Sync device time if enabled
        if self.config.sync_device_time:
            logger.info("Synchronizing device time...")
            if self.device.sync_time():
                self._last_time_sync = time.time()
                logger.info("Device time synchronized successfully")
            else:
                logger.warning("Failed to sync device time, continuing anyway")

        # Step 3: Connect to MQTT broker (Requirement 3.1)
        logger.info("Connecting to MQTT broker...")

        # Configure Last Will and Testament before connecting
        self.publisher.set_last_will()

        if not self.publisher.connect():
            logger.error("Failed to connect to MQTT broker")
            self.device.disconnect()
            return False

        # Step 4: Publish discovery payloads (Requirement 4.1)
        logger.info("Publishing Home Assistant discovery payloads...")
        self.publisher.publish_discovery(self._device_info)

        # Step 5: Publish online availability (Requirement 3.2)
        logger.info("Publishing online availability status...")
        self.publisher.publish_availability("online")

        # Step 6: From now on, re-announce the device after every reconnect.
        # Registered here (rather than in __init__) so the initial announcement
        # above isn't duplicated by the callback for the first connection.
        self.publisher.on_connected = self._on_mqtt_connected

        # Give the watchdog a starting point: setup succeeded just now
        self._last_successful_publish = time.time()

        logger.info("Bridge setup completed successfully")
        return True

    def _on_mqtt_connected(self) -> None:
        """Re-announce the device after the MQTT connection is re-established.

        Called from the MQTT network thread. Retained discovery and
        availability messages are lost if the broker restarts without
        persistence, which leaves Home Assistant showing the sensors as
        unavailable even though the bridge is publishing again.

        Must not wait for broker acknowledgements: this runs on the thread that
        would have to process them.
        """
        if self._device_info is None:
            return

        logger.info("MQTT reconnected, re-publishing discovery and availability")
        self.publisher.publish_discovery(self._device_info)
        self.publisher.publish_availability("online")

    def poll_and_publish(self) -> bool:
        """Poll device and publish sensor data to MQTT.

        Polls all sensors from the RadPro device, creates a RadiationMeasurement
        object, and publishes sensor states to MQTT. Individual sensor failures
        are handled gracefully - if one sensor fails, the others are still published.

        Returns:
            bool: True only if the core measurements were published *and*
                acknowledged by the broker. This is the signal the watchdog
                uses, so it must never report success for data that did not
                actually leave the process.

        Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.3
        """
        if self._device_info is None:
            logger.error("Cannot poll: device information not available")
            return False

        logger.debug("Starting sensor polling cycle...")

        # Check if time sync is needed
        if self.config.sync_device_time and self.config.time_sync_interval > 0:
            time_since_sync = time.time() - self._last_time_sync
            if time_since_sync >= self.config.time_sync_interval:
                logger.info("Periodic time sync triggered")
                if self.device.sync_time():
                    self._last_time_sync = time.time()
                    logger.info("Device time re-synchronized")

        # Poll core sensors (Requirements 2.2, 2.3, 2.4, 2.6)
        tube_rate = self.device.get_tube_rate()
        if tube_rate is None:
            logger.warning("Failed to get tube rate, skipping this polling cycle")
            return False

        tube_pulse_count = self.device.get_tube_pulse_count()
        if tube_pulse_count is None:
            logger.warning("Failed to get tube pulse count, skipping this polling cycle")
            return False

        battery_voltage = self.device.get_battery_voltage()
        if battery_voltage is None:
            logger.warning("Failed to get battery voltage, skipping this polling cycle")
            return False

        tube_sensitivity = self.device.get_tube_sensitivity()
        if tube_sensitivity is None:
            logger.warning("Failed to get tube sensitivity, skipping this polling cycle")
            return False

        tube_lifetime = self.device.get_tube_lifetime()
        if tube_lifetime is None:
            logger.warning("Failed to get tube lifetime, using 0 as default")
            tube_lifetime = 0

        # Poll advanced sensors if enabled
        tube_dead_time = None
        tube_dead_time_compensation = None
        tube_hv_duty_cycle = None
        tube_hv_frequency = None

        if self.config.enable_advanced_sensors:
            tube_dead_time = self.device.get_tube_dead_time()
            tube_dead_time_compensation = self.device.get_tube_dead_time_compensation()
            tube_hv_duty_cycle = self.device.get_tube_hv_duty_cycle()
            tube_hv_frequency = self.device.get_tube_hv_frequency()

        # Update pulse tracker and get moving averages
        cpm_1min = None
        cpm_5min = None
        cpm_15min = None

        if self.pulse_tracker is not None:
            self.pulse_tracker.add_measurement(tube_pulse_count)
            averages = self.pulse_tracker.get_all_moving_averages()

            # Map window sizes to variables
            for window, cpm in averages.items():
                if window == 1:
                    cpm_1min = cpm
                elif window == 5:
                    cpm_5min = cpm
                elif window == 15:
                    cpm_15min = cpm

        # Create RadiationMeasurement object (Requirement 2.5)
        measurement = RadiationMeasurement(
            timestamp=datetime.now(),
            tube_rate=tube_rate,
            tube_pulse_count=tube_pulse_count,
            battery_voltage=battery_voltage,
            tube_sensitivity=tube_sensitivity,
            tube_lifetime=tube_lifetime,
            tube_dead_time=tube_dead_time,
            tube_dead_time_compensation=tube_dead_time_compensation,
            tube_hv_duty_cycle=tube_hv_duty_cycle,
            tube_hv_frequency=tube_hv_frequency,
            cpm_1min=cpm_1min,
            cpm_5min=cpm_5min,
            cpm_15min=cpm_15min,
        )

        # Log the measurement
        logger.info(
            f"Measurement: dose_rate={measurement.dose_rate:.3f} µSv/h, "
            f"cpm={measurement.tube_rate:.1f}, "
            f"battery={measurement.battery_voltage:.2f}V"
        )

        # Publish core sensor states to MQTT (Requirement 3.3)
        core_published = [
            self._publish_sensor_safe("dose_rate", measurement.dose_rate),
            self._publish_sensor_safe("cpm", measurement.tube_rate),
            self._publish_sensor_safe("total_pulses", measurement.tube_pulse_count),
            self._publish_sensor_safe("battery_voltage", measurement.battery_voltage),
            self._publish_sensor_safe("tube_lifetime", measurement.tube_lifetime),
        ]

        # Publish advanced sensors if enabled and available
        if self.config.enable_advanced_sensors:
            if tube_dead_time is not None:
                self._publish_sensor_safe("tube_dead_time", tube_dead_time)
            if tube_dead_time_compensation is not None:
                self._publish_sensor_safe(
                    "tube_dead_time_compensation", tube_dead_time_compensation
                )
            if tube_hv_duty_cycle is not None:
                self._publish_sensor_safe("hv_duty_cycle", tube_hv_duty_cycle)
            if tube_hv_frequency is not None:
                self._publish_sensor_safe("hv_frequency", tube_hv_frequency)

        # Publish moving averages if available
        if self.config.enable_pulse_tracking:
            if cpm_1min is not None:
                self._publish_sensor_safe("cpm_1min", cpm_1min)
            if cpm_5min is not None:
                self._publish_sensor_safe("cpm_5min", cpm_5min)
            if cpm_15min is not None:
                self._publish_sensor_safe("cpm_15min", cpm_15min)

        logger.debug("Sensor polling cycle completed")

        if not all(core_published):
            logger.warning("Core sensor values could not be published to MQTT")
            return False

        # A successful publish() only means the message was queued. Wait for
        # the broker to acknowledge it, otherwise a dead network thread or a
        # black-holed socket would still look like a healthy cycle.
        if not self.publisher.wait_for_delivery(self.config.publish_ack_timeout):
            logger.warning("MQTT broker did not acknowledge this cycle's data")
            return False

        # Record the successful cycle (Requirement 6.6)
        self._last_successful_publish = time.time()
        self._write_health_check()
        return True

    def _publish_sensor_safe(self, sensor_name: str, value: float | int) -> bool:
        """Safely publish a sensor value, handling errors gracefully.

        Args:
            sensor_name: Name of the sensor
            value: Sensor value to publish

        Returns:
            bool: True if the value was accepted for delivery
        """
        try:
            return bool(self.publisher.publish_sensor_state(sensor_name, value))
        except Exception as e:
            logger.error(f"Failed to publish {sensor_name}: {e}")
            return False

    def _write_health_check(self) -> None:
        """Write health check timestamp to file.

        Writes the current timestamp to the health file after each successful
        publish. This file is used by the Docker health check to verify the
        bridge is still delivering data.

        The file is written atomically so a health check that runs mid-write
        never sees a truncated timestamp.

        Requirements: 6.6
        """
        path = self.config.health_file
        try:
            timestamp = time.time()
            tmp_path = f"{path}.tmp"
            with open(tmp_path, "w") as f:
                f.write(f"{timestamp}\n")
            os.replace(tmp_path, path)
            logger.debug(f"Health check file updated: {timestamp}")
        except Exception as e:
            logger.warning(f"Failed to write health check file: {e}")

    def _clear_health_check(self) -> None:
        """Remove a stale health file left behind by a previous run.

        A restarted container keeps its filesystem, so an old timestamp must
        not be able to make a bridge that never finished starting up look
        healthy.
        """
        try:
            os.unlink(self.config.health_file)
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Failed to remove stale health check file: {e}")

    def _recover_connections(self) -> None:
        """Try to recover after repeated polling failures.

        A USB serial port can stay open while the device has stopped answering,
        so the port being "connected" is not evidence that it works - force a
        reconnect instead of trusting is_connected().
        """
        logger.warning(
            f"{self._consecutive_failures} consecutive failed cycles, "
            "attempting to recover connections"
        )

        # Reset first, so recovery runs periodically rather than on every
        # single cycle. The watchdog is the backstop if it never succeeds.
        self._consecutive_failures = 0

        if not self.publisher.is_connected():
            # The failures are explained by MQTT, which reconnects on its own.
            # Cycling the serial port here would only add churn to a device
            # that is working fine.
            logger.warning("MQTT is disconnected; waiting for its automatic reconnect")
            return

        if self.device.reconnect(
            max_retries=RECOVERY_RETRIES,
            backoff_base=self.config.retry_backoff_base,
        ):
            logger.info("Device reconnected successfully")
            device_info = self.device.get_device_id()
            if device_info is not None:
                self._device_info = device_info
            else:
                logger.error("Device reconnected but did not return its device ID")
        else:
            logger.error("Failed to reconnect to device")

    def _start_hard_watchdog(self, timeout: float) -> None:
        """Start a daemon thread that force-exits a wedged process.

        The watchdog check in the polling loop only runs if the loop is still
        turning. It cannot help when the main thread is stuck for good - a USB
        read blocked in the kernel after a controller glitch, or a lock held by
        a thread that died. This thread has no such dependency: it force-exits
        the process so the container supervisor restarts it, and the MQTT Last
        Will tells Home Assistant the bridge went offline.

        Args:
            timeout: Seconds without a successful publish before force-exiting
        """

        def _watch() -> None:
            while not self._shutdown_requested:
                if self._shutdown_event.wait(WATCHDOG_CHECK_INTERVAL):
                    return

                stalled_for = time.time() - self._last_successful_publish
                if stalled_for > timeout:
                    logger.critical(
                        f"Hard watchdog: the bridge has been stuck for {stalled_for:.0f}s "
                        f"(limit {timeout:.0f}s), force-exiting for a restart"
                    )
                    logging.shutdown()  # flush handlers, os._exit skips cleanup
                    os._exit(EXIT_WATCHDOG_TRIPPED)

        thread = threading.Thread(target=_watch, name="watchdog", daemon=True)
        thread.start()
        logger.info(f"Hard watchdog started (limit: {timeout:.0f}s)")

    def _sleep_until_next_poll(self) -> None:
        """Sleep for the poll interval, waking immediately on shutdown."""
        self._shutdown_event.wait(self.config.poll_interval)

    def run(self) -> int:
        """Main application loop.

        Calls setup() to initialize connections, then enters the polling loop
        with configurable interval. Handles errors and continues operation.
        The loop runs until shutdown is requested via signal handler, or until
        the watchdog decides the bridge is no longer delivering data.

        Returns:
            int: Process exit code. Non-zero asks the container supervisor for
                a restart, which is the only reliable way out of a state the
                process cannot repair itself (wedged USB stack, hung MQTT
                client, device stuck not answering).

        Requirements: 2.1
        """
        logger.info("Starting RadPro MQTT Bridge...")

        self._clear_health_check()

        # Call setup() (Requirement 2.1)
        if not self.setup():
            logger.error("Setup failed, exiting so the supervisor can restart the bridge")
            self.shutdown()
            return EXIT_SETUP_FAILED

        watchdog_timeout = self.config.effective_watchdog_timeout
        self._start_hard_watchdog(watchdog_timeout * HARD_WATCHDOG_FACTOR)

        # Enter polling loop with configurable interval (Requirement 2.1)
        logger.info(
            f"Entering polling loop (interval: {self.config.poll_interval}s, "
            f"watchdog: {watchdog_timeout}s)"
        )

        while not self._shutdown_requested:
            try:
                if self.poll_and_publish():
                    self._consecutive_failures = 0
                else:
                    self._consecutive_failures += 1

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, shutting down...")
                break
            except Exception as e:
                # Handle errors and continue operation (Requirement 2.1)
                self._consecutive_failures += 1
                logger.error(f"Error in polling loop: {e}", exc_info=True)
                logger.info("Continuing operation after error...")

            if self._consecutive_failures >= self.config.max_consecutive_failures:
                self._recover_connections()

            # Give up and let the supervisor restart us if data has not reached
            # the broker for too long (Requirement 6.6)
            stalled_for = time.time() - self._last_successful_publish
            if stalled_for > watchdog_timeout:
                logger.critical(
                    f"Watchdog: no data reached the MQTT broker for {stalled_for:.0f}s "
                    f"(limit {watchdog_timeout}s), exiting for a restart"
                )
                self.shutdown()
                return EXIT_WATCHDOG_TRIPPED

            self._sleep_until_next_poll()

        logger.info("Polling loop exited")
        self.shutdown()
        return EXIT_OK

    def shutdown(self) -> None:
        """Graceful shutdown of the bridge.

        Performs cleanup in the following order:
        1. Publish offline availability
        2. Disconnect from MQTT
        3. Disconnect from USB

        Requirements: 6.5
        """
        logger.info("Shutting down RadPro MQTT Bridge...")

        # Stop the watchdog thread first: shutting down is not a stall
        self._shutdown_requested = True
        self._shutdown_event.set()

        # Step 1: Publish offline availability (Requirement 6.5)
        try:
            if self.publisher.is_connected():
                logger.info("Publishing offline availability status...")
                if self.publisher.publish_availability("offline"):
                    # Wait for the broker to acknowledge before closing the
                    # socket, otherwise the status is lost on the way out
                    self.publisher.wait_for_delivery(timeout=2.0)
        except Exception as e:
            logger.error(f"Error publishing offline status: {e}")

        # Step 2: Disconnect from MQTT (Requirement 6.5)
        try:
            logger.info("Disconnecting from MQTT broker...")
            self.publisher.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting from MQTT: {e}")

        # Step 3: Disconnect from USB (Requirement 6.5)
        try:
            logger.info("Disconnecting from RadPro device...")
            self.device.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting from device: {e}")

        logger.info("Shutdown complete")

    def _signal_handler(self, signum: int, frame: object) -> None:
        """Handle shutdown signals.

        Called when SIGTERM or SIGINT is received. Sets the shutdown flag
        to trigger graceful shutdown in the main loop.

        Args:
            signum: Signal number
            frame: Current stack frame (unused)

        Requirements: 6.5
        """
        signal_name = signal.Signals(signum).name
        logger.info(f"Received signal {signal_name} ({signum}), initiating shutdown...")
        self._shutdown_requested = True
        self._shutdown_event.set()

    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown.

        Registers handlers for SIGTERM and SIGINT signals to enable
        graceful shutdown when the application receives these signals.

        Requirements: 6.5
        """
        logger.debug("Setting up signal handlers...")
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        logger.debug("Signal handlers configured")
