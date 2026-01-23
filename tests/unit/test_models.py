"""Unit tests for data models."""

from datetime import datetime

from src.models import DeviceInfo, RadiationMeasurement


class TestDeviceInfo:
    """Tests for DeviceInfo dataclass."""

    def test_device_info_creation(self):
        """Test DeviceInfo creation with valid data."""
        device_info = DeviceInfo(hardware_id="RadPro", software_id="v1.2.3", device_id="RP12345")

        assert device_info.hardware_id == "RadPro"
        assert device_info.software_id == "v1.2.3"
        assert device_info.device_id == "RP12345"

    def test_device_info_equality(self):
        """Test DeviceInfo equality comparison."""
        device_info1 = DeviceInfo(hardware_id="RadPro", software_id="v1.2.3", device_id="RP12345")
        device_info2 = DeviceInfo(hardware_id="RadPro", software_id="v1.2.3", device_id="RP12345")

        assert device_info1 == device_info2

    def test_device_info_inequality(self):
        """Test DeviceInfo inequality comparison."""
        device_info1 = DeviceInfo(hardware_id="RadPro", software_id="v1.2.3", device_id="RP12345")
        device_info2 = DeviceInfo(hardware_id="RadPro", software_id="v1.2.3", device_id="RP99999")

        assert device_info1 != device_info2


class TestRadiationMeasurement:
    """Tests for RadiationMeasurement dataclass."""

    def test_radiation_measurement_creation(self):
        """Test RadiationMeasurement creation with valid data."""
        timestamp = datetime.now()
        measurement = RadiationMeasurement(
            timestamp=timestamp,
            tube_rate=23.5,
            tube_pulse_count=12345,
            battery_voltage=1.42,
            tube_sensitivity=153.8,
            tube_lifetime=86400,
        )

        assert measurement.timestamp == timestamp
        assert measurement.tube_rate == 23.5
        assert measurement.tube_pulse_count == 12345
        assert measurement.battery_voltage == 1.42
        assert measurement.tube_sensitivity == 153.8
        assert measurement.tube_lifetime == 86400

    def test_dose_rate_calculation(self):
        """Test dose rate calculation (Requirement 2.5)."""
        measurement = RadiationMeasurement(
            timestamp=datetime.now(),
            tube_rate=23.5,
            tube_pulse_count=12345,
            battery_voltage=1.42,
            tube_sensitivity=153.8,
            tube_lifetime=86400,
        )

        # dose_rate = tube_rate / tube_sensitivity
        expected_dose_rate = 23.5 / 153.8
        assert abs(measurement.dose_rate - expected_dose_rate) < 0.0001

    def test_dose_rate_with_zero_sensitivity(self):
        """Test dose rate calculation with zero sensitivity."""
        measurement = RadiationMeasurement(
            timestamp=datetime.now(),
            tube_rate=23.5,
            tube_pulse_count=12345,
            battery_voltage=1.42,
            tube_sensitivity=0.0,  # Zero sensitivity
            tube_lifetime=86400,
        )

        # Should return 0.0 to avoid division by zero
        assert measurement.dose_rate == 0.0

    def test_dose_rate_with_zero_tube_rate(self):
        """Test dose rate calculation with zero tube rate."""
        measurement = RadiationMeasurement(
            timestamp=datetime.now(),
            tube_rate=0.0,
            tube_pulse_count=0,
            battery_voltage=1.42,
            tube_sensitivity=153.8,
            tube_lifetime=0,
        )

        # dose_rate = 0.0 / 153.8 = 0.0
        assert measurement.dose_rate == 0.0

    def test_dose_rate_with_high_values(self):
        """Test dose rate calculation with high values."""
        measurement = RadiationMeasurement(
            timestamp=datetime.now(),
            tube_rate=1000.0,
            tube_pulse_count=999999,
            battery_voltage=1.5,
            tube_sensitivity=100.0,
            tube_lifetime=999999,
        )

        # dose_rate = 1000.0 / 100.0 = 10.0
        assert measurement.dose_rate == 10.0


class TestDevicePayload:
    """Tests for DevicePayload dataclass."""

    def test_device_payload_creation(self):
        """Test DevicePayload creation with valid data."""
        from src.models import DevicePayload

        device_payload = DevicePayload(
            identifiers=["radpro_12345"],
            name="RadPro radpro_12345",
            manufacturer="RadPro",
            model="RadPro",
            sw_version="1.2.3",
        )

        assert device_payload.identifiers == ["radpro_12345"]
        assert device_payload.name == "RadPro radpro_12345"
        assert device_payload.manufacturer == "RadPro"
        assert device_payload.model == "RadPro"
        assert device_payload.sw_version == "1.2.3"

    def test_device_payload_with_multiple_identifiers(self):
        """Test DevicePayload with multiple identifiers."""
        from src.models import DevicePayload

        device_payload = DevicePayload(
            identifiers=["radpro_12345", "serial_67890"],
            name="RadPro Device",
            manufacturer="RadPro",
            model="RadPro v2",
            sw_version="2.0.0",
        )

        assert len(device_payload.identifiers) == 2
        assert "radpro_12345" in device_payload.identifiers
        assert "serial_67890" in device_payload.identifiers


class TestDiscoveryPayload:
    """Tests for DiscoveryPayload dataclass."""

    def test_discovery_payload_creation(self):
        """Test DiscoveryPayload creation with all fields."""
        from src.models import DevicePayload, DiscoveryPayload

        device = DevicePayload(
            identifiers=["radpro_12345"],
            name="RadPro radpro_12345",
            manufacturer="RadPro",
            model="RadPro",
            sw_version="1.2.3",
        )

        payload = DiscoveryPayload(
            name="Dose Rate",
            unique_id="radpro_12345_dose_rate",
            state_topic="radpro/dose_rate/state",
            availability_topic="radpro/availability",
            device=device,
            device_class=None,
            unit_of_measurement="µSv/h",
            icon="mdi:radioactive",
            state_class="measurement",
        )

        assert payload.name == "Dose Rate"
        assert payload.unique_id == "radpro_12345_dose_rate"
        assert payload.state_topic == "radpro/dose_rate/state"
        assert payload.availability_topic == "radpro/availability"
        assert payload.device == device
        assert payload.device_class is None
        assert payload.unit_of_measurement == "µSv/h"
        assert payload.icon == "mdi:radioactive"
        assert payload.state_class == "measurement"

    def test_discovery_payload_to_json_all_fields(self):
        """Test DiscoveryPayload JSON serialization with all fields."""
        import json
        from src.models import DevicePayload, DiscoveryPayload

        device = DevicePayload(
            identifiers=["radpro_12345"],
            name="RadPro radpro_12345",
            manufacturer="RadPro",
            model="RadPro",
            sw_version="1.2.3",
        )

        payload = DiscoveryPayload(
            name="Dose Rate",
            unique_id="radpro_12345_dose_rate",
            state_topic="radpro/dose_rate/state",
            availability_topic="radpro/availability",
            device=device,
            device_class=None,
            unit_of_measurement="µSv/h",
            icon="mdi:radioactive",
            state_class="measurement",
        )

        json_str = payload.to_json()
        parsed = json.loads(json_str)

        # Verify required fields
        assert parsed["name"] == "Dose Rate"
        assert parsed["unique_id"] == "radpro_12345_dose_rate"
        assert parsed["state_topic"] == "radpro/dose_rate/state"
        assert parsed["availability_topic"] == "radpro/availability"

        # Verify device information
        assert parsed["device"]["identifiers"] == ["radpro_12345"]
        assert parsed["device"]["name"] == "RadPro radpro_12345"
        assert parsed["device"]["manufacturer"] == "RadPro"
        assert parsed["device"]["model"] == "RadPro"
        assert parsed["device"]["sw_version"] == "1.2.3"

        # Verify optional fields
        assert "device_class" not in parsed  # None values should be excluded
        assert parsed["unit_of_measurement"] == "µSv/h"
        assert parsed["icon"] == "mdi:radioactive"
        assert parsed["state_class"] == "measurement"

    def test_discovery_payload_to_json_with_device_class(self):
        """Test DiscoveryPayload JSON serialization with device_class."""
        import json
        from src.models import DevicePayload, DiscoveryPayload

        device = DevicePayload(
            identifiers=["radpro_12345"],
            name="RadPro radpro_12345",
            manufacturer="RadPro",
            model="RadPro",
            sw_version="1.2.3",
        )

        payload = DiscoveryPayload(
            name="Battery Voltage",
            unique_id="radpro_12345_battery_voltage",
            state_topic="radpro/battery_voltage/state",
            availability_topic="radpro/availability",
            device=device,
            device_class="voltage",
            unit_of_measurement="V",
            icon=None,
            state_class="measurement",
        )

        json_str = payload.to_json()
        parsed = json.loads(json_str)

        # Verify device_class is included
        assert parsed["device_class"] == "voltage"
        # Verify icon is excluded (None value)
        assert "icon" not in parsed

    def test_discovery_payload_to_json_minimal_fields(self):
        """Test DiscoveryPayload JSON serialization with minimal fields."""
        import json
        from src.models import DevicePayload, DiscoveryPayload

        device = DevicePayload(
            identifiers=["radpro_12345"],
            name="RadPro radpro_12345",
            manufacturer="RadPro",
            model="RadPro",
            sw_version="1.2.3",
        )

        payload = DiscoveryPayload(
            name="Test Sensor",
            unique_id="radpro_12345_test",
            state_topic="radpro/test/state",
            availability_topic="radpro/availability",
            device=device,
        )

        json_str = payload.to_json()
        parsed = json.loads(json_str)

        # Verify required fields are present
        assert parsed["name"] == "Test Sensor"
        assert parsed["unique_id"] == "radpro_12345_test"
        assert parsed["state_topic"] == "radpro/test/state"
        assert parsed["availability_topic"] == "radpro/availability"
        assert "device" in parsed

        # Verify optional fields are excluded
        assert "device_class" not in parsed
        assert "unit_of_measurement" not in parsed
        assert "icon" not in parsed
        assert "state_class" not in parsed

    def test_discovery_payload_to_json_is_valid_json(self):
        """Test that to_json produces valid JSON."""
        import json
        from src.models import DevicePayload, DiscoveryPayload

        device = DevicePayload(
            identifiers=["radpro_12345"],
            name="RadPro radpro_12345",
            manufacturer="RadPro",
            model="RadPro",
            sw_version="1.2.3",
        )

        payload = DiscoveryPayload(
            name="Dose Rate",
            unique_id="radpro_12345_dose_rate",
            state_topic="radpro/dose_rate/state",
            availability_topic="radpro/availability",
            device=device,
            unit_of_measurement="µSv/h",
        )

        json_str = payload.to_json()

        # Should not raise exception
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    def test_discovery_payload_to_json_unicode_handling(self):
        """Test that to_json handles unicode characters correctly."""
        import json
        from src.models import DevicePayload, DiscoveryPayload

        device = DevicePayload(
            identifiers=["radpro_12345"],
            name="RadPro radpro_12345",
            manufacturer="RadPro",
            model="RadPro",
            sw_version="1.2.3",
        )

        payload = DiscoveryPayload(
            name="Dose Rate",
            unique_id="radpro_12345_dose_rate",
            state_topic="radpro/dose_rate/state",
            availability_topic="radpro/availability",
            device=device,
            unit_of_measurement="µSv/h",  # Unicode character
        )

        json_str = payload.to_json()
        parsed = json.loads(json_str)

        # Verify unicode is preserved
        assert parsed["unit_of_measurement"] == "µSv/h"
