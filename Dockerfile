# RadPro MQTT Bridge Dockerfile
# Multi-stage build for minimal image size

FROM python:3.14-slim as builder

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

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

# Copy uv from builder
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src/ ./src/

# Create health check file directory
RUN mkdir -p /tmp

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app/.venv/bin:$PATH"

# Health check
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, time; mtime = os.path.getmtime('/tmp/health') if os.path.exists('/tmp/health') else 0; exit(0 if time.time() - mtime < 120 else 1)"

# Run the application
CMD ["python", "-m", "src.main"]
