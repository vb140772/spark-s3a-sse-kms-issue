#!/bin/bash
# Run Sidekick HTTPS frontend test
# This script:
# 1. Generates ECDSA certificates for Sidekick (if needed)
# 2. Starts MinIO and Sidekick with docker-compose
# 3. Runs S3 operations test through Sidekick

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "Sidekick HTTPS Frontend Test Setup"
echo "============================================================"
echo ""

# Check if certificates exist
if [ ! -f "certs/sidekick/public.crt" ] || [ ! -f "certs/sidekick/private.key" ]; then
    echo "Certificates not found. Generating ECDSA certificates..."
    echo ""
    bash docker/generate-sidekick-certs.sh certs/sidekick "MinIO Sidekick CA" "sidekick.local"
    echo ""
else
    echo "✅ Certificates already exist in certs/sidekick/"
fi

echo ""
echo "Starting services with docker-compose..."
docker-compose -f docker-compose-sidekick.yml up -d

echo ""
echo "Waiting for services to be ready..."
sleep 15

# Wait for Sidekick to be ready (check if port is listening)
echo "Waiting for Sidekick to start..."
for i in {1..30}; do
    if docker-compose -f docker-compose-sidekick.yml ps sidekick | grep -q "Up"; then
        echo "✅ Sidekick is running"
        break
    fi
    sleep 1
done

echo ""
echo "Checking service status..."
docker-compose -f docker-compose-sidekick.yml ps

echo ""
echo "Running S3 operations test through Sidekick..."
echo "============================================================"
docker-compose -f docker-compose-sidekick.yml exec -T s3-test-client /app/scripts/test_sidekick_s3.sh

echo ""
echo "============================================================"
echo "Test Complete!"
echo "============================================================"
echo ""
echo "To stop services:"
echo "  docker-compose -f docker-compose-sidekick.yml down"
echo ""
echo "To view logs:"
echo "  docker-compose -f docker-compose-sidekick.yml logs -f sidekick"
echo ""

