# HTTPS Connectivity Test Scripts

This directory contains several test scripts to verify HTTPS connectivity from Spark to AIStor with proper SSL/TLS certificate validation.

## Test Scripts Overview

### 1. `test_aistor_https.py` - Python SSL/TLS Test Suite
**Purpose**: Comprehensive Python-based tests for HTTPS connectivity

**What it tests**:
- DNS resolution for aistor hostname
- TCP connection to port 9000
- SSL/TLS handshake and certificate validation
- HTTPS endpoint accessibility
- S3 API with boto3 (if available)
- Java truststore verification

**Run with**:
```bash
./run-https-test.sh
# or directly:
docker exec spark-master python3 /opt/spark/scripts/test_aistor_https.py
```

**Exit codes**:
- 0: All tests passed
- 1: Some tests failed
- 2: No tests passed

---

### 2. `test_aistor_curl.sh` - Shell/Curl Test Suite
**Purpose**: Simple curl and shell-based tests for HTTPS connectivity and S3 API

**What it tests**:
- DNS resolution
- TCP connectivity
- HTTPS connection with CA verification
- S3 REST API endpoint
- Certificate chain verification
- CA certificate in system trust store
- CA certificate in Java keystore
- S3 API ListBuckets operation
- Bucket accessibility
- MinIO console separation

**Run with**:
```bash
docker exec spark-master bash /opt/spark/scripts/test_aistor_curl.sh
```

**Features**:
- No Python dependencies required
- Uses standard Unix tools (curl, openssl, keytool)
- Detailed certificate information
- AWS CLI integration (if available)

---

### 3. `test_s3_api.py` - S3 API Operations Test
**Purpose**: Test actual S3 operations using boto3

**What it tests**:
- S3 client creation with SSL verification
- ListBuckets operation
- Bucket existence check
- ListObjects operation
- PUT/GET/DELETE object operations
- Multipart upload capability

**Run with**:
```bash
docker exec spark-master python3 /opt/spark/scripts/test_s3_api.py
```

**Requirements**:
- boto3 library (optional, will skip if not available)
- Install with: `pip install boto3`

**Exit codes**:
- 0: All tests passed
- 1: Tests failed
- 2: boto3 not installed (skipped)

---

### 4. `sql_test.py` - Spark SQL with S3A over HTTPS
**Purpose**: End-to-end Spark SQL test with direct HTTPS connection to AIStor

**What it tests**:
- Spark S3A connection over HTTPS
- Certificate validation through Java truststore
- Data write to S3
- Data read from S3
- SQL queries on S3 data

**Run with**:
```bash
./run-spark-sql-test.sh [options]

Options:
  --select-only   Skip write operations, only read and query
  --quiet, -q     Reduce output verbosity
```

**Configuration**:
- Endpoint: `https://aistor:9000`
- SSL enabled with certificate verification
- Uses Java truststore for CA validation

---

## Quick Test Commands

### Test HTTPS Connectivity (Python)
```bash
./run-https-test.sh
```

### Test HTTPS Connectivity (Shell/Curl)
```bash
docker exec spark-master bash /opt/spark/scripts/test_aistor_curl.sh
```

### Test S3 API Operations
```bash
docker exec spark-master python3 /opt/spark/scripts/test_s3_api.py
```

### Test Spark SQL with HTTPS
```bash
# Full test (write + read + query)
./run-spark-sql-test.sh

# Quiet mode
./run-spark-sql-test.sh --quiet

# Read-only mode
./run-spark-sql-test.sh --select-only --quiet
```

---

## Expected Results

### All Tests Passing ✅
When all tests pass, you should see:
- DNS resolution working
- TCP connection successful
- SSL/TLS handshake with valid certificate
- HTTPS endpoints accessible
- CA certificate in both system and Java truststore
- S3 API responding correctly
- Spark S3A operations working over HTTPS

### Common Issues

#### Certificate Validation Fails ❌
**Symptoms**: SSL/TLS errors, certificate verification failures

**Solutions**:
1. Verify CA certificate is in system trust store:
   ```bash
   docker exec spark-master ls -la /usr/local/share/ca-certificates/minio-ca.crt
   ```

2. Verify CA certificate is in Java truststore:
   ```bash
   docker exec spark-master bash -c 'keytool -list -keystore ${JAVA_HOME}/lib/security/cacerts -storepass changeit -alias minio-ca'
   ```

3. Rebuild Spark container if certificates were updated:
   ```bash
   docker-compose build spark-master
   docker-compose up -d spark-master
   ```

#### Connection Refused ❌
**Symptoms**: Cannot connect to aistor:9000

**Solutions**:
1. Verify AIStor container is running:
   ```bash
   docker ps | grep aistor
   ```

2. Check AIStor health:
   ```bash
   curl -k https://localhost:9000/minio/health/live
   ```

3. Check Docker network connectivity:
   ```bash
   docker exec spark-master ping -c 3 aistor
   ```

---

## Architecture

### Direct HTTPS Connection (Current)
```
Spark S3A → HTTPS (port 9000) → AIStor → HTTPS/mTLS → MinKMS
         └── SSL/TLS with CA verification
```

**Benefits**:
- End-to-end encryption
- Certificate validation at every hop
- No HTTP plaintext exposure
- Production-ready security

### Certificate Trust Chain
```
MinIO Root CA (custom CA certificate)
  └── AIStor Server Certificate (CN=aistor)
      ├── Trusted by: System CA store (/usr/local/share/ca-certificates/)
      └── Trusted by: Java keystore (${JAVA_HOME}/lib/security/cacerts)
```

---

## Troubleshooting

### Enable Verbose Logging

For Spark S3A debugging:
```bash
docker exec spark-master bash -c 'export SPARK_LOG_LEVEL=DEBUG && /opt/spark/bin/spark-submit ...'
```

For curl debugging:
```bash
curl -v https://aistor:9000/
```

For OpenSSL debugging:
```bash
openssl s_client -connect aistor:9000 -servername aistor -showcerts
```

### Check Certificate Expiry
```bash
echo | openssl s_client -connect aistor:9000 -servername aistor 2>/dev/null | openssl x509 -noout -dates
```

---

## Additional Resources

- **Spark S3A Documentation**: Configuration options for SSL/TLS
- **MinIO TLS Guide**: Certificate setup and configuration
- **Java Keytool**: Managing Java truststore certificates
- **AWS SDK**: S3 client SSL configuration

---

## Summary

These test scripts provide comprehensive validation of:
1. ✅ Network connectivity (DNS, TCP)
2. ✅ SSL/TLS certificate validation
3. ✅ CA certificate trust (system & Java)
4. ✅ S3 API functionality
5. ✅ Spark S3A operations over HTTPS

If all tests pass, your Spark cluster can securely connect to AIStor over HTTPS with proper certificate validation! 🎉



