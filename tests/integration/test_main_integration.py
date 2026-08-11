"""Integration tests for main entry point.

Tests the complete application startup flow including configuration,
logging, and component initialization.
"""

import os
from unittest.mock import MagicMock, patch

from src.main import main


class TestMainIntegration:
    """Integration test cases for main entry point."""

    @patch("src.main.RadProBridge")
    def test_main_complete_flow(self, mock_bridge: MagicMock) -> None:
        """Test complete main execution flow.

        Verifies the entire flow from configuration loading through
        bridge execution with realistic environment variables.
        """
        # Setup mock bridge
        mock_bridge_instance = MagicMock()
        mock_bridge_instance.run.return_value = 0
        mock_bridge.return_value = mock_bridge_instance

        # Set up realistic environment variables
        test_env = {
            "MQTT_HOST": "mqtt.example.com",
            "MQTT_PORT": "1883",
            "MQTT_USERNAME": "testuser",
            "MQTT_PASSWORD": "testpass",
            "MQTT_TOPIC_PREFIX": "radpro",
            "HA_DISCOVERY_PREFIX": "homeassistant",
            "RADPRO_DEVICE": "/dev/ttyACM0",
            "POLL_INTERVAL": "60",
            "LOG_LEVEL": "INFO",
            "LOG_FORMAT": "text",
        }

        # Run main with test environment
        with patch.dict(os.environ, test_env, clear=True):
            exit_code = main()

        # Verify successful execution
        assert exit_code == 0

        # Verify bridge was created with correct configuration
        mock_bridge.assert_called_once()
        config = mock_bridge.call_args[1]["config"]

        assert config.mqtt_host == "mqtt.example.com"
        assert config.mqtt_port == 1883
        assert config.mqtt_username == "testuser"
        assert config.mqtt_password == "testpass"
        assert config.mqtt_topic_prefix == "radpro"
        assert config.ha_discovery_prefix == "homeassistant"
        assert config.device_path == "/dev/ttyACM0"
        assert config.poll_interval == 60
        assert config.log_level == "INFO"

        # Verify bridge methods were called
        mock_bridge_instance.setup_signal_handlers.assert_called_once()
        mock_bridge_instance.run.assert_called_once()

    @patch("src.main.RadProBridge")
    def test_main_with_json_logging(self, mock_bridge: MagicMock) -> None:
        """Test main with JSON logging enabled.

        Verifies that JSON logging is properly configured when LOG_FORMAT=json.
        """
        # Setup mock bridge
        mock_bridge_instance = MagicMock()
        mock_bridge_instance.run.return_value = 0
        mock_bridge.return_value = mock_bridge_instance

        # Set up environment with JSON logging
        test_env = {
            "MQTT_HOST": "mqtt.example.com",
            "LOG_LEVEL": "DEBUG",
            "LOG_FORMAT": "json",
        }

        # Run main with test environment
        with patch.dict(os.environ, test_env, clear=True):
            exit_code = main()

        # Verify successful execution
        assert exit_code == 0

        # Verify configuration
        config = mock_bridge.call_args[1]["config"]
        assert config.log_level == "DEBUG"

    def test_main_missing_required_config(self) -> None:
        """Test main with missing required configuration.

        Verifies that missing MQTT_HOST results in configuration error.
        """
        # Set up environment without MQTT_HOST
        test_env = {
            "LOG_LEVEL": "INFO",
        }

        # Run main with incomplete environment
        with patch.dict(os.environ, test_env, clear=True):
            exit_code = main()

        # Verify error exit code
        assert exit_code == 1

    @patch("src.main.RadProBridge")
    def test_main_with_defaults(self, mock_bridge: MagicMock) -> None:
        """Test main with default configuration values.

        Verifies that default values are used when optional environment
        variables are not provided.
        """
        # Setup mock bridge
        mock_bridge_instance = MagicMock()
        mock_bridge_instance.run.return_value = 0
        mock_bridge.return_value = mock_bridge_instance

        # Set up minimal environment (only required variables)
        test_env = {
            "MQTT_HOST": "mqtt.example.com",
        }

        # Run main with minimal environment
        with patch.dict(os.environ, test_env, clear=True):
            exit_code = main()

        # Verify successful execution
        assert exit_code == 0

        # Verify default values were used
        config = mock_bridge.call_args[1]["config"]
        assert config.mqtt_port == 1883  # Default
        assert config.mqtt_topic_prefix == "radpro"  # Default
        assert config.ha_discovery_prefix == "homeassistant"  # Default
        assert config.device_path == "/dev/ttyACM0"  # Default
        assert config.poll_interval == 60  # Default
        assert config.log_level == "INFO"  # Default
