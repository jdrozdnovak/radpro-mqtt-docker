"""Configuration management for RadPro MQTT Bridge.

This module provides configuration loading and validation from environment variables.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Configuration for RadPro MQTT Bridge.

    This dataclass holds all configuration parameters for the bridge application,
    loaded from environment variables with sensible defaults.

    Attributes:
        device_path: USB device path for RadPro device (Requirement 9.1)
        serial_baudrate: Serial communication baud rate
        serial_timeout: Timeout for serial operations in seconds
        mqtt_host: MQTT broker hostname (Requirement 9.2)
        mqtt_port: MQTT broker port (Requirement 9.3)
        mqtt_username: MQTT authentication username (Requirement 9.4)
        mqtt_password: MQTT authentication password (Requirement 9.5)
        mqtt_topic_prefix: Prefix for MQTT topics (Requirement 9.6)
        ha_discovery_prefix: Home Assistant discovery prefix (Requirement 9.8)
        poll_interval: Data polling interval in seconds (Requirement 9.7)
        log_level: Logging verbosity level (Requirement 9.9)
        max_retries: Maximum connection retry attempts
        retry_backoff_base: Base for exponential backoff calculation
    """

    # USB Serial Configuration (Requirement 9.1)
    device_path: str = "/dev/ttyACM0"
    serial_baudrate: int = 115200
    serial_timeout: float = 5.0

    # MQTT Configuration (Requirements 9.2, 9.3, 9.4, 9.5, 9.6)
    mqtt_host: str = ""  # Required, no default
    mqtt_port: int = 1883
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_topic_prefix: str = "radpro"

    # Home Assistant Configuration (Requirement 9.8)
    ha_discovery_prefix: str = "homeassistant"

    # Application Configuration (Requirements 9.7, 9.9)
    poll_interval: int = 60
    log_level: str = "INFO"
    max_retries: int = 10
    retry_backoff_base: float = 2.0

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables.

        Reads configuration values from environment variables and creates
        a Config instance. Uses default values for optional parameters.

        Environment variable mapping:
        - RADPRO_DEVICE -> device_path (Requirement 9.1)
        - MQTT_HOST -> mqtt_host (Requirement 9.2)
        - MQTT_PORT -> mqtt_port (Requirement 9.3)
        - MQTT_USERNAME -> mqtt_username (Requirement 9.4)
        - MQTT_PASSWORD -> mqtt_password (Requirement 9.5)
        - MQTT_TOPIC_PREFIX -> mqtt_topic_prefix (Requirement 9.6)
        - POLL_INTERVAL -> poll_interval (Requirement 9.7)
        - HA_DISCOVERY_PREFIX -> ha_discovery_prefix (Requirement 9.8)
        - LOG_LEVEL -> log_level (Requirement 9.9)

        Returns:
            Config: Configuration instance with values from environment

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Load required parameters
        mqtt_host = os.getenv("MQTT_HOST", "")

        # Load optional parameters with defaults
        device_path = os.getenv("RADPRO_DEVICE", "/dev/ttyACM0")
        mqtt_port_str = os.getenv("MQTT_PORT", "1883")
        mqtt_username = os.getenv("MQTT_USERNAME")
        mqtt_password = os.getenv("MQTT_PASSWORD")
        mqtt_topic_prefix = os.getenv("MQTT_TOPIC_PREFIX", "radpro")
        ha_discovery_prefix = os.getenv("HA_DISCOVERY_PREFIX", "homeassistant")
        poll_interval_str = os.getenv("POLL_INTERVAL", "60")
        log_level = os.getenv("LOG_LEVEL", "INFO")

        # Type conversions with error handling (Requirement 9.10)
        try:
            mqtt_port = int(mqtt_port_str)
        except ValueError as e:
            raise ValueError(
                f"Invalid MQTT_PORT value '{mqtt_port_str}': must be an integer"
            ) from e

        try:
            poll_interval = int(poll_interval_str)
        except ValueError as e:
            raise ValueError(
                f"Invalid POLL_INTERVAL value '{poll_interval_str}': must be an integer"
            ) from e

        # Create config instance
        config = cls(
            device_path=device_path,
            mqtt_host=mqtt_host,
            mqtt_port=mqtt_port,
            mqtt_username=mqtt_username,
            mqtt_password=mqtt_password,
            mqtt_topic_prefix=mqtt_topic_prefix,
            ha_discovery_prefix=ha_discovery_prefix,
            poll_interval=poll_interval,
            log_level=log_level,
        )

        return config

    def validate(self) -> None:
        """Validate configuration values.

        Checks that all required parameters are present and that all
        parameter values are within valid ranges.

        Raises:
            ValueError: If validation fails (Requirement 9.10)
        """
        # Validate required parameters (Requirement 9.10)
        if not self.mqtt_host:
            raise ValueError("MQTT_HOST is required but not provided")

        # Validate parameter ranges (Requirement 9.10)
        if self.mqtt_port < 1 or self.mqtt_port > 65535:
            raise ValueError(f"MQTT_PORT must be between 1 and 65535, got {self.mqtt_port}")

        if self.poll_interval < 1:
            raise ValueError(f"POLL_INTERVAL must be at least 1 second, got {self.poll_interval}")

        if self.serial_timeout <= 0:
            raise ValueError(f"Serial timeout must be positive, got {self.serial_timeout}")

        if self.max_retries < 0:
            raise ValueError(f"max_retries must be non-negative, got {self.max_retries}")

        if self.retry_backoff_base <= 1.0:
            raise ValueError(
                f"retry_backoff_base must be greater than 1.0, got {self.retry_backoff_base}"
            )

        # Validate log level (Requirement 9.9)
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_log_levels}, got '{self.log_level}'")

        # Validate device path is not empty
        if not self.device_path:
            raise ValueError("RADPRO_DEVICE cannot be empty")

        # Validate topic prefixes are not empty
        if not self.mqtt_topic_prefix:
            raise ValueError("MQTT_TOPIC_PREFIX cannot be empty")

        if not self.ha_discovery_prefix:
            raise ValueError("HA_DISCOVERY_PREFIX cannot be empty")
