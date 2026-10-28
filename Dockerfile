# syntax=docker/dockerfile:1

# ---- Build stage ----
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Copy pyproject and lock files (if using uv, but we can use pip)
COPY pyproject.toml .
# Install dependencies
RUN pip install --upgrade pip && pip install .

# ---- Runtime stage ----
FROM python:3.11-slim

WORKDIR /app

# Copy only needed runtime files
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app /app

# Ensure non-root user
RUN useradd --uid 1000 --create-home appuser && chown -R appuser:appuser /app
USER appuser

# Set entrypoint (the console script defined in pyproject)
ENTRYPOINT ["perplexity-browser-api"]
