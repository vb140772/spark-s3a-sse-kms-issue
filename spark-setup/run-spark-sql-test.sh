#!/bin/bash
# Simple test script for Spark SQL with MinIO
# Usage: ./run-spark-sql-test.sh [options]
# Options:
#   --select-only   Only run SELECT queries on existing data (skip write operations)
#   --quiet, -q     Reduce output verbosity (show only essential information)
#   --direct        Use HTTPS directly to AIStor (instead of via Sidekick)
#   --http          Use HTTP via Sidekick HTTP frontend (http://sidekick-http:8091)
#   --sse-kms       Enable SSE-KMS encryption using MinKMS (requires HTTPS endpoint)

echo "Running Spark SQL test with MinIO AIStor..."
echo ""

docker exec spark-master /opt/spark/bin/spark-submit \
  --master local[2] \
  --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.367 \
  --conf spark.jars.ivy=/tmp/ivy-cache \
  /opt/spark/scripts/sql_test.py "$@"
