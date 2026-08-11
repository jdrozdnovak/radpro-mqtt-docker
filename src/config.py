"""Configuration management for RadPro MQTT Bridge.

This module provides configuration loading and validation from environment variables.
"""

import os
import socket
from dataclasses import dataclass


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
        mqtt_client_id: MQTT client identifier (empty = derived from hostname)
        mqtt_keepalive: MQTT keepalive interval in seconds
        ha_discovery_prefix: Home Assistant discovery prefix (Requirement 9.8)
        poll_interval: Data polling interval in seconds (Requirement 9.7)
        log_level: Logging verbosity level (Requirement 9.9)
        max_retries: Maximum device connection retry attempts (MQTT
            reconnection is handled by the MQTT client itself)
        retry_backoff_base: Base for exponential backoff calculation
        watchdog_timeout: Seconds without a successful publish before the
            process exits so the container supervisor restarts it (0 = auto)
        health_file: Path of the file touched after every successful publish
        max_consecutive_failures: Failed poll cycles before forcing a device
            reconnect
        publish_ack_timeout: Seconds to wait for the broker to acknowledge a
            QoS 1 publish before considering the connection stalled
    """

    # USB Serial Configuration (Requirement 9.1)
    device_path: str = "/dev/ttyACM0"
    serial_baudrate: int = 115200
    serial_timeout: float = 5.0

    # MQTT Configuration (Requirements 9.2, 9.3, 9.4, 9.5, 9.6)
    mqtt_host: str = ""  # Required, no default
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_topic_prefix: str = "radpro"
    mqtt_client_id: str = ""  # Empty means "derive a unique id from the hostname"
    mqtt_keepalive: int = 60

    # Home Assistant Configuration (Requirement 9.8)
    ha_discovery_prefix: str = "homeassistant"

    # Application Configuration (Requirements 9.7, 9.9)
    poll_interval: int = 60
    log_level: str = "INFO"
    max_retries: int = 10
    retry_backoff_base: float = 2.0

    # Reliability / self-healing configuration
    watchdog_timeout: int = 0  # 0 = derive from poll_interval
    health_file: str = "/tmp/health"
    max_consecutive_failures: int = 5
    publish_ack_timeout: float = 10.0

    # Enhanced Features Configuration
    enable_advanced_sensors: bool = True
    sync_device_time: bool = True
    time_sync_interval: int = 86400  # Re-sync every 24 hours (0 = once only)
    enable_pulse_tracking: bool = True
    pulse_tracking_windows: tuple[int, ...] = (1, 5, 15)  # Minutes for moving averages

    @property
    def effective_watchdog_timeout(self) -> int:
        """Seconds of no successful publish that count as a stalled bridge.

        When WATCHDOG_TIMEOUT is not set explicitly, allow five polling cycles
        (but never less than 5 minutes) before declaring the bridge stalled.

        Returns:
            int: Watchdog timeout in seconds
        """
        if self.watchdog_timeout > 0:
            return self.watchdog_timeout
        return max(300, self.poll_interval * 5)

    @property
    def effective_client_id(self) -> str:
        """MQTT client identifier to use when connecting.

        A client id must be unique per broker connection: if two clients share
        one, the broker kicks the older connection off in an endless loop and
        data silently stops flowing. Derive a per-host default when the user
        has not configured one explicitly.

        Returns:
            str: The MQTT client identifier
        """
        if self.mqtt_client_id:
            return self.mqtt_client_id
        return f"radpro-mqtt-bridge-{socket.gethostname()}"

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
        - MQTT_CLIENT_ID -> mqtt_client_id
        - MQTT_KEEPALIVE -> mqtt_keepalive
        - WATCHDOG_TIMEOUT -> watchdog_timeout
        - HEALTH_FILE -> health_file
        - MAX_CONSECUTIVE_FAILURES -> max_consecutive_failures
        - PUBLISH_ACK_TIMEOUT -> publish_ack_timeout

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
        mqtt_client_id = os.getenv("MQTT_CLIENT_ID", "")
        mqtt_keepalive_str = os.getenv("MQTT_KEEPALIVE", "60")
        ha_discovery_prefix = os.getenv("HA_DISCOVERY_PREFIX", "homeassistant")
        poll_interval_str = os.getenv("POLL_INTERVAL", "60")
        log_level = os.getenv("LOG_LEVEL", "INFO")

        # Reliability / self-healing configuration
        watchdog_timeout_str = os.getenv("WATCHDOG_TIMEOUT", "0")
        health_file = os.getenv("HEALTH_FILE", "/tmp/health")
        max_consecutive_failures_str = os.getenv("MAX_CONSECUTIVE_FAILURES", "5")
        publish_ack_timeout_str = os.getenv("PUBLISH_ACK_TIMEOUT", "10.0")

        # Enhanced features configuration
        enable_advanced_sensors = os.getenv("ENABLE_ADVANCED_SENSORS", "true").lower() == "true"
        sync_device_time = os.getenv("SYNC_DEVICE_TIME", "true").lower() == "true"
        time_sync_interval_str = os.getenv("TIME_SYNC_INTERVAL", "86400")
        enable_pulse_tracking = os.getenv("ENABLE_PULSE_TRACKING", "true").lower() == "true"
        pulse_tracking_windows_str = os.getenv("PULSE_TRACKING_WINDOWS", "1,5,15")

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

        try:
            time_sync_interval = int(time_sync_interval_str)
        except ValueError as e:
            raise ValueError(
                f"Invalid TIME_SYNC_INTERVAL value '{time_sync_interval_str}': must be an integer"
            ) from e

        try:
            mqtt_keepalive = int(mqtt_keepalive_str)
        except ValueError as e:
            raise ValueError(
                f"Invalid MQTT_KEEPALIVE value '{mqtt_keepalive_str}': must be an integer"
            ) from e

        try:
            watchdog_timeout = int(watchdog_timeout_str)
        except ValueError as e:
            raise ValueError(
                f"Invalid WATCHDOG_TIMEOUT value '{watchdog_timeout_str}': must be an integer"
            ) from e

        try:
            max_consecutive_failures = int(max_consecutive_failures_str)
        except ValueError as e:
            raise ValueError(
                f"Invalid MAX_CONSECUTIVE_FAILURES value '{max_consecutive_failures_str}': "
                f"must be an integer"
            ) from e

        try:
            publish_ack_timeout = float(publish_ack_timeout_str)
        except ValueError as e:
            raise ValueError(
                f"Invalid PUBLISH_ACK_TIMEOUT value '{publish_ack_timeout_str}': must be a number"
            ) from e

        # Parse pulse tracking windows
        try:
            pulse_tracking_windows = tuple(
                int(w.strip()) for w in pulse_tracking_windows_str.split(",")
            )
        except ValueError as e:
            raise ValueError(
                f"Invalid PULSE_TRACKING_WINDOWS value '{pulse_tracking_windows_str}': "
                f"must be comma-separated integers"
            ) from e

        # Create config instance
        config = cls(
            device_path=device_path,
            mqtt_host=mqtt_host,
            mqtt_port=mqtt_port,
            mqtt_username=mqtt_username,
            mqtt_password=mqtt_password,
            mqtt_topic_prefix=mqtt_topic_prefix,
            mqtt_client_id=mqtt_client_id,
            mqtt_keepalive=mqtt_keepalive,
            ha_discovery_prefix=ha_discovery_prefix,
            poll_interval=poll_interval,
            log_level=log_level,
            watchdog_timeout=watchdog_timeout,
            health_file=health_file,
            max_consecutive_failures=max_consecutive_failures,
            publish_ack_timeout=publish_ack_timeout,
            enable_advanced_sensors=enable_advanced_sensors,
            sync_device_time=sync_device_time,
            time_sync_interval=time_sync_interval,
            enable_pulse_tracking=enable_pulse_tracking,
            pulse_tracking_windows=pulse_tracking_windows,
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

        # Validate reliability settings
        if self.mqtt_keepalive < 5:
            raise ValueError(
                f"MQTT_KEEPALIVE must be at least 5 seconds, got {self.mqtt_keepalive}"
            )

        if self.watchdog_timeout < 0:
            raise ValueError(f"WATCHDOG_TIMEOUT must be non-negative, got {self.watchdog_timeout}")

        if 0 < self.watchdog_timeout <= self.poll_interval:
            raise ValueError(
                f"WATCHDOG_TIMEOUT ({self.watchdog_timeout}s) must be greater than "
                f"POLL_INTERVAL ({self.poll_interval}s), otherwise the bridge would "
                "restart before it can publish"
            )

        if self.max_consecutive_failures < 1:
            raise ValueError(
                f"MAX_CONSECUTIVE_FAILURES must be at least 1, got {self.max_consecutive_failures}"
            )

        if self.publish_ack_timeout <= 0:
            raise ValueError(
                f"PUBLISH_ACK_TIMEOUT must be positive, got {self.publish_ack_timeout}"
            )

        if not self.health_file:
            raise ValueError("HEALTH_FILE cannot be empty")
