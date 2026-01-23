"""Property-based tests for MQTT topic construction.

Tests universal properties of topic construction across various inputs
using hypothesis for property-based testing.
"""

import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import Mock, patch

from src.config import Config
from src.mqtt_publisher import MQTTPublisher


# Strategy for valid topic prefixes (alphanumeric, underscores, hyphens)
topic_prefix_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-"),
    min_size=1,
    max_size=50,
).filter(lambda x: x and not x.startswith("-") and not x.endswith("-"))

# Strategy for sensor types (alphanumeric, underscores)
sensor_type_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"),
    min_size=1,
    max_size=30,
).filter(lambda x: x and x[0].isalpha())

# Strategy for node IDs and object IDs
identifier_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-"),
    min_size=1,
    max_size=50,
).filter(lambda x: x and x[0].isalnum())


class TestTopicConstructionProperties:
    """Property-based tests for topic construction."""

    @settings(max_examples=20)
    @given(prefix=topic_prefix_strategy, sensor_type=sensor_type_strategy)
    @patch("src.mqtt_publisher.mqtt.Client")
    def test_property_4_state_topic_format(self, mock_client_class, prefix, sensor_type):
        """Property 4: Topic Construction with Prefix.

        For any valid topic prefix and sensor type, the constructed state topic
        SHALL follow the pattern "{prefix}/{sensor_type}/state".

        **Validates: Requirements 3.5, 3.6**

        Feature: radpro-mqtt-bridge, Property 4: Topic Construction with Prefix
        """
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        config = Config(
            mqtt_host="test.mosquitto.org",
            mqtt_port=1883,
            mqtt_topic_prefix=prefix,
        )

        publisher = MQTTPublisher(config)
        state_topic = publisher.get_state_topic(sensor_type)

        # Verify the topic follows the expected pattern
        expected_topic = f"{prefix}/{sensor_type}/state"
        assert state_topic == expected_topic

        # Verify the topic contains all three parts
        parts = state_topic.split("/")
        assert len(parts) == 3
        assert parts[0] == prefix
        assert parts[1] == sensor_type
        assert parts[2] == "state"

    @settings(max_examples=20)
    @given(
        discovery_prefix=topic_prefix_strategy,
        node_id=identifier_strategy,
        object_id=identifier_strategy,
    )
    @patch("src.mqtt_publisher.mqtt.Client")
    def test_property_5_discovery_topic_format(
        self, mock_client_class, discovery_prefix, node_id, object_id
    ):
        """Property 5: Discovery Topic Format.

        For any valid discovery prefix, node_id, and object_id, the constructed
        discovery topic SHALL follow the pattern
        "{discovery_prefix}/sensor/{node_id}/{object_id}/config".

        **Validates: Requirements 4.2, 4.7**

        Feature: radpro-mqtt-bridge, Property 5: Discovery Topic Format
        """
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        config = Config(
            mqtt_host="test.mosquitto.org",
            mqtt_port=1883,
            ha_discovery_prefix=discovery_prefix,
        )

        publisher = MQTTPublisher(config)
        discovery_topic = publisher.get_discovery_topic(node_id, object_id)

        # Verify the topic follows the expected pattern
        expected_topic = f"{discovery_prefix}/sensor/{node_id}/{object_id}/config"
        assert discovery_topic == expected_topic

        # Verify the topic contains all five parts
        parts = discovery_topic.split("/")
        assert len(parts) == 5
        assert parts[0] == discovery_prefix
        assert parts[1] == "sensor"
        assert parts[2] == node_id
        assert parts[3] == object_id
        assert parts[4] == "config"

    @settings(max_examples=20)
    @given(prefix=topic_prefix_strategy)
    @patch("src.mqtt_publisher.mqtt.Client")
    def test_availability_topic_consistency(self, mock_client_class, prefix):
        """Test that availability topic is consistent with prefix.

        For any valid prefix, the availability topic should always use
        the same format.
        """
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        config = Config(
            mqtt_host="test.mosquitto.org",
            mqtt_port=1883,
            mqtt_topic_prefix=prefix,
        )

        publisher = MQTTPublisher(config)
        availability_topic = publisher.get_availability_topic()

        # Verify the topic follows the expected pattern
        expected_topic = f"{prefix}/availability"
        assert availability_topic == expected_topic

        # Verify the topic contains exactly two parts
        parts = availability_topic.split("/")
        assert len(parts) == 2
        assert parts[0] == prefix
        assert parts[1] == "availability"

    @settings(max_examples=20)
    @given(
        prefix=topic_prefix_strategy,
        sensor_type=sensor_type_strategy,
    )
    @patch("src.mqtt_publisher.mqtt.Client")
    def test_state_topic_no_trailing_slash(self, mock_client_class, prefix, sensor_type):
        """Test that state topics never have trailing slashes."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        config = Config(
            mqtt_host="test.mosquitto.org",
            mqtt_port=1883,
            mqtt_topic_prefix=prefix,
        )

        publisher = MQTTPublisher(config)
        state_topic = publisher.get_state_topic(sensor_type)

        # Verify no trailing slash
        assert not state_topic.endswith("/")

    @settings(max_examples=20)
    @given(
        discovery_prefix=topic_prefix_strategy,
        node_id=identifier_strategy,
        object_id=identifier_strategy,
    )
    @patch("src.mqtt_publisher.mqtt.Client")
    def test_discovery_topic_no_trailing_slash(
        self, mock_client_class, discovery_prefix, node_id, object_id
    ):
        """Test that discovery topics never have trailing slashes."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        config = Config(
            mqtt_host="test.mosquitto.org",
            mqtt_port=1883,
            ha_discovery_prefix=discovery_prefix,
        )

        publisher = MQTTPublisher(config)
        discovery_topic = publisher.get_discovery_topic(node_id, object_id)

        # Verify no trailing slash
        assert not discovery_topic.endswith("/")

    @settings(max_examples=20)
    @given(
        prefix=topic_prefix_strategy,
        sensor_type=sensor_type_strategy,
    )
    @patch("src.mqtt_publisher.mqtt.Client")
    def test_state_topic_no_double_slashes(self, mock_client_class, prefix, sensor_type):
        """Test that state topics never contain double slashes."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        config = Config(
            mqtt_host="test.mosquitto.org",
            mqtt_port=1883,
            mqtt_topic_prefix=prefix,
        )

        publisher = MQTTPublisher(config)
        state_topic = publisher.get_state_topic(sensor_type)

        # Verify no double slashes
        assert "//" not in state_topic

    @settings(max_examples=20)
    @given(
        discovery_prefix=topic_prefix_strategy,
        node_id=identifier_strategy,
        object_id=identifier_strategy,
    )
    @patch("src.mqtt_publisher.mqtt.Client")
    def test_discovery_topic_no_double_slashes(
        self, mock_client_class, discovery_prefix, node_id, object_id
    ):
        """Test that discovery topics never contain double slashes."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        config = Config(
            mqtt_host="test.mosquitto.org",
            mqtt_port=1883,
            ha_discovery_prefix=discovery_prefix,
        )

        publisher = MQTTPublisher(config)
        discovery_topic = publisher.get_discovery_topic(node_id, object_id)

        # Verify no double slashes
        assert "//" not in discovery_topic
