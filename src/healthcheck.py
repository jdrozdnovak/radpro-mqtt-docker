"""Container health check for RadPro MQTT Bridge.

Run as ``python -m src.healthcheck``. Exits 0 while the bridge is still
delivering data to the broker and 1 once it has gone quiet, which is what the
Dockerfile HEALTHCHECK reports to the container runtime.

The bridge rewrites its health file after every acknowledged publish, so a
stale file means data is no longer reaching MQTT - even if the process is
still running and its logs look normal.
"""

import os
import sys
import time

from src.config import Config


def read_health_timestamp(path: str) -> float | None:
    """Read the timestamp of the last successful publish.

    Args:
        path: Path of the health file written by the bridge

    Returns:
        float | None: Unix timestamp of the last successful publish, or None
            if the file is missing or unreadable
    """
    try:
        with open(path) as f:
            content = f.read().strip()
    except OSError:
        return None

    try:
        return float(content)
    except ValueError:
        # Fall back to the file's mtime if the contents are truncated
        try:
            return os.path.getmtime(path)
        except OSError:
            return None


def check_health(config: Config, now: float | None = None) -> tuple[bool, str]:
    """Determine whether the bridge is still delivering data.

    Args:
        config: Configuration providing the health file path and timeout
        now: Current Unix timestamp (defaults to the actual current time)

    Returns:
        tuple[bool, str]: Health state and a human-readable reason
    """
    # One extra polling interval of slack so a cycle that is merely slow does
    # not flap the container between healthy and unhealthy
    max_age = config.effective_watchdog_timeout + config.poll_interval
    current_time = time.time() if now is None else now

    timestamp = read_health_timestamp(config.health_file)
    if timestamp is None:
        return False, f"No health file at {config.health_file}: bridge has not published yet"

    age = current_time - timestamp
    if age > max_age:
        return False, f"Last successful publish was {age:.0f}s ago (limit {max_age}s)"

    return True, f"Last successful publish was {age:.0f}s ago"


def main() -> int:
    """Entry point for the container health check.

    Returns:
        int: 0 if healthy, 1 otherwise
    """
    try:
        config = Config.from_env()
    except ValueError as e:
        print(f"unhealthy: invalid configuration: {e}", file=sys.stderr)
        return 1

    healthy, reason = check_health(config)
    if healthy:
        print(f"healthy: {reason}")
        return 0

    print(f"unhealthy: {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
