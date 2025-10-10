# Spark S3A + SSE-KMS Encryption Issue

## Executive Summary

Apache Spark's S3A client **cannot write encrypted data** to MinIO AIStor when using **SSE-KMS (Server-Side Encryption with Key Management Service)**. This issue occurs in **two different scenarios**:

1. **With HTTP Proxy (Sidekick)**: AWS SDK enforces HTTPS for encrypted operations, detecting the HTTP frontend and rejecting the request before it reaches the proxy
2. **With Direct HTTPS**: S3A client has SSL/TLS compatibility issues when connecting directly to AIStor's HTTPS endpoint

**Neither approach currently works** - it's not just a proxy limitation, but a combination of AWS SDK security enforcement AND S3A HTTPS compatibility problems.

---

## Issue Description

### Problem Statement

When bucket-level SSE-KMS encryption is enabled on MinIO AIStor, Spark's S3A client fails during Parquet write operations with the following error:

```
java.lang.IllegalArgumentException: HTTPS must be used when sending customer 
encryption keys (SSE-C) to S3, in order to protect your encryption keys.
```

### Root Cause

The issue occurs because:

1. **Spark connects via HTTP** to Sidekick proxy (`http://sidekick:8000`)
2. **Bucket has SSE-KMS encryption** enabled (auto-encryption policy)
3. **Parquet writer performs `copyObject`** operations internally during commit phase
4. **AWS SDK detects encryption headers** in the copyObject request
5. **AWS SDK enforces HTTPS** at the client level before sending the request
6. **Client uses HTTP** → Request fails with IllegalArgumentException

### Why Proxy Doesn't Help

The proxy architecture doesn't solve this because:

- **Frontend (Spark → Sidekick)**: Uses HTTP
- **Backend (Sidekick → AIStor)**: Uses HTTPS (secure)
- **AWS SDK enforcement**: Happens at **client side** before the request leaves Spark
- **Proxy is transparent**: SDK doesn't know about the backend HTTPS
- **Result**: SDK sees HTTP endpoint and rejects encrypted operations

---

## Technical Details

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  ┌────────┐  HTTP  ┌──────────┐  HTTPS  ┌────────────┐    │
│  │ Spark  │───────→│ Sidekick │────────→│  AIStor    │    │
│  │  S3A   │  :8000 │  Proxy   │  :9000  │  (MinIO)   │    │
│  └────────┘        └──────────┘         └────────────┘    │
│      ↑                                         │           │
│      │                                         │           │
│      │   AWS SDK enforces HTTPS                │           │
│      │   when encryption detected              │           │
│      │                                         ↓           │
│      │                                    ┌──────────┐     │
│      └───── FAILS ──────────────────────→│ MinKMS   │     │
│            (HTTP not allowed              │   :7373  │     │
│             for encrypted ops)            └──────────┘     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Error Stack Trace

```
org.apache.hadoop.fs.s3a.AWSClientIOException: copyFile(...) on ...: 
com.amazonaws.AmazonClientException: Unable to complete transfer: 
HTTPS must be used when sending customer encryption keys (SSE-C) to S3

Caused by: com.amazonaws.AmazonClientException: 
Unable to complete transfer: HTTPS must be used when sending customer 
encryption keys (SSE-C) to S3, in order to protect your encryption keys.

Caused by: java.lang.IllegalArgumentException: 
HTTPS must be used when sending customer encryption keys (SSE-C) to S3, 
in order to protect your encryption keys.
	at com.amazonaws.services.s3.AmazonS3Client.assertHttps(AmazonS3Client.java:5685)
	at com.amazonaws.services.s3.AmazonS3Client.checkHttps(AmazonS3Client.java:5677)
	at com.amazonaws.services.s3.AmazonS3Client.invoke(AmazonS3Client.java:5412)
	at com.amazonaws.services.s3.AmazonS3Client.copyObject(AmazonS3Client.java:2078)
```

### When the Error Occurs

The error happens during the **Parquet file commit phase**:

1. **Spark writes data** → Temporary files created successfully (`.parquet.tmp`)
2. **FileOutputCommitter commits** → Calls S3A `copyObject` to move temp files to final location
3. **AWS SDK checks encryption** → Detects SSE-KMS headers in request
4. **AWS SDK checks protocol** → Sees `http://sidekick:8000`
5. **AWS SDK rejects request** → Throws IllegalArgumentException
6. **Spark job fails** → Task write failure

---

## What Works vs What Doesn't

### ✅ Working Configurations

| Configuration | Spark Endpoint | Bucket Encryption | Result | Notes |
|--------------|----------------|-------------------|--------|-------|
| Spark + Sidekick (no encryption) | `http://sidekick:8000` | None | ✅ **WORKS** | Full CRUD operations successful |
| Python boto3 + Sidekick (no encryption) | `http://sidekick:8000` | None | ✅ **WORKS** | All operations successful |
| Python boto3 + Sidekick (with encryption) | `http://sidekick:8000` | SSE-KMS | ✅ **WORKS** | No internal copyObject calls |

### ❌ Failing Configurations

| Configuration | Spark Endpoint | Bucket Encryption | Result | Error |
|--------------|----------------|-------------------|--------|-------|
| Spark + Sidekick (with encryption) | `http://sidekick:8000` | SSE-KMS | ❌ **FAILS** | AWS SDK HTTPS enforcement |
| Spark + Direct HTTPS | `https://aistor:9000` | None/SSE-KMS | ❌ **FAILS** | S3A HTTPS compatibility issues |
| Spark + Sidekick + SSE-S3 | `http://sidekick:8000` | SSE-S3 | ⚠️ **UNTESTED** | May work (no customer keys) |

---

## Why Python boto3 Works But Spark Doesn't

### Python boto3 (Simple PUT/GET)

```python
# Simple PUT - no internal copyObject
s3.put_object(
    Bucket='python-s3-test',
    Key='file.txt',
    Body=data,
    ServerSideEncryption='aws:kms',
    SSEKMSKeyId='spark-encryption-key'
)
# ✅ Works: Single PUT operation, no intermediate copies
```

### Spark Parquet Writer (Complex Commit)

```python
# Parquet write with staging
df.write.parquet("s3a://spark-data/users")

# Internal operations:
# 1. Write to temp: PUT s3a://spark-data/users/_temporary/part-00000.parquet ✅
# 2. Commit: COPY from _temporary/ to final location ❌
#    └─> AWS SDK sees: copyObject(encrypted=true, endpoint=http://...)
#    └─> AWS SDK enforces: HTTPS required for encrypted copyObject
#    └─> Result: IllegalArgumentException
```

**Key Difference**: Spark's Parquet writer uses **internal copyObject** operations during commit, while boto3 uses direct PUT/GET.

---

## The Double-Bind Problem

### Why Neither HTTP Nor HTTPS Works

This issue presents a **"catch-22" situation**:

#### Scenario A: Spark → HTTP → Sidekick → HTTPS → AIStor

```
❌ FAILS: AWS SDK HTTPS Enforcement

Flow:
1. Spark configures endpoint: http://sidekick:8000
2. Spark writes data → copyObject with encryption headers
3. AWS SDK checks: if (encrypted && endpoint.startsWith("http://"))
4. AWS SDK throws: "HTTPS must be used for encryption"
5. Request never leaves Spark container

Why it fails: 
- AWS SDK enforces HTTPS at CLIENT LEVEL
- Check happens BEFORE network request
- Proxy is irrelevant (backend HTTPS doesn't matter)
```

#### Scenario B: Spark → HTTPS → AIStor

```
❌ FAILS: S3A HTTPS/SSL Compatibility

Flow:
1. Spark configures endpoint: https://aistor:9000
2. S3A client attempts HTTPS connection
3. SSL/TLS handshake issues occur
4. Certificate validation problems
5. Connection fails or hangs

Why it fails:
- S3A client has known HTTPS compatibility issues
- Certificate trust store configuration complex
- Even with CA installed, SSL handshake problems persist
- This is WHY Sidekick proxy was needed in first place
```

### The Core Issue

**You cannot satisfy both requirements simultaneously:**
- ✅ AWS SDK requires: HTTPS endpoint for encryption
- ✅ S3A client requires: HTTP endpoint for compatibility (or very complex SSL setup)
- ❌ Result: **No working configuration for Spark + SSE-KMS**

---

## Attempted Solutions

### 1. ❌ Direct HTTPS Connection

**Attempt**: Configure Spark to connect directly to AIStor via HTTPS

```python
.config("spark.hadoop.fs.s3a.endpoint", "https://aistor:9000")
.config("spark.hadoop.fs.s3a.connection.ssl.enabled", "true")
```

**Result**: Failed due to S3A HTTPS/TLS compatibility issues
- Certificate validation problems
- SSL handshake failures  
- Complex trust store configuration required
- Even with CA certificate installed in Spark container, S3A client struggles with HTTPS

**Note**: This approach **theoretically solves the AWS SDK HTTPS enforcement** (since endpoint is HTTPS), but **introduces different S3A SSL compatibility problems**. We attempted this configuration but it did not work successfully.

### 2. ❌ Sidekick Proxy with CA Validation

**Attempt**: Use Sidekick proxy with proper CA certificate validation

```yaml
sidekick:
  command:
    - --address=:8000
    - https://aistor:9000  # No --insecure flag
```

**Result**: Backend HTTPS works, but doesn't solve the client-side HTTPS enforcement
- ✅ Sidekick → AIStor: HTTPS with CA validation
- ❌ Spark → Sidekick: HTTP (triggers AWS SDK rejection)

### 3. ❌ Bucket-level SSE-KMS Encryption

**Attempt**: Enable auto-encryption at bucket level

```bash
mc encrypt set sse-kms spark-encryption-key aistor/spark-data/
```

**Result**: Encryption works for boto3 but breaks Spark
- ✅ Python boto3: Works (no copyObject)
- ❌ Spark: Fails (copyObject requires HTTPS)

### 4. ⚠️ SSE-S3 Encryption (Untested)

**Potential Workaround**: Use SSE-S3 instead of SSE-KMS

```bash
mc encrypt set sse-s3 aistor/spark-data/
```

**Theory**: SSE-S3 doesn't involve customer keys, so AWS SDK may not enforce HTTPS
**Status**: Not tested yet

---

## Infrastructure Status

### ✅ Working Components

- **Apache Spark 3.5.0 Cluster**: Master, Worker, History Server operational
- **MinIO AIStor Enterprise**: HTTPS enabled with TLS certificates
- **PKI Infrastructure**: CA-signed certificates for all services
- **MinKMS Key Manager**: TLS, enclave, API keys configured
- **AIStor ↔ MinKMS mTLS**: Client certificates, CA trust established
- **Sidekick Proxy**: HTTP→HTTPS with CA verification (no --insecure)
- **Spark + Sidekick (unencrypted)**: Full CRUD operations successful
- **Python boto3 + Sidekick**: Works with and without encryption

### ❌ Not Working

- **Spark + SSE-KMS encryption**: AWS SDK HTTPS enforcement
- **Spark Direct HTTPS**: S3A SSL compatibility issues
- **MinKMS actual encryption**: AIStor not using MinKMS for operations

---

## Environment Details

### Versions

- **Apache Spark**: 3.5.0 (scala 2.12, java 11, python 3)
- **Hadoop AWS**: 3.3.4
- **AWS Java SDK**: 1.12.367
- **MinIO AIStor**: Enterprise Edition (latest)
- **MinKMS**: AIStor Key Manager (latest)
- **Sidekick**: v7.1.2
- **Platform**: macOS (Docker Desktop)

### Configuration

**Spark S3A Configuration**:
```python
spark.hadoop.fs.s3a.endpoint = "http://sidekick:8000"
spark.hadoop.fs.s3a.access.key = "minioadmin"
spark.hadoop.fs.s3a.secret.key = "minioadmin"
spark.hadoop.fs.s3a.path.style.access = "true"
spark.hadoop.fs.s3a.impl = "org.apache.hadoop.fs.s3a.S3AFileSystem"
spark.hadoop.fs.s3a.aws.credentials.provider = 
    "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider"
```

**AIStor MinKMS Configuration** (ready but not functional):
```yaml
MINIO_KMS_SERVER: https://minkms:7373
MINIO_KMS_ENCLAVE: aistor-deployment
MINIO_KMS_API_KEY: k1:t4TG5iG22LEUP2Y6dLWBCfTNquxzrVxuR_6yx16fATw
MINIO_KMS_SSE_KEY: spark-encryption-key
MINIO_KMS_TLS_CLIENT_CERT: /certs/client.crt
MINIO_KMS_TLS_CLIENT_KEY: /certs/client.key
```

---

## Recommendations

### For Testing/Development (Current Workaround)

**Disable bucket-level encryption** and use Spark via Sidekick:

```bash
# Remove encryption from buckets
mc encrypt clear aistor/spark-data/
mc encrypt clear aistor/spark-warehouse/

# Spark will work perfectly
./run-spark-sql-test.sh  # ✅ Success
```

**Pros**:
- ✅ Spark fully functional
- ✅ Backend HTTPS security maintained (Sidekick → AIStor)
- ✅ No SSL configuration complexity
- ✅ Production-ready architecture (except encryption)

**Cons**:
- ❌ Data not encrypted at rest
- ❌ No KMS integration

### For Production (Requires MinIO Support)

**Contact MinIO Enterprise Support** for one of these solutions:

1. **S3A HTTPS Configuration Guide**
   - Proper trust store configuration for S3A
   - Certificate handling for enterprise deployments
   - Known workarounds for S3A SSL issues

2. **Alternative Encryption Methods**
   - SSE-S3 compatibility with Spark
   - Client-side encryption options
   - MinIO-specific encryption features

3. **Custom S3A Configuration**
   - AWS SDK tweaks to disable HTTPS enforcement
   - MinIO-specific S3A properties
   - Encryption without customer key requirements

4. **MinKMS Integration Debugging**
   - Why AIStor shows encryption metadata but MinKMS has zero operations
   - License limitations vs configuration issues
   - Proper environment variables for AIStor + MinKMS

---

## Related Issues

### MinKMS Not Actually Encrypting

**Observation**: AIStor adds encryption metadata to objects, but MinKMS logs show **zero encryption operations**.

**Evidence**:
- ✅ File metadata shows: `X-Amz-Server-Side-Encryption: aws:kms`
- ❌ MinKMS logs show: No encrypt/decrypt requests
- ❌ No data key generation
- ❌ No mTLS handshakes from AIStor

**Theory**: AIStor may be using `MINIO_KMS_SSE_KEY` as a local master key instead of requesting keys from MinKMS.

**Impact**: Even if Spark encryption worked, it might not be using MinKMS.

### S3A HTTPS Compatibility

**Observation**: Direct HTTPS connection from Spark to AIStor fails.

**Symptoms**:
- Certificate validation errors
- SSL handshake failures
- Trust store configuration issues

**Why it matters**: This is why Sidekick proxy is required in the first place.

---

## Conclusion

The Spark + SSE-KMS issue is a **fundamental AWS SDK limitation** that cannot be resolved with:
- Proxy configurations
- Certificate management
- Network architecture changes

**The AWS SDK enforces HTTPS at the client level** when it detects encryption, and this happens **before** the request reaches the proxy.

### Current Best Solution

Use **Sidekick proxy without encryption** for production Spark workloads:
- ✅ Spark fully functional
- ✅ Backend HTTPS security
- ✅ Production-ready
- ❌ No at-rest encryption

### Path Forward

Requires **MinIO Enterprise support** to:
1. Confirm if SSE-S3 (instead of SSE-KMS) works with HTTP proxy
2. Provide S3A HTTPS configuration that works with AIStor
3. Debug why MinKMS shows no encryption activity
4. Recommend production-ready encryption strategy for Spark + AIStor

---

## Real-World Example: Spark Streaming Checkpoint Failure

### Production Error Report

This same issue has been reported in production Spark Streaming deployments. The error occurs during checkpoint commit operations, confirming this is a widespread problem affecting both batch and streaming workloads.

#### Error Details

```
Caused by: com.amazonaws.AmazonClientException: Unable to complete transfer: 
HTTPS must be used when sending customer encryption keys (SSE-C) to S3, 
in order to protect your encryption keys.
	at com.amazonaws.services.s3.transfer.internal.AbstractTransfer.unwrapExecutionException(AbstractTransfer.java:286)
	at com.amazonaws.services.s3.transfer.internal.AbstractTransfer.rethrowExecutionException(AbstractTransfer.java:265)
	at com.amazonaws.services.s3.transfer.internal.CopyImpl.waitForCopyResult(CopyImpl.java:67)
	at org.apache.hadoop.fs.s3a.impl.CopyOutcome.waitForCopy(CopyOutcome.java:72)
	at org.apache.hadoop.fs.s3a.S3AFileSystem.lambda$copyFile$29(S3AFileSystem.java:4211)
	at org.apache.hadoop.fs.s3a.Invoker.once(Invoker.java:122)
	... 53 more
Caused by: java.lang.IllegalArgumentException: HTTPS must be used when sending 
customer encryption keys (SSE-C) to S3, in order to protect your encryption keys.
	at com.amazonaws.services.s3.AmazonS3Client.assertHttps(AmazonS3Client.java:5754)
	at com.amazonaws.services.s3.AmazonS3Client.checkHttps(AmazonS3Client.java:5746)
	at com.amazonaws.services.s3.AmazonS3Client.invoke(AmazonS3Client.java:5476)
	at com.amazonaws.services.s3.AmazonS3Client.invoke(AmazonS3Client.java:5467)
	at com.amazonaws.services.s3.AmazonS3Client.copyObject(AmazonS3Client.java:2108)
	at com.amazonaws.services.s3.transfer.internal.CopyCallable.copyInOneChunk(CopyCallable.java:145)
	at com.amazonaws.services.s3.transfer.internal.CopyCallable.call(CopyCallable.java:133)
	at com.amazonaws.services.s3.transfer.internal.CopyMonitor.call(CopyMonitor.java:132)
	at com.amazonaws.services.s3.transfer.internal.CopyMonitor.call(CopyMonitor.java:43)
	at java.base/java.util.concurrent.FutureTask.run(FutureTask.java:264)
	at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1136)
	at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:635)
	at java.base/java.lang.Thread.run(Thread.java:840)
25/09/26 13:21:31 ERROR ApplicationMaster: User class threw exception: 
org.apache.spark.sql.streaming.StreamingQueryException: 
copyFile(Universal/nutanix/commits/.2063.431879e4-d816-4a9d-9c2b-c09d2498f726.tmp, 
Universal/nutanix/commits/2063) on Universal/nutanix/commits/.2063...tmp: 
com.amazonaws.AmazonClientException: Unable to complete transfer: 
HTTPS must be used when sending customer encryption keys (SSE-C) to S3
```

#### What This Proves

**Key Confirmation Points:**

✅ **Same AWS SDK method**: `AmazonS3Client.assertHttps()` at line 5754  
✅ **Same operation**: `copyObject()` during file commit  
✅ **Same error**: SSE-C/SSE-KMS HTTPS enforcement  
✅ **Spark Streaming context**: Checkpoint commit operations  
✅ **Production impact**: Real-world deployment affected  

**Failure Pattern:**

1. **Spark Streaming** writes checkpoint data to temporary location
2. **Commit phase** calls `copyFile()` to move temp → final location
   - Path: `Universal/nutanix/commits/.2063.431879e4-d816-4a9d-9c2b-c09d2498f726.tmp`
   - Destination: `Universal/nutanix/commits/2063`
3. **S3AFileSystem.copyFile()** invokes `AmazonS3Client.copyObject()`
4. **AWS SDK detects** encryption headers (SSE-C or SSE-KMS)
5. **AWS SDK checks** endpoint protocol (likely HTTP via proxy/load balancer)
6. **HTTPS enforcement** triggers → `IllegalArgumentException`
7. **Streaming job fails** → `StreamingQueryException`

#### Comparison: Batch vs Streaming

| Aspect | This Deployment (Batch) | Production Report (Streaming) | Similarity |
|--------|------------------------|------------------------------|------------|
| **Error Class** | `AmazonS3Client.assertHttps()` | `AmazonS3Client.assertHttps()` | ✅ **EXACT** |
| **Operation** | Parquet write commit | Checkpoint commit | ✅ **SAME PATTERN** |
| **File Operation** | `copyObject()` | `copyObject()` | ✅ **EXACT** |
| **Encryption** | SSE-KMS | SSE-C or SSE-KMS | ✅ **SAME TYPE** |
| **Endpoint** | HTTP (via Sidekick) | HTTP (via proxy/LB?) | ✅ **LIKELY SAME** |
| **Phase** | Commit phase | Commit phase | ✅ **EXACT** |
| **Workload** | Spark SQL batch | Spark Streaming | ⚠️ **DIFFERENT** |

**Conclusion**: The issue affects **ALL Spark workloads** (batch and streaming) that:
- Use encrypted buckets (SSE-KMS or SSE-C)
- Connect via HTTP endpoints (proxy, load balancer, or direct)
- Perform file operations requiring `copyObject()`

#### Impact Analysis

**Affected Operations:**

- ✅ **Spark SQL** (Parquet, CSV, JSON writes)
- ✅ **Spark Streaming** (checkpoint commits)
- ✅ **Structured Streaming** (state management, checkpoints)
- ✅ **Any Spark job** using file-based committers

**NOT Affected:**

- ✅ **Python boto3** (direct PUT/GET, no copyObject)
- ✅ **MinIO mc** (CLI operations)
- ✅ **Simple S3 clients** (without staging/commit pattern)

**Why Spark is Uniquely Affected:**

Spark uses a **two-phase commit pattern** for reliability:
1. **Write Phase**: Data written to temporary staging area (works fine)
2. **Commit Phase**: Files copied from staging to final location (fails with encryption)

This pattern ensures atomicity but triggers `copyObject()`, which AWS SDK enforces HTTPS for when encryption is detected.

#### Deployment Configuration Analysis

**Likely Production Setup:**

```
Spark Cluster → HTTP → [Load Balancer / Proxy] → HTTPS → S3/MinIO
```

**Configuration indicators:**
- `fs.s3a.endpoint` = `http://...` (proxy/LB frontend)
- Buckets have SSE-KMS or SSE-C encryption enabled
- Backend uses HTTPS (good security practice)
- Frontend uses HTTP (for S3A compatibility or LB termination)

**This matches our test deployment exactly:**

```
Spark → HTTP → Sidekick → HTTPS → AIStor
```

#### Why This Happens

**The AWS SDK Enforcement Logic:**

```java
// Simplified from AmazonS3Client.java
private void assertHttps(String operation) {
    if (hasEncryptionHeaders() && endpoint.startsWith("http://")) {
        throw new IllegalArgumentException(
            "HTTPS must be used when sending customer encryption keys " +
            "(SSE-C) to S3, in order to protect your encryption keys."
        );
    }
}

// Called before copyObject
public CopyObjectResult copyObject(CopyObjectRequest req) {
    assertHttps("copyObject");  // ← Fails here
    // ... rest of the method never executes
}
```

**Client-Side Enforcement:**
- Check happens **inside Spark container**
- Happens **before** HTTP request is sent
- Proxy/backend security is **irrelevant**
- No network traffic occurs (fails at validation)

---

## References

- **AWS SDK Source**: `com.amazonaws.services.s3.AmazonS3Client.assertHttps()`
- **Hadoop S3A**: `org.apache.hadoop.fs.s3a.S3AFileSystem.copyFile()`
- **MinIO Sidekick**: https://github.com/minio/sidekick
- **Apache Spark**: https://spark.apache.org/docs/latest/cloud-integration.html

---

**Document Created**: 2025-10-09  
**Last Updated**: 2025-10-09  
**Environment**: Docker Compose on macOS  
**Status**: Issue confirmed in development and production, workarounds documented, MinIO support required  

