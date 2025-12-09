# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System-level dependencies required by Python packages
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        gcc \
        git \
        cmake \
    && rm -rf /var/lib/apt/lists/*

# Clone and build fast_align (before COPY to improve layer caching)
RUN git clone https://github.com/clab/fast_align.git /opt/fast_align \
    && cd /opt/fast_align \
    && mkdir -p build \
    && cd build \
    && cmake .. \
    && make

# Install Python dependencies first to leverage Docker layer caching
COPY pipeline-worker/requirements.txt /tmp/pipeline-worker-requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/pipeline-worker-requirements.txt

# Copy the entire project so the worker can access local packages like greekroom and utilities
COPY . .

RUN python -m pip install ./greekroom

ENV PYTHONPATH=/app \
    ROOT_DIR=/app \
    FAST_ALIGN_SRC_DIR=/opt/fast_align \
    PORT=8080

EXPOSE 8080

CMD ["python", "pipeline-worker/webhook.py"]

