# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System-level dependencies required by Python packages
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first to leverage Docker layer caching
COPY pipeline-worker/requirements.txt /tmp/pipeline-worker-requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/pipeline-worker-requirements.txt

# Copy the entire project so the worker can access local packages like greekroom and utilities
COPY . .

# Remove any Python cache files that might have been copied (safety measure)
RUN find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \

RUN python -m pip install ./greekroom

ENV PYTHONPATH=/app \
    PORT=8080

EXPOSE 8080

CMD ["python", "pipeline-worker/main.py"]

