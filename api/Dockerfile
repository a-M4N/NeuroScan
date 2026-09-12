FROM python:3.13-slim AS builder
WORKDIR /app

# Install build dependencies for compiling Python extensions (e.g. psycopg2, CFFI)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency specifications
COPY pyproject.toml uv.lock ./

# Install locked dependencies into virtual environment
ENV UV_NO_MANAGED_PYTHON=1
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13-slim
WORKDIR /app

# Install runtime system libraries:
# - libpq5: PostgreSQL runtime client
# - libxcb1, libgl1, libglib2.0-0: OpenCV headless runtime
# - libpango-1.0-0, libpangoft2-1.0-0, libpangocairo-1.0-0, libcairo2, libgdk-pixbuf-2.0-0, libffi8, shared-mime-info, fonts-liberation: WeasyPrint PDF runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libxcb1 \
    libgl1 \
    libglib2.0-0 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy prebuilt virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Ensure runtime directories exist for data persistence (scans, heatmaps, reports)
RUN mkdir -p data/scans data/heatmaps data/reports

# Copy application configuration and codebase
COPY alembic.ini ./
COPY api/ ./api/
COPY models/src/ ./models/src/
COPY models/checkpoints/ ./models/checkpoints/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Run database migrations automatically before starting Uvicorn
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn api.main:app --host 0.0.0.0 --port 8000"]