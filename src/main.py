"""Main entry point for RadPro MQTT Bridge.

This module provides the main entry point for the application, handling
configuration loading, logging setup, and application lifecycle management.
"""

import logging
import os
import sys

from src.config import Config
from src.logging_config import configure_logging
from src.radpro_bridge import RadProBridge

logger = logging.getLogger(__name__)


def main() -> int:
    """Main entry point for the RadPro MQTT Bridge application.

    This function:
    1. Loads configuration from environment variables
    2. Initializes logging with the configured level
    3. Creates and runs the RadProBridge
    4. Handles top-level exceptions

    Returns:
        int: Exit code (0 for success, 1 for failure)

    Requirements: 6.1, 6.3, 6.4
    """
    try:
        # Step 1: Load configuration from environment (Requirements 6.1, 6.3)
        print("Loading configuration from environment variables...")
        config = Config.from_env()

        # Validate configuration (Requirement 6.3)
        config.validate()

        # Step 2: Initialize logging (Requirements 6.4, 9.9)
        # Use JSON format in production (when LOG_FORMAT=json)
        log_format = os.getenv("LOG_FORMAT", "text").lower()
        json_format = log_format == "json"

        configure_logging(log_level=config.log_level, json_format=json_format)

        logger.info("RadPro MQTT Bridge starting...")
        logger.info(
            f"Configuration loaded: device={config.device_path}, "
            f"mqtt_host={config.mqtt_host}:{config.mqtt_port}, "
            f"poll_interval={config.poll_interval}s, "
            f"log_level={config.log_level}"
        )

        # Step 3: Create and run RadProBridge (Requirement 6.1)
        bridge = RadProBridge(config=config)

        # Set up signal handlers for graceful shutdown
        bridge.setup_signal_handlers()

        # Run the bridge (this blocks until shutdown)
        bridge.run()

        logger.info("RadPro MQTT Bridge stopped successfully")
        return 0

    except ValueError as e:
        # Configuration validation error (Requirement 6.3)
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    except KeyboardInterrupt:
        # User interrupted with Ctrl+C
        print("\nInterrupted by user", file=sys.stderr)
        return 0

    except Exception as e:
        # Handle top-level exceptions (Requirement 6.1)
        # If logging is configured, use logger; otherwise print to stderr
        if logger.hasHandlers():
            logger.error(f"Fatal error: {e}", exc_info=True)
        else:
            print(f"Fatal error: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
