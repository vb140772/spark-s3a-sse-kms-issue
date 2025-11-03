#!/bin/bash
# Test HTTPS connectivity from Spark container to AIStor
# This validates SSL/TLS certificate trust and S3 API accessibility

echo "Running HTTPS connectivity tests from Spark container..."
echo ""

docker exec spark-master python3 /opt/spark/scripts/test_aistor_https.py



