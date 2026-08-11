"""Unit tests for main entry point.

Tests the main entry point functionality including configuration loading,
logging setup, and error handling.
"""

import os
from unittest.mock import MagicMock, patch

from src.main import main


class TestMain:
    """Test cases for main entry point."""

    @patch("src.main.RadProBridge")
    @patch("src.main.configure_logging")
    @patch("src.main.Config.from_env")
    def test_main_success(
        self,
        mock_config_from_env: MagicMock,
        mock_configure_logging: MagicMock,
        mock_bridge: MagicMock,
    ) -> None:
        """Test successful main execution.

        Verifies that main() successfully:
        - Loads configuration
        - Validates configuration
        - Configures logging
        - Creates and runs the bridge
        - Returns exit code 0
        """
        # Setup mock configuration
        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config.device_path = "/dev/ttyACM0"
        mock_config.mqtt_host = "localhost"
        mock_config.mqtt_port = 1883
        mock_config.poll_interval = 60
        mock_config_from_env.return_value = mock_config

        # Setup mock bridge
        mock_bridge_instance = MagicMock()
        mock_bridge_instance.run.return_value = 0
        mock_bridge.return_value = mock_bridge_instance

        # Run main
        with patch.dict(os.environ, {"LOG_FORMAT": "text"}):
            exit_code = main()

        # Verify configuration was loaded and validated
        mock_config_from_env.assert_called_once()
        mock_config.validate.assert_called_once()

        # Verify logging was configured
        mock_configure_logging.assert_called_once_with(log_level="INFO", json_format=False)

        # Verify bridge was created and run
        mock_bridge.assert_called_once_with(config=mock_config)
        mock_bridge_instance.setup_signal_handlers.assert_called_once()
        mock_bridge_instance.run.assert_called_once()

        # Verify exit code
        assert exit_code == 0

    @patch("src.main.RadProBridge")
    @patch("src.main.configure_logging")
    @patch("src.main.Config.from_env")
    def test_main_json_logging(
        self,
        mock_config_from_env: MagicMock,
        mock_configure_logging: MagicMock,
        mock_bridge: MagicMock,
    ) -> None:
        """Test main with JSON logging format.

        Verifies that LOG_FORMAT=json enables JSON logging.
        """
        # Setup mock configuration
        mock_config = MagicMock()
        mock_config.log_level = "DEBUG"
        mock_config_from_env.return_value = mock_config

        # Setup mock bridge
        mock_bridge_instance = MagicMock()
        mock_bridge_instance.run.return_value = 0
        mock_bridge.return_value = mock_bridge_instance

        # Run main with JSON format
        with patch.dict(os.environ, {"LOG_FORMAT": "json"}):
            exit_code = main()

        # Verify JSON logging was enabled
        mock_configure_logging.assert_called_once_with(log_level="DEBUG", json_format=True)

        assert exit_code == 0

    @patch("src.main.Config.from_env")
    def test_main_configuration_error(self, mock_config_from_env: MagicMock) -> None:
        """Test main with configuration validation error.

        Verifies that configuration errors result in exit code 1.
        """
        # Setup mock to raise ValueError
        mock_config = MagicMock()
        mock_config.validate.side_effect = ValueError("MQTT_HOST is required")
        mock_config_from_env.return_value = mock_config

        # Run main
        exit_code = main()

        # Verify exit code is 1
        assert exit_code == 1

    @patch("src.main.RadProBridge")
    @patch("src.main.configure_logging")
    @patch("src.main.Config.from_env")
    def test_main_keyboard_interrupt(
        self,
        mock_config_from_env: MagicMock,
        mock_configure_logging: MagicMock,
        mock_bridge: MagicMock,
    ) -> None:
        """Test main with keyboard interrupt.

        Verifies that KeyboardInterrupt results in clean exit with code 0.
        """
        # Setup mock configuration
        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config_from_env.return_value = mock_config

        # Setup mock bridge to raise KeyboardInterrupt
        mock_bridge_instance = MagicMock()
        mock_bridge_instance.run.side_effect = KeyboardInterrupt()
        mock_bridge.return_value = mock_bridge_instance

        # Run main
        with patch.dict(os.environ, {"LOG_FORMAT": "text"}):
            exit_code = main()

        # Verify exit code is 0 (clean exit)
        assert exit_code == 0

    @patch("src.main.RadProBridge")
    @patch("src.main.configure_logging")
    @patch("src.main.Config.from_env")
    def test_main_unexpected_exception(
        self,
        mock_config_from_env: MagicMock,
        mock_configure_logging: MagicMock,
        mock_bridge: MagicMock,
    ) -> None:
        """Test main with unexpected exception.

        Verifies that unexpected exceptions result in exit code 1.
        """
        # Setup mock configuration
        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config_from_env.return_value = mock_config

        # Setup mock bridge to raise unexpected exception
        mock_bridge_instance = MagicMock()
        mock_bridge_instance.run.side_effect = RuntimeError("Unexpected error")
        mock_bridge.return_value = mock_bridge_instance

        # Run main
        with patch.dict(os.environ, {"LOG_FORMAT": "text"}):
            exit_code = main()

        # Verify exit code is 1
        assert exit_code == 1

    @patch("src.main.RadProBridge")
    @patch("src.main.configure_logging")
    @patch("src.main.Config.from_env")
    def test_main_propagates_restart_request(
        self,
        mock_config_from_env: MagicMock,
        mock_configure_logging: MagicMock,
        mock_bridge: MagicMock,
    ) -> None:
        """Test that a watchdog-triggered exit reaches the container runtime.

        The bridge asks for a restart by exiting non-zero; swallowing that here
        would leave a stalled bridge running forever under a restart policy
        that only reacts to failures.
        """
        mock_config = MagicMock()
        mock_config.log_level = "INFO"
        mock_config_from_env.return_value = mock_config

        mock_bridge_instance = MagicMock()
        mock_bridge_instance.run.return_value = 2
        mock_bridge.return_value = mock_bridge_instance

        with patch.dict(os.environ, {"LOG_FORMAT": "text"}):
            exit_code = main()

        assert exit_code == 2
