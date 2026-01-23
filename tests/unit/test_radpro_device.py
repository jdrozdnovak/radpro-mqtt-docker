"""Unit tests for RadProDevice class."""

from unittest.mock import MagicMock, call, patch

import serial

from src.radpro_device import RadProDevice


class TestRadProDeviceInit:
    """Tests for RadProDevice initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        device = RadProDevice("/dev/ttyACM0")

        assert device.device_path == "/dev/ttyACM0"
        assert device.baudrate == 115200
        assert device.timeout == 5.0
        assert device._serial is None

    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        device = RadProDevice("/dev/ttyUSB0", baudrate=9600, timeout=10.0)

        assert device.device_path == "/dev/ttyUSB0"
        assert device.baudrate == 9600
        assert device.timeout == 10.0
        assert device._serial is None


class TestRadProDeviceConnect:
    """Tests for RadProDevice connection management."""

    @patch("src.radpro_device.serial.Serial")
    def test_connect_success(self, mock_serial_class):
        """Test successful connection to device."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        result = device.connect()

        # Verify connection was successful
        assert result is True
        assert device.is_connected() is True

        # Verify serial port was opened with correct parameters (Requirement 1.1)
        mock_serial_class.assert_called_once_with(
            port="/dev/ttyACM0",
            baudrate=115200,
            bytesize=serial.EIGHTBITS,  # 8 data bits
            parity=serial.PARITY_NONE,  # No parity
            stopbits=serial.STOPBITS_ONE,  # 1 stop bit
            timeout=5.0,
            xonxoff=False,  # No software flow control
            rtscts=False,  # No hardware flow control
            dsrdtr=False,  # No hardware flow control
        )

    @patch("src.radpro_device.serial.Serial")
    def test_connect_serial_exception(self, mock_serial_class):
        """Test connection failure due to serial exception."""
        # Setup mock to raise exception
        mock_serial_class.side_effect = serial.SerialException("Device not found")

        device = RadProDevice("/dev/ttyACM0")
        result = device.connect()

        # Verify connection failed
        assert result is False
        assert device.is_connected() is False
        assert device._serial is None

    @patch("src.radpro_device.serial.Serial")
    def test_connect_port_not_open(self, mock_serial_class):
        """Test connection when port fails to open."""
        # Setup mock with is_open = False
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = False
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        result = device.connect()

        # Verify connection failed
        assert result is False

    @patch("src.radpro_device.serial.Serial")
    def test_connect_unexpected_exception(self, mock_serial_class):
        """Test connection failure due to unexpected exception."""
        # Setup mock to raise unexpected exception
        mock_serial_class.side_effect = RuntimeError("Unexpected error")

        device = RadProDevice("/dev/ttyACM0")
        result = device.connect()

        # Verify connection failed gracefully
        assert result is False
        assert device.is_connected() is False
        assert device._serial is None


class TestRadProDeviceDisconnect:
    """Tests for RadProDevice disconnection."""

    @patch("src.radpro_device.serial.Serial")
    def test_disconnect_when_connected(self, mock_serial_class):
        """Test disconnection when device is connected."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Disconnect
        device.disconnect()

        # Verify disconnection
        mock_serial_instance.close.assert_called_once()
        assert device._serial is None
        assert device.is_connected() is False

    def test_disconnect_when_not_connected(self):
        """Test disconnection when device is not connected."""
        device = RadProDevice("/dev/ttyACM0")

        # Should not raise exception
        device.disconnect()

        assert device._serial is None
        assert device.is_connected() is False

    @patch("src.radpro_device.serial.Serial")
    def test_disconnect_with_close_error(self, mock_serial_class):
        """Test disconnection when close() raises exception."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.close.side_effect = Exception("Close error")
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Should handle exception gracefully
        device.disconnect()

        # Verify serial is set to None even with error
        assert device._serial is None


class TestRadProDeviceIsConnected:
    """Tests for RadProDevice connection status check."""

    def test_is_connected_when_not_initialized(self):
        """Test is_connected when device is not initialized."""
        device = RadProDevice("/dev/ttyACM0")

        assert device.is_connected() is False

    @patch("src.radpro_device.serial.Serial")
    def test_is_connected_when_connected(self, mock_serial_class):
        """Test is_connected when device is connected."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        assert device.is_connected() is True

    @patch("src.radpro_device.serial.Serial")
    def test_is_connected_after_disconnect(self, mock_serial_class):
        """Test is_connected after disconnection."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()
        device.disconnect()

        assert device.is_connected() is False

    @patch("src.radpro_device.serial.Serial")
    def test_is_connected_when_port_closed_externally(self, mock_serial_class):
        """Test is_connected when port is closed externally."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Simulate external port closure
        mock_serial_instance.is_open = False

        assert device.is_connected() is False


class TestRadProDeviceSendCommand:
    """Tests for RadProDevice send_command method."""

    @patch("src.radpro_device.serial.Serial")
    def test_send_command_success_with_data(self, mock_serial_class):
        """Test successful command with data response."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK 123.45\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Send command
        response = device.send_command("GET tubeRate")

        # Verify command was sent with \r\n termination (Requirement 1.3)
        mock_serial_instance.write.assert_called_once_with(b"GET tubeRate\r\n")
        mock_serial_instance.flush.assert_called_once()

        # Verify response was read until \r\n (Requirement 1.3)
        mock_serial_instance.read_until.assert_called_once_with(b"\r\n")

        # Verify response parsing (Requirement 1.3)
        assert response == "123.45"

    @patch("src.radpro_device.serial.Serial")
    def test_send_command_success_no_data(self, mock_serial_class):
        """Test successful command with OK but no data."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Send command
        response = device.send_command("RESET")

        # Verify response is empty string for OK with no data
        assert response == ""

    @patch("src.radpro_device.serial.Serial")
    def test_send_command_error_response(self, mock_serial_class):
        """Test command that returns ERROR response."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"ERROR Invalid command\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Send command
        response = device.send_command("INVALID")

        # Verify ERROR response returns None (Requirement 1.3)
        assert response is None

    @patch("src.radpro_device.serial.Serial")
    def test_send_command_timeout(self, mock_serial_class):
        """Test command timeout handling."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b""  # Empty response indicates timeout
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Send command
        response = device.send_command("GET tubeRate")

        # Verify timeout returns None (Requirement 1.3)
        assert response is None

    @patch("src.radpro_device.serial.Serial")
    def test_send_command_serial_timeout_exception(self, mock_serial_class):
        """Test command with serial timeout exception."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.side_effect = serial.SerialTimeoutException("Timeout")
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Send command
        response = device.send_command("GET tubeRate")

        # Verify timeout exception returns None (Requirement 1.3)
        assert response is None

    @patch("src.radpro_device.serial.Serial")
    def test_send_command_serial_exception(self, mock_serial_class):
        """Test command with serial communication exception."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.write.side_effect = serial.SerialException("Write error")
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Send command
        response = device.send_command("GET tubeRate")

        # Verify serial exception returns None
        assert response is None

    @patch("src.radpro_device.serial.Serial")
    def test_send_command_unicode_decode_error(self, mock_serial_class):
        """Test command with invalid unicode in response."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"\xff\xfe\r\n"  # Invalid UTF-8
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Send command
        response = device.send_command("GET tubeRate")

        # Verify decode error returns None
        assert response is None

    @patch("src.radpro_device.serial.Serial")
    def test_send_command_unexpected_response_format(self, mock_serial_class):
        """Test command with unexpected response format."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"UNKNOWN response\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Send command
        response = device.send_command("GET tubeRate")

        # Verify unexpected format returns None
        assert response is None

    def test_send_command_not_connected(self):
        """Test send_command when device is not connected."""
        device = RadProDevice("/dev/ttyACM0")

        # Send command without connecting
        response = device.send_command("GET tubeRate")

        # Verify returns None when not connected
        assert response is None

    @patch("src.radpro_device.serial.Serial")
    def test_send_command_with_semicolon_data(self, mock_serial_class):
        """Test command with semicolon-separated data in response."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK hardware;software;device123\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Send command
        response = device.send_command("GET deviceId")

        # Verify full response is returned (parsing is done by caller)
        assert response == "hardware;software;device123"

    @patch("src.radpro_device.serial.Serial")
    def test_send_command_unexpected_exception(self, mock_serial_class):
        """Test command with unexpected exception."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.write.side_effect = RuntimeError("Unexpected error")
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Send command
        response = device.send_command("GET tubeRate")

        # Verify unexpected exception returns None
        assert response is None


class TestRadProDeviceGetDeviceId:
    """Tests for RadProDevice get_device_id method."""

    @patch("src.radpro_device.serial.Serial")
    def test_get_device_id_success(self, mock_serial_class):
        """Test successful device ID retrieval."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK RadPro;v1.2.3;RP12345\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get device ID
        device_info = device.get_device_id()

        # Verify command was sent
        mock_serial_instance.write.assert_called_with(b"GET deviceId\r\n")

        # Verify parsing (Requirement 5.2)
        assert device_info is not None
        assert device_info.hardware_id == "RadPro"
        assert device_info.software_id == "v1.2.3"
        assert device_info.device_id == "RP12345"

    @patch("src.radpro_device.serial.Serial")
    def test_get_device_id_with_whitespace(self, mock_serial_class):
        """Test device ID retrieval with whitespace in response."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK  RadPro ; v1.2.3 ; RP12345  \r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get device ID
        device_info = device.get_device_id()

        # Verify whitespace is stripped
        assert device_info is not None
        assert device_info.hardware_id == "RadPro"
        assert device_info.software_id == "v1.2.3"
        assert device_info.device_id == "RP12345"

    @patch("src.radpro_device.serial.Serial")
    def test_get_device_id_invalid_format_too_few_parts(self, mock_serial_class):
        """Test device ID retrieval with invalid format (too few parts)."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK RadPro;v1.2.3\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get device ID
        device_info = device.get_device_id()

        # Verify returns None for invalid format
        assert device_info is None

    @patch("src.radpro_device.serial.Serial")
    def test_get_device_id_invalid_format_too_many_parts(self, mock_serial_class):
        """Test device ID retrieval with invalid format (too many parts)."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK RadPro;v1.2.3;RP12345;extra\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get device ID
        device_info = device.get_device_id()

        # Verify returns None for invalid format
        assert device_info is None

    @patch("src.radpro_device.serial.Serial")
    def test_get_device_id_command_failure(self, mock_serial_class):
        """Test device ID retrieval when command fails."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"ERROR\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get device ID
        device_info = device.get_device_id()

        # Verify returns None on command failure
        assert device_info is None


class TestRadProDeviceGetTubeRate:
    """Tests for RadProDevice get_tube_rate method."""

    @patch("src.radpro_device.serial.Serial")
    def test_get_tube_rate_success(self, mock_serial_class):
        """Test successful tube rate retrieval."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK 23.5\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get tube rate
        tube_rate = device.get_tube_rate()

        # Verify command was sent (Requirement 2.2)
        mock_serial_instance.write.assert_called_with(b"GET tubeRate\r\n")

        # Verify parsing
        assert tube_rate == 23.5

    @patch("src.radpro_device.serial.Serial")
    def test_get_tube_rate_zero(self, mock_serial_class):
        """Test tube rate retrieval with zero value."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK 0.0\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get tube rate
        tube_rate = device.get_tube_rate()

        # Verify zero is valid
        assert tube_rate == 0.0

    @patch("src.radpro_device.serial.Serial")
    def test_get_tube_rate_invalid_format(self, mock_serial_class):
        """Test tube rate retrieval with invalid format."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK invalid\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get tube rate
        tube_rate = device.get_tube_rate()

        # Verify returns None for invalid format
        assert tube_rate is None

    @patch("src.radpro_device.serial.Serial")
    def test_get_tube_rate_command_failure(self, mock_serial_class):
        """Test tube rate retrieval when command fails."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"ERROR\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get tube rate
        tube_rate = device.get_tube_rate()

        # Verify returns None on command failure
        assert tube_rate is None


class TestRadProDeviceGetTubePulseCount:
    """Tests for RadProDevice get_tube_pulse_count method."""

    @patch("src.radpro_device.serial.Serial")
    def test_get_tube_pulse_count_success(self, mock_serial_class):
        """Test successful tube pulse count retrieval."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK 12345\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get tube pulse count
        pulse_count = device.get_tube_pulse_count()

        # Verify command was sent (Requirement 2.3)
        mock_serial_instance.write.assert_called_with(b"GET tubePulseCount\r\n")

        # Verify parsing
        assert pulse_count == 12345

    @patch("src.radpro_device.serial.Serial")
    def test_get_tube_pulse_count_zero(self, mock_serial_class):
        """Test tube pulse count retrieval with zero value."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK 0\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get tube pulse count
        pulse_count = device.get_tube_pulse_count()

        # Verify zero is valid
        assert pulse_count == 0

    @patch("src.radpro_device.serial.Serial")
    def test_get_tube_pulse_count_invalid_format(self, mock_serial_class):
        """Test tube pulse count retrieval with invalid format."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK 123.45\r\n"  # Float instead of int
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get tube pulse count
        pulse_count = device.get_tube_pulse_count()

        # Verify returns None for invalid format
        assert pulse_count is None

    @patch("src.radpro_device.serial.Serial")
    def test_get_tube_pulse_count_command_failure(self, mock_serial_class):
        """Test tube pulse count retrieval when command fails."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"ERROR\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get tube pulse count
        pulse_count = device.get_tube_pulse_count()

        # Verify returns None on command failure
        assert pulse_count is None


class TestRadProDeviceGetBatteryVoltage:
    """Tests for RadProDevice get_battery_voltage method."""

    @patch("src.radpro_device.serial.Serial")
    def test_get_battery_voltage_success(self, mock_serial_class):
        """Test successful battery voltage retrieval."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK 1.42\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get battery voltage
        voltage = device.get_battery_voltage()

        # Verify command was sent (Requirement 2.4)
        mock_serial_instance.write.assert_called_with(b"GET deviceBatteryVoltage\r\n")

        # Verify parsing
        assert voltage == 1.42

    @patch("src.radpro_device.serial.Serial")
    def test_get_battery_voltage_invalid_format(self, mock_serial_class):
        """Test battery voltage retrieval with invalid format."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK invalid\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get battery voltage
        voltage = device.get_battery_voltage()

        # Verify returns None for invalid format
        assert voltage is None

    @patch("src.radpro_device.serial.Serial")
    def test_get_battery_voltage_command_failure(self, mock_serial_class):
        """Test battery voltage retrieval when command fails."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"ERROR\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get battery voltage
        voltage = device.get_battery_voltage()

        # Verify returns None on command failure
        assert voltage is None


class TestRadProDeviceGetTubeSensitivity:
    """Tests for RadProDevice get_tube_sensitivity method."""

    @patch("src.radpro_device.serial.Serial")
    def test_get_tube_sensitivity_success(self, mock_serial_class):
        """Test successful tube sensitivity retrieval."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK 153.8\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get tube sensitivity
        sensitivity = device.get_tube_sensitivity()

        # Verify command was sent (Requirement 2.6)
        mock_serial_instance.write.assert_called_with(b"GET tubeSensitivity\r\n")

        # Verify parsing
        assert sensitivity == 153.8

    @patch("src.radpro_device.serial.Serial")
    def test_get_tube_sensitivity_invalid_format(self, mock_serial_class):
        """Test tube sensitivity retrieval with invalid format."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK invalid\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get tube sensitivity
        sensitivity = device.get_tube_sensitivity()

        # Verify returns None for invalid format
        assert sensitivity is None

    @patch("src.radpro_device.serial.Serial")
    def test_get_tube_sensitivity_command_failure(self, mock_serial_class):
        """Test tube sensitivity retrieval when command fails."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"ERROR\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get tube sensitivity
        sensitivity = device.get_tube_sensitivity()

        # Verify returns None on command failure
        assert sensitivity is None


class TestRadProDeviceGetTubeLifetime:
    """Tests for RadProDevice get_tube_lifetime method."""

    @patch("src.radpro_device.serial.Serial")
    def test_get_tube_lifetime_success(self, mock_serial_class):
        """Test successful tube lifetime retrieval."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK 86400\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get tube lifetime
        lifetime = device.get_tube_lifetime()

        # Verify command was sent (Requirement 5.1)
        mock_serial_instance.write.assert_called_with(b"GET tubeLifetime\r\n")

        # Verify parsing
        assert lifetime == 86400

    @patch("src.radpro_device.serial.Serial")
    def test_get_tube_lifetime_zero(self, mock_serial_class):
        """Test tube lifetime retrieval with zero value."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK 0\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get tube lifetime
        lifetime = device.get_tube_lifetime()

        # Verify zero is valid
        assert lifetime == 0

    @patch("src.radpro_device.serial.Serial")
    def test_get_tube_lifetime_invalid_format(self, mock_serial_class):
        """Test tube lifetime retrieval with invalid format."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"OK 123.45\r\n"  # Float instead of int
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get tube lifetime
        lifetime = device.get_tube_lifetime()

        # Verify returns None for invalid format
        assert lifetime is None

    @patch("src.radpro_device.serial.Serial")
    def test_get_tube_lifetime_command_failure(self, mock_serial_class):
        """Test tube lifetime retrieval when command fails."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.return_value = b"ERROR\r\n"
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Get tube lifetime
        lifetime = device.get_tube_lifetime()

        # Verify returns None on command failure
        assert lifetime is None


class TestRadProDeviceReconnect:
    """Tests for RadProDevice reconnection with retry logic."""

    @patch("src.radpro_device.serial.Serial")
    def test_reconnect_success_first_attempt(self, mock_serial_class):
        """Test successful reconnection on first attempt."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")

        # Attempt reconnection
        result = device.reconnect(max_retries=3, backoff_base=2.0)

        # Verify reconnection was successful (Requirement 1.4, 8.1)
        assert result is True
        assert device.is_connected() is True

        # Verify connect was called
        mock_serial_class.assert_called()

    @patch("src.radpro_device.serial.Serial")
    @patch("time.sleep")  # Mock sleep to speed up test
    def test_reconnect_success_after_retries(self, mock_sleep, mock_serial_class):
        """Test successful reconnection after multiple retry attempts."""
        # Setup mock to fail twice, then succeed
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                # First two attempts fail
                raise serial.SerialException("Connection failed")
            else:
                # Third attempt succeeds
                return mock_serial_instance

        mock_serial_class.side_effect = side_effect

        device = RadProDevice("/dev/ttyACM0")

        # Attempt reconnection
        result = device.reconnect(max_retries=5, backoff_base=2.0)

        # Verify reconnection was successful after retries (Requirement 1.4, 8.1)
        assert result is True
        assert device.is_connected() is True

        # Verify multiple connection attempts were made
        assert mock_serial_class.call_count == 3

        # Verify exponential backoff was used (Requirement 8.1)
        assert mock_sleep.call_count == 2  # Two retries before success
        # First retry: 2^0 = 1 second, second retry: 2^1 = 2 seconds
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)

    @patch("src.radpro_device.serial.Serial")
    @patch("time.sleep")  # Mock sleep to speed up test
    def test_reconnect_failure_max_retries_exceeded(self, mock_sleep, mock_serial_class):
        """Test reconnection failure after exceeding max retries."""
        # Setup mock to always fail
        mock_serial_class.side_effect = serial.SerialException("Device not found")

        device = RadProDevice("/dev/ttyACM0")

        # Attempt reconnection
        result = device.reconnect(max_retries=3, backoff_base=2.0)

        # Verify reconnection failed (Requirement 8.1)
        assert result is False
        assert device.is_connected() is False

        # Verify all retry attempts were made (initial + 3 retries = 4 total)
        assert mock_serial_class.call_count == 4

        # Verify exponential backoff was used
        assert mock_sleep.call_count == 3

    @patch("src.radpro_device.serial.Serial")
    def test_reconnect_disconnects_first_if_connected(self, mock_serial_class):
        """Test that reconnect disconnects first if device is already connected."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Verify device is connected
        assert device.is_connected() is True

        # Attempt reconnection
        result = device.reconnect(max_retries=3, backoff_base=2.0)

        # Verify disconnect was called before reconnecting
        mock_serial_instance.close.assert_called()

        # Verify reconnection was successful
        assert result is True
        assert device.is_connected() is True

    @patch("src.radpro_device.serial.Serial")
    @patch("time.sleep")
    def test_reconnect_logs_all_attempts(self, mock_sleep, mock_serial_class):
        """Test that all reconnection attempts are logged."""
        # Setup mock to fail twice, then succeed
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise serial.SerialException("Connection failed")
            else:
                mock_serial_instance = MagicMock()
                mock_serial_instance.is_open = True
                return mock_serial_instance

        mock_serial_class.side_effect = side_effect

        device = RadProDevice("/dev/ttyACM0")

        # Attempt reconnection (Requirement 8.1 - log all connection attempts)
        with patch("src.radpro_device.logger") as mock_logger:
            result = device.reconnect(max_retries=5, backoff_base=2.0)

            # Verify reconnection was successful
            assert result is True

            # Verify logging occurred (Requirement 8.1)
            # Should log: initial attempt, retry attempts, and success
            assert mock_logger.info.call_count >= 3


class TestRadProDeviceUSBDisconnectionDetection:
    """Tests for USB disconnection detection in send_command."""

    @patch("src.radpro_device.serial.Serial")
    def test_send_command_detects_usb_disconnection(self, mock_serial_class):
        """Test that send_command detects USB disconnection via SerialException."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.write.side_effect = serial.SerialException("Device disconnected")
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Verify device is initially connected
        assert device.is_connected() is True

        # Send command that triggers disconnection
        response = device.send_command("GET tubeRate")

        # Verify disconnection was detected (Requirement 1.4, 8.1)
        assert response is None
        assert device._serial is None  # Device marked as disconnected

    @patch("src.radpro_device.serial.Serial")
    def test_send_command_detects_read_error(self, mock_serial_class):
        """Test that send_command detects USB disconnection during read."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.read_until.side_effect = serial.SerialException("Read error")
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Send command that triggers disconnection during read
        response = device.send_command("GET tubeRate")

        # Verify disconnection was detected (Requirement 1.4, 8.1)
        assert response is None
        assert device._serial is None  # Device marked as disconnected

    @patch("src.radpro_device.serial.Serial")
    def test_send_command_logs_usb_disconnection(self, mock_serial_class):
        """Test that USB disconnection is logged."""
        # Setup mock
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.write.side_effect = serial.SerialException("Device disconnected")
        mock_serial_class.return_value = mock_serial_instance

        device = RadProDevice("/dev/ttyACM0")
        device.connect()

        # Send command with logging verification (Requirement 8.1)
        with patch("src.radpro_device.logger") as mock_logger:
            response = device.send_command("GET tubeRate")

            # Verify disconnection was logged
            assert response is None
            mock_logger.error.assert_any_call(
                "Serial communication error for command 'GET tubeRate': Device disconnected"
            )
            mock_logger.warning.assert_called_with(
                "USB disconnection detected, marking device as disconnected"
            )
