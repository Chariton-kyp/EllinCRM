# syntax=docker/dockerfile:1
# ========================================
# EllinCRM - Backend
# Production Dockerfile (Multi-stage Build)
# ========================================
# Author: Kypraios Chariton (Κυπραίος Χαρίτων)
# ========================================

# ------------------------------
# Stage 1: Builder
# ------------------------------
FROM python:3.14-slim-bookworm AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ------------------------------
# Stage 2: Production
# ------------------------------
FROM python:3.14-slim-bookworm AS production

# Labels
LABEL maintainer="Kypraios Chariton"
LABEL project="EllinCRM - Backend API"
LABEL version="1.0.0"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_ENV=production

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy wheels from builder and install
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels

# Copy application code
COPY app/ ./app/

# Copy Alembic configuration and migrations
COPY alembic.ini ./
COPY alembic/ ./alembic/

# Create non-root user for security
RUN adduser --disabled-password --gecos '' --uid 1000 appuser \
    && mkdir -p /app/output /app/data \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port for the API
EXPOSE 7000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7000/health || exit 1

# Default command - run migrations then start uvicorn
# Migrations run automatically on container start
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 7000"]
