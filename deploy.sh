#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Deploying LinkedIn AI SDR ==="

echo "Pulling latest changes..."
git pull origin main

echo "Building and starting container..."
docker compose up -d --build

echo "Waiting for health check..."
sleep 10

if curl -sf http://localhost:9000/health > /dev/null 2>&1; then
    echo "Health check: OK"
else
    echo "Health check: FAILED"
    echo "Recent logs:"
    docker compose logs --tail=30
    exit 1
fi

echo "=== Deploy complete ==="
