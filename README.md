# RadPro MQTT Bridge

[![Build Status](https://github.com/yourusername/radpro-mqtt-bridge/workflows/Build/badge.svg)](https://github.com/yourusername/radpro-mqtt-bridge/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

A containerized Python application that bridges [RadPro](https://radpro.software/) Geiger counter devices to MQTT brokers with Home Assistant auto-discovery support. Monitor radiation levels in your home automation system with automatic device integration.

## Features

- **Automatic Device Discovery**: Seamlessly integrates with Home Assistant via MQTT Discovery
- **Real-time Monitoring**: Continuous radiation measurement polling with configurable intervals
- **Comprehensive Metrics**: Tracks dose rate (µSv/h), counts per minute (CPM), total pulses, battery voltage, and tube lifetime
- **Resilient Operation**: Automatic reconnection handling for both USB and MQTT connections
- **Docker Ready**: Fully containerized with multi-architecture support (amd64, arm64)
- **Easy Configuration**: Environment variable-based configuration with sensible defaults
- **Production Ready**: Comprehensive logging, health checks, and graceful shutdown handling

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- RadPro Geiger counter device connected via USB
- MQTT broker (e.g., Mosquitto) running and accessible
- (Optional) Home Assistant instance for automatic integration

### Installation with Docker Compose

1. **Create a `docker-compose.yml` file:**

```yaml
version: '3.8'

services:
  radpro-mqtt-bridge:
    image: ghcr.io/yourusername/radpro-mqtt-bridge:latest
    container_name: radpro-mqtt-bridge
    restart: unless-stopped
    
    devices:
      - /dev/ttyACM0:/dev/ttyACM0
    
    environment:
      - MQTT_HOST=your-mqtt-broker.local
      - MQTT_PORT=1883
      - MQTT_USERNAME=your-username  # Optional
      - MQTT_PASSWORD=your-password  # Optional
      - MQTT_TOPIC_PREFIX=radpro
      - HA_DISCOVERY_PREFIX=homeassistant
      - RADPRO_DEVICE=/dev/ttyACM0
      - POLL_INTERVAL=60
      - LOG_LEVEL=INFO
```

2. **Start the container:**

```bash
docker-compose up -d
```

3. **Check the logs:**

```bash
docker-compose logs -f radpro-mqtt-bridge
```

### Installation with Docker Run

```bash
docker run -d \
  --name radpro-mqtt-bridge \
  --device=/dev/ttyACM0:/dev/ttyACM0 \
  --restart unless-stopped \
  -e MQTT_HOST=your-mqtt-broker.local \
  -e MQTT_PORT=1883 \
  -e MQTT_USERNAME=your-username \
  -e MQTT_PASSWORD=your-password \
  -e RADPRO_DEVICE=/dev/ttyACM0 \
  -e POLL_INTERVAL=60 \
  -e LOG_LEVEL=INFO \
  ghcr.io/yourusername/radpro-mqtt-bridge:latest
```

## Configuration

All configuration is done via environment variables:

### Required Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `MQTT_HOST` | MQTT broker hostname or IP address | `mosquitto.local` |

### Optional Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `MQTT_PORT` | MQTT broker port | `1883` |
| `MQTT_USERNAME` | MQTT authentication username | _(none)_ |
| `MQTT_PASSWORD` | MQTT authentication password | _(none)_ |
| `MQTT_TOPIC_PREFIX` | Prefix for MQTT topics | `radpro` |
| `HA_DISCOVERY_PREFIX` | Home Assistant discovery prefix | `homeassistant` |
| `RADPRO_DEVICE` | USB device path for RadPro device | `/dev/ttyACM0` |
| `POLL_INTERVAL` | Data polling interval in seconds | `60` |
| `LOG_LEVEL` | Logging verbosity (DEBUG, INFO, WARNING, ERROR) | `INFO` |

### Finding Your USB Device

To find the correct USB device path for your RadPro device:

```bash
# List USB serial devices
ls -l /dev/ttyACM* /dev/ttyUSB*

# Or use dmesg to see recent USB connections
dmesg | grep tty
```

Common device paths:
- Linux: `/dev/ttyACM0` or `/dev/ttyUSB0`
- macOS: `/dev/cu.usbmodem*`

## Home Assistant Integration

The bridge automatically configures itself in Home Assistant using MQTT Discovery. No manual configuration is required!

### Automatic Setup

1. Ensure your Home Assistant instance is connected to the same MQTT broker
2. Start the RadPro MQTT Bridge
3. The following sensors will automatically appear in Home Assistant:
   - **Dose Rate** (µSv/h) - Current radiation dose rate
   - **Counts Per Minute** (CPM) - Radiation detection events per minute
   - **Total Pulses** - Cumulative radiation detection count
   - **Battery Voltage** (V) - RadPro device battery level
   - **Tube Lifetime** (s) - Geiger tube operational lifetime

### Device Information

The bridge publishes complete device information to Home Assistant:
- **Manufacturer**: RadPro
- **Model**: Hardware ID from device
- **Software Version**: Firmware version from device
- **Unique Identifier**: Device ID from device

### Example Automation

Create automations based on radiation levels:

```yaml
automation:
  - alias: "High Radiation Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.radpro_dose_rate
        above: 0.5  # µSv/h
    action:
      - service: notify.mobile_app
        data:
          message: "High radiation detected: {{ states('sensor.radpro_dose_rate') }} µSv/h"
```

### Lovelace Dashboard Card

Display radiation data in your dashboard:

```yaml
type: entities
title: Radiation Monitor
entities:
  - entity: sensor.radpro_dose_rate
    name: Dose Rate
  - entity: sensor.radpro_cpm
    name: Counts Per Minute
  - entity: sensor.radpro_battery_voltage
    name: Battery
  - entity: sensor.radpro_total_pulses
    name: Total Pulses
  - entity: sensor.radpro_tube_lifetime
    name: Tube Lifetime
```

## MQTT Topics

The bridge publishes data to the following MQTT topics (with default prefix `radpro`):

### State Topics

- `radpro/dose_rate/state` - Dose rate in µSv/h (JSON)
- `radpro/cpm/state` - Counts per minute (JSON)
- `radpro/total_pulses/state` - Total pulse count (JSON)
- `radpro/battery_voltage/state` - Battery voltage in volts (JSON)
- `radpro/tube_lifetime/state` - Tube lifetime in seconds (JSON)
- `radpro/availability` - Online/offline status

### Discovery Topics

Home Assistant discovery payloads are published to:
- `homeassistant/sensor/{device_id}/{sensor_name}/config`

## Troubleshooting

### Container Won't Start

**Problem**: Container exits immediately after starting

**Solutions**:
1. Check that `MQTT_HOST` is set correctly:
   ```bash
   docker logs radpro-mqtt-bridge
   ```

2. Verify MQTT broker is accessible:
   ```bash
   # Test MQTT connection
   docker run --rm -it eclipse-mosquitto:2 mosquitto_sub -h your-mqtt-broker.local -t '#' -v
   ```

3. Check configuration validation errors in logs

### USB Device Not Found

**Problem**: "Failed to connect to RadPro device" error

**Solutions**:
1. Verify device is connected:
   ```bash
   ls -l /dev/ttyACM0
   ```

2. Check device permissions:
   ```bash
   # Add user to dialout group (Linux)
   sudo usermod -a -G dialout $USER
   
   # Or run container with privileged mode (not recommended for production)
   docker run --privileged ...
   ```

3. Try a different device path:
   ```bash
   # List all USB serial devices
   ls -l /dev/tty*
   ```

4. Check if device is already in use by another process:
   ```bash
   lsof /dev/ttyACM0
   ```

### Device Not Appearing in Home Assistant

**Problem**: Sensors don't show up in Home Assistant

**Solutions**:
1. Verify MQTT integration is configured in Home Assistant:
   - Go to Settings → Devices & Services
   - Check that MQTT integration is set up

2. Check MQTT discovery prefix matches Home Assistant configuration:
   - Default is `homeassistant`
   - Verify with `HA_DISCOVERY_PREFIX` environment variable

3. Check MQTT broker logs for discovery messages:
   ```bash
   # Subscribe to discovery topics
   mosquitto_sub -h your-mqtt-broker.local -t 'homeassistant/sensor/#' -v
   ```

4. Restart Home Assistant after starting the bridge

### Connection Keeps Dropping

**Problem**: Frequent disconnections and reconnections

**Solutions**:
1. Check USB cable quality - try a different cable
2. Check for USB power issues - use a powered USB hub
3. Increase polling interval to reduce USB traffic:
   ```yaml
   environment:
     - POLL_INTERVAL=120  # Poll every 2 minutes
   ```
4. Check system logs for USB errors:
   ```bash
   dmesg | grep -i usb
   ```

### High CPU Usage

**Problem**: Container using excessive CPU

**Solutions**:
1. Increase polling interval:
   ```yaml
   environment:
     - POLL_INTERVAL=300  # Poll every 5 minutes
   ```

2. Reduce log verbosity:
   ```yaml
   environment:
     - LOG_LEVEL=WARNING
   ```

### MQTT Authentication Failures

**Problem**: "Connection refused" or authentication errors

**Solutions**:
1. Verify MQTT credentials are correct
2. Check MQTT broker allows connections from Docker network
3. Test credentials manually:
   ```bash
   mosquitto_sub -h your-mqtt-broker.local -u username -P password -t '#'
   ```

### Viewing Detailed Logs

Enable debug logging for detailed troubleshooting:

```yaml
environment:
  - LOG_LEVEL=DEBUG
```

Then view logs:
```bash
docker-compose logs -f radpro-mqtt-bridge
```

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup instructions and contribution guidelines.

## Architecture

The bridge consists of three main components:

1. **USB Serial Handler** (`RadProDevice`): Manages communication with the RadPro device using the pyserial library
2. **MQTT Publisher** (`MQTTPublisher`): Handles MQTT connection, discovery payloads, and state publishing
3. **Main Loop** (`RadProBridge`): Orchestrates polling, data collection, and publishing

### Data Flow

```
RadPro Device (USB) → Bridge Application → MQTT Broker → Home Assistant
```

1. Bridge connects to RadPro device via USB serial (115200 baud, 8N1)
2. Bridge polls device for measurements at configured interval
3. Bridge calculates dose rate from CPM and tube sensitivity
4. Bridge publishes sensor states to MQTT topics
5. Home Assistant discovers and displays sensors automatically

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [RadPro](https://radpro.software/) - Open-source Geiger counter firmware
- [Home Assistant](https://www.home-assistant.io/) - Open-source home automation platform
- [Eclipse Mosquitto](https://mosquitto.org/) - Open-source MQTT broker

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/radpro-mqtt-bridge/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/radpro-mqtt-bridge/discussions)
- **RadPro Documentation**: [radpro.software](https://radpro.software/)

## Changelog

See [GitHub Releases](https://github.com/yourusername/radpro-mqtt-bridge/releases) for version history and changes.
