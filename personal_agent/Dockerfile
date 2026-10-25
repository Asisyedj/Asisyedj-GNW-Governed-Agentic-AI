# Multi‑stage Docker build for the personal AI agent
# -------------------------------------------------
# Stage 1 – build the virtual environment and install deps
FROM python:3.12-slim AS builder
WORKDIR /app

# Install build‑time dependencies (git, gcc for possible wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git gcc && rm -rf /var/lib/apt/lists/*

# Copy only the requirements first to leverage layer caching
COPY requirements.txt .
RUN python -m venv /venv && \
    /venv/bin/pip install --upgrade pip && \
    /venv/bin/pip install --no-cache-dir -r requirements.txt

# Stage 2 – runtime image
FROM python:3.12-slim AS runtime
WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH"

# Copy the source code
COPY personal_agent/ personal_agent/
COPY .gitignore .
COPY README.md .

# Set a non‑root user for safety (optional)
RUN useradd -m agent && chown -R agent:agent /app
USER agent

# Entry point runs the REPL; can be overridden at runtime
ENTRYPOINT ["python", "-m", "personal_agent.agent.repl"]
