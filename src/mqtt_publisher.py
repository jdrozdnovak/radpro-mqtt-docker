"""MQTT publisher for RadPro MQTT Bridge.

This module provides the MQTTPublisher class for managing MQTT connections
and publishing messages to an MQTT broker.
"""

import logging
import time
from typing import Any

import paho.mqtt.client as mqtt

from src.config import Config
from src.models import DeviceInfo, DevicePayload, DiscoveryPayload

logger = logging.getLogger(__name__)

# Sensor definitions for Home Assistant MQTT Discovery (Requirements 3.6, 4.2, 4.4)
SENSORS: dict[str, dict[str, Any]] = {
    "dose_rate": {
        "name": "Dose Rate",
        "device_class": None,  # No standard device class for radiation
        "unit_of_measurement": "µSv/h",
        "icon": "mdi:radioactive",
        "state_class": "measurement",
    },
    "cpm": {
        "name": "Counts Per Minute",
        "device_class": None,
        "unit_of_measurement": "CPM",
        "icon": "mdi:counter",
        "state_class": "measurement",
    },
    "total_pulses": {
        "name": "Total Pulses",
        "device_class": None,
        "unit_of_measurement": "pulses",
        "icon": "mdi:counter",
        "state_class": "total_increasing",
    },
    "battery_voltage": {
        "name": "Battery Voltage",
        "device_class": "voltage",
        "unit_of_measurement": "V",
        "state_class": "measurement",
    },
    "tube_lifetime": {
        "name": "Tube Lifetime",
        "device_class": "duration",
        "unit_of_measurement": "s",
        "icon": "mdi:timer-outline",
        "state_class": "total_increasing",
    },
}


class MQTTPublisher:
    """Manages MQTT connection and message publishing.

    This class handles connection management to an MQTT broker, including
    authentication, Last Will and Testament configuration, and message publishing.

    Attributes:
        config: Configuration object with MQTT settings
    """

    def __init__(self, config: Config):
        """Initialize MQTT client with configuration.

        Creates a paho-mqtt client instance and configures it with the
        provided settings. The client is not connected until connect() is called.

        Args:
            config: Configuration object containing MQTT settings

        Requirements: 3.1
        """
        self.config = config
        self._client: mqtt.Client | None = None
        self._connected = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = config.max_retries
        self._should_reconnect = True

        # Create MQTT client instance
        self._client = mqtt.Client(client_id="radpro-mqtt-bridge", clean_session=True)

        # Set up callbacks
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

        # Configure authentication if credentials provided (Requirement 3.1)
        if config.mqtt_username and config.mqtt_password:
            logger.debug(f"Configuring MQTT authentication for user: {config.mqtt_username}")
            self._client.username_pw_set(config.mqtt_username, config.mqtt_password)
        elif config.mqtt_username:
            logger.debug(f"Configuring MQTT authentication for user: {config.mqtt_username}")
            self._client.username_pw_set(config.mqtt_username)

        logger.debug(f"MQTTPublisher initialized: host={config.mqtt_host}, port={config.mqtt_port}")

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: dict, rc: int) -> None:
        """Callback for when the client connects to the broker.

        Args:
            client: The MQTT client instance
            userdata: User data (unused)
            flags: Response flags from the broker
            rc: Connection result code
        """
        if rc == 0:
            self._connected = True
            self._reconnect_attempts = 0  # Reset reconnection attempts on success
            logger.info(
                f"Connected to MQTT broker at " f"{self.config.mqtt_host}:{self.config.mqtt_port}"
            )
        else:
            self._connected = False
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorized",
            }
            error_msg = error_messages.get(rc, f"Connection refused - unknown error code {rc}")
            logger.error(f"Failed to connect to MQTT broker: {error_msg}")

            # Handle authentication errors (Requirement 8.2)
            if rc in [4, 5]:
                logger.error("Authentication error detected - will not retry with same credentials")
                self._should_reconnect = False

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        """Callback for when the client disconnects from the broker.

        Args:
            client: The MQTT client instance
            userdata: User data (unused)
            rc: Disconnection result code
        """
        self._connected = False
        if rc == 0:
            logger.info("Disconnected from MQTT broker (clean disconnect)")
        else:
            logger.warning(f"Disconnected from MQTT broker unexpectedly (code: {rc})")
            # Trigger automatic reconnection for unexpected disconnects (Requirement 8.2)
            if self._should_reconnect:
                logger.info("Will attempt to reconnect to MQTT broker")
                self._attempt_reconnect()

    def _attempt_reconnect(self) -> None:
        """Attempt to reconnect to MQTT broker with exponential backoff.

        This method implements automatic reconnection with exponential backoff
        when the connection is lost unexpectedly. It respects the maximum
        retry limit and handles authentication errors appropriately.

        Requirements: 8.2
        """
        if not self._should_reconnect:
            logger.info("Reconnection disabled (authentication error or manual disconnect)")
            return

        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error(
                f"Maximum reconnection attempts ({self._max_reconnect_attempts}) reached. "
                "Entering failed state."
            )
            return

        # Calculate exponential backoff delay (Requirement 8.2)
        delay = self.config.retry_backoff_base**self._reconnect_attempts
        self._reconnect_attempts += 1

        logger.info(
            f"Attempting to reconnect to MQTT broker "
            f"(attempt {self._reconnect_attempts}/{self._max_reconnect_attempts}) "
            f"in {delay:.2f} seconds..."
        )

        # Wait before attempting reconnection
        time.sleep(delay)

        try:
            # Attempt to reconnect
            if self._client is None:
                logger.error("Cannot reconnect: MQTT client not initialized")
                return

            logger.info(
                f"Reconnecting to MQTT broker at "
                f"{self.config.mqtt_host}:{self.config.mqtt_port}"
            )

            # The paho-mqtt client will automatically try to reconnect
            # We just need to call reconnect() which uses the existing connection parameters
            self._client.reconnect()

            # Wait for connection to establish (with timeout)
            timeout = 10  # seconds
            start_time = time.time()
            while not self._connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            if self._connected:
                logger.info("Successfully reconnected to MQTT broker")
            else:
                logger.warning("Reconnection attempt timed out")
                # Will retry on next disconnect callback if still not connected

        except Exception as e:
            logger.error(f"Error during reconnection attempt: {e}")
            # The disconnect callback will be triggered again if connection fails

    def set_last_will(self) -> None:
        """Configure MQTT Last Will and Testament for availability.

        Sets up the Last Will message that will be published automatically
        by the broker if the client disconnects unexpectedly. This is used
        to publish an "offline" status to the availability topic.

        Requirements: 3.4
        """
        if self._client is None:
            logger.error("Cannot set Last Will: MQTT client not initialized")
            return

        availability_topic = f"{self.config.mqtt_topic_prefix}/availability"

        try:
            # Configure Last Will and Testament (Requirement 3.4)
            self._client.will_set(topic=availability_topic, payload="offline", qos=1, retain=True)
            logger.debug(f"Last Will configured: topic={availability_topic}, payload=offline")
        except Exception as e:
            logger.error(f"Failed to set Last Will: {e}")

    def connect(self) -> bool:
        """Connect to the MQTT broker.

        Establishes a connection to the MQTT broker using the configured
        host, port, and authentication credentials. The Last Will and Testament
        should be configured before calling this method. Enables automatic
        reconnection on successful connection.

        Returns:
            bool: True if connection successful, False otherwise

        Requirements: 3.1
        """
        if self._client is None:
            logger.error("Cannot connect: MQTT client not initialized")
            return False

        try:
            # Enable automatic reconnection for new connections
            self._should_reconnect = True
            self._reconnect_attempts = 0

            logger.info(
                f"Attempting to connect to MQTT broker at "
                f"{self.config.mqtt_host}:{self.config.mqtt_port}"
            )

            # Enable automatic reconnection in paho-mqtt
            # This will automatically reconnect if connection is lost
            self._client.reconnect_delay_set(min_delay=1, max_delay=120)

            # Connect to broker (Requirement 3.1)
            self._client.connect(
                host=self.config.mqtt_host, port=self.config.mqtt_port, keepalive=60
            )

            # Start network loop in background thread
            self._client.loop_start()

            # Wait for connection to establish (with timeout)
            timeout = 10  # seconds
            start_time = time.time()
            while not self._connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            if self._connected:
                logger.info("Successfully connected to MQTT broker")
                return True
            else:
                logger.error("Connection timeout: failed to connect to MQTT broker")
                return False

        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from the MQTT broker.

        Gracefully disconnects from the MQTT broker and stops the network loop.
        This method is safe to call even if not connected. Disables automatic
        reconnection to prevent reconnection after intentional disconnect.

        Requirements: 3.1
        """
        if self._client is None:
            logger.debug("Disconnect called but MQTT client not initialized")
            return

        try:
            # Disable automatic reconnection for manual disconnect
            self._should_reconnect = False

            if self._connected:
                logger.info("Disconnecting from MQTT broker")
                self._client.disconnect()
                self._client.loop_stop()
                self._connected = False
                logger.info("Disconnected from MQTT broker")
            else:
                logger.debug("Disconnect called but not connected to broker")
                self._client.loop_stop()
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
            self._connected = False

    def is_connected(self) -> bool:
        """Check if connected to the MQTT broker.

        Returns:
            bool: True if connected, False otherwise

        Requirements: 3.1
        """
        return self._connected

    def get_state_topic(self, sensor_type: str) -> str:
        """Construct state topic for a sensor.

        Constructs the MQTT topic where sensor state data will be published,
        following the pattern: {prefix}/{sensor_type}/state

        Args:
            sensor_type: The type of sensor (e.g., "dose_rate", "cpm")

        Returns:
            str: The constructed state topic

        Requirements: 3.6
        """
        return f"{self.config.mqtt_topic_prefix}/{sensor_type}/state"

    def get_availability_topic(self) -> str:
        """Construct availability topic.

        Constructs the MQTT topic where availability status (online/offline)
        will be published.

        Returns:
            str: The constructed availability topic

        Requirements: 3.6
        """
        return f"{self.config.mqtt_topic_prefix}/availability"

    def get_discovery_topic(self, node_id: str, object_id: str) -> str:
        """Construct Home Assistant discovery topic for a sensor.

        Constructs the MQTT topic where Home Assistant discovery payloads
        will be published, following the pattern:
        {discovery_prefix}/sensor/{node_id}/{object_id}/config

        Args:
            node_id: The node identifier (typically device_id)
            object_id: The object identifier (typically sensor type)

        Returns:
            str: The constructed discovery topic

        Requirements: 4.2
        """
        return f"{self.config.ha_discovery_prefix}/sensor/{node_id}/{object_id}/config"

    def generate_discovery_payload(
        self, device_info: DeviceInfo, sensor_type: str
    ) -> DiscoveryPayload:
        """Generate Home Assistant discovery payload for a sensor.

        Creates a complete discovery payload for a specific sensor type,
        including all required fields for Home Assistant auto-discovery.

        Args:
            device_info: Device identification information
            sensor_type: Type of sensor (must be a key in SENSORS dict)

        Returns:
            DiscoveryPayload: Complete discovery payload ready for publishing

        Raises:
            KeyError: If sensor_type is not found in SENSORS dictionary

        Requirements: 4.1, 4.3, 4.5, 4.6, 5.3, 5.4, 5.5
        """
        if sensor_type not in SENSORS:
            raise KeyError(f"Unknown sensor type: {sensor_type}")

        sensor_config = SENSORS[sensor_type]

        # Create device payload (Requirements 4.3, 5.3, 5.4, 5.5)
        device_payload = DevicePayload(
            identifiers=[device_info.device_id],
            name=f"RadPro {device_info.device_id}",
            manufacturer="RadPro",
            model=device_info.hardware_id,
            sw_version=device_info.software_id,
        )

        # Construct unique_id for the sensor (Requirement 4.6)
        unique_id = f"{device_info.device_id}_{sensor_type}"

        # Get topics (Requirements 4.5)
        state_topic = self.get_state_topic(sensor_type)
        availability_topic = self.get_availability_topic()

        # Create discovery payload (Requirements 4.1, 4.3, 4.5, 4.6)
        discovery_payload = DiscoveryPayload(
            name=sensor_config["name"],
            unique_id=unique_id,
            state_topic=state_topic,
            availability_topic=availability_topic,
            device=device_payload,
            device_class=sensor_config.get("device_class"),
            unit_of_measurement=sensor_config.get("unit_of_measurement"),
            icon=sensor_config.get("icon"),
            state_class=sensor_config.get("state_class"),
        )

        logger.debug(
            f"Generated discovery payload for {sensor_type}: "
            f"unique_id={unique_id}, state_topic={state_topic}"
        )

        return discovery_payload

    def publish_discovery(self, device_info: DeviceInfo) -> None:
        """Publish Home Assistant discovery payloads for all sensors.

        Publishes discovery configuration messages for all defined sensors
        to enable Home Assistant auto-discovery. Each sensor gets its own
        discovery topic following the Home Assistant MQTT Discovery format.
        Automatically reconnects if connection is lost.

        Args:
            device_info: Device identification information

        Requirements: 4.1, 4.2
        """
        # Ensure we're connected before publishing
        if not self._ensure_connected():
            logger.error("Cannot publish discovery: not connected to MQTT broker")
            return

        logger.info(
            f"Publishing Home Assistant discovery payloads for device {device_info.device_id}"
        )

        # Publish discovery payload for each sensor (Requirement 4.1)
        for sensor_type in SENSORS.keys():
            try:
                # Generate discovery payload
                payload = self.generate_discovery_payload(device_info, sensor_type)

                # Construct discovery topic (Requirement 4.2)
                topic = self.get_discovery_topic(device_info.device_id, sensor_type)

                # Publish discovery payload
                result = self._client.publish(
                    topic=topic,
                    payload=payload.to_json(),
                    qos=1,
                    retain=True,  # Retain discovery messages
                )

                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    logger.debug(f"Published discovery for {sensor_type} to {topic}")
                else:
                    logger.error(
                        f"Failed to publish discovery for {sensor_type}: " f"error code {result.rc}"
                    )

            except Exception as e:
                logger.error(f"Error publishing discovery for {sensor_type}: {e}")

        logger.info(f"Completed publishing discovery payloads for {len(SENSORS)} sensors")

    def _ensure_connected(self) -> bool:
        """Ensure MQTT connection is active, reconnect if needed.

        Checks if the client is connected and attempts to reconnect if not.
        This provides resilience against transient connection losses.

        Returns:
            bool: True if connected (or successfully reconnected), False otherwise
        """
        if self._client is None:
            logger.error("MQTT client not initialized")
            return False

        # Check if already connected
        if self._connected and self._client.is_connected():
            return True

        # Not connected, attempt to reconnect
        logger.warning("MQTT connection lost, attempting to reconnect...")

        try:
            # Try to reconnect
            self._client.reconnect()

            # Wait briefly for reconnection
            timeout = 5  # seconds
            start_time = time.time()
            while not self._connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            if self._connected:
                logger.info("Successfully reconnected to MQTT broker")
                return True
            else:
                logger.error("Failed to reconnect to MQTT broker")
                return False

        except Exception as e:
            logger.error(f"Error during reconnection: {e}")
            return False

    def publish_sensor_state(self, sensor: str, value: Any) -> None:
        """Publish sensor state to MQTT.

        Publishes a sensor's current value to its state topic in JSON format.
        The value is serialized to JSON and published to the sensor's state topic.
        Automatically reconnects if connection is lost.

        Args:
            sensor: The sensor type (e.g., "dose_rate", "cpm")
            value: The sensor value to publish (will be JSON serialized)

        Requirements: 3.3
        """
        # Ensure we're connected before publishing
        if not self._ensure_connected():
            logger.error(f"Cannot publish sensor state for {sensor}: not connected to MQTT broker")
            return

        try:
            # Get the state topic for this sensor
            topic = self.get_state_topic(sensor)

            # Serialize value to JSON (Requirement 3.3)
            import json

            payload = json.dumps(value)

            # Publish to state topic
            result = self._client.publish(topic=topic, payload=payload, qos=1, retain=False)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Published state for {sensor} to {topic}: {payload}")
            else:
                logger.error(
                    f"Failed to publish state for {sensor} to {topic}: error code {result.rc}"
                )

        except Exception as e:
            logger.error(f"Error publishing sensor state for {sensor}: {e}")

    def publish_availability(self, status: str) -> None:
        """Publish availability status to MQTT.

        Publishes the bridge's availability status (online/offline) to the
        availability topic. This is used by Home Assistant to determine if
        the device is reachable. Automatically reconnects if connection is lost.

        Args:
            status: Availability status ("online" or "offline")

        Requirements: 3.2, 3.4
        """
        if self._client is None:
            logger.error("Cannot publish availability: MQTT client not initialized")
            return

        # For offline status, don't try to reconnect (we're shutting down)
        if status == "offline":
            if not self.is_connected():
                logger.warning("Cannot publish offline status: not connected")
                return
        else:
            # For online status, ensure we're connected
            if not self._ensure_connected():
                logger.error("Cannot publish availability: not connected to MQTT broker")
                return

        try:
            # Get the availability topic
            topic = self.get_availability_topic()

            # Publish availability status (Requirements 3.2, 3.4)
            result = self._client.publish(topic=topic, payload=status, qos=1, retain=True)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Published availability status: {status}")
            else:
                logger.error(
                    f"Failed to publish availability status to {topic}: error code {result.rc}"
                )

        except Exception as e:
            logger.error(f"Error publishing availability status: {e}")
