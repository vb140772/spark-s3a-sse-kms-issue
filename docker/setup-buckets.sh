#!/bin/sh
set -e

echo "=========================================="
echo "MinIO Client - Initial Setup"
echo "=========================================="

# Wait for AIStor to be ready
echo "Waiting for AIStor..."
sleep 15

# Configure alias with HTTPS (AIStor has TLS certs in image)
echo "Configuring AIStor alias with HTTPS..."
mc alias set aistor https://aistor:9000 minioadmin minioadmin --insecure

echo ""
echo "Creating buckets..."
mc mb aistor/spark-data --ignore-existing
mc mb aistor/spark-warehouse --ignore-existing
mc mb aistor/python-s3-test --ignore-existing

echo ""
echo "Enabling SSE-KMS encryption on buckets..."
mc encrypt set sse-kms spark-encryption-key aistor/spark-data/
mc encrypt set sse-kms spark-encryption-key aistor/spark-warehouse/
mc encrypt set sse-kms spark-encryption-key aistor/python-s3-test/

echo ""
echo "Verifying encryption settings..."
mc encrypt info aistor/spark-data/
mc encrypt info aistor/spark-warehouse/
mc encrypt info aistor/python-s3-test/

echo ""
echo "=========================================="
echo "✅ Buckets created and encrypted!"
echo "=========================================="
echo ""
echo "Available buckets:"
mc ls aistor/

echo ""
echo "MinIO Client is now ready for commands:"
echo "  docker exec minio-client mc ls aistor/"
echo "  docker exec minio-client mc admin info aistor"
echo ""

