#!/usr/bin/env python3
import argparse
from pyspark.sql import SparkSession

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Spark SQL test with MinIO AIStor S3')
parser.add_argument('--select-only', action='store_true', 
                    help='Only run SELECT queries on existing data (skip write operations)')
parser.add_argument('--quiet', '-q', action='store_true',
                    help='Reduce output verbosity (show only essential information)')
parser.add_argument('--sse-kms', action='store_true',
                    help='Enable SSE-KMS encryption using MinKMS (key: spark-encryption-key)')
parser.add_argument('--direct', action='store_true',
                    help='Use HTTPS directly to AIStor (https://aistor:9000) instead of HTTP via Sidekick')
args = parser.parse_args()

# Determine endpoint and protocol based on flags
if args.direct:
    # Use HTTPS directly to AIStor
    endpoint = "https://aistor:9000"
    ssl_enabled = True
    app_name = "SQL-Test-MinIO-AIStor-HTTPS-Direct"
    protocol = "HTTPS (direct to AIStor)"
else:
    # Use HTTPS via Sidekick proxy (default)
    endpoint = "https://sidekick:8090"
    ssl_enabled = True
    app_name = "SQL-Test-MinIO-Sidekick-HTTPS"
    protocol = "HTTPS (via Sidekick)"

# Create Spark session
# Configuration: Spark S3A → HTTPS → [Sidekick/AIStor] → AIStor → MinKMS
spark_builder = SparkSession.builder \
    .appName(app_name) \
    .master("local[2]") \
    .config("spark.hadoop.fs.s3a.endpoint", endpoint) \
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", str(ssl_enabled).lower()) \
    .config("spark.hadoop.fs.s3a.connection.timeout", "10000") \
    .config("spark.hadoop.fs.s3a.connection.establish.timeout", "5000") \
    .config("spark.hadoop.fs.s3a.connection.maximum", "15") \
    .config("spark.hadoop.fs.s3a.retry.attempts", "3") \
    .config("spark.hadoop.fs.s3a.retry.interval", "1000ms") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .config("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")

# Handle encryption configuration
# IMPORTANT: With MINIO_KMS_AUTO_ENCRYPTION=on, AIStor handles encryption automatically
# Spark should NOT send encryption headers to avoid AWS SDK HTTPS enforcement
# The --sse-kms flag is kept for compatibility but doesn't actually set headers when using HTTP
if args.sse_kms:
    if args.direct:
        # Only set encryption headers when using HTTPS (direct connection)
        spark_builder \
            .config("spark.hadoop.fs.s3a.server-side-encryption-algorithm", "SSE-KMS") \
            .config("spark.hadoop.fs.s3a.server-side-encryption.key", "spark-encryption-key")
    else:
        # With HTTP + auto-encryption: Don't set any encryption headers
        # AIStor will encrypt automatically via MINIO_KMS_AUTO_ENCRYPTION=on
        # Setting headers would trigger AWS SDK HTTPS enforcement
        pass  # No encryption headers - let AIStor handle it
else:
    # Explicitly disable ALL encryption headers in S3A
    # This ensures AWS SDK doesn't detect encryption and enforce HTTPS
    # With MINIO_KMS_AUTO_ENCRYPTION=on, AIStor will handle encryption automatically
    spark_builder \
        .config("spark.hadoop.fs.s3a.server-side-encryption-algorithm", "") \
        .config("spark.hadoop.fs.s3a.server-side-encryption.key", "") \
        .config("spark.hadoop.fs.s3a.server-side-encryption.key.md5", "")

spark = spark_builder.getOrCreate()

# Note: Protocol and encryption configuration
# HTTP via Sidekick architecture (default):
# - Spark S3A → Sidekick: HTTP (no SSL between Spark and Sidekick)
# - Sidekick → AIStor: HTTPS (TLS encrypted, CA verified)
# - AIStor → MinKMS: HTTPS/mTLS (encryption key management - if enabled)
# - Backend security maintained via Sidekick proxy
#
# Direct HTTPS architecture (when using --direct):
# - Spark S3A → AIStor: HTTPS (TLS encrypted, custom CA certificate trusted via Java keystore)
# - AIStor → MinKMS: HTTPS/mTLS (encryption key management - if enabled)
# - CA certificate is pre-installed in Java trust store (see Dockerfile.spark)
# - Direct connection without proxy layer
# - ⚠️  May hang due to certificate KeyUsage issue

if not args.quiet:
    print(f"✅ Spark session created with MinIO AIStor S3!")
    print(f"   Protocol: {protocol}")
    print(f"   Endpoint: {endpoint}")
    if args.direct:
        print("⚠️  NOTE: Direct HTTPS may hang due to certificate KeyUsage issue")
        print("   Certificate missing 'Digital Signature' in KeyUsage extension")
        print("   Consider using HTTP via Sidekick (default) instead")
    if args.sse_kms:
        if args.direct:
            print("🔒 SSE-KMS encryption: Client-side headers enabled (HTTPS required)")
        else:
            print("🔒 SSE-KMS encryption: AIStor auto-encryption enabled (no client headers)")
            print("   AIStor will encrypt automatically via MINIO_KMS_AUTO_ENCRYPTION")
            print("   Spark sends no encryption headers to avoid HTTPS enforcement")
    else:
        print("🔓 Encryption: AIStor auto-encryption enabled (no client headers)")
        print("   AIStor will encrypt automatically via MINIO_KMS_AUTO_ENCRYPTION")

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
