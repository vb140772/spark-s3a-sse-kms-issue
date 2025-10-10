#!/usr/bin/env python3
import argparse
from pyspark.sql import SparkSession

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Spark SQL test with MinIO AIStor S3')
parser.add_argument('--select-only', action='store_true', 
                    help='Only run SELECT queries on existing data (skip write operations)')
parser.add_argument('--quiet', '-q', action='store_true',
                    help='Reduce output verbosity (show only essential information)')
args = parser.parse_args()

# Create Spark session with Sidekick proxy
# Configuration: HTTP to Sidekick, Sidekick → HTTPS → AIStor, AIStor → MinKMS
spark = SparkSession.builder \
    .appName("SQL-Test-MinIO-Sidekick") \
    .master("local[2]") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://sidekick:8090") \
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .config("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider") \
    .getOrCreate()

# Note: Sidekick proxy architecture with MinKMS backend
# - Spark S3A → Sidekick: HTTP (S3A compatible, no SSL issues)
# - Sidekick → AIStor: HTTPS (TLS encrypted, CA verified)
# - AIStor → MinKMS: HTTPS/mTLS (encryption key management)
# - Backend security maintained with proper certificate validation
# - Note: SSE-KMS encryption will fail due to AWS SDK HTTPS enforcement (see SPARK_SSE_KMS_ISSUE.md)

if not args.quiet:
    print("✅ Spark session created with MinIO AIStor S3!")

if not args.select_only:
    # Create test data
    data = [(1, "Alice", 100), (2, "Bob", 200), (3, "Charlie", 150)]
    df = spark.createDataFrame(data, ["id", "name", "amount"])

    if not args.quiet:
        print("\nOriginal Data:")
    df.show()

    # Save to MinIO AIStor S3
    if not args.quiet:
        print("\n💾 Saving to MinIO AIStor S3 (s3a://spark-data/users)...")
    df.write.mode("overwrite").parquet("s3a://spark-data/users")
    if not args.quiet:
        print("✅ Data saved to AIStor!")
else:
    if not args.quiet:
        print("\n🔍 Running in SELECT-ONLY mode (skipping write operations)")

# Read from MinIO AIStor S3
if not args.quiet:
    print("\n📥 Reading from MinIO AIStor S3...")
users = spark.read.parquet("s3a://spark-data/users")

if not args.quiet:
    print("\nData from MinIO:")
users.show()

# Register as SQL table
users.createOrReplaceTempView("users")

# Run SQL query
if not args.quiet:
    print("\n🔍 SQL Query: SELECT * FROM users WHERE amount > 100")
result = spark.sql("SELECT * FROM users WHERE amount > 100")
result.show()

if not args.select_only:
    # Save query results back to MinIO AIStor
    if not args.quiet:
        print("\n💾 Saving query results to AIStor...")
    result.write.mode("overwrite").parquet("s3a://spark-data/high_value_users")
    if not args.quiet:
        print("✅ Results saved to s3a://spark-data/high_value_users")

if not args.quiet:
    print("\n" + "="*60)
    print("✅ Success! Spark SQL with MinIO AIStor S3!")
    print("="*60)
    print("📊 AIStor Console: http://localhost:9001")
    print("🔑 MinKMS available: https://localhost:7373 (standalone)")
    print("Login: minioadmin / minioadmin")

spark.stop()
