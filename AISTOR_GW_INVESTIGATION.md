# AIStor-GW Investigation: Spark S3A Compatibility Issue

## Executive Summary

**AIStor-GW works perfectly with Python boto3** but is **incompatible with Apache Spark S3A** due to header stripping during request re-signing. The root cause is that AIStor-GW's V4 signer removes AWS SDK metadata headers (`Amz-Sdk-Retry`) that Spark S3A requires, causing `400 Bad Request` errors from AIStor.

---

## Investigation Results

### ✅ What Works

| Client | Via AIStor-GW | Encryption | Result |
|--------|--------------|------------|--------|
| **Python boto3** | ✅ Yes | SSE-KMS | ✅ **WORKS PERFECTLY** |
| **MinIO mc** | N/A | SSE-KMS | ✅ Works (direct) |
| **Apache Spark S3A** | ❌ No | None | ❌ **400 Bad Request** |

### ❌ What Doesn't Work

**Spark S3A → AIStor-GW → AIStor**: Fails with `400 Bad Request` due to header stripping

---

## Root Cause Analysis

### The Problem

AIStor-GW's request re-signing process **strips AWS SDK metadata headers** that Spark S3A client includes in requests:

**Incoming Request from Spark:**
```
Headers:
  ✅ Amz-Sdk-Retry: 0/0/500
  ✅ Amz-Sdk-Request: attempt=1;max=21
  ✅ Amz-Sdk-Invocation-Id: cd88cd71-7d21-2506-81e6-ee1a9ebdf23f
  ✅ X-Amz-Date: 20251009T200447Z
  ✅ X-Amz-Content-Sha256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
  ✅ Authorization: AWS4-HMAC-SHA256 Credential=minioadmin/20251009/...
```

**Outgoing Request (after aistor-gw re-signing):**
```
Headers:
  ❌ Amz-Sdk-Retry: MISSING!  ← Stripped during re-signing
  ✅ Amz-Sdk-Request: attempt=1;max=21
  ✅ Amz-Sdk-Invocation-Id: cd88cd71-7d21-2506-81e6-ee1a9ebdf23f
  ✅ X-Amz-Date: 20251009T200447Z (updated)
  ✅ X-Amz-Content-Sha256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
  ✅ Authorization: AWS4-HMAC-SHA256 Credential=minioadmin/20251009/... (re-signed)
```

**Result**: AIStor returns `400 Bad Request` due to malformed/incomplete headers

---

## Technical Details

### AIStor-GW Request Processing Flow

1. **Client sends request** with authentication headers
2. **AIStor-GW receives request** in `ServeHTTP()`
3. **Director function modifies request**:
   - Updates scheme/host (HTTP → HTTPS, aistor-gw → aistor)
   - Adds SSE-C headers (if configured)
   - Updates X-Amz-Date to current time
   - **RE-SIGNS request** using `signer.SignV4Trailer()`
4. **SignV4Trailer removes non-standard headers**
5. **Forwards modified request** to backend
6. **AIStor rejects** due to missing expected headers

### Why boto3 Works But Spark Doesn't

**boto3 requests:**
- Simple header set
- No `Amz-Sdk-Retry` header
- Standard S3 API headers only
- Re-signing doesn't break anything ✅

**Spark S3A requests:**
- Rich AWS SDK metadata headers
- `Amz-Sdk-Retry` header for retry logic
- Additional SDK-specific headers
- Re-signing strips critical headers ❌

---

## Code Changes Made

### Enhanced Logging in aistor-gw

Modified `/Users/vb140772/src/aistor-gw/pkg/proxy/proxy.go`:

1. **Added detailed incoming request logging**:
   ```go
   logger.Printf("╔═══ INCOMING REQUEST ═══════════════════════════════════")
   logger.Printf("║ Method: %s, Path: %s, RawQuery: %s", req.Method, req.URL.Path, req.URL.RawQuery)
   // Log ALL headers (filtered for auth/amz/host)
   for k, v := range req.Header {
       if strings.Contains(strings.ToLower(k), "auth") || 
          strings.Contains(strings.ToLower(k), "amz") || 
          strings.Contains(strings.ToLower(k), "host") {
           logger.Printf("║   %s: %s", k, strings.Join(v, ","))
       }
   }
   ```

2. **Fixed missing Host header issue**:
   ```go
   // Ensure Host header is set (critical for S3 signature verification)
   if host := req.Header.Get("Host"); host != "" {
       req.Header.Set("Host", host)
   } else {
       // If Host header is empty, set it to the backend host
       req.Header.Set("Host", minioURL.Host)
   }
   ```

3. **Added X-Amz-Date update**:
   ```go
   // Update X-Amz-Date to current time before re-signing
   currentTime := time.Now().UTC()
   req.Header.Set("X-Amz-Date", currentTime.Format("20060102T150405Z"))
   ```

4. **Added outgoing request and response logging**:
   ```go
   logger.Printf("╠═══ OUTGOING REQUEST (after re-signing) ═══════════════")
   // Log all final headers
   
   p.rp.ModifyResponse = func(resp *http.Response) error {
       logger.Printf("╔═══ RESPONSE FROM BACKEND ═════════════════════════════")
       logger.Printf("║ Status: %d %s", resp.StatusCode, resp.Status)
       return nil
   }
   ```

### Docker Configuration

Created `docker/Dockerfile.aistor-gw`:
```dockerfile
FROM golang:1.24-alpine AS build
WORKDIR /build
COPY go.* .
COPY cmd ./cmd
COPY pkg ./pkg
RUN CGO_ENABLED=0 go build ./cmd/aistor-gw

FROM alpine:latest
WORKDIR /root/
RUN apk add --no-cache ca-certificates
COPY --from=build /build/aistor-gw .
ENTRYPOINT ["./aistor-gw"]
```

Created `aistor-gw-creds.yaml`:
```yaml
static:
  access_key_id: minioadmin
  secret_access_key: minioadmin
```

Updated `docker-compose.yml` with aistor-gw service:
```yaml
aistor-gw:
  image: aistor-gw:local
  container_name: aistor-gw
  ports:
    - "8000:8000"
  environment:
    VERBOSE: "true"
    LOCAL_ENDPOINT: "0.0.0.0:8000"
    MINIO_ENDPOINT: "https://aistor:9000"
    MINIO_CACERT_FILE: "/certs/ca.crt"
    CREDS_FILE: "/config/creds.yaml"
  volumes:
    - ./aistor-gw-creds.yaml:/config/creds.yaml:ro
    - ./certs/ca/ca.crt:/certs/ca.crt:ro
```

---

## Architectural Implications

### Current Three-Tier Design

```
Clients → AIStor-GW:8000 → AIStor:9000 ← MinKMS:7373
         (HTTP)           (HTTPS)        (mTLS)
```

**Status:**
- ✅ **Python boto3**: Works with SSE-KMS encryption
- ❌ **Spark S3A**: 400 Bad Request (header incompatibility)

### Alternative: Hybrid Architecture

```
Python boto3 → AIStor-GW:8000 → AIStor:9000 ← MinKMS:7373
               (HTTP)           (HTTPS)        (mTLS)
                                  ↑
Spark S3A → Sidekick:8090 ────────┘
            (HTTP→HTTPS)
```

**Benefits:**
- ✅ Python gets encryption (via aistor-gw)
- ✅ Spark works without encryption (via sidekick)
- ✅ Sidekick provides HA/load balancing
- ❌ Spark data not encrypted (AWS SDK limitation)

---

## Findings for MinIO Support

### Issue Report

**Product**: AIStor Gateway (aistor-gw)  
**Client**: Apache Spark 3.5.0 with S3A connector (Hadoop 3.3.4, AWS SDK 1.12.367)  
**Problem**: 400 Bad Request when Spark S3A accesses via aistor-gw  

**Root Cause**: `signer.SignV4Trailer()` strips AWS SDK metadata headers during request re-signing:
- Header `Amz-Sdk-Retry` present in incoming request
- Header `Amz-Sdk-Retry` **missing** in outgoing request
- AIStor rejects request with 400 Bad Request

**Impact**: AIStor-GW incompatible with Spark S3A client (but works with boto3)

**Request**: 
1. Guidance on preserving AWS SDK headers during re-signing
2. Spark S3A best practices with aistor-gw
3. Alternative approaches for Spark + SSE-KMS encryption

### Test Evidence

Detailed request/response logs available showing:
- ✅ boto3 requests: No `Amz-Sdk-Retry` header → Works (200 OK)
- ❌ Spark requests: Has `Amz-Sdk-Retry` header → Fails (400 Bad Request)
- ✅ Header stripping confirmed via enhanced logging

---

## Recommendations

### Immediate (Development/Testing)

**Use Sidekick for Spark**:
```yaml
# Spark configuration
spark.hadoop.fs.s3a.endpoint = "http://sidekick:8090"
```

**Use AIStor-GW for Python boto3**:
```python
# Python boto3 configuration
s3 = boto3.client('s3', endpoint_url='http://aistor-gw:8000', ...)
```

### Short-term (Production Without Encryption)

**Single architecture with Sidekick**:
- All clients → Sidekick → AIStor
- No encryption (AWS SDK limitation)
- Works for both Spark and Python
- HA via Sidekick load balancing

### Long-term (Production With Encryption)

**Option 1**: Contact MinIO Support
- Report aistor-gw + Spark S3A compatibility issue
- Request enhanced signer that preserves SDK headers
- Official solution for Spark + SSE-KMS

**Option 2**: Hybrid Architecture
- Python → aistor-gw (with encryption)
- Spark → Sidekick (without encryption)
- Accept that Spark data isn't encrypted

**Option 3**: Wait for AWS SDK/S3A Updates
- Future S3A versions might work with HTTPS
- AWS SDK might relax HTTPS enforcement
- Community solutions may emerge

---

## Files Modified

### In aistor-gw Source

- `/Users/vb140772/src/aistor-gw/pkg/proxy/proxy.go`
  - Added comprehensive request/response logging
  - Fixed missing Host header issue
  - Added X-Amz-Date update before re-signing
  - Created backup: `proxy.go.orig`

### In Deployment

- `docker/Dockerfile.aistor-gw` - Custom Dockerfile for building
- `aistor-gw-creds.yaml` - Static credentials file
- `docker-compose.yml` - Added aistor-gw service
- `scripts/sql_test.py` - Updated endpoint to aistor-gw
- `scripts/s3_crud_test.py` - Updated endpoint to aistor-gw

---

## Test Results Summary

| Test | Client | Via | Encryption | Result | Notes |
|------|--------|-----|------------|--------|-------|
| **Python S3 CRUD** | boto3 | aistor-gw | SSE-KMS | ✅ **PASS** | All operations successful |
| **Spark SQL** | S3A | aistor-gw | None | ❌ **FAIL** | 400 Bad Request |
| **Spark SQL** | S3A | sidekick | None | ✅ **PASS** | Works without encryption |
| **Spark SQL** | S3A | sidekick | SSE-KMS | ❌ **FAIL** | AWS SDK HTTPS enforcement |

---

## Conclusion

**AIStor-GW is a powerful tool for transparent encryption** but has **incompatibility with Spark S3A** due to how it handles request re-signing. The signer strips AWS SDK metadata headers that S3A clients expect, causing malformed requests.

**For Python/boto3 clients**, aistor-gw provides:
- ✅ Transparent SSE-C/SSE-KMS encryption
- ✅ LDAP/AD authentication
- ✅ Credential rotation
- ✅ HTTP frontend with HTTPS backend security

**For Spark S3A**, alternative solutions are needed:
- Use Sidekick (no encryption)
- Contact MinIO support for S3A-compatible solution
- Wait for enhanced aistor-gw signer

The investigation has provided **valuable debugging information** and **detailed logs** that can be shared with MinIO Enterprise Support to help resolve this compatibility issue.

---

**Investigation Date**: 2025-10-09  
**Environment**: Docker Compose on macOS  
**AIStor-GW Version**: Built from source (latest)  
**Status**: Root cause identified, MinIO support recommended  

