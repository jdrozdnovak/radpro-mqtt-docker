"""Main application orchestrator for RadPro MQTT Bridge.

This module provides the RadProBridge class that orchestrates all components
of the bridge application, including USB serial communication, MQTT publishing,
and the main polling loop.
"""

import logging
import signal
import time
from datetime import datetime

from src.config import Config
from src.models import DeviceInfo, RadiationMeasurement
from src.mqtt_publisher import MQTTPublisher
from src.radpro_device import RadProDevice

logger = logging.getLogger(__name__)


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

        Creates instances of Config, RadProDevice, and MQTTPublisher
        components. The components are not connected until setup() is called.

        Args:
            config: Configuration object containing all application settings

        Requirements: 6.1
        """
        self.config = config
        self._device_info: DeviceInfo | None = None
        self._shutdown_requested = False

        # Create RadProDevice instance (Requirement 6.1)
        self.device = RadProDevice(
            device_path=config.device_path,
            baudrate=config.serial_baudrate,
            timeout=config.serial_timeout,
        )

        # Create MQTTPublisher instance (Requirement 6.1)
        self.publisher = MQTTPublisher(config=config)

        logger.info("RadProBridge initialized")
        logger.debug(
            f"Configuration: device={config.device_path}, "
            f"mqtt_host={config.mqtt_host}:{config.mqtt_port}, "
            f"poll_interval={config.poll_interval}s"
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

        logger.info("Bridge setup completed successfully")
        return True

    def poll_and_publish(self) -> None:
        """Poll device and publish sensor data to MQTT.

        Polls all sensors from the RadPro device, creates a RadiationMeasurement
        object, and publishes sensor states to MQTT. Individual sensor failures
        are handled gracefully - if one sensor fails, the others are still published.

        Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.3
        """
        if self._device_info is None:
            logger.error("Cannot poll: device information not available")
            return

        logger.debug("Starting sensor polling cycle...")

        # Poll all sensors from device (Requirements 2.2, 2.3, 2.4, 2.6)
        # Handle individual sensor failures gracefully (Requirement 2.7)

        tube_rate = self.device.get_tube_rate()
        if tube_rate is None:
            logger.warning("Failed to get tube rate, skipping this polling cycle")
            return

        tube_pulse_count = self.device.get_tube_pulse_count()
        if tube_pulse_count is None:
            logger.warning("Failed to get tube pulse count, skipping this polling cycle")
            return

        battery_voltage = self.device.get_battery_voltage()
        if battery_voltage is None:
            logger.warning("Failed to get battery voltage, skipping this polling cycle")
            return

        tube_sensitivity = self.device.get_tube_sensitivity()
        if tube_sensitivity is None:
            logger.warning("Failed to get tube sensitivity, skipping this polling cycle")
            return

        tube_lifetime = self.device.get_tube_lifetime()
        if tube_lifetime is None:
            logger.warning("Failed to get tube lifetime, skipping this polling cycle")
            return

        # Create RadiationMeasurement object (Requirement 2.5)
        measurement = RadiationMeasurement(
            timestamp=datetime.now(),
            tube_rate=tube_rate,
            tube_pulse_count=tube_pulse_count,
            battery_voltage=battery_voltage,
            tube_sensitivity=tube_sensitivity,
            tube_lifetime=tube_lifetime,
        )

        # Log the measurement
        logger.info(
            f"Measurement: dose_rate={measurement.dose_rate:.3f} µSv/h, "
            f"cpm={measurement.tube_rate:.1f}, "
            f"battery={measurement.battery_voltage:.2f}V"
        )

        # Publish sensor states to MQTT (Requirement 3.3)
        # Handle individual sensor publish failures gracefully (Requirement 2.7)
        try:
            self.publisher.publish_sensor_state("dose_rate", measurement.dose_rate)
        except Exception as e:
            logger.error(f"Failed to publish dose_rate: {e}")

        try:
            self.publisher.publish_sensor_state("cpm", measurement.tube_rate)
        except Exception as e:
            logger.error(f"Failed to publish cpm: {e}")

        try:
            self.publisher.publish_sensor_state("total_pulses", measurement.tube_pulse_count)
        except Exception as e:
            logger.error(f"Failed to publish total_pulses: {e}")

        try:
            self.publisher.publish_sensor_state("battery_voltage", measurement.battery_voltage)
        except Exception as e:
            logger.error(f"Failed to publish battery_voltage: {e}")

        try:
            self.publisher.publish_sensor_state("tube_lifetime", measurement.tube_lifetime)
        except Exception as e:
            logger.error(f"Failed to publish tube_lifetime: {e}")

        logger.debug("Sensor polling cycle completed")

        # Write health check file (Requirement 6.6)
        self._write_health_check()

    def _write_health_check(self) -> None:
        """Write health check timestamp to file.

        Writes the current timestamp to /tmp/health after each successful poll.
        This file is used by Docker health checks to verify the application
        is running correctly.

        Requirements: 6.6
        """
        try:
            import time

            timestamp = time.time()
            with open("/tmp/health", "w") as f:
                f.write(f"{timestamp}\n")
            logger.debug(f"Health check file updated: {timestamp}")
        except Exception as e:
            logger.warning(f"Failed to write health check file: {e}")

    def run(self) -> None:
        """Main application loop.

        Calls setup() to initialize connections, then enters the polling loop
        with configurable interval. Handles errors and continues operation.
        The loop runs until shutdown is requested via signal handler.

        Requirements: 2.1
        """
        logger.info("Starting RadPro MQTT Bridge...")

        # Call setup() (Requirement 2.1)
        if not self.setup():
            logger.error("Setup failed, exiting")
            return

        # Enter polling loop with configurable interval (Requirement 2.1)
        logger.info(f"Entering polling loop (interval: {self.config.poll_interval}s)")

        while not self._shutdown_requested:
            try:
                # Poll and publish sensor data
                self.poll_and_publish()

                # Sleep for the configured poll interval
                # Check shutdown flag more frequently to allow quick shutdown
                sleep_interval = 1.0  # Check every second
                elapsed = 0.0
                while elapsed < self.config.poll_interval and not self._shutdown_requested:
                    time.sleep(sleep_interval)
                    elapsed += sleep_interval

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, shutting down...")
                break
            except Exception as e:
                # Handle errors and continue operation (Requirement 2.1)
                logger.error(f"Error in polling loop: {e}", exc_info=True)
                logger.info("Continuing operation after error...")

                # Check if device is still connected, attempt reconnection if needed
                if not self.device.is_connected():
                    logger.warning("Device disconnected, attempting to reconnect...")
                    if self.device.reconnect(
                        max_retries=self.config.max_retries,
                        backoff_base=self.config.retry_backoff_base,
                    ):
                        logger.info("Device reconnected successfully")
                        # Re-retrieve device info after reconnection
                        self._device_info = self.device.get_device_id()
                    else:
                        logger.error("Failed to reconnect to device")

                # Check if MQTT is still connected
                if not self.publisher.is_connected():
                    logger.warning("MQTT disconnected, waiting for automatic reconnection...")

                # Sleep before next attempt
                time.sleep(self.config.poll_interval)

        logger.info("Polling loop exited")
        self.shutdown()

    def shutdown(self) -> None:
        """Graceful shutdown of the bridge.

        Performs cleanup in the following order:
        1. Publish offline availability
        2. Disconnect from MQTT
        3. Disconnect from USB

        Requirements: 6.5
        """
        logger.info("Shutting down RadPro MQTT Bridge...")

        # Step 1: Publish offline availability (Requirement 6.5)
        try:
            if self.publisher.is_connected():
                logger.info("Publishing offline availability status...")
                self.publisher.publish_availability("offline")
                # Give time for the message to be sent
                time.sleep(0.5)
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
