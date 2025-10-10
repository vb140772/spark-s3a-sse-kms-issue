#!/bin/bash
# Simple test script for Spark SQL with MinIO

echo "Running Spark SQL test with MinIO AIStor..."
echo ""

docker exec spark-master /opt/spark/bin/spark-submit \
  --master local[2] \
  --packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.367 \
  --conf spark.jars.ivy=/tmp/ivy-cache \
  /opt/spark/scripts/sql_test.py
