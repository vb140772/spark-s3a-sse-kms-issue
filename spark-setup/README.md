# Spark + AIStor + Sidekick Setup

This directory contains the main Docker Compose setup for Spark with MinIO AIStor and Sidekick HTTPS proxy.

## Architecture

```
Spark → HTTPS (port 8090) → Sidekick → HTTPS (port 9000) → AIStor → MinKMS
```

- **Spark**: Apache Spark cluster with S3A support
- **Sidekick**: HTTPS frontend proxy (port 8090)
- **AIStor**: MinIO AIStor with HTTPS (port 9000)
- **MinKMS**: Key Management Service for server-side encryption

## Quick Start

### 1. Prerequisites

Ensure you have:
- Docker and Docker Compose installed
- Certificates generated (see parent directory)
- MinIO license file (`minio.license`)

### 2. Start Services

```bash
cd spark-setup
docker-compose up -d
```

### 3. Run Tests

```bash
# Spark SQL test
./run-spark-sql-test.sh

# Python S3 test
./run-python-s3-test.sh
```

## Services

### MinIO AIStor
- **Container**: `aistor`
- **Ports**: 
  - 9000:9000 (S3 API - HTTPS)
  - 9001:9001 (Console - HTTPS)
- **MinKMS**: Integrated for server-side encryption

### Sidekick
- **Container**: `sidekick`
- **Port**: 8090:8090 (HTTPS frontend)
- **Backend**: `https://aistor:9000`

### Spark
- **Container**: `spark-master`, `spark-worker`, `spark-history`
- **Ports**:
  - 8080:8080 (Spark Master UI)
  - 7077:7077 (Spark Master)
  - 18080:18080 (Spark History Server)

### MinKMS
- **Container**: `minkms`
- **Port**: 7373:7373 (HTTPS)

## Configuration

All paths in `docker-compose.yml` are relative to the parent directory:
- `../docker/` - Dockerfiles
- `../certs/` - Certificates
- `../scripts/` - Test scripts
- `../data/` - Data volumes
- `../minkms/` - MinKMS configuration

## Notes

- The Sidekick frontend uses HTTPS with certificates from `../certs/sidekick/`
- Spark trusts both MinIO CA and Sidekick CA for certificate validation
- All services use the same Docker network for communication

