# Spark S3A + MinIO Sidekick: HTTP vs HTTPS Issue Lab

## Problem Description

This lab demonstrates a critical issue where **Apache Spark S3A works correctly with HTTPS endpoints** (both Sidekick HTTPS frontend and direct HTTPS to AIStor), but **fails when using Sidekick HTTP frontend**.

### Issue Summary

- ✅ **Works**: Spark → HTTPS → Sidekick HTTPS → HTTPS → AIStor
- ✅ **Works**: Spark → HTTPS → AIStor (direct)
- ❌ **Fails**: Spark → HTTP → Sidekick HTTP → HTTPS → AIStor

### Root Cause Analysis (RCA)

**Root Cause**: Protocol mismatch between encryption requirements and connection configuration.

#### The Problem Chain:

1. **Spark S3A is configured to use encryption** (SSE-C or SSE-KMS) when writing to MinIO AIStor
2. **Encryption requires HTTPS protocol** - AWS SDK enforces HTTPS to protect encryption keys during transit
3. **Sidekick HTTP frontend provides HTTP** (not HTTPS) connection
4. **AWS S3 client rejects the operation** - When Spark attempts to write/commit files, the AWS S3 client detects the HTTP connection and fails

#### Key Error Message:

```
java.lang.IllegalArgumentException: HTTPS must be used when sending 
customer encryption keys (SSE-C) to S3, in order to protect your encryption keys.
```

This error occurs at:
- `com.amazonaws.services.s3.AmazonS3Client.assertHttps()` - line 5685
- During file copy operations in the S3A filesystem
- Specifically during task commit phase when Spark tries to move temporary files to final location

#### Configuration Issue:

Even with `MINIO_KMS_AUTO_ENCRYPTION=on` enabled on AIStor, if Spark sends encryption headers (SSE-C or SSE-KMS), the AWS SDK enforces HTTPS. The HTTP Sidekick frontend cannot satisfy this requirement.

## Lab Purpose

This lab provides a reproducible environment to demonstrate:
1. How Spark S3A works correctly with HTTPS endpoints
2. How Spark S3A fails with HTTP endpoints when encryption is involved
3. The specific error conditions and AWS SDK behavior

## Architecture

```
┌─────────┐         ┌──────────────┐         ┌──────────────┐         ┌─────────┐
│  Spark  │────────▶│   Sidekick   │────────▶│   AIStor     │────────▶│  MinKMS │
│  S3A    │         │              │         │  (MinIO)     │         │         │
└─────────┘         └──────────────┘         └──────────────┘         └─────────┘

Working Configurations:
✅ Spark → HTTPS → Sidekick-HTTPS (port 8090) → HTTPS → AIStor
✅ Spark → HTTPS → AIStor (port 9000) direct

Failing Configuration:
❌ Spark → HTTP → Sidekick-HTTP (port 8091) → HTTPS → AIStor
```

## Quick Start

### Prerequisites

- Docker Desktop for Mac
- **MinIO Enterprise License**: A valid `minio.license` file must be present in the project root directory
  - This file is required for MinIO AIStor and MinKMS Enterprise features
  - The file is gitignored (see `.gitignore`) and should not be committed to version control
  - If you don't have a license, contact MinIO for Enterprise licensing
- Basic understanding of Spark, S3, and TLS/SSL

### 1. Generate Certificates

```bash
# Generate PKI certificates (MinIO, MinKMS, AIStor)
./docker/generate-certs.sh

# Generate Sidekick certificates (for HTTPS frontend)
./docker/generate-sidekick-certs.sh certs/sidekick "MinIO Sidekick CA" "sidekick.local"
```

### 2. Start Services

```bash
cd spark-setup
docker-compose up -d
```

Wait for services to be healthy:
```bash
docker-compose ps
```

Expected status:
- `aistor` - Up (healthy)
- `minkms` - Up
- `sidekick-https` - Up (port 8090)
- `sidekick-http` - Up (port 8091)
- `spark-master`, `spark-worker`, `spark-history` - Up

### 3. Reproduce the Issue

#### Test 1: HTTPS via Sidekick (✅ WORKS)

```bash
cd spark-setup
./run-spark-sql-test.sh --quiet
```

**Expected Result**: ✅ Success - Data written and read successfully (default uses HTTPS)

#### Test 2: Direct HTTPS to AIStor (✅ WORKS)

```bash
cd spark-setup
./run-spark-sql-test.sh --direct --quiet
```

**Expected Result**: ✅ Success - Data written and read successfully

#### Test 3: HTTP via Sidekick (❌ FAILS)

```bash
cd spark-setup
./run-spark-sql-test.sh --http --quiet
```

**Expected Result**: ❌ Failure - Exception with "HTTPS must be used when sending customer encryption keys"

## Test Script Options

The `run-spark-sql-test.sh` script supports:

```bash
./run-spark-sql-test.sh [options]

Options:
  --select-only   Only run SELECT queries on existing data (skip write operations)
  --quiet, -q     Reduce output verbosity (show only essential information)
  --direct        Use HTTPS directly to AIStor (https://aistor:9000) ✅ WORKS
  --http          Use HTTP via Sidekick HTTP frontend (http://sidekick-http:8091) ❌ FAILS
  (default)       Use HTTPS via Sidekick HTTPS frontend (https://sidekick:8090) ✅ WORKS
  --sse-kms       Enable SSE-KMS encryption using MinKMS (requires HTTPS endpoint)
```

## Error Details

When running with `--http` flag, you'll see:

```
java.lang.IllegalArgumentException: HTTPS must be used when sending 
customer encryption keys (SSE-C) to S3, in order to protect your encryption keys.
	at com.amazonaws.services.s3.AmazonS3Client.assertHttps(AmazonS3Client.java:5685)
	at com.amazonaws.services.s3.AmazonS3Client.copyObject(AmazonS3Client.java:1800)
	...
```

This occurs during:
- Task commit phase
- File copy operations in S3A
- Moving temporary files to final location

## Why HTTPS Works But HTTP Doesn't

### Working: HTTPS Endpoints

1. **Spark → Sidekick HTTPS**:
   - Spark connects via HTTPS to `https://sidekick:8090`
   - Certificate validation passes (Sidekick CA in Java truststore)
   - AWS SDK allows encryption headers over HTTPS
   - ✅ Success

2. **Spark → AIStor Direct HTTPS**:
   - Spark connects via HTTPS to `https://aistor:9000`
   - Certificate validation passes (MinIO CA in Java truststore)
   - AWS SDK allows encryption headers over HTTPS
   - ✅ Success

### Failing: HTTP Endpoint

1. **Spark → Sidekick HTTP**:
   - Spark connects via HTTP to `http://sidekick-http:8091`
   - Connection succeeds (no SSL/TLS)
   - AWS SDK detects HTTP connection
   - **AWS SDK enforces HTTPS for encryption** → Rejects operation
   - ❌ Failure: `HTTPS must be used when sending customer encryption keys`

### AWS SDK Security Enforcement

The AWS SDK has built-in security checks:
- **SSE-C (Server-Side Encryption with Customer-provided keys)**: Requires HTTPS
- **SSE-KMS (Server-Side Encryption with Key Management Service)**: Requires HTTPS
- **Any encryption headers**: Triggers HTTPS requirement

This is enforced at `AmazonS3Client.assertHttps()` to protect encryption keys in transit.

## Solution

**Use HTTPS frontend** for Sidekick when Spark needs to send encryption headers:

1. **Option 1**: Use Sidekick HTTPS frontend (default)
   ```bash
   ./run-spark-sql-test.sh  # Default uses HTTPS via sidekick:8090
   ```

2. **Option 2**: Use direct HTTPS to AIStor
   ```bash
   ./run-spark-sql-test.sh --direct  # Uses HTTPS directly to aistor:9000
   ```

3. **Option 3**: Disable encryption headers in Spark (let AIStor handle auto-encryption)
   - Remove `--sse-kms` flag
   - Don't set `spark.hadoop.fs.s3a.server-side-encryption-algorithm`
   - AIStor will encrypt automatically via `MINIO_KMS_AUTO_ENCRYPTION=on`

## Services

### MinIO AIStor (Enterprise Object Storage)
- **Container**: `aistor`
- **Ports**: 
  - 9000:9000 (S3 API - HTTPS)
  - 9001:9001 (Console - HTTP)
- **MinKMS**: Integrated for server-side encryption
- **Auto-Encryption**: Enabled via `MINIO_KMS_AUTO_ENCRYPTION=on`

### Sidekick HTTPS Frontend (✅ Works)
- **Container**: `sidekick-https`
- **Port**: 8090:8090 (HTTPS frontend)
- **Backend**: `https://aistor:9000` (HTTPS)
- **Use**: Default (no flag needed)

### Sidekick HTTP Frontend (❌ Fails with Encryption)
- **Container**: `sidekick-http`
- **Port**: 8091:8091 (HTTP frontend)
- **Backend**: `https://aistor:9000` (HTTPS)
- **Use**: `--http` flag (demonstrates the issue)

### Apache Spark Cluster
- **Containers**: `spark-master`, `spark-worker`, `spark-history`
- **Ports**:
  - 8080:8080 (Spark Master UI)
  - 7077:7077 (Spark Master)
  - 18080:18080 (Spark History Server)
- **S3A Configuration**: Points to Sidekick or AIStor based on flags

### MinKMS (Key Management Service)
- **Container**: `minkms`
- **Port**: 7373:7373 (HTTPS)
- **Purpose**: Key management for AIStor encryption

## Project Structure

```
spark-s3a-sse-kms-issue/
├── docker/                         # Docker build files
│   ├── Dockerfile.spark            # Spark cluster image with CA trust
│   ├── Dockerfile.aistor           # AIStor with CA trust + HTTPS
│   ├── Dockerfile.sidekick         # Sidekick proxy
│   ├── Dockerfile.python-s3-test    # Python S3 test client
│   ├── generate-certs.sh           # PKI certificate generation
│   └── generate-sidekick-certs.sh  # Sidekick ECDSA certificate generation
├── spark-setup/                    # Main Spark + AIStor + Sidekick setup
│   ├── docker-compose.yml          # Service orchestration
│   ├── run-spark-sql-test.sh       # Spark SQL test script
│   └── run-python-s3-test.sh       # Python S3 test script
├── certs/                          # Generated PKI certificates
│   ├── ca/                         # Root CA
│   ├── minkms/                     # MinKMS TLS certs
│   ├── aistor/                     # AIStor TLS + client certs
│   └── sidekick/                   # Sidekick HTTPS certs
├── scripts/                        # Test scripts
│   ├── sql_test.py                 # Spark SQL test (main test script)
│   └── s3_crud_test.py             # Python S3 CRUD test
├── minio.license                   # ⚠️ REQUIRED: MinIO Enterprise license file (gitignored)
│                                   # Must be obtained from MinIO and placed in project root
├── minkms/                         # MinKMS configuration
│   ├── config.yaml                 # TLS settings
│   └── minkms.env                  # HSM key
└── data/                           # Local Spark data
```

## Common Commands

### Service Management

```bash
cd spark-setup

# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Stop and remove all data
docker-compose down -v

# View logs
docker-compose logs -f minio
docker-compose logs -f sidekick-https
docker-compose logs -f sidekick-http
docker-compose logs spark-master

# Check service status
docker-compose ps
```

### Testing

```bash
cd spark-setup

# Test HTTPS (works - default)
./run-spark-sql-test.sh --quiet

# Test direct HTTPS (works)
./run-spark-sql-test.sh --direct --quiet

# Test HTTP (fails - demonstrates the issue)
./run-spark-sql-test.sh --http --quiet

# Read-only test (works with any endpoint)
./run-spark-sql-test.sh --select-only --quiet
```

### Access Web UIs

- **Spark Master**: http://localhost:8080
- **Spark History**: http://localhost:18080
- **AIStor Console**: http://localhost:9001 (minioadmin/minioadmin)
- **MinKMS API**: https://localhost:7373 (HTTPS only)

## Troubleshooting

### Issue: "HTTPS must be used when sending customer encryption keys"

**Cause**: Using HTTP endpoint with encryption headers.

**Solution**: 
- Use HTTPS endpoint (default, no flag needed)
- Or use direct HTTPS (`--direct`)
- Or disable encryption headers in Spark (let AIStor handle auto-encryption)

### Issue: Certificate validation fails

**Cause**: Certificate not in Java truststore.

**Solution**: 
- Ensure certificates are generated: `./docker/generate-certs.sh`
- Rebuild Spark image: `docker-compose build spark-master`
- Restart services: `docker-compose restart spark-master`

### Issue: Services not starting

**Cause**: Missing certificates or license.

**Solution**:
```bash
# Check certificates
ls -la certs/ca/ca.crt certs/aistor/server.crt certs/sidekick/ca.crt

# Check license file (REQUIRED)
ls -la minio.license

# If minio.license is missing:
# 1. Obtain MinIO Enterprise license from MinIO
# 2. Place the license file in the project root: minio.license
# 3. Restart services: docker-compose restart minio

# Regenerate certificates if needed
./docker/generate-certs.sh
./docker/generate-sidekick-certs.sh certs/sidekick "MinIO Sidekick CA" "sidekick.local"
```

### Issue: "License file not found" or AIStor/MinKMS fails to start

**Cause**: Missing `minio.license` file.

**Solution**:
1. Ensure `minio.license` file exists in the project root directory
2. Verify the file is readable: `cat minio.license | head -1` (should show JWT token)
3. Check Docker volume mount in `docker-compose.yml` points to the correct location
4. Restart the service: `docker-compose restart minio minkms`

## References

- [MinIO AIStor Documentation](https://docs.min.io/enterprise/aistor-object-store/)
- [MinIO Sidekick GitHub](https://github.com/minio/sidekick)
- [Apache Spark S3A Documentation](https://hadoop.apache.org/docs/stable/hadoop-aws/tools/hadoop-aws/index.html)
- [AWS SDK S3 Encryption Requirements](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingEncryption.html)

## Production Deployment

For production deployments using Sidekick as a Linux systemd service (not Docker), see:
- **[SIDEKICK_SYSTEMD_SETUP.md](SIDEKICK_SYSTEMD_SETUP.md)** - Complete guide for setting up Sidekick as a systemd service with HTTPS, including certificate generation and configuration

## Summary

This lab demonstrates that **Apache Spark S3A requires HTTPS when encryption headers are present**, even if the backend (AIStor) supports HTTPS. The AWS SDK enforces this security requirement to protect encryption keys in transit.

**Key Findings**:
- ✅ HTTPS endpoints (Sidekick HTTPS, direct AIStor HTTPS) work correctly
- ❌ HTTP endpoints fail when Spark sends encryption headers
- 🔒 AWS SDK enforces HTTPS for SSE-C and SSE-KMS operations
- 💡 Solution: Use HTTPS frontend or disable encryption headers in Spark

---

**Last Updated**: 2025-11-04  
**Purpose**: Lab to reproduce and demonstrate Spark S3A HTTP vs HTTPS encryption issue  
**Status**: Issue reproducible ✅
