#!/bin/bash
# Script to run pipeline-worker container with 1Password injected environment variables
#
# Usage:
#   ./run-with-1password.sh
#
# Before running:
#   1. Ensure you're signed in: op signin
#   2. Build the image from root directory: docker build -f pipeline-worker/Dockerfile -t pipeline-worker .
#   3. Run the script: ./run-with-1password.sh
# The script uses op run to inject secrets from the .env.op file at runtime

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_OP_FILE="${SCRIPT_DIR}/.env.op"

# Check if 1Password CLI is available
if ! command -v op &> /dev/null; then
    echo "Error: 1Password CLI (op) is not installed or not in PATH"
    exit 1
fi

# Check if .env.op file exists
if [ ! -f "$ENV_OP_FILE" ]; then
    echo "Error: .env.op file not found: $ENV_OP_FILE"
    exit 1
fi

echo "Checking 1Password connection..."

# Check if user is signed in to 1Password
if ! op account list &> /dev/null 2>&1; then
    echo "Error: Not signed in to 1Password. Please run 'op signin' first"
    exit 1
fi

# Stop and remove existing container if it exists
if docker ps -a --format '{{.Names}}' | grep -q "^pipeline-worker$"; then
    echo "Stopping and removing existing container..."
    docker stop pipeline-worker 2>/dev/null || true
    docker rm pipeline-worker 2>/dev/null || true
fi

echo "Starting container with 1Password injected environment variables..."
echo "Using .env.op file: $ENV_OP_FILE"

# Use op run to inject environment variables from .env.op and run docker
op run --env-file="$ENV_OP_FILE" -- \
    docker run -d \
    -p 8080:8080 \
    --name pipeline-worker \
    -e CONTENT_SERVER_URL \
    -e R2_STORAGE_ENDPOINT \
    -e R2_ACCESS_KEY_ID \
    -e R2_SECRET_ACCESS_KEY \
    -e BLOB_OUTPUT_PREFIX \
    -e SERVICE_BUS_CONNECTION_STRING \
    pipeline-worker

echo "Container started successfully!"
echo "View logs with: docker logs -f pipeline-worker"

