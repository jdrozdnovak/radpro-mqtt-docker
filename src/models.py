"""Data models for RadPro MQTT Bridge.

This module defines dataclasses for device information and radiation measurements.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


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

    Requirements: 2.5
    """

    timestamp: datetime
    tube_rate: float
    tube_pulse_count: int
    battery_voltage: float
    tube_sensitivity: float
    tube_lifetime: int

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
    device_class: Optional[str] = None
    unit_of_measurement: Optional[str] = None
    icon: Optional[str] = None
    state_class: Optional[str] = None

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
