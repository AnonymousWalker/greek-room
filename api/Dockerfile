# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# System-level dependencies required by uvicorn and sil-machine
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first to leverage Docker layer caching
COPY api/requirements.txt /tmp/api-requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/api-requirements.txt

# Copy the entire project so FastAPI can access local packages like greekroom
COPY . .

RUN python -m pip install ./greekroom

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

