# Sidekick + AIStor Test Setup

This directory contains a standalone test setup for MinIO AIStor with Sidekick HTTPS frontend.

## Purpose

This is a simplified, isolated test environment to verify:
- Sidekick HTTPS frontend functionality
- S3 operations through Sidekick
- Certificate validation
- Load balancing and health checks

## Architecture

```
Client → HTTPS (port 8000) → Sidekick → HTTPS (port 9000) → MinIO AIStor
```

- **Frontend**: Sidekick serves HTTPS on port 8000
- **Backend**: Sidekick connects to MinIO over HTTPS on port 9000
- **Certificates**: ECDSA certificates for Sidekick frontend

## Quick Start

### 1. Generate Certificates

```bash
cd sidekick-test
../docker/generate-sidekick-certs.sh ../certs/sidekick "MinIO Sidekick CA" "sidekick.local"
```

### 2. Run Test

```bash
./run-sidekick-test.sh
```

This will:
- Generate certificates (if needed)
- Start MinIO and Sidekick
- Run S3 operations test

## Services

### MinIO AIStor
- **Container**: `aistor-sidekick`
- **Ports**: 
  - 9000:9000 (S3 API - HTTPS)
  - 9001:9001 (Console - HTTPS)
- **Note**: No MinKMS integration in this test setup

### Sidekick
- **Container**: `sidekick-https`
- **Port**: 8000:8000 (HTTPS frontend)
- **Backend**: `https://minio:9000`

### S3 Test Client
- **Container**: `s3-test-client`
- **Purpose**: Test S3 operations through Sidekick HTTPS
- **Tools**: boto3, curl, openssl

## Configuration

All paths reference the parent directory:
- `../docker/` - Dockerfiles
- `../certs/` - Certificates
- `../scripts/` - Test scripts

## Differences from Main Setup

This setup is simplified:
- ✅ Single MinIO container (no MinKMS)
- ✅ Sidekick with HTTPS frontend
- ✅ Simple S3 test client
- ✅ Focused on testing Sidekick HTTPS functionality

## Testing

The test script (`test_sidekick_s3.sh`) performs:
1. ✅ List buckets
2. ✅ Create bucket (if needed)
3. ✅ Upload object
4. ✅ List objects
5. ✅ Download object
6. ✅ Delete object (cleanup)

## Cleanup

```bash
docker-compose -f docker-compose-sidekick.yml down
docker-compose -f docker-compose-sidekick.yml down -v  # Remove volumes
```

