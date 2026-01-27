"""Data models for RadPro MQTT Bridge.

This module defines dataclasses for device information and radiation measurements.
"""

import json
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DeviceInfo:
    """Device identification information from RadPro device.

    Attributes:
        hardware_id: Hardware identifier (e.g., "RadPro")
        software_id: Software/firmware version
        device_id: Unique device identifier

    Requirements: 5.2
    """

    hardware_id: str
    software_id: str
    device_id: str


@dataclass
class RadiationMeasurement:
    """Radiation measurement data from RadPro device.

    Attributes:
        timestamp: Time when the measurement was taken
        tube_rate: Tube rate in counts per minute (CPM)
        tube_pulse_count: Total pulse count since device startup
        battery_voltage: Battery voltage in volts
        tube_sensitivity: Tube sensitivity in CPM per µSv/h
        tube_lifetime: Tube operational lifetime in seconds
        tube_dead_time: Tube dead time in microseconds (optional)
        tube_dead_time_compensation: Dead time compensation in seconds (optional)
        tube_hv_duty_cycle: HV generator duty cycle percentage (optional)
        tube_hv_frequency: HV generator frequency in Hz (optional)
        cpm_1min: 1-minute moving average CPM (optional)
        cpm_5min: 5-minute moving average CPM (optional)
        cpm_15min: 15-minute moving average CPM (optional)

    Requirements: 2.5
    """

    timestamp: datetime
    tube_rate: float
    tube_pulse_count: int
    battery_voltage: float
    tube_sensitivity: float
    tube_lifetime: int

    # Advanced sensors (optional)
    tube_dead_time: float | None = None
    tube_dead_time_compensation: float | None = None
    tube_hv_duty_cycle: float | None = None
    tube_hv_frequency: float | None = None

    # Moving averages (optional)
    cpm_1min: float | None = None
    cpm_5min: float | None = None
    cpm_15min: float | None = None

    @property
    def dose_rate(self) -> float:
        """Calculate dose rate in µSv/h.

        The dose rate is calculated using the formula:
        dose_rate = tube_rate / tube_sensitivity

        Returns:
            float: Dose rate in microsieverts per hour (µSv/h)

        Requirements: 2.5
        """
        if self.tube_sensitivity == 0:
            return 0.0
        return self.tube_rate / self.tube_sensitivity


@dataclass
class DevicePayload:
    """Device information for Home Assistant MQTT Discovery.

    This dataclass represents the device information included in Home Assistant
    discovery payloads. It provides details about the physical device that
    sensors belong to.

    Attributes:
        identifiers: List of unique identifiers for the device
        name: Human-readable device name
        manufacturer: Device manufacturer name
        model: Device model name
        sw_version: Software/firmware version

    Requirements: 4.3, 5.3, 5.4, 5.5
    """

    identifiers: list[str]
    name: str
    manufacturer: str
    model: str
    sw_version: str


@dataclass
class DiscoveryPayload:
    """Home Assistant MQTT Discovery payload.

    This dataclass represents a complete Home Assistant MQTT Discovery payload
    for a sensor. It includes all required fields for Home Assistant to
    automatically configure and display the sensor.

    Attributes:
        name: Human-readable sensor name
        unique_id: Unique identifier for the sensor entity
        state_topic: MQTT topic where sensor state is published
        availability_topic: MQTT topic where availability status is published
        device: Device information
        device_class: Home Assistant device class (optional)
        unit_of_measurement: Unit of measurement for the sensor value (optional)
        icon: Material Design Icon identifier (optional)
        state_class: State class for statistics (optional)

    Requirements: 4.1, 4.3, 4.5, 4.6
    """

    name: str
    unique_id: str
    state_topic: str
    availability_topic: str
    device: DevicePayload
    device_class: str | None = None
    unit_of_measurement: str | None = None
    icon: str | None = None
    state_class: str | None = None

    def to_json(self) -> str:
        """Serialize discovery payload to JSON for MQTT publishing.

        Converts the discovery payload to a JSON string suitable for publishing
        to MQTT. Fields with None values are excluded from the output.

        Returns:
            str: JSON-formatted discovery payload

        Requirements: 4.3
        """
        # Build dictionary with all fields
        payload_dict = {
            "name": self.name,
            "unique_id": self.unique_id,
            "state_topic": self.state_topic,
            "availability_topic": self.availability_topic,
            "device": {
                "identifiers": self.device.identifiers,
                "name": self.device.name,
                "manufacturer": self.device.manufacturer,
                "model": self.device.model,
                "sw_version": self.device.sw_version,
            },
        }

        # Add optional fields only if they have values
        if self.device_class is not None:
            payload_dict["device_class"] = self.device_class
        if self.unit_of_measurement is not None:
            payload_dict["unit_of_measurement"] = self.unit_of_measurement
        if self.icon is not None:
            payload_dict["icon"] = self.icon
        if self.state_class is not None:
            payload_dict["state_class"] = self.state_class

        return json.dumps(payload_dict)
