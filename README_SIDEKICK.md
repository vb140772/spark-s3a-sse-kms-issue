# Sidekick HTTPS Frontend Setup

This is a separate, simplified Docker Compose setup for testing MinIO AIStor with Sidekick HTTPS frontend.

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
./docker/generate-sidekick-certs.sh certs/sidekick "MinIO Sidekick CA" "sidekick.local"
```

This creates:
- `certs/sidekick/ca.crt` - CA certificate (trust this in clients)
- `certs/sidekick/public.crt` - Server certificate for Sidekick
- `certs/sidekick/private.key` - Server private key for Sidekick

### 2. Start Services

```bash
./run-sidekick-test.sh
```

This will:
- Generate certificates (if needed)
- Start MinIO and Sidekick
- Run S3 operations test

### 3. Manual Testing

You can also run the test manually:

```bash
# Start services
docker-compose -f docker-compose-sidekick.yml up -d

# Run test
docker-compose -f docker-compose-sidekick.yml exec s3-test-client /app/scripts/test_sidekick_s3.sh

# Or run Python test interactively
docker-compose -f docker-compose-sidekick.yml exec s3-test-client python3 /app/scripts/test_sidekick_s3.sh
```

## Services

### MinIO AIStor
- **Container**: `aistor-sidekick`
- **Ports**: 
  - 9000:9000 (S3 API - HTTPS)
  - 9001:9001 (Console - HTTPS)
- **Health**: `https://localhost:9000/minio/health/live`

### Sidekick
- **Container**: `sidekick-https`
- **Port**: 8000:8000 (HTTPS frontend)
- **Backend**: `https://minio:9000`
- **Certificates**: Mounted from `certs/sidekick/`

### S3 Test Client
- **Container**: `s3-test-client`
- **Purpose**: Test S3 operations through Sidekick HTTPS
- **Tools**: boto3, curl, openssl

## Certificate Management

### Certificate Generation

The `generate-sidekick-certs.sh` script creates ECDSA certificates:

```bash
./docker/generate-sidekick-certs.sh [cert_dir] [ca_name] [domain]
```

**Parameters**:
- `cert_dir`: Directory for certificates (default: `certs/sidekick`)
- `ca_name`: CA certificate name (default: `MinIO Sidekick CA`)
- `domain`: Server certificate domain (default: `sidekick.local`)

### Certificate Files

| File | Purpose | Used By |
|------|---------|---------|
| `ca.crt` | CA certificate | Clients (trust this) |
| `public.crt` | Server certificate | Sidekick (--cert) |
| `private.key` | Server private key | Sidekick (--key) |

### Certificate Validation

```bash
# Verify certificate is ECDSA
openssl x509 -in certs/sidekick/public.crt -text -noout | grep "Public Key Algorithm"

# Verify certificate chain
openssl verify -CAfile certs/sidekick/ca.crt certs/sidekick/public.crt

# Check certificate details
openssl x509 -in certs/sidekick/public.crt -text -noout
```

## Testing

### Test Script

The `test_sidekick_s3.sh` script performs:
1. ✅ List buckets
2. ✅ Create bucket (if needed)
3. ✅ Upload object
4. ✅ List objects
5. ✅ Download object
6. ✅ Delete object (cleanup)

### Manual Testing with curl

```bash
# Test HTTPS connection (with certificate validation)
curl -v --cacert certs/sidekick/ca.crt https://localhost:8000/minio/health/live

# Test S3 API
curl -v --cacert certs/sidekick/ca.crt https://localhost:8000/
```

### Manual Testing with Python

```bash
docker-compose -f docker-compose-sidekick.yml exec s3-test-client python3
```

```python
import boto3

s3 = boto3.client(
    's3',
    endpoint_url='https://sidekick:8000',
    aws_access_key_id='minioadmin',
    aws_secret_access_key='minioadmin',
    verify=True  # Uses system CA store
)

# List buckets
response = s3.list_buckets()
print(response)
```

## Configuration

### Sidekick Options

The Sidekick service uses these options:
- `--address=:8000` - Listen on port 8000
- `--health-path=/minio/health/cluster` - Health check endpoint
- `--log` - Enable logging
- `--cacert=/etc/sidekick/certs/ca.crt` - CA cert for backend MinIO
- `--cert=/etc/sidekick/certs/public.crt` - TLS cert for frontend
- `--key=/etc/sidekick/certs/private.key` - TLS key for frontend

### Environment Variables

Test client environment variables:
- `S3_ENDPOINT`: Sidekick HTTPS endpoint (default: `https://sidekick:8000`)
- `S3_ACCESS_KEY`: MinIO access key (default: `minioadmin`)
- `S3_SECRET_KEY`: MinIO secret key (default: `minioadmin`)
- `S3_BUCKET`: Test bucket name (default: `test-bucket`)

## Troubleshooting

### Certificate Issues

**Error**: `SSL: certificate verify failed`

**Solution**: Ensure CA certificate is trusted:
```bash
# In test client container
cp /certs/ca.crt /usr/local/share/ca-certificates/sidekick-ca.crt
update-ca-certificates
```

### Connection Issues

**Error**: `Connection refused` or `Name resolution failed`

**Solution**: Check service names and network:
```bash
docker-compose -f docker-compose-sidekick.yml ps
docker network inspect <network_name>
```

### Sidekick Not Starting

**Check logs**:
```bash
docker-compose -f docker-compose-sidekick.yml logs sidekick
```

**Verify certificates exist**:
```bash
ls -la certs/sidekick/
```

## Cleanup

```bash
# Stop services
docker-compose -f docker-compose-sidekick.yml down

# Remove volumes (optional)
docker-compose -f docker-compose-sidekick.yml down -v

# Remove certificates (optional)
rm -rf certs/sidekick/*
```

## Differences from Main Setup

This setup is simplified:
- ✅ Single MinIO container (no MinKMS)
- ✅ Sidekick with HTTPS frontend
- ✅ Simple S3 test client
- ✅ ECDSA certificates (better performance)
- ✅ Focused on testing Sidekick HTTPS functionality

## Next Steps

Once this works, you can:
1. Integrate this Sidekick configuration into the main setup
2. Use the same certificate generation for other services
3. Test Spark S3A with this Sidekick HTTPS endpoint

