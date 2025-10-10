#!/usr/bin/env python3
from pyspark.sql import SparkSession

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

print("✅ Spark session created with MinIO AIStor S3!")

# Create test data
data = [(1, "Alice", 100), (2, "Bob", 200), (3, "Charlie", 150)]
df = spark.createDataFrame(data, ["id", "name", "amount"])

print("\nOriginal Data:")
df.show()

# Save to MinIO AIStor S3
print("\n💾 Saving to MinIO AIStor S3 (s3a://spark-data/users)...")
df.write.mode("overwrite").parquet("s3a://spark-data/users")
print("✅ Data saved to AIStor!")

# Read from MinIO AIStor S3
print("\n📥 Reading from MinIO AIStor S3...")
users = spark.read.parquet("s3a://spark-data/users")

print("\nData from MinIO:")
users.show()

# Register as SQL table
users.createOrReplaceTempView("users")

# Run SQL query
print("\n🔍 SQL Query: SELECT * FROM users WHERE amount > 100")
result = spark.sql("SELECT * FROM users WHERE amount > 100")
result.show()

# Save query results back to MinIO AIStor
print("\n💾 Saving query results to AIStor...")
result.write.mode("overwrite").parquet("s3a://spark-data/high_value_users")
print("✅ Results saved to s3a://spark-data/high_value_users")

print("\n" + "="*60)
print("✅ Success! Spark SQL with MinIO AIStor S3!")
print("="*60)
print("📊 AIStor Console: http://localhost:9001")
print("🔑 MinKMS available: https://localhost:7373 (standalone)")
print("Login: minioadmin / minioadmin")

spark.stop()
