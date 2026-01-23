"""Unit tests for RadProBridge class.

Tests the main application orchestrator that coordinates all components.
"""


from src.config import Config
from src.mqtt_publisher import MQTTPublisher
from src.radpro_bridge import RadProBridge
from src.radpro_device import RadProDevice


class TestRadProBridgeInitialization:
    """Test RadProBridge initialization (Task 7.1)."""

    def test_init_creates_config_device_and_publisher(self):
        """Test that __init__ creates Config, RadProDevice, and MQTTPublisher instances.

        Requirements: 6.1
        """
        # Create a valid configuration
        config = Config(
            mqtt_host="test.mosquitto.org",
            device_path="/dev/ttyACM0",
            serial_baudrate=115200,
            serial_timeout=5.0,
        )

        # Initialize RadProBridge
        bridge = RadProBridge(config)

        # Verify that the bridge has the correct attributes
        assert bridge.config is config
        assert isinstance(bridge.device, RadProDevice)
        assert isinstance(bridge.publisher, MQTTPublisher)

    def test_init_passes_correct_parameters_to_device(self):
        """Test that device is initialized with correct parameters from config.

        Requirements: 6.1
        """
        config = Config(
            mqtt_host="test.mosquitto.org",
            device_path="/dev/ttyUSB0",
            serial_baudrate=9600,
            serial_timeout=10.0,
        )

        bridge = RadProBridge(config)

        # Verify device parameters
        assert bridge.device.device_path == "/dev/ttyUSB0"
        assert bridge.device.baudrate == 9600
        assert bridge.device.timeout == 10.0

    def test_init_passes_correct_parameters_to_publisher(self):
        """Test that publisher is initialized with correct config.

        Requirements: 6.1
        """
        config = Config(
            mqtt_host="mqtt.example.com",
            mqtt_port=8883,
            mqtt_username="testuser",
            mqtt_password="testpass",
            mqtt_topic_prefix="custom_prefix",
        )

        bridge = RadProBridge(config)

        # Verify publisher has the correct config
        assert bridge.publisher.config is config
        assert bridge.publisher.config.mqtt_host == "mqtt.example.com"
        assert bridge.publisher.config.mqtt_port == 8883
        assert bridge.publisher.config.mqtt_username == "testuser"
        assert bridge.publisher.config.mqtt_password == "testpass"
        assert bridge.publisher.config.mqtt_topic_prefix == "custom_prefix"

    def test_init_with_default_config_values(self):
        """Test initialization with default configuration values.

        Requirements: 6.1
        """
        config = Config(mqtt_host="localhost")

        bridge = RadProBridge(config)

        # Verify default values are used
        assert bridge.device.device_path == "/dev/ttyACM0"
        assert bridge.device.baudrate == 115200
        assert bridge.device.timeout == 5.0
        assert bridge.publisher.config.mqtt_port == 1883
        assert bridge.publisher.config.mqtt_topic_prefix == "radpro"

    def test_init_does_not_connect_to_device(self):
        """Test that initialization does not automatically connect to device.

        Requirements: 6.1
        """
        config = Config(mqtt_host="localhost")

        bridge = RadProBridge(config)

        # Verify device is not connected after initialization
        assert not bridge.device.is_connected()

    def test_init_does_not_connect_to_mqtt(self):
        """Test that initialization does not automatically connect to MQTT broker.

        Requirements: 6.1
        """
        config = Config(mqtt_host="localhost")

        bridge = RadProBridge(config)

        # Verify MQTT is not connected after initialization
        assert not bridge.publisher.is_connected()
