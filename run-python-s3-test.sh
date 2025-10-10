#!/bin/bash
set -e

echo "=========================================="
echo "Running Python S3 CRUD Test"
echo "=========================================="
echo ""
echo "This test will:"
echo "  1. Connect to AIStor via Sidekick (HTTP proxy)"
echo "  2. Create encrypted objects in python-s3-test bucket"
echo "  3. Read, Update, and Delete objects"
echo "  4. Verify SSE-KMS encryption"
echo ""
echo "Press Ctrl+C to cancel, or wait 5 seconds..."
sleep 5

echo ""
echo "Starting test..."
echo ""

docker exec python-s3-test python /app/s3_crud_test.py

echo ""
echo "=========================================="
echo "Test Complete!"
echo "=========================================="

