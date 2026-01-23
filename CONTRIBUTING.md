# Contributing to RadPro MQTT Bridge

Thank you for your interest in contributing to RadPro MQTT Bridge! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Release Process](#release-process)

## Code of Conduct

This project follows a standard code of conduct. Please be respectful and constructive in all interactions with other contributors.

## Getting Started

### Prerequisites

- Python 3.10 or higher (supports 3.10, 3.11, 3.12, 3.13, 3.14)
- [UV](https://github.com/astral-sh/uv) - Fast Python package installer and resolver
- Git
- Docker (for container testing)
- A RadPro Geiger counter device (for hardware testing)
- An MQTT broker (Mosquitto recommended for testing)

### Installing UV

UV is a fast Python package installer that replaces pip, virtualenv, and poetry:

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Or via Homebrew:**
```bash
brew install uv
```

**Windows:**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Development Setup

### 1. Fork and Clone the Repository

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR-USERNAME/radpro-mqtt-bridge.git
cd radpro-mqtt-bridge
```

### 2. Create a Virtual Environment

```bash
# Create virtual environment (80x faster than venv)
uv venv

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate  # Windows
```

### 3. Install Dependencies

```bash
# Install all dependencies including development tools
uv sync

# Or install from pyproject.toml
uv pip install -e ".[dev]"
```

This installs:
- Core dependencies: `pyserial`, `paho-mqtt`
- Development tools: `pytest`, `hypothesis`, `pytest-mock`, `black`, `mypy`, `ruff`

### 4. Verify Installation

```bash
# Run tests to verify setup
uv run pytest

# Check code formatting
uv run black --check src/ tests/

# Run linter
uv run ruff check src/ tests/

# Run type checker
uv run mypy src/
```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Your Changes

- Write code following the [Code Style Guidelines](#code-style-guidelines)
- Add tests for new functionality
- Update documentation as needed
- Keep commits focused and atomic

### 3. Run Tests and Checks

```bash
# Run all tests
uv run pytest

# Run specific test types
uv run pytest tests/unit/
uv run pytest tests/property/
uv run pytest tests/integration/

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Format code
uv run black src/ tests/

# Lint code
uv run ruff check src/ tests/ --fix

# Type check
uv run mypy src/
```

### 4. Commit Your Changes

```bash
git add .
git commit -m "feat: add new feature description"
```

**Commit Message Format:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test additions or changes
- `refactor:` - Code refactoring
- `style:` - Code style changes (formatting, etc.)
- `chore:` - Maintenance tasks

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Code Style Guidelines

### Python Style

This project follows strict code quality standards:

#### Line Length
- **Maximum line length: 100 characters**
- Enforced by Black formatter

#### Formatting
- Use [Black](https://black.readthedocs.io/) for code formatting
- Run before committing: `uv run black src/ tests/`

#### Linting
- Use [Ruff](https://docs.astral.sh/ruff/) for linting
- Enabled rules:
  - `E` - pycodestyle errors
  - `W` - pycodestyle warnings
  - `F` - pyflakes
  - `I` - isort (import sorting)
  - `B` - flake8-bugbear
  - `UP` - pyupgrade
- Run before committing: `uv run ruff check src/ tests/ --fix`

#### Type Hints
- **Type hints are required** for all functions and methods
- Use [mypy](https://mypy.readthedocs.io/) for type checking
- Strict mode enabled
- Run before committing: `uv run mypy src/`

#### Example

```python
from typing import Optional

def calculate_dose_rate(tube_rate: float, sensitivity: float) -> float:
    """Calculate radiation dose rate.
    
    Args:
        tube_rate: Counts per minute
        sensitivity: Tube sensitivity in cpm/µSv/h
        
    Returns:
        Dose rate in µSv/h
        
    Raises:
        ValueError: If sensitivity is zero
    """
    if sensitivity == 0:
        raise ValueError("Sensitivity cannot be zero")
    return tube_rate / sensitivity
```

### Documentation Style

#### Docstrings
- Use Google-style docstrings
- Include type information
- Document all parameters, return values, and exceptions
- Link to requirements where applicable

#### Comments
- Use comments to explain *why*, not *what*
- Link requirements: `# Requirement 9.1`
- Keep comments up-to-date with code changes

#### README and Documentation
- Keep README.md up-to-date with new features
- Update configuration documentation for new environment variables
- Add troubleshooting entries for common issues

## Testing

### Testing Philosophy

This project uses a dual testing approach:

1. **Unit Tests**: Test specific examples, edge cases, and error conditions
2. **Property-Based Tests**: Test universal properties across all inputs using Hypothesis

Both types of tests are valuable and complement each other.

### Writing Unit Tests

```python
# tests/unit/test_config.py
import pytest
from src.config import Config

def test_config_from_env_with_defaults(monkeypatch):
    """Test configuration loading with default values."""
    monkeypatch.setenv("MQTT_HOST", "test-broker")
    
    config = Config.from_env()
    
    assert config.mqtt_host == "test-broker"
    assert config.mqtt_port == 1883  # Default value
    assert config.poll_interval == 60  # Default value
```

### Writing Property-Based Tests

```python
# tests/property/test_calculations.py
from hypothesis import given, strategies as st
from src.models import RadiationMeasurement

@given(
    tube_rate=st.floats(min_value=0.0, max_value=10000.0),
    sensitivity=st.floats(min_value=0.1, max_value=1000.0)
)
def test_dose_rate_calculation_property(tube_rate, sensitivity):
    """Property: dose_rate = tube_rate / sensitivity for all valid inputs.
    
    Feature: radpro-mqtt-bridge, Property 1: Dose Rate Calculation
    Validates: Requirements 2.5
    """
    expected = tube_rate / sensitivity
    
    measurement = RadiationMeasurement(
        timestamp=datetime.now(),
        tube_rate=tube_rate,
        tube_pulse_count=0,
        battery_voltage=1.5,
        tube_sensitivity=sensitivity,
        tube_lifetime=0
    )
    
    assert abs(measurement.dose_rate - expected) < 0.001
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test types
uv run pytest -m unit
uv run pytest -m property
uv run pytest -m integration

# Run with coverage
uv run pytest --cov=src --cov-report=html
open htmlcov/index.html  # View coverage report

# Run specific test file
uv run pytest tests/unit/test_config.py

# Run with verbose output
uv run pytest -v

# Run with debug output
uv run pytest -s
```

### Test Organization

```
tests/
├── unit/              # Unit tests for specific functionality
│   ├── test_config.py
│   ├── test_radpro_device.py
│   ├── test_mqtt_publisher.py
│   └── test_models.py
├── property/          # Property-based tests
│   ├── test_calculations.py
│   ├── test_serialization.py
│   └── test_topic_construction.py
└── integration/       # Integration tests
    └── test_end_to_end.py
```

## Submitting Changes

### Pull Request Process

1. **Ensure all tests pass**: `uv run pytest`
2. **Ensure code is formatted**: `uv run black src/ tests/`
3. **Ensure code is linted**: `uv run ruff check src/ tests/`
4. **Ensure type checking passes**: `uv run mypy src/`
5. **Update documentation** if needed
6. **Create pull request** with clear description

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Property tests added/updated
- [ ] Integration tests added/updated
- [ ] All tests pass

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings generated
```

### Review Process

1. Automated checks must pass (tests, linting, type checking)
2. At least one maintainer review required
3. Address review feedback
4. Maintainer will merge when approved

## Release Process

Releases are automated via GitHub Actions:

### Version Tagging

```bash
# Create and push a version tag
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

### Automated Build

When a tag is pushed:
1. GitHub Actions builds Docker images for amd64 and arm64
2. Images are tagged with version number and pushed to GitHub Container Registry
3. Release notes are generated automatically

### Manual Release Steps

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create and push version tag
4. GitHub Actions handles the rest

## Development Tips

### Using UV Effectively

```bash
# Add a new dependency
uv add package-name

# Add a development dependency
uv add --dev package-name

# Update all dependencies
uv sync --upgrade

# Show installed packages
uv pip list

# Show dependency tree
uv pip tree
```

### Local Testing with Docker

```bash
# Build local Docker image
docker build -t radpro-mqtt-bridge:dev .

# Run with local image
docker run --rm \
  --device=/dev/ttyACM0:/dev/ttyACM0 \
  -e MQTT_HOST=localhost \
  radpro-mqtt-bridge:dev
```

### Debugging

```bash
# Run with debug logging
export LOG_LEVEL=DEBUG
python -m src.main

# Run with Python debugger
python -m pdb -m src.main

# Run tests with debugger on failure
uv run pytest --pdb
```

### Mock MQTT Broker for Testing

```bash
# Start Mosquitto in Docker
docker run -d --name mosquitto -p 1883:1883 eclipse-mosquitto:2

# Subscribe to all topics
mosquitto_sub -h localhost -t '#' -v

# Publish test message
mosquitto_pub -h localhost -t 'test/topic' -m 'test message'
```

## Getting Help

- **Questions**: Open a [GitHub Discussion](https://github.com/yourusername/radpro-mqtt-bridge/discussions)
- **Bugs**: Open a [GitHub Issue](https://github.com/yourusername/radpro-mqtt-bridge/issues)
- **Security**: Email security@example.com (do not open public issues)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
