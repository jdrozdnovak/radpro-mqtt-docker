# RadPro MQTT Bridge Dockerfile
# Multi-stage build for minimal image size

FROM python:3.14-slim AS builder

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock* ./
COPY README.md ./

# Install dependencies using uv
RUN uv sync --frozen --no-dev

# Final stage
FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src/ ./src/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app/.venv/bin:$PATH"

# Dump a traceback if the process is killed by a fatal signal, so a wedged
# bridge leaves evidence behind in the container logs
ENV PYTHONFAULTHANDLER=1

# Health check: reports unhealthy once data stops reaching the MQTT broker.
# The threshold follows WATCHDOG_TIMEOUT/POLL_INTERVAL, so it stays correct
# when those are changed. The bridge restarts itself on a stall; this makes
# the stall visible to `docker ps` and to supervisors that watch health.
HEALTHCHECK --interval=60s --timeout=10s --start-period=120s --retries=3 \
    CMD ["python", "-m", "src.healthcheck"]

# Run the application
CMD ["python", "-m", "src.main"]
