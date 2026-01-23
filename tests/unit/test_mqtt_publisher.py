"""Unit tests for MQTTPublisher class.

Tests the MQTT connection management functionality including initialization,
connection, disconnection, and Last Will and Testament configuration.
"""

from unittest.mock import Mock, patch

import paho.mqtt.client as mqtt
import pytest

from src.config import Config
from src.mqtt_publisher import MQTTPublisher


@pytest.fixture
def config():
    """Create a test configuration."""
    return Config(
        mqtt_host="test.mosquitto.org",
        mqtt_port=1883,
        mqtt_username="testuser",
        mqtt_password="testpass",
        mqtt_topic_prefix="radpro",
    )


@pytest.fixture
def config_no_auth():
    """Create a test configuration without authentication."""
    return Config(
        mqtt_host="test.mosquitto.org",
        mqtt_port=1883,
        mqtt_username=None,
        mqtt_password=None,
        mqtt_topic_prefix="radpro",
    )


class TestMQTTPublisherInit:
    """Tests for MQTTPublisher initialization."""

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_init_creates_client(self, mock_client_class, config):
        """Test that __init__ creates an MQTT client instance."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)

        # Verify client was created with correct parameters
        mock_client_class.assert_called_once_with(
            client_id="radpro-mqtt-bridge", clean_session=True
        )
        assert publisher.config == config
        assert publisher._client == mock_client

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_init_sets_callbacks(self, mock_client_class, config):
        """Test that __init__ sets up connection callbacks."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)

        # Verify callbacks were set
        assert mock_client.on_connect == publisher._on_connect
        assert mock_client.on_disconnect == publisher._on_disconnect

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_init_with_authentication(self, mock_client_class, config):
        """Test that __init__ configures authentication when credentials provided."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        MQTTPublisher(config)

        # Verify authentication was configured
        mock_client.username_pw_set.assert_called_once_with("testuser", "testpass")

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_init_without_authentication(self, mock_client_class, config_no_auth):
        """Test that __init__ works without authentication credentials."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        MQTTPublisher(config_no_auth)

        # Verify authentication was not configured
        mock_client.username_pw_set.assert_not_called()

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_init_with_username_only(self, mock_client_class):
        """Test that __init__ configures authentication with username only."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        config = Config(
            mqtt_host="test.mosquitto.org",
            mqtt_port=1883,
            mqtt_username="testuser",
            mqtt_password=None,
            mqtt_topic_prefix="radpro",
        )

        MQTTPublisher(config)

        # Verify authentication was configured with username only
        mock_client.username_pw_set.assert_called_once_with("testuser")


class TestMQTTPublisherConnect:
    """Tests for MQTTPublisher connect method."""

    @patch("src.mqtt_publisher.mqtt.Client")
    @patch("src.mqtt_publisher.time.sleep")
    def test_connect_success(self, mock_sleep, mock_client_class, config):
        """Test successful connection to MQTT broker."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)

        # Simulate successful connection by calling the callback
        def connect_side_effect(*args, **kwargs):
            publisher._on_connect(mock_client, None, {}, 0)

        mock_client.connect.side_effect = connect_side_effect

        result = publisher.connect()

        # Verify connection was attempted
        mock_client.connect.assert_called_once_with(
            host="test.mosquitto.org", port=1883, keepalive=60
        )
        mock_client.loop_start.assert_called_once()
        assert result is True
        assert publisher.is_connected() is True

    @patch("src.mqtt_publisher.mqtt.Client")
    @patch("src.mqtt_publisher.time.sleep")
    @patch("src.mqtt_publisher.time.time")
    def test_connect_timeout(self, mock_time, mock_sleep, mock_client_class, config):
        """Test connection timeout when broker doesn't respond."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Simulate timeout by making time progress
        mock_time.side_effect = [0, 0.1, 0.2, 11]  # Exceeds 10 second timeout

        publisher = MQTTPublisher(config)
        result = publisher.connect()

        # Verify connection failed
        assert result is False
        assert publisher.is_connected() is False

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_connect_exception(self, mock_client_class, config):
        """Test connection failure due to exception."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.connect.side_effect = Exception("Connection error")

        publisher = MQTTPublisher(config)
        result = publisher.connect()

        # Verify connection failed
        assert result is False
        assert publisher.is_connected() is False


class TestMQTTPublisherDisconnect:
    """Tests for MQTTPublisher disconnect method."""

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_disconnect_when_connected(self, mock_client_class, config):
        """Test disconnection when connected to broker."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)
        publisher._connected = True

        publisher.disconnect()

        # Verify disconnect was called
        mock_client.disconnect.assert_called_once()
        mock_client.loop_stop.assert_called_once()
        assert publisher.is_connected() is False

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_disconnect_when_not_connected(self, mock_client_class, config):
        """Test disconnection when not connected to broker."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)
        publisher._connected = False

        publisher.disconnect()

        # Verify disconnect was not called but loop_stop was
        mock_client.disconnect.assert_not_called()
        mock_client.loop_stop.assert_called_once()

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_disconnect_handles_exception(self, mock_client_class, config):
        """Test that disconnect handles exceptions gracefully."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.disconnect.side_effect = Exception("Disconnect error")

        publisher = MQTTPublisher(config)
        publisher._connected = True

        # Should not raise exception
        publisher.disconnect()

        # Verify connection state was updated
        assert publisher.is_connected() is False


class TestMQTTPublisherLastWill:
    """Tests for MQTTPublisher Last Will and Testament configuration."""

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_set_last_will(self, mock_client_class, config):
        """Test Last Will and Testament configuration."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)
        publisher.set_last_will()

        # Verify Last Will was configured
        mock_client.will_set.assert_called_once_with(
            topic="radpro/availability", payload="offline", qos=1, retain=True
        )

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_set_last_will_with_custom_prefix(self, mock_client_class):
        """Test Last Will configuration with custom topic prefix."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        config = Config(
            mqtt_host="test.mosquitto.org",
            mqtt_port=1883,
            mqtt_topic_prefix="custom_prefix",
        )

        publisher = MQTTPublisher(config)
        publisher.set_last_will()

        # Verify Last Will uses custom prefix
        mock_client.will_set.assert_called_once_with(
            topic="custom_prefix/availability", payload="offline", qos=1, retain=True
        )

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_set_last_will_handles_exception(self, mock_client_class, config):
        """Test that set_last_will handles exceptions gracefully."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.will_set.side_effect = Exception("Will set error")

        publisher = MQTTPublisher(config)

        # Should not raise exception
        publisher.set_last_will()


class TestMQTTPublisherCallbacks:
    """Tests for MQTT client callbacks."""

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_on_connect_success(self, mock_client_class, config):
        """Test on_connect callback with successful connection."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)
        publisher._on_connect(mock_client, None, {}, 0)

        # Verify connection state was updated
        assert publisher.is_connected() is True

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_on_connect_failure(self, mock_client_class, config):
        """Test on_connect callback with connection failure."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)

        # Test various error codes
        for error_code in [1, 2, 3, 4, 5]:
            publisher._on_connect(mock_client, None, {}, error_code)
            assert publisher.is_connected() is False

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_on_disconnect_clean(self, mock_client_class, config):
        """Test on_disconnect callback with clean disconnect."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)
        publisher._connected = True
        publisher._on_disconnect(mock_client, None, 0)

        # Verify connection state was updated
        assert publisher.is_connected() is False

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_on_disconnect_unexpected(self, mock_client_class, config):
        """Test on_disconnect callback with unexpected disconnect."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)
        publisher._connected = True
        publisher._on_disconnect(mock_client, None, 1)

        # Verify connection state was updated
        assert publisher.is_connected() is False


class TestMQTTPublisherIsConnected:
    """Tests for MQTTPublisher is_connected method."""

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_is_connected_when_connected(self, mock_client_class, config):
        """Test is_connected returns True when connected."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)
        publisher._connected = True

        assert publisher.is_connected() is True

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_is_connected_when_not_connected(self, mock_client_class, config):
        """Test is_connected returns False when not connected."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)
        publisher._connected = False

        assert publisher.is_connected() is False


class TestMQTTPublisherTopicConstruction:
    """Tests for MQTT topic construction methods."""

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_get_state_topic(self, mock_client_class, config):
        """Test state topic construction with default prefix."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)

        # Test various sensor types
        assert publisher.get_state_topic("dose_rate") == "radpro/dose_rate/state"
        assert publisher.get_state_topic("cpm") == "radpro/cpm/state"
        assert publisher.get_state_topic("total_pulses") == "radpro/total_pulses/state"
        assert publisher.get_state_topic("battery_voltage") == "radpro/battery_voltage/state"
        assert publisher.get_state_topic("tube_lifetime") == "radpro/tube_lifetime/state"

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_get_state_topic_custom_prefix(self, mock_client_class):
        """Test state topic construction with custom prefix."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        config = Config(
            mqtt_host="test.mosquitto.org",
            mqtt_port=1883,
            mqtt_topic_prefix="custom_prefix",
        )

        publisher = MQTTPublisher(config)

        assert publisher.get_state_topic("dose_rate") == "custom_prefix/dose_rate/state"

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_get_availability_topic(self, mock_client_class, config):
        """Test availability topic construction."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)

        assert publisher.get_availability_topic() == "radpro/availability"

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_get_availability_topic_custom_prefix(self, mock_client_class):
        """Test availability topic construction with custom prefix."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        config = Config(
            mqtt_host="test.mosquitto.org",
            mqtt_port=1883,
            mqtt_topic_prefix="my_radpro",
        )

        publisher = MQTTPublisher(config)

        assert publisher.get_availability_topic() == "my_radpro/availability"

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_get_discovery_topic(self, mock_client_class, config):
        """Test discovery topic construction with default prefix."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)

        # Test with typical node_id and object_id values
        assert (
            publisher.get_discovery_topic("radpro_12345", "dose_rate")
            == "homeassistant/sensor/radpro_12345/dose_rate/config"
        )
        assert (
            publisher.get_discovery_topic("radpro_12345", "cpm")
            == "homeassistant/sensor/radpro_12345/cpm/config"
        )

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_get_discovery_topic_custom_prefix(self, mock_client_class):
        """Test discovery topic construction with custom discovery prefix."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        config = Config(
            mqtt_host="test.mosquitto.org",
            mqtt_port=1883,
            mqtt_topic_prefix="radpro",
            ha_discovery_prefix="custom_ha",
        )

        publisher = MQTTPublisher(config)

        assert (
            publisher.get_discovery_topic("radpro_12345", "dose_rate")
            == "custom_ha/sensor/radpro_12345/dose_rate/config"
        )


class TestSensorDefinitions:
    """Tests for SENSORS dictionary."""

    def test_sensors_dictionary_exists(self):
        """Test that SENSORS dictionary is defined."""
        from src.mqtt_publisher import SENSORS

        assert SENSORS is not None
        assert isinstance(SENSORS, dict)

    def test_all_required_sensors_defined(self):
        """Test that all required sensors are defined."""
        from src.mqtt_publisher import SENSORS

        required_sensors = ["dose_rate", "cpm", "total_pulses", "battery_voltage", "tube_lifetime"]

        for sensor in required_sensors:
            assert sensor in SENSORS, f"Sensor {sensor} not found in SENSORS"

    def test_sensor_metadata_completeness(self):
        """Test that each sensor has all required metadata fields."""
        from src.mqtt_publisher import SENSORS

        required_fields = ["name", "device_class", "unit_of_measurement", "state_class"]

        for sensor_type, metadata in SENSORS.items():
            for field in required_fields:
                assert field in metadata, f"Sensor {sensor_type} missing required field: {field}"

    def test_dose_rate_sensor_metadata(self):
        """Test dose_rate sensor metadata."""
        from src.mqtt_publisher import SENSORS

        dose_rate = SENSORS["dose_rate"]
        assert dose_rate["name"] == "Dose Rate"
        assert dose_rate["device_class"] is None
        assert dose_rate["unit_of_measurement"] == "µSv/h"
        assert dose_rate["icon"] == "mdi:radioactive"
        assert dose_rate["state_class"] == "measurement"

    def test_cpm_sensor_metadata(self):
        """Test cpm sensor metadata."""
        from src.mqtt_publisher import SENSORS

        cpm = SENSORS["cpm"]
        assert cpm["name"] == "Counts Per Minute"
        assert cpm["device_class"] is None
        assert cpm["unit_of_measurement"] == "CPM"
        assert cpm["icon"] == "mdi:counter"
        assert cpm["state_class"] == "measurement"

    def test_total_pulses_sensor_metadata(self):
        """Test total_pulses sensor metadata."""
        from src.mqtt_publisher import SENSORS

        total_pulses = SENSORS["total_pulses"]
        assert total_pulses["name"] == "Total Pulses"
        assert total_pulses["device_class"] is None
        assert total_pulses["unit_of_measurement"] == "pulses"
        assert total_pulses["icon"] == "mdi:counter"
        assert total_pulses["state_class"] == "total_increasing"

    def test_battery_voltage_sensor_metadata(self):
        """Test battery_voltage sensor metadata."""
        from src.mqtt_publisher import SENSORS

        battery_voltage = SENSORS["battery_voltage"]
        assert battery_voltage["name"] == "Battery Voltage"
        assert battery_voltage["device_class"] == "voltage"
        assert battery_voltage["unit_of_measurement"] == "V"
        assert battery_voltage["state_class"] == "measurement"

    def test_tube_lifetime_sensor_metadata(self):
        """Test tube_lifetime sensor metadata."""
        from src.mqtt_publisher import SENSORS

        tube_lifetime = SENSORS["tube_lifetime"]
        assert tube_lifetime["name"] == "Tube Lifetime"
        assert tube_lifetime["device_class"] == "duration"
        assert tube_lifetime["unit_of_measurement"] == "s"
        assert tube_lifetime["icon"] == "mdi:timer-outline"
        assert tube_lifetime["state_class"] == "total_increasing"


class TestDiscoveryPayloadGeneration:
    """Tests for Home Assistant discovery payload generation."""

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_generate_discovery_payload_dose_rate(self, mock_client_class, config):
        """Test discovery payload generation for dose_rate sensor."""
        from src.models import DeviceInfo

        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)

        device_info = DeviceInfo(
            hardware_id="RadPro", software_id="1.2.3", device_id="radpro_12345"
        )

        payload = publisher.generate_discovery_payload(device_info, "dose_rate")

        # Verify payload structure
        assert payload.name == "Dose Rate"
        assert payload.unique_id == "radpro_12345_dose_rate"
        assert payload.state_topic == "radpro/dose_rate/state"
        assert payload.availability_topic == "radpro/availability"
        assert payload.device_class is None
        assert payload.unit_of_measurement == "µSv/h"
        assert payload.icon == "mdi:radioactive"
        assert payload.state_class == "measurement"

        # Verify device information
        assert payload.device.identifiers == ["radpro_12345"]
        assert payload.device.name == "RadPro radpro_12345"
        assert payload.device.manufacturer == "RadPro"
        assert payload.device.model == "RadPro"
        assert payload.device.sw_version == "1.2.3"

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_generate_discovery_payload_cpm(self, mock_client_class, config):
        """Test discovery payload generation for cpm sensor."""
        from src.models import DeviceInfo

        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)

        device_info = DeviceInfo(
            hardware_id="RadPro", software_id="1.2.3", device_id="radpro_12345"
        )

        payload = publisher.generate_discovery_payload(device_info, "cpm")

        # Verify payload structure
        assert payload.name == "Counts Per Minute"
        assert payload.unique_id == "radpro_12345_cpm"
        assert payload.state_topic == "radpro/cpm/state"
        assert payload.unit_of_measurement == "CPM"
        assert payload.icon == "mdi:counter"
        assert payload.state_class == "measurement"

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_generate_discovery_payload_battery_voltage(self, mock_client_class, config):
        """Test discovery payload generation for battery_voltage sensor."""
        from src.models import DeviceInfo

        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)

        device_info = DeviceInfo(
            hardware_id="RadPro", software_id="1.2.3", device_id="radpro_12345"
        )

        payload = publisher.generate_discovery_payload(device_info, "battery_voltage")

        # Verify payload structure
        assert payload.name == "Battery Voltage"
        assert payload.unique_id == "radpro_12345_battery_voltage"
        assert payload.state_topic == "radpro/battery_voltage/state"
        assert payload.device_class == "voltage"
        assert payload.unit_of_measurement == "V"
        assert payload.state_class == "measurement"

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_generate_discovery_payload_all_sensors(self, mock_client_class, config):
        """Test discovery payload generation for all sensor types."""
        from src.models import DeviceInfo
        from src.mqtt_publisher import SENSORS

        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)

        device_info = DeviceInfo(
            hardware_id="RadPro", software_id="1.2.3", device_id="radpro_12345"
        )

        # Generate payloads for all sensors
        for sensor_type in SENSORS.keys():
            payload = publisher.generate_discovery_payload(device_info, sensor_type)

            # Verify common fields are present
            assert payload.name is not None
            assert payload.unique_id == f"radpro_12345_{sensor_type}"
            assert payload.state_topic == f"radpro/{sensor_type}/state"
            assert payload.availability_topic == "radpro/availability"

            # Verify device info is consistent
            assert payload.device.identifiers == ["radpro_12345"]
            assert payload.device.manufacturer == "RadPro"
            assert payload.device.model == "RadPro"
            assert payload.device.sw_version == "1.2.3"

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_generate_discovery_payload_unknown_sensor(self, mock_client_class, config):
        """Test discovery payload generation with unknown sensor type."""
        from src.models import DeviceInfo

        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)

        device_info = DeviceInfo(
            hardware_id="RadPro", software_id="1.2.3", device_id="radpro_12345"
        )

        # Should raise KeyError for unknown sensor type
        with pytest.raises(KeyError, match="Unknown sensor type: invalid_sensor"):
            publisher.generate_discovery_payload(device_info, "invalid_sensor")

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_generate_discovery_payload_custom_prefix(self, mock_client_class):
        """Test discovery payload generation with custom topic prefix."""
        from src.models import DeviceInfo

        mock_client = Mock()
        mock_client_class.return_value = mock_client

        config = Config(
            mqtt_host="test.mosquitto.org",
            mqtt_port=1883,
            mqtt_topic_prefix="custom_prefix",
            ha_discovery_prefix="custom_ha",
        )

        publisher = MQTTPublisher(config)

        device_info = DeviceInfo(
            hardware_id="RadPro", software_id="1.2.3", device_id="radpro_12345"
        )

        payload = publisher.generate_discovery_payload(device_info, "dose_rate")

        # Verify custom prefixes are used
        assert payload.state_topic == "custom_prefix/dose_rate/state"
        assert payload.availability_topic == "custom_prefix/availability"

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_generate_discovery_payload_different_device_ids(self, mock_client_class, config):
        """Test discovery payload generation with different device IDs."""
        from src.models import DeviceInfo

        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)

        # Test with different device IDs
        device_ids = ["radpro_12345", "radpro_67890", "device_abc"]

        for device_id in device_ids:
            device_info = DeviceInfo(hardware_id="RadPro", software_id="1.2.3", device_id=device_id)

            payload = publisher.generate_discovery_payload(device_info, "dose_rate")

            # Verify device ID is used correctly
            assert payload.unique_id == f"{device_id}_dose_rate"
            assert payload.device.identifiers == [device_id]
            assert payload.device.name == f"RadPro {device_id}"


class TestPublishDiscovery:
    """Tests for publish_discovery method."""

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_discovery_all_sensors(self, mock_client_class, config):
        """Test that publish_discovery publishes for all sensors."""
        from src.models import DeviceInfo
        from src.mqtt_publisher import SENSORS

        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock successful publish
        mock_result = Mock()
        mock_result.rc = mqtt.MQTT_ERR_SUCCESS
        mock_client.publish.return_value = mock_result

        publisher = MQTTPublisher(config)
        publisher._connected = True

        device_info = DeviceInfo(
            hardware_id="RadPro", software_id="1.2.3", device_id="radpro_12345"
        )

        publisher.publish_discovery(device_info)

        # Verify publish was called for each sensor
        assert mock_client.publish.call_count == len(SENSORS)

        # Verify each sensor was published with correct topic and payload
        for sensor_type in SENSORS.keys():
            expected_topic = f"homeassistant/sensor/radpro_12345/{sensor_type}/config"

            # Find the call for this sensor
            found = False
            for call_args in mock_client.publish.call_args_list:
                if call_args[1]["topic"] == expected_topic:
                    found = True
                    # Verify QoS and retain settings
                    assert call_args[1]["qos"] == 1
                    assert call_args[1]["retain"] is True
                    # Verify payload is valid JSON
                    import json

                    payload_dict = json.loads(call_args[1]["payload"])
                    assert "name" in payload_dict
                    assert "unique_id" in payload_dict
                    assert "state_topic" in payload_dict
                    assert "availability_topic" in payload_dict
                    assert "device" in payload_dict
                    break

            assert found, f"Discovery not published for sensor: {sensor_type}"

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_discovery_not_connected(self, mock_client_class, config):
        """Test that publish_discovery handles not connected state."""
        from src.models import DeviceInfo

        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)
        publisher._connected = False

        device_info = DeviceInfo(
            hardware_id="RadPro", software_id="1.2.3", device_id="radpro_12345"
        )

        # Should not raise exception
        publisher.publish_discovery(device_info)

        # Verify publish was not called
        mock_client.publish.assert_not_called()

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_discovery_correct_topic_format(self, mock_client_class, config):
        """Test that publish_discovery uses correct topic format."""
        from src.models import DeviceInfo

        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock successful publish
        mock_result = Mock()
        mock_result.rc = mqtt.MQTT_ERR_SUCCESS
        mock_client.publish.return_value = mock_result

        publisher = MQTTPublisher(config)
        publisher._connected = True

        device_info = DeviceInfo(
            hardware_id="RadPro", software_id="1.2.3", device_id="radpro_12345"
        )

        publisher.publish_discovery(device_info)

        # Verify all topics follow the correct format
        for call_args in mock_client.publish.call_args_list:
            topic = call_args[1]["topic"]
            # Topic should match: {ha_discovery_prefix}/sensor/{node_id}/{object_id}/config
            assert topic.startswith("homeassistant/sensor/radpro_12345/")
            assert topic.endswith("/config")

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_discovery_custom_prefixes(self, mock_client_class):
        """Test publish_discovery with custom discovery prefix."""
        from src.models import DeviceInfo

        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock successful publish
        mock_result = Mock()
        mock_result.rc = mqtt.MQTT_ERR_SUCCESS
        mock_client.publish.return_value = mock_result

        config = Config(
            mqtt_host="test.mosquitto.org",
            mqtt_port=1883,
            mqtt_topic_prefix="custom_prefix",
            ha_discovery_prefix="custom_ha",
        )

        publisher = MQTTPublisher(config)
        publisher._connected = True

        device_info = DeviceInfo(
            hardware_id="RadPro", software_id="1.2.3", device_id="radpro_12345"
        )

        publisher.publish_discovery(device_info)

        # Verify all topics use custom discovery prefix
        for call_args in mock_client.publish.call_args_list:
            topic = call_args[1]["topic"]
            assert topic.startswith("custom_ha/sensor/radpro_12345/")

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_discovery_handles_publish_error(self, mock_client_class, config):
        """Test that publish_discovery handles publish errors gracefully."""
        from src.models import DeviceInfo

        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock failed publish
        mock_result = Mock()
        mock_result.rc = mqtt.MQTT_ERR_NO_CONN
        mock_client.publish.return_value = mock_result

        publisher = MQTTPublisher(config)
        publisher._connected = True

        device_info = DeviceInfo(
            hardware_id="RadPro", software_id="1.2.3", device_id="radpro_12345"
        )

        # Should not raise exception
        publisher.publish_discovery(device_info)

        # Verify publish was attempted for all sensors
        from src.mqtt_publisher import SENSORS

        assert mock_client.publish.call_count == len(SENSORS)

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_discovery_handles_exception(self, mock_client_class, config):
        """Test that publish_discovery handles exceptions gracefully."""
        from src.models import DeviceInfo

        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock exception during publish
        mock_client.publish.side_effect = Exception("Publish error")

        publisher = MQTTPublisher(config)
        publisher._connected = True

        device_info = DeviceInfo(
            hardware_id="RadPro", software_id="1.2.3", device_id="radpro_12345"
        )

        # Should not raise exception
        publisher.publish_discovery(device_info)

        # Verify publish was attempted for all sensors
        from src.mqtt_publisher import SENSORS

        assert mock_client.publish.call_count == len(SENSORS)

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_discovery_payload_structure(self, mock_client_class, config):
        """Test that published discovery payloads have correct structure."""
        import json

        from src.models import DeviceInfo

        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock successful publish
        mock_result = Mock()
        mock_result.rc = mqtt.MQTT_ERR_SUCCESS
        mock_client.publish.return_value = mock_result

        publisher = MQTTPublisher(config)
        publisher._connected = True

        device_info = DeviceInfo(
            hardware_id="RadPro", software_id="1.2.3", device_id="radpro_12345"
        )

        publisher.publish_discovery(device_info)

        # Verify each published payload has correct structure
        for call_args in mock_client.publish.call_args_list:
            payload_json = call_args[1]["payload"]
            payload_dict = json.loads(payload_json)

            # Verify required fields
            assert "name" in payload_dict
            assert "unique_id" in payload_dict
            assert "state_topic" in payload_dict
            assert "availability_topic" in payload_dict
            assert "device" in payload_dict

            # Verify device structure
            device = payload_dict["device"]
            assert "identifiers" in device
            assert "name" in device
            assert "manufacturer" in device
            assert "model" in device
            assert "sw_version" in device

            # Verify device values
            assert device["identifiers"] == ["radpro_12345"]
            assert device["manufacturer"] == "RadPro"
            assert device["model"] == "RadPro"
            assert device["sw_version"] == "1.2.3"


class TestPublishSensorState:
    """Tests for publish_sensor_state method."""

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_sensor_state_success(self, mock_client_class, config):
        """Test successful sensor state publishing."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock successful publish
        mock_result = Mock()
        mock_result.rc = mqtt.MQTT_ERR_SUCCESS
        mock_client.publish.return_value = mock_result

        publisher = MQTTPublisher(config)
        publisher._connected = True

        # Publish a sensor state
        publisher.publish_sensor_state("dose_rate", 0.15)

        # Verify publish was called with correct parameters
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args[1]
        assert call_args["topic"] == "radpro/dose_rate/state"
        assert call_args["payload"] == "0.15"
        assert call_args["qos"] == 1
        assert call_args["retain"] is False

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_sensor_state_json_serialization(self, mock_client_class, config):
        """Test that sensor values are JSON serialized."""

        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock successful publish
        mock_result = Mock()
        mock_result.rc = mqtt.MQTT_ERR_SUCCESS
        mock_client.publish.return_value = mock_result

        publisher = MQTTPublisher(config)
        publisher._connected = True

        # Test with different value types
        test_cases = [
            ("dose_rate", 0.15, "0.15"),
            ("cpm", 23.5, "23.5"),
            ("total_pulses", 12345, "12345"),
            ("battery_voltage", 1.42, "1.42"),
            ("tube_lifetime", 3600, "3600"),
        ]

        for sensor, value, expected_json in test_cases:
            mock_client.publish.reset_mock()
            publisher.publish_sensor_state(sensor, value)

            call_args = mock_client.publish.call_args[1]
            assert call_args["payload"] == expected_json

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_sensor_state_not_connected(self, mock_client_class, config):
        """Test that publish_sensor_state handles not connected state."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)
        publisher._connected = False

        # Should not raise exception
        publisher.publish_sensor_state("dose_rate", 0.15)

        # Verify publish was not called
        mock_client.publish.assert_not_called()

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_sensor_state_publish_error(self, mock_client_class, config):
        """Test that publish_sensor_state handles publish errors."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock failed publish
        mock_result = Mock()
        mock_result.rc = mqtt.MQTT_ERR_NO_CONN
        mock_client.publish.return_value = mock_result

        publisher = MQTTPublisher(config)
        publisher._connected = True

        # Should not raise exception
        publisher.publish_sensor_state("dose_rate", 0.15)

        # Verify publish was attempted
        mock_client.publish.assert_called_once()

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_sensor_state_exception(self, mock_client_class, config):
        """Test that publish_sensor_state handles exceptions gracefully."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock exception during publish
        mock_client.publish.side_effect = Exception("Publish error")

        publisher = MQTTPublisher(config)
        publisher._connected = True

        # Should not raise exception
        publisher.publish_sensor_state("dose_rate", 0.15)

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_sensor_state_custom_prefix(self, mock_client_class):
        """Test sensor state publishing with custom topic prefix."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock successful publish
        mock_result = Mock()
        mock_result.rc = mqtt.MQTT_ERR_SUCCESS
        mock_client.publish.return_value = mock_result

        config = Config(
            mqtt_host="test.mosquitto.org",
            mqtt_port=1883,
            mqtt_topic_prefix="custom_prefix",
        )

        publisher = MQTTPublisher(config)
        publisher._connected = True

        publisher.publish_sensor_state("dose_rate", 0.15)

        # Verify custom prefix is used
        call_args = mock_client.publish.call_args[1]
        assert call_args["topic"] == "custom_prefix/dose_rate/state"

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_sensor_state_all_sensor_types(self, mock_client_class, config):
        """Test publishing state for all sensor types."""

        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock successful publish
        mock_result = Mock()
        mock_result.rc = mqtt.MQTT_ERR_SUCCESS
        mock_client.publish.return_value = mock_result

        publisher = MQTTPublisher(config)
        publisher._connected = True

        # Test publishing for each sensor type
        test_values = {
            "dose_rate": 0.15,
            "cpm": 23.5,
            "total_pulses": 12345,
            "battery_voltage": 1.42,
            "tube_lifetime": 3600,
        }

        for sensor_type, value in test_values.items():
            mock_client.publish.reset_mock()
            publisher.publish_sensor_state(sensor_type, value)

            # Verify correct topic was used
            call_args = mock_client.publish.call_args[1]
            assert call_args["topic"] == f"radpro/{sensor_type}/state"


class TestPublishAvailability:
    """Tests for publish_availability method."""

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_availability_online(self, mock_client_class, config):
        """Test publishing online availability status."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock successful publish
        mock_result = Mock()
        mock_result.rc = mqtt.MQTT_ERR_SUCCESS
        mock_client.publish.return_value = mock_result

        publisher = MQTTPublisher(config)
        publisher._connected = True

        publisher.publish_availability("online")

        # Verify publish was called with correct parameters
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args[1]
        assert call_args["topic"] == "radpro/availability"
        assert call_args["payload"] == "online"
        assert call_args["qos"] == 1
        assert call_args["retain"] is True

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_availability_offline(self, mock_client_class, config):
        """Test publishing offline availability status."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock successful publish
        mock_result = Mock()
        mock_result.rc = mqtt.MQTT_ERR_SUCCESS
        mock_client.publish.return_value = mock_result

        publisher = MQTTPublisher(config)
        publisher._connected = True

        publisher.publish_availability("offline")

        # Verify publish was called with correct parameters
        call_args = mock_client.publish.call_args[1]
        assert call_args["payload"] == "offline"

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_availability_custom_prefix(self, mock_client_class):
        """Test availability publishing with custom topic prefix."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock successful publish
        mock_result = Mock()
        mock_result.rc = mqtt.MQTT_ERR_SUCCESS
        mock_client.publish.return_value = mock_result

        config = Config(
            mqtt_host="test.mosquitto.org",
            mqtt_port=1883,
            mqtt_topic_prefix="custom_prefix",
        )

        publisher = MQTTPublisher(config)
        publisher._connected = True

        publisher.publish_availability("online")

        # Verify custom prefix is used
        call_args = mock_client.publish.call_args[1]
        assert call_args["topic"] == "custom_prefix/availability"

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_availability_publish_error(self, mock_client_class, config):
        """Test that publish_availability handles publish errors."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock failed publish
        mock_result = Mock()
        mock_result.rc = mqtt.MQTT_ERR_NO_CONN
        mock_client.publish.return_value = mock_result

        publisher = MQTTPublisher(config)
        publisher._connected = True

        # Should not raise exception
        publisher.publish_availability("online")

        # Verify publish was attempted
        mock_client.publish.assert_called_once()

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_availability_exception(self, mock_client_class, config):
        """Test that publish_availability handles exceptions gracefully."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock exception during publish
        mock_client.publish.side_effect = Exception("Publish error")

        publisher = MQTTPublisher(config)
        publisher._connected = True

        # Should not raise exception
        publisher.publish_availability("online")

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_availability_client_not_initialized(self, mock_client_class, config):
        """Test that publish_availability handles uninitialized client."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(config)
        publisher._client = None

        # Should not raise exception
        publisher.publish_availability("online")

        # Verify publish was not called
        mock_client.publish.assert_not_called()
