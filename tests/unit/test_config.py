"""Unit tests for configuration management."""

import pytest

from src.config import Config


class TestConfigDefaults:
    """Test default configuration values."""

    def test_config_has_correct_defaults(self):
        """Test that Config dataclass has correct default values."""
        config = Config(mqtt_host="test.example.com")

        # USB Serial defaults
        assert config.device_path == "/dev/ttyACM0"
        assert config.serial_baudrate == 115200
        assert config.serial_timeout == 5.0

        # MQTT defaults
        assert config.mqtt_host == "test.example.com"
        assert config.mqtt_port == 1883
        assert config.mqtt_username is None
        assert config.mqtt_password is None
        assert config.mqtt_topic_prefix == "radpro"

        # Home Assistant defaults
        assert config.ha_discovery_prefix == "homeassistant"

        # Application defaults
        assert config.poll_interval == 60
        assert config.log_level == "INFO"
        assert config.max_retries == 10
        assert config.retry_backoff_base == 2.0


class TestConfigFromEnv:
    """Test configuration loading from environment variables."""

    def test_from_env_with_minimal_config(self, monkeypatch):
        """Test loading config with only required parameters."""
        monkeypatch.setenv("MQTT_HOST", "mqtt.example.com")

        config = Config.from_env()

        assert config.mqtt_host == "mqtt.example.com"
        assert config.device_path == "/dev/ttyACM0"  # default
        assert config.mqtt_port == 1883  # default
        assert config.poll_interval == 60  # default

    def test_from_env_with_all_parameters(self, monkeypatch):
        """Test loading config with all parameters specified."""
        monkeypatch.setenv("RADPRO_DEVICE", "/dev/ttyUSB0")
        monkeypatch.setenv("MQTT_HOST", "mqtt.example.com")
        monkeypatch.setenv("MQTT_PORT", "8883")
        monkeypatch.setenv("MQTT_USERNAME", "testuser")
        monkeypatch.setenv("MQTT_PASSWORD", "testpass")
        monkeypatch.setenv("MQTT_TOPIC_PREFIX", "custom_prefix")
        monkeypatch.setenv("HA_DISCOVERY_PREFIX", "custom_ha")
        monkeypatch.setenv("POLL_INTERVAL", "30")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        config = Config.from_env()

        assert config.device_path == "/dev/ttyUSB0"
        assert config.mqtt_host == "mqtt.example.com"
        assert config.mqtt_port == 8883
        assert config.mqtt_username == "testuser"
        assert config.mqtt_password == "testpass"
        assert config.mqtt_topic_prefix == "custom_prefix"
        assert config.ha_discovery_prefix == "custom_ha"
        assert config.poll_interval == 30
        assert config.log_level == "DEBUG"

    def test_from_env_with_invalid_mqtt_port(self, monkeypatch):
        """Test that invalid MQTT_PORT raises ValueError."""
        monkeypatch.setenv("MQTT_HOST", "mqtt.example.com")
        monkeypatch.setenv("MQTT_PORT", "not_a_number")

        with pytest.raises(ValueError, match="Invalid MQTT_PORT value"):
            Config.from_env()

    def test_from_env_with_invalid_poll_interval(self, monkeypatch):
        """Test that invalid POLL_INTERVAL raises ValueError."""
        monkeypatch.setenv("MQTT_HOST", "mqtt.example.com")
        monkeypatch.setenv("POLL_INTERVAL", "not_a_number")

        with pytest.raises(ValueError, match="Invalid POLL_INTERVAL value"):
            Config.from_env()

    def test_from_env_without_mqtt_host(self, monkeypatch):
        """Test that missing MQTT_HOST creates config but fails validation."""
        # Clear MQTT_HOST if it exists
        monkeypatch.delenv("MQTT_HOST", raising=False)

        config = Config.from_env()
        assert config.mqtt_host == ""

        # Should fail validation
        with pytest.raises(ValueError, match="MQTT_HOST is required"):
            config.validate()


class TestConfigValidation:
    """Test configuration validation."""

    def test_validate_with_valid_config(self):
        """Test that valid configuration passes validation."""
        config = Config(mqtt_host="mqtt.example.com")
        config.validate()  # Should not raise

    def test_validate_missing_mqtt_host(self):
        """Test that missing MQTT_HOST fails validation."""
        config = Config(mqtt_host="")

        with pytest.raises(ValueError, match="MQTT_HOST is required"):
            config.validate()

    def test_validate_invalid_mqtt_port_too_low(self):
        """Test that MQTT_PORT below 1 fails validation."""
        config = Config(mqtt_host="mqtt.example.com", mqtt_port=0)

        with pytest.raises(ValueError, match="MQTT_PORT must be between 1 and 65535"):
            config.validate()

    def test_validate_invalid_mqtt_port_too_high(self):
        """Test that MQTT_PORT above 65535 fails validation."""
        config = Config(mqtt_host="mqtt.example.com", mqtt_port=70000)

        with pytest.raises(ValueError, match="MQTT_PORT must be between 1 and 65535"):
            config.validate()

    def test_validate_invalid_poll_interval(self):
        """Test that POLL_INTERVAL less than 1 fails validation."""
        config = Config(mqtt_host="mqtt.example.com", poll_interval=0)

        with pytest.raises(ValueError, match="POLL_INTERVAL must be at least 1 second"):
            config.validate()

    def test_validate_invalid_serial_timeout(self):
        """Test that negative serial timeout fails validation."""
        config = Config(mqtt_host="mqtt.example.com", serial_timeout=-1.0)

        with pytest.raises(ValueError, match="Serial timeout must be positive"):
            config.validate()

    def test_validate_invalid_max_retries(self):
        """Test that negative max_retries fails validation."""
        config = Config(mqtt_host="mqtt.example.com", max_retries=-1)

        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            config.validate()

    def test_validate_invalid_retry_backoff_base(self):
        """Test that retry_backoff_base <= 1.0 fails validation."""
        config = Config(mqtt_host="mqtt.example.com", retry_backoff_base=1.0)

        with pytest.raises(ValueError, match="retry_backoff_base must be greater than 1.0"):
            config.validate()

    def test_validate_invalid_log_level(self):
        """Test that invalid LOG_LEVEL fails validation."""
        config = Config(mqtt_host="mqtt.example.com", log_level="INVALID")

        with pytest.raises(ValueError, match="LOG_LEVEL must be one of"):
            config.validate()

    def test_validate_valid_log_levels(self):
        """Test that all valid log levels pass validation."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in valid_levels:
            config = Config(mqtt_host="mqtt.example.com", log_level=level)
            config.validate()  # Should not raise

    def test_validate_log_level_case_insensitive(self):
        """Test that log level validation is case-insensitive."""
        config = Config(mqtt_host="mqtt.example.com", log_level="debug")
        config.validate()  # Should not raise (uppercase check in validation)

    def test_validate_empty_device_path(self):
        """Test that empty device path fails validation."""
        config = Config(mqtt_host="mqtt.example.com", device_path="")

        with pytest.raises(ValueError, match="RADPRO_DEVICE cannot be empty"):
            config.validate()

    def test_validate_empty_mqtt_topic_prefix(self):
        """Test that empty MQTT topic prefix fails validation."""
        config = Config(mqtt_host="mqtt.example.com", mqtt_topic_prefix="")

        with pytest.raises(ValueError, match="MQTT_TOPIC_PREFIX cannot be empty"):
            config.validate()

    def test_validate_empty_ha_discovery_prefix(self):
        """Test that empty HA discovery prefix fails validation."""
        config = Config(mqtt_host="mqtt.example.com", ha_discovery_prefix="")

        with pytest.raises(ValueError, match="HA_DISCOVERY_PREFIX cannot be empty"):
            config.validate()


class TestConfigIntegration:
    """Integration tests for configuration loading and validation."""

    def test_from_env_and_validate_success(self, monkeypatch):
        """Test complete flow: load from env and validate."""
        monkeypatch.setenv("MQTT_HOST", "mqtt.example.com")
        monkeypatch.setenv("MQTT_PORT", "1883")
        monkeypatch.setenv("POLL_INTERVAL", "60")

        config = Config.from_env()
        config.validate()  # Should not raise

        assert config.mqtt_host == "mqtt.example.com"

    def test_from_env_and_validate_failure(self, monkeypatch):
        """Test that invalid env values are caught during validation."""
        monkeypatch.setenv("MQTT_HOST", "mqtt.example.com")
        monkeypatch.setenv("MQTT_PORT", "70000")  # Invalid port

        config = Config.from_env()
        with pytest.raises(ValueError, match="MQTT_PORT must be between 1 and 65535"):
            config.validate()
