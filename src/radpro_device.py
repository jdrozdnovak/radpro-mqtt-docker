"""USB Serial communication handler for RadPro devices.

This module provides the RadProDevice class for managing USB serial
communication with RadPro Geiger counter devices.
"""

import logging

import serial

from src.models import DeviceInfo
from src.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class RadProDevice:
    """Manages USB serial communication with a RadPro device.

    This class handles connection management, command sending, and response
    parsing for RadPro Geiger counter devices connected via USB serial.

    Attributes:
        device_path: Path to the USB serial device (e.g., /dev/ttyACM0)
        baudrate: Serial communication baud rate (115200 for RadPro)
        timeout: Timeout for serial operations in seconds
    """

    def __init__(self, device_path: str, baudrate: int = 115200, timeout: float = 5.0):
        """Initialize RadProDevice with connection parameters.

        Args:
            device_path: Path to the USB serial device
            baudrate: Serial communication baud rate (default: 115200)
            timeout: Timeout for serial operations in seconds (default: 5.0)

        Requirements: 1.1
        """
        self.device_path = device_path
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial: serial.Serial | None = None

        logger.debug(
            f"RadProDevice initialized: device={device_path}, "
            f"baudrate={baudrate}, timeout={timeout}"
        )

    def connect(self) -> bool:
        """Establish USB serial connection to the RadPro device.

        Attempts to open a serial connection with the configured parameters:
        - Baudrate: 115200
        - Data bits: 8
        - Parity: None
        - Stop bits: 1
        - Flow control: None (8N1 configuration)

        Returns:
            bool: True if connection successful, False otherwise

        Requirements: 1.1, 1.2
        """
        try:
            logger.info(f"Attempting to connect to RadPro device at {self.device_path}")

            # Open serial connection with 8N1 configuration (Requirement 1.1)
            self._serial = serial.Serial(
                port=self.device_path,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,  # 8 data bits
                parity=serial.PARITY_NONE,  # No parity
                stopbits=serial.STOPBITS_ONE,  # 1 stop bit
                timeout=self.timeout,
                xonxoff=False,  # No software flow control
                rtscts=False,  # No hardware flow control
                dsrdtr=False,  # No hardware flow control
            )

            if self._serial.is_open:
                # Give the device a moment to initialize after connection
                import time

                time.sleep(0.5)

                # Clear any pending data in the input buffer
                self._serial.reset_input_buffer()
                self._serial.reset_output_buffer()

                logger.info(f"Successfully connected to RadPro device at {self.device_path}")
                return True
            else:
                logger.error(f"Failed to open serial port {self.device_path}")
                return False

        except serial.SerialException as e:
            logger.error(f"Serial connection error: {e}")
            self._serial = None
            return False
        except Exception as e:
            logger.error(f"Unexpected error during connection: {e}")
            self._serial = None
            return False

    def disconnect(self) -> None:
        """Close the USB serial connection.

        Safely closes the serial connection if it's open. This method
        is safe to call even if the connection is already closed.

        Requirements: 1.1
        """
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
                logger.info(f"Disconnected from RadPro device at {self.device_path}")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
            finally:
                self._serial = None
        else:
            logger.debug("Disconnect called but device was not connected")
            self._serial = None

    def is_connected(self) -> bool:
        """Check if the device is currently connected.

        Returns:
            bool: True if connected and port is open, False otherwise

        Requirements: 1.1
        """
        return self._serial is not None and self._serial.is_open

    def reconnect(self, max_retries: int = 10, backoff_base: float = 2.0) -> bool:
        """Attempt to reconnect to the device with retry logic.

        This method attempts to reconnect to the device after a disconnection,
        using exponential backoff between retry attempts. All connection attempts
        are logged.

        Args:
            max_retries: Maximum number of retry attempts (default: 10)
            backoff_base: Base for exponential backoff calculation (default: 2.0)

        Returns:
            bool: True if reconnection successful, False otherwise

        Requirements: 1.4, 8.1
        """
        logger.info(f"Attempting to reconnect to device at {self.device_path}")

        # First, ensure we're disconnected
        if self.is_connected():
            logger.debug("Device still connected, disconnecting first")
            self.disconnect()

        # Use the retry decorator to attempt reconnection
        @retry_with_backoff(
            max_retries=max_retries,
            backoff_base=backoff_base,
            exceptions=(serial.SerialException, OSError),
            on_retry=lambda e, attempt: logger.info(
                f"Reconnection attempt {attempt}/{max_retries + 1} failed: {e}"
            ),
        )
        def _attempt_connect() -> bool:
            """Internal function to attempt connection with retry logic."""
            logger.info(f"Connecting to device at {self.device_path} (attempt in progress)")
            success = self.connect()
            if not success:
                # Raise exception to trigger retry
                raise serial.SerialException("Failed to establish connection")
            return success

        try:
            result = _attempt_connect()
            if result:
                logger.info(f"Successfully reconnected to device at {self.device_path}")
            return result
        except Exception as e:
            logger.error(
                f"Failed to reconnect to device at {self.device_path} "
                f"after {max_retries} retries: {e}"
            )
            return False

    def send_command(self, command: str) -> str | None:
        """Send a command to the RadPro device and return the response.

        Commands are sent with \\r\\n termination as per the RadPro protocol.
        Responses are read until \\r\\n is received. The method parses OK/ERROR
        responses and implements timeout handling.

        If a USB communication error is detected, this method will attempt to
        reconnect to the device before failing.

        Args:
            command: The command to send (without \\r\\n termination)

        Returns:
            Optional[str]: The response string (without OK/ERROR prefix and \\r\\n),
                          or None if the command failed, timed out, or device is not connected

        Requirements: 1.3, 1.4, 8.1
        """
        if not self.is_connected() or self._serial is None:
            logger.error("Cannot send command: device not connected")
            return None

        try:
            # Send command with \r\n termination (Requirement 1.3)
            command_bytes = f"{command}\r\n".encode("ascii")
            logger.debug(f"Sending command: {command}")
            self._serial.write(command_bytes)
            self._serial.flush()

            # Read response until \r\n (Requirement 1.3)
            response_bytes = self._serial.read_until(b"\r\n")

            # Check for timeout (Requirement 1.3)
            if not response_bytes:
                logger.error(f"Command timeout: no response received for '{command}'")
                return None

            # Decode response
            response = response_bytes.decode("ascii").strip()
            logger.debug(f"Received response: {response}")

            # Parse OK/ERROR responses (Requirement 1.3)
            if response.startswith("OK"):
                # Extract the data after "OK " prefix
                if len(response) > 3:
                    result: str = response[3:]  # Return everything after "OK "
                    return result
                else:
                    return ""  # OK with no data
            elif response.startswith("ERROR"):
                logger.error(f"Device returned ERROR for command '{command}': {response}")
                return None
            else:
                logger.warning(f"Unexpected response format for command '{command}': {response}")
                return None

        except serial.SerialTimeoutException:
            logger.error(f"Serial timeout while sending command '{command}'")
            return None
        except serial.SerialException as e:
            # USB disconnection detected (Requirement 1.4, 8.1)
            logger.error(f"Serial communication error for command '{command}': {e}")
            logger.warning("USB disconnection detected, marking device as disconnected")
            self._serial = None
            return None
        except UnicodeDecodeError as e:
            logger.error(f"Failed to decode response for command '{command}': {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error sending command '{command}': {e}")
            return None

    def get_device_id(self) -> DeviceInfo | None:
        """Get device identification information.

        Sends the GET deviceId command and parses the response in the format:
        "hardware;software;device"

        Returns:
            Optional[DeviceInfo]: Device information with hardware_id, software_id,
                                 and device_id fields, or None if the command fails

        Requirements: 5.1, 5.2
        """
        response = self.send_command("GET deviceId")

        if response is None:
            logger.error("Failed to get device ID: no response")
            return None

        try:
            # Parse response format: "hardware;software;device"
            parts = response.split(";")

            if len(parts) != 3:
                logger.error(
                    f"Invalid device ID response format: expected 3 parts, got {len(parts)}"
                )
                return None

            hardware_id, software_id, device_id = parts
            device_info = DeviceInfo(
                hardware_id=hardware_id.strip(),
                software_id=software_id.strip(),
                device_id=device_id.strip(),
            )

            logger.debug(
                f"Device ID retrieved: hardware={device_info.hardware_id}, "
                f"software={device_info.software_id}, device={device_info.device_id}"
            )

            return device_info

        except Exception as e:
            logger.error(f"Error parsing device ID response '{response}': {e}")
            return None

    def get_tube_rate(self) -> float | None:
        """Get tube rate in counts per minute (CPM).

        Sends the GET tubeRate command to retrieve the current radiation
        detection rate.

        Returns:
            Optional[float]: Tube rate in CPM, or None if the command fails

        Requirements: 2.2
        """
        response = self.send_command("GET tubeRate")

        if response is None:
            logger.error("Failed to get tube rate: no response")
            return None

        try:
            tube_rate = float(response)
            logger.debug(f"Tube rate retrieved: {tube_rate} CPM")
            return tube_rate

        except ValueError as e:
            logger.error(f"Error parsing tube rate response '{response}': {e}")
            return None

    def get_tube_pulse_count(self) -> int | None:
        """Get total pulse count since device startup.

        Sends the GET tubePulseCount command to retrieve the cumulative
        number of radiation detection events.

        Returns:
            Optional[int]: Total pulse count, or None if the command fails

        Requirements: 2.3
        """
        response = self.send_command("GET tubePulseCount")

        if response is None:
            logger.error("Failed to get tube pulse count: no response")
            return None

        try:
            pulse_count = int(response)
            logger.debug(f"Tube pulse count retrieved: {pulse_count}")
            return pulse_count

        except ValueError as e:
            logger.error(f"Error parsing tube pulse count response '{response}': {e}")
            return None

    def get_battery_voltage(self) -> float | None:
        """Get battery voltage in volts.

        Sends the GET deviceBatteryVoltage command to retrieve the current
        battery voltage level.

        Returns:
            Optional[float]: Battery voltage in volts, or None if the command fails

        Requirements: 2.4
        """
        response = self.send_command("GET deviceBatteryVoltage")

        if response is None:
            logger.error("Failed to get battery voltage: no response")
            return None

        try:
            battery_voltage = float(response)
            logger.debug(f"Battery voltage retrieved: {battery_voltage} V")
            return battery_voltage

        except ValueError as e:
            logger.error(f"Error parsing battery voltage response '{response}': {e}")
            return None

    def get_tube_sensitivity(self) -> float | None:
        """Get tube sensitivity in CPM per µSv/h.

        Sends the GET tubeSensitivity command to retrieve the tube's
        sensitivity calibration value, which is used to calculate dose rate.

        Returns:
            Optional[float]: Tube sensitivity in CPM/(µSv/h), or None if the command fails

        Requirements: 2.6
        """
        response = self.send_command("GET tubeSensitivity")

        if response is None:
            logger.error("Failed to get tube sensitivity: no response")
            return None

        try:
            tube_sensitivity = float(response)
            logger.debug(f"Tube sensitivity retrieved: {tube_sensitivity} CPM/(µSv/h)")
            return tube_sensitivity

        except ValueError as e:
            logger.error(f"Error parsing tube sensitivity response '{response}': {e}")
            return None

    def get_tube_lifetime(self) -> int | None:
        """Get tube operational lifetime in seconds.

        Sends the GET tubeTime command to retrieve the cumulative
        operational time of the Geiger-Müller tube.

        Returns:
            Optional[int]: Tube lifetime in seconds, or None if the command fails

        Requirements: 5.1
        """
        response = self.send_command("GET tubeTime")

        if response is None:
            logger.error("Failed to get tube lifetime: no response")
            return None

        try:
            tube_lifetime = int(response)
            logger.debug(f"Tube lifetime retrieved: {tube_lifetime} seconds")
            return tube_lifetime

        except ValueError as e:
            logger.error(f"Error parsing tube lifetime response '{response}': {e}")
            return None

    def get_tube_dead_time(self) -> float | None:
        """Get tube dead time measurement in microseconds.

        The dead time is the period after a detection event during which
        the tube cannot detect another event. This affects measurement
        accuracy at high count rates.

        Returns:
            Optional[float]: Tube dead time in microseconds, or None if the command fails
        """
        response = self.send_command("GET tubeDeadTime")

        if response is None:
            logger.error("Failed to get tube dead time: no response")
            return None

        try:
            dead_time = float(response)
            logger.debug(f"Tube dead time retrieved: {dead_time} µs")
            return dead_time

        except ValueError as e:
            logger.error(f"Error parsing tube dead time response '{response}': {e}")
            return None

    def get_tube_dead_time_compensation(self) -> float | None:
        """Get tube dead time compensation value in seconds.

        This is the correction factor applied to measurements to compensate
        for dead time losses at high count rates.

        Returns:
            Optional[float]: Dead time compensation in seconds, or None if the command fails
        """
        response = self.send_command("GET tubeDeadTimeCompensation")

        if response is None:
            logger.error("Failed to get tube dead time compensation: no response")
            return None

        try:
            compensation = float(response)
            logger.debug(f"Tube dead time compensation retrieved: {compensation} s")
            return compensation

        except ValueError as e:
            logger.error(f"Error parsing dead time compensation response '{response}': {e}")
            return None

    def get_tube_hv_duty_cycle(self) -> float | None:
        """Get high voltage generator PWM duty cycle as a percentage.

        The duty cycle indicates the high voltage generator's operating state.
        Values closer to 100% may indicate the tube is approaching its voltage limit.

        Returns:
            Optional[float]: HV duty cycle as percentage (0-100), or None if the command fails
        """
        response = self.send_command("GET tubeHVDutyCycle")

        if response is None:
            logger.error("Failed to get HV duty cycle: no response")
            return None

        try:
            duty_cycle = float(response)
            logger.debug(f"HV duty cycle retrieved: {duty_cycle}%")
            return duty_cycle

        except ValueError as e:
            logger.error(f"Error parsing HV duty cycle response '{response}': {e}")
            return None

    def get_tube_hv_frequency(self) -> float | None:
        """Get high voltage generator PWM frequency in Hz.

        The frequency of the PWM signal used to generate the high voltage
        for the Geiger-Müller tube.

        Returns:
            Optional[float]: HV frequency in Hz, or None if the command fails
        """
        response = self.send_command("GET tubeHVFrequency")

        if response is None:
            logger.error("Failed to get HV frequency: no response")
            return None

        try:
            frequency = float(response)
            logger.debug(f"HV frequency retrieved: {frequency} Hz")
            return frequency

        except ValueError as e:
            logger.error(f"Error parsing HV frequency response '{response}': {e}")
            return None

    def get_device_time(self) -> int | None:
        """Get device's internal time as Unix timestamp.

        Returns:
            Optional[int]: Unix timestamp, or None if the command fails
        """
        response = self.send_command("GET deviceTime")

        if response is None:
            logger.error("Failed to get device time: no response")
            return None

        try:
            device_time = int(response)
            logger.debug(f"Device time retrieved: {device_time}")
            return device_time

        except ValueError as e:
            logger.error(f"Error parsing device time response '{response}': {e}")
            return None

    def sync_time(self) -> bool:
        """Synchronize device time with system time.

        Sets the device's internal clock to match the system time,
        including timezone offset. This ensures accurate timestamps
        in the device's datalog.

        Returns:
            bool: True if time sync successful, False otherwise
        """
        import time

        try:
            current_time = int(time.time())

            # Calculate timezone offset
            if time.localtime().tm_isdst:
                current_timezone = time.altzone
            else:
                current_timezone = time.timezone

            # Convert to decimal hours (RadPro expects format like -5.0 for EST)
            timezone_hours = -current_timezone / 3600.0

            # Set device time
            time_response = self.send_command(f"SET deviceTime {current_time}")
            if time_response is None:
                logger.error("Failed to set device time")
                return False

            # Set device timezone
            tz_response = self.send_command(f"SET deviceTimeZone {timezone_hours:.1f}")
            if tz_response is None:
                logger.error("Failed to set device timezone")
                return False

            logger.info(f"Device time synchronized: {current_time} (TZ: {timezone_hours:+.1f}h)")
            return True

        except Exception as e:
            logger.error(f"Error syncing device time: {e}")
            return False
