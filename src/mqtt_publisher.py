"""MQTT publisher for RadPro MQTT Bridge.

This module provides the MQTTPublisher class for managing MQTT connections
and publishing messages to an MQTT broker.
"""

import json
import logging
import threading
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode

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
    # Advanced sensors
    "tube_dead_time": {
        "name": "Tube Dead Time",
        "device_class": None,
        "unit_of_measurement": "µs",
        "icon": "mdi:timer-sand",
        "state_class": "measurement",
    },
    "tube_dead_time_compensation": {
        "name": "Dead Time Compensation",
        "device_class": None,
        "unit_of_measurement": "s",
        "icon": "mdi:timer-cog",
        "state_class": "measurement",
    },
    "hv_duty_cycle": {
        "name": "HV Duty Cycle",
        "device_class": None,
        "unit_of_measurement": "%",
        "icon": "mdi:sine-wave",
        "state_class": "measurement",
    },
    "hv_frequency": {
        "name": "HV Frequency",
        "device_class": "frequency",
        "unit_of_measurement": "Hz",
        "state_class": "measurement",
    },
    # Moving average CPM sensors
    "cpm_1min": {
        "name": "CPM (1 min avg)",
        "device_class": None,
        "unit_of_measurement": "CPM",
        "icon": "mdi:chart-line",
        "state_class": "measurement",
    },
    "cpm_5min": {
        "name": "CPM (5 min avg)",
        "device_class": None,
        "unit_of_measurement": "CPM",
        "icon": "mdi:chart-line",
        "state_class": "measurement",
    },
    "cpm_15min": {
        "name": "CPM (15 min avg)",
        "device_class": None,
        "unit_of_measurement": "CPM",
        "icon": "mdi:chart-line",
        "state_class": "measurement",
    },
}


class MQTTPublisher:
    """Manages MQTT connection and message publishing.

    This class handles connection management to an MQTT broker, including
    authentication, Last Will and Testament configuration, and message publishing.

    Reconnection is delegated entirely to paho-mqtt: ``loop_start()`` runs a
    network thread that re-establishes the connection with exponential backoff
    whenever it is lost. Reconnecting by hand from a callback (or from the
    polling thread) fights that thread for the socket and is a known way to
    wedge the client into a state where it looks connected but never delivers
    anything again.

    Attributes:
        config: Configuration object with MQTT settings
        on_connected: Optional callback invoked from the network thread after
            every successful (re)connection, used to re-announce discovery and
            availability. It must not block waiting on broker acknowledgements.
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
        self._connect_result = threading.Event()
        self._last_message_info: mqtt.MQTTMessageInfo | None = None
        self.on_connected: Callable[[], None] | None = None

        # Create MQTT client instance.
        # reconnect_on_failure=True (the default) makes the loop_start() thread
        # retry forever with the backoff set in connect().
        self._client = mqtt.Client(
            CallbackAPIVersion.VERSION2,
            client_id=config.effective_client_id,
            clean_session=True,
            reconnect_on_failure=True,
        )

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

        logger.debug(
            f"MQTTPublisher initialized: host={config.mqtt_host}, port={config.mqtt_port}, "
            f"client_id={config.effective_client_id}"
        )

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        connect_flags: mqtt.ConnectFlags,
        reason_code: ReasonCode,
        properties: Properties | None = None,
    ) -> None:
        """Callback for when the client connects to the broker.

        Args:
            client: The MQTT client instance
            userdata: User data (unused)
            connect_flags: Flags from the broker's CONNACK
            reason_code: Connection result reason code
            properties: MQTT v5 properties (unused)
        """
        if reason_code.is_failure:
            self._connected = False
            logger.error(f"Failed to connect to MQTT broker: {reason_code}")
            # Unblock connect(); the network thread keeps retrying in the
            # background, including for auth errors - credentials may be fixed
            # on the broker without restarting this container.
            self._connect_result.set()
            return

        self._connected = True
        logger.info(f"Connected to MQTT broker at {self.config.mqtt_host}:{self.config.mqtt_port}")
        self._connect_result.set()

        # Re-announce ourselves after every reconnect: a restarted broker may
        # have lost the retained discovery and availability messages, which
        # leaves the entities stuck as unavailable in Home Assistant.
        if self.on_connected is not None:
            try:
                self.on_connected()
            except Exception as e:
                logger.error(f"Error in on_connected handler: {e}", exc_info=True)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: ReasonCode,
        properties: Properties | None = None,
    ) -> None:
        """Callback for when the client disconnects from the broker.

        This only records the state change. Reconnection is handled by the
        paho-mqtt network thread started in connect(); doing it here would
        block that very thread.

        Args:
            client: The MQTT client instance
            userdata: User data (unused)
            disconnect_flags: Flags describing the disconnect
            reason_code: Disconnection reason code
            properties: MQTT v5 properties (unused)
        """
        self._connected = False

        if reason_code.is_failure or disconnect_flags.is_disconnect_packet_from_server:
            logger.warning(
                f"Disconnected from MQTT broker unexpectedly ({reason_code}); "
                "the client will reconnect automatically"
            )
        else:
            logger.info("Disconnected from MQTT broker (clean disconnect)")

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

    def connect(self, timeout: float = 10.0) -> bool:
        """Connect to the MQTT broker.

        Establishes a connection to the MQTT broker using the configured
        host, port, and authentication credentials. The Last Will and Testament
        should be configured before calling this method. Starts the background
        network thread, which keeps the connection alive and re-establishes it
        automatically if it drops.

        Args:
            timeout: Seconds to wait for the broker's CONNACK

        Returns:
            bool: True if connection successful, False otherwise

        Requirements: 3.1
        """
        if self._client is None:
            logger.error("Cannot connect: MQTT client not initialized")
            return False

        try:
            self._connect_result.clear()

            logger.info(
                f"Attempting to connect to MQTT broker at "
                f"{self.config.mqtt_host}:{self.config.mqtt_port}"
            )

            # Bound the automatic reconnect backoff of the network thread.
            # Capping at 60s keeps an outage from turning into a 2-minute gap.
            self._client.reconnect_delay_set(min_delay=1, max_delay=60)

            # Connect to broker (Requirement 3.1)
            self._client.connect(
                host=self.config.mqtt_host,
                port=self.config.mqtt_port,
                keepalive=self.config.mqtt_keepalive,
            )

            # Start network loop in background thread
            self._client.loop_start()

            # Wait for the CONNACK to be processed by the network thread
            self._connect_result.wait(timeout)

            if self._connected:
                logger.info("Successfully connected to MQTT broker")
                return True

            logger.error("Failed to connect to MQTT broker within timeout")
            return False

        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from the MQTT broker.

        Gracefully disconnects from the MQTT broker and stops the network loop.
        This method is safe to call even if not connected.

        Requirements: 3.1
        """
        if self._client is None:
            logger.debug("Disconnect called but MQTT client not initialized")
            return

        try:
            if self._connected:
                logger.info("Disconnecting from MQTT broker")
                self._client.disconnect()
                self._connected = False
            else:
                logger.debug("Disconnect called but not connected to broker")

            # Always stop the network thread, otherwise it keeps reconnecting
            self._client.loop_stop()
            logger.info("Disconnected from MQTT broker")
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
            self._connected = False

    def is_connected(self) -> bool:
        """Check if connected to the MQTT broker.

        Combines our own view of the connection with the client's, so a socket
        that paho has already given up on is never reported as usable.

        Returns:
            bool: True if connected, False otherwise

        Requirements: 3.1
        """
        if self._client is None:
            return False
        return bool(self._connected and self._client.is_connected())

    def wait_for_delivery(self, timeout: float = 10.0) -> bool:
        """Wait for the broker to acknowledge the most recent publish.

        Publishing is asynchronous: ``publish()`` only queues a message for the
        network thread. Waiting for the QoS 1 acknowledgement is what proves
        messages are actually reaching the broker - without it the bridge
        cannot tell a healthy connection from a network thread that has died
        or a socket that is silently black-holing data.

        Must only be called from the polling thread: calling it from an MQTT
        callback would block the very thread that processes acknowledgements.

        Args:
            timeout: Seconds to wait for the acknowledgement

        Returns:
            bool: True if the message was acknowledged (or nothing was
                pending), False if it timed out or failed
        """
        message_info = self._last_message_info
        if message_info is None:
            return True

        try:
            # wait_for_publish() returns silently when it times out, so the
            # acknowledgement has to be confirmed explicitly afterwards
            message_info.wait_for_publish(timeout)
            if message_info.is_published():
                return True
            logger.error(f"Publish was not acknowledged by the broker within {timeout}s")
            return False
        except (RuntimeError, ValueError) as e:
            logger.error(f"Publish failed: {e}")
            return False
        finally:
            self._last_message_info = None

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

    def publish_discovery(self, device_info: DeviceInfo) -> bool:
        """Publish Home Assistant discovery payloads for all sensors.

        Publishes discovery configuration messages for all defined sensors
        to enable Home Assistant auto-discovery. Each sensor gets its own
        discovery topic following the Home Assistant MQTT Discovery format.

        Args:
            device_info: Device identification information

        Returns:
            bool: True if every discovery payload was handed to the client

        Requirements: 4.1, 4.2
        """
        if not self.is_connected() or self._client is None:
            logger.error("Cannot publish discovery: not connected to MQTT broker")
            return False

        logger.info(
            f"Publishing Home Assistant discovery payloads for device {device_info.device_id}"
        )

        success = True

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
                    success = False
                    logger.error(
                        f"Failed to publish discovery for {sensor_type}: " f"error code {result.rc}"
                    )

            except Exception as e:
                success = False
                logger.error(f"Error publishing discovery for {sensor_type}: {e}")

        logger.info(f"Completed publishing discovery payloads for {len(SENSORS)} sensors")
        return success

    def publish_sensor_state(self, sensor: str, value: Any) -> bool:
        """Publish sensor state to MQTT.

        Publishes a sensor's current value to its state topic in JSON format.
        The value is serialized to JSON and published to the sensor's state topic.

        Readings are dropped rather than queued while the broker is
        unreachable: a Geiger reading that arrives minutes late is worthless,
        and queueing them would grow without bound during an outage.

        Args:
            sensor: The sensor type (e.g., "dose_rate", "cpm")
            value: The sensor value to publish (will be JSON serialized)

        Returns:
            bool: True if the message was accepted by the client for delivery

        Requirements: 3.3
        """
        if not self.is_connected() or self._client is None:
            # Debug level on purpose: during an outage this would otherwise be
            # one error line per sensor per cycle. The caller logs the failed
            # cycle once.
            logger.debug(f"Cannot publish sensor state for {sensor}: not connected to MQTT broker")
            return False

        try:
            # Get the state topic for this sensor
            topic = self.get_state_topic(sensor)

            # Serialize value to JSON (Requirement 3.3)
            payload = json.dumps(value)

            # Publish to state topic
            result = self._client.publish(topic=topic, payload=payload, qos=1, retain=False)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                # Remember the handle so the caller can confirm the broker
                # actually acknowledged this cycle's data
                self._last_message_info = result
                logger.debug(f"Published state for {sensor} to {topic}: {payload}")
                return True

            logger.error(f"Failed to publish state for {sensor} to {topic}: error code {result.rc}")
            return False

        except Exception as e:
            logger.error(f"Error publishing sensor state for {sensor}: {e}")
            return False

    def publish_availability(self, status: str) -> bool:
        """Publish availability status to MQTT.

        Publishes the bridge's availability status (online/offline) to the
        availability topic. This is used by Home Assistant to determine if
        the device is reachable.

        Args:
            status: Availability status ("online" or "offline")

        Returns:
            bool: True if the message was accepted by the client for delivery

        Requirements: 3.2, 3.4
        """
        if self._client is None:
            logger.error("Cannot publish availability: MQTT client not initialized")
            return False

        if not self.is_connected():
            logger.warning(f"Cannot publish availability '{status}': not connected to MQTT broker")
            return False

        try:
            # Get the availability topic
            topic = self.get_availability_topic()

            # Publish availability status (Requirements 3.2, 3.4)
            result = self._client.publish(topic=topic, payload=status, qos=1, retain=True)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self._last_message_info = result
                logger.info(f"Published availability status: {status}")
                return True

            logger.error(
                f"Failed to publish availability status to {topic}: error code {result.rc}"
            )
            return False

        except Exception as e:
            logger.error(f"Error publishing availability status: {e}")
            return False
