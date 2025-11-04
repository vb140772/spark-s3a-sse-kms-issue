# MinIO Sidekick Systemd Service Setup with HTTPS

This guide explains how to set up MinIO Sidekick as a Linux systemd service with HTTPS frontend, suitable for production deployments.

## Overview

MinIO Sidekick is a high-performance HTTP/HTTPS proxy and load balancer. This guide covers:
- Installing Sidekick binary
- Generating or using custom SSL/TLS certificates
- Configuring Sidekick as a systemd service
- Setting up HTTPS frontend with backend connections

## Prerequisites

- Linux system with systemd (Ubuntu 20.04+, RHEL 8+, or similar)
- Root or sudo access
- MinIO AIStor or MinIO server running (backend)
- Valid SSL/TLS certificates for HTTPS frontend

## Architecture

```
Client (Spark/Boto3) → HTTPS → Sidekick (systemd service) → HTTPS → MinIO AIStor
```

- **Frontend**: Sidekick serves HTTPS (e.g., port 8090)
- **Backend**: Sidekick connects to MinIO over HTTPS (e.g., port 9000)
- **Protocol**: End-to-end HTTPS encryption

## Installation

### Option 1: Download Pre-built Binary

```bash
# Download latest Sidekick binary
cd /usr/local/bin
sudo wget https://github.com/minio/sidekick/releases/latest/download/sidekick-linux-amd64
sudo chmod +x sidekick-linux-amd64
sudo mv sidekick-linux-amd64 sidekick
```

### Option 2: Build from Source

```bash
# Install Go if not present
sudo apt-get install -y golang-go  # Ubuntu/Debian
# or
sudo yum install -y golang  # RHEL/CentOS

# Clone and build
git clone https://github.com/minio/sidekick.git
cd sidekick
go build -o sidekick
sudo cp sidekick /usr/local/bin/
sudo chmod +x /usr/local/bin/sidekick
```

### Verify Installation

```bash
sidekick --version
```

## Certificate Generation

Sidekick requires SSL/TLS certificates for HTTPS frontend. You have two options:

### Option 1: Use Your Own Certificates

If you already have SSL/TLS certificates (e.g., from Let's Encrypt, internal CA, or commercial provider):

**Certificate Requirements:**
- Server certificate (`.crt` or `.pem` file)
- Private key (`.key` file)
- Certificate must be valid for the hostname/domain you'll use
- Certificate should include the hostname in Subject Alternative Name (SAN)

**Example with Let's Encrypt:**
```bash
# Certificates are typically in:
/etc/letsencrypt/live/your-domain/fullchain.pem
/etc/letsencrypt/live/your-domain/privkey.pem

# Use these directly in Sidekick configuration
```

**Example with Internal CA:**
```bash
# If you have certificates from your internal CA:
/etc/ssl/certs/sidekick.crt
/etc/ssl/private/sidekick.key
```

### Option 2: Generate Self-Signed Certificates

For testing or internal use, you can generate self-signed certificates:

#### Using OpenSSL (RSA)

```bash
# Create certificate directory
sudo mkdir -p /etc/sidekick/certs
cd /etc/sidekick/certs

# Generate private key
sudo openssl genrsa -out sidekick.key 2048

# Generate certificate signing request
sudo openssl req -new -key sidekick.key -out sidekick.csr \
  -subj "/CN=sidekick.example.com" \
  -addext "subjectAltName=DNS:sidekick.example.com,DNS:sidekick,DNS:localhost,IP:127.0.0.1"

# Generate self-signed certificate (valid for 1 year)
sudo openssl x509 -req -in sidekick.csr -signkey sidekick.key \
  -out sidekick.crt -days 365 \
  -extfile <(echo "subjectAltName=DNS:sidekick.example.com,DNS:sidekick,DNS:localhost,IP:127.0.0.1")

# Set proper permissions
sudo chmod 600 sidekick.key
sudo chmod 644 sidekick.crt

# Clean up CSR
sudo rm sidekick.csr
```

#### Using OpenSSL (ECDSA - Recommended)

ECDSA certificates are smaller and more efficient:

```bash
# Create certificate directory
sudo mkdir -p /etc/sidekick/certs
cd /etc/sidekick/certs

# Generate ECDSA private key (prime256v1 curve)
sudo openssl ecparam -name prime256v1 -genkey -out sidekick.key

# Create certificate configuration
sudo tee sidekick.conf <<EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = sidekick.example.com

[v3_req]
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = sidekick.example.com
DNS.2 = sidekick
DNS.3 = localhost
IP.1 = 127.0.0.1
EOF

# Generate certificate signing request
sudo openssl req -new -key sidekick.key -out sidekick.csr -config sidekick.conf

# Generate self-signed certificate
sudo openssl x509 -req -in sidekick.csr -signkey sidekick.key \
  -out sidekick.crt -days 365 -extensions v3_req -extfile sidekick.conf

# Set proper permissions
sudo chmod 600 sidekick.key
sudo chmod 644 sidekick.crt

# Clean up
sudo rm sidekick.csr sidekick.conf
```

#### Certificate Validation

Verify your certificate:

```bash
# View certificate details
openssl x509 -in /etc/sidekick/certs/sidekick.crt -text -noout

# Check certificate validity
openssl x509 -in /etc/sidekick/certs/sidekick.crt -noout -dates

# Verify certificate matches private key
openssl x509 -noout -modulus -in /etc/sidekick/certs/sidekick.crt | openssl md5
openssl rsa -noout -modulus -in /etc/sidekick/certs/sidekick.key | openssl md5
# Both MD5 hashes should match
```

## Systemd Service Configuration

### Create Service User

```bash
# Create dedicated user for Sidekick
sudo useradd -r -s /bin/false -d /var/lib/sidekick sidekick

# Create directories
sudo mkdir -p /var/lib/sidekick
sudo mkdir -p /var/log/sidekick
sudo mkdir -p /etc/sidekick

# Set ownership
sudo chown -R sidekick:sidekick /var/lib/sidekick
sudo chown -R sidekick:sidekick /var/log/sidekick
sudo chown -R sidekick:sidekick /etc/sidekick
```

### Create Systemd Service File

Create `/etc/systemd/system/sidekick.service`:

```ini
[Unit]
Description=MinIO Sidekick HTTPS Proxy
Documentation=https://github.com/minio/sidekick
After=network.target

[Service]
Type=simple
User=sidekick
Group=sidekick
WorkingDirectory=/var/lib/sidekick

# Sidekick command
# Replace values in <> with your actual configuration
ExecStart=/usr/local/bin/sidekick \
  --address=:8090 \
  --health-path=/minio/health/live \
  --log \
  --cert=/etc/sidekick/certs/sidekick.crt \
  --key=/etc/sidekick/certs/sidekick.key \
  https://minio-backend.example.com:9000

# Alternative: Use --insecure flag if backend certificate is self-signed
# and not trusted by system CA store
# ExecStart=/usr/local/bin/sidekick \
#   --address=:8090 \
#   --health-path=/minio/health/live \
#   --log \
#   --insecure \
#   --cert=/etc/sidekick/certs/sidekick.crt \
#   --key=/etc/sidekick/certs/sidekick.key \
#   https://minio-backend.example.com:9000

# Restart policy
Restart=always
RestartSec=5

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/sidekick

# Resource limits
LimitNOFILE=65536

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=sidekick

[Install]
WantedBy=multi-user.target
```

### Configuration Options

**Frontend Configuration:**
- `--address=:8090` - Listen on port 8090 (all interfaces)
- `--address=127.0.0.1:8090` - Listen only on localhost
- `--cert=/path/to/cert.crt` - SSL certificate file
- `--key=/path/to/key.key` - SSL private key file

**Backend Configuration:**
- `https://minio-backend.example.com:9000` - Backend HTTPS endpoint
- `--insecure` - Skip TLS verification for backend (use with caution)
- `--cacert=/path/to/ca.crt` - CA certificate for backend verification

**Health Check:**
- `--health-path=/minio/health/live` - Health check endpoint path

**Logging:**
- `--log` - Enable request logging

### Multiple Backend Endpoints

For load balancing across multiple MinIO servers:

```ini
ExecStart=/usr/local/bin/sidekick \
  --address=:8090 \
  --health-path=/minio/health/live \
  --log \
  --cert=/etc/sidekick/certs/sidekick.crt \
  --key=/etc/sidekick/certs/sidekick.key \
  https://minio1.example.com:9000 \
  https://minio2.example.com:9000 \
  https://minio3.example.com:9000 \
  https://minio4.example.com:9000
```

### Set Certificate Permissions

Ensure the service user can read certificates:

```bash
# If certificates are in /etc/sidekick/certs
sudo chmod 644 /etc/sidekick/certs/sidekick.crt
sudo chmod 600 /etc/sidekick/certs/sidekick.key
sudo chown root:sidekick /etc/sidekick/certs/sidekick.key
sudo chown root:sidekick /etc/sidekick/certs/sidekick.crt
```

## Enable and Start Service

```bash
# Reload systemd to recognize new service
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable sidekick

# Start the service
sudo systemctl start sidekick

# Check status
sudo systemctl status sidekick

# View logs
sudo journalctl -u sidekick -f
```

## Verification

### Test HTTPS Connection

```bash
# Test health endpoint
curl -k https://localhost:8090/minio/health/live

# Test with proper certificate validation (if using public CA)
curl --cacert /etc/sidekick/certs/sidekick.crt https://localhost:8090/minio/health/live
```

### Test from Remote Client

If using a self-signed certificate, you'll need to trust the CA certificate on the client:

```bash
# On client machine, download the certificate
scp server:/etc/sidekick/certs/sidekick.crt /tmp/sidekick-ca.crt

# Test connection
curl --cacert /tmp/sidekick-ca.crt https://sidekick.example.com:8090/minio/health/live
```

### Check Service Logs

```bash
# View recent logs
sudo journalctl -u sidekick -n 50

# Follow logs in real-time
sudo journalctl -u sidekick -f

# View logs since boot
sudo journalctl -u sidekick -b
```

## Configuration Examples

### Example 1: Single Backend with Custom CA

If your MinIO backend uses a self-signed certificate:

```ini
ExecStart=/usr/local/bin/sidekick \
  --address=:8090 \
  --health-path=/minio/health/live \
  --log \
  --cert=/etc/sidekick/certs/sidekick.crt \
  --key=/etc/sidekick/certs/sidekick.key \
  --cacert=/etc/ssl/certs/minio-ca.crt \
  https://minio.internal.example.com:9000
```

### Example 2: HTTP Frontend (No HTTPS)

For testing or internal networks (not recommended for production):

```ini
ExecStart=/usr/local/bin/sidekick \
  --address=:8091 \
  --health-path=/minio/health/live \
  --log \
  --insecure \
  https://minio-backend.example.com:9000
```

**Note**: HTTP frontend will fail with Spark S3A when encryption headers are present (see main README.md for details).

### Example 3: Production with Let's Encrypt

```ini
ExecStart=/usr/local/bin/sidekick \
  --address=:8090 \
  --health-path=/minio/health/live \
  --log \
  --cert=/etc/letsencrypt/live/sidekick.example.com/fullchain.pem \
  --key=/etc/letsencrypt/live/sidekick.example.com/privkey.pem \
  https://minio-backend.example.com:9000
```

## Troubleshooting

### Service Fails to Start

```bash
# Check service status
sudo systemctl status sidekick

# Check logs
sudo journalctl -u sidekick -n 100

# Common issues:
# 1. Certificate file not found or not readable
# 2. Port already in use
# 3. Backend not accessible
# 4. Permission issues
```

### Certificate Issues

```bash
# Verify certificate is valid
openssl x509 -in /etc/sidekick/certs/sidekick.crt -text -noout

# Check certificate expiration
openssl x509 -in /etc/sidekick/certs/sidekick.crt -noout -dates

# Test certificate and key match
openssl x509 -noout -modulus -in /etc/sidekick/certs/sidekick.crt | openssl md5
openssl rsa -noout -modulus -in /etc/sidekick/certs/sidekick.key | openssl md5
```

### Port Already in Use

```bash
# Check what's using the port
sudo netstat -tlnp | grep 8090
# or
sudo ss -tlnp | grep 8090

# Kill the process if needed (be careful!)
sudo kill -9 <PID>
```

### Backend Connection Issues

```bash
# Test backend connectivity
curl -k https://minio-backend.example.com:9000/minio/health/live

# Check DNS resolution
nslookup minio-backend.example.com

# Test from Sidekick server
sudo -u sidekick curl -k https://minio-backend.example.com:9000/minio/health/live
```

### Permission Issues

```bash
# Ensure service user can read certificates
sudo chown root:sidekick /etc/sidekick/certs/sidekick.key
sudo chmod 640 /etc/sidekick/certs/sidekick.key
sudo chmod 644 /etc/sidekick/certs/sidekick.crt

# Ensure service user can write logs
sudo chown -R sidekick:sidekick /var/log/sidekick
```

## Security Best Practices

1. **Use Strong Certificates**: Prefer ECDSA certificates over RSA for better performance
2. **Proper Permissions**: Certificate keys should be readable only by service user
3. **Regular Updates**: Keep Sidekick binary updated to latest version
4. **Firewall**: Only open necessary ports (8090 for HTTPS frontend)
5. **Log Monitoring**: Monitor logs for suspicious activity
6. **Certificate Rotation**: Implement certificate rotation before expiration
7. **Backend Verification**: Use `--cacert` instead of `--insecure` when possible

## Certificate Renewal (Let's Encrypt)

If using Let's Encrypt certificates:

```bash
# Create renewal hook script
sudo tee /etc/letsencrypt/renewal-hooks/deploy/sidekick.sh <<'EOF'
#!/bin/bash
systemctl restart sidekick
EOF

sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/sidekick.sh

# Test renewal
sudo certbot renew --dry-run
```

## Monitoring

### Health Check Endpoint

Sidekick exposes a health check endpoint:

```bash
# Check health
curl https://sidekick.example.com:8090/minio/health/live

# Integrate with monitoring systems
# Example: Prometheus blackbox exporter
# Example: Nagios/Icinga health check
```

### Log Monitoring

```bash
# Monitor for errors
sudo journalctl -u sidekick -f | grep -i error

# Count requests per minute
sudo journalctl -u sidekick --since "1 minute ago" | grep "LOG:" | wc -l
```

## Integration with Spark

Once Sidekick is running, configure Spark to use it:

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("Spark-Sidekick") \
    .config("spark.hadoop.fs.s3a.endpoint", "https://sidekick.example.com:8090") \
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "true") \
    .config("spark.hadoop.fs.s3a.access.key", "your-access-key") \
    .config("spark.hadoop.fs.s3a.secret.key", "your-secret-key") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .getOrCreate()
```

**Important**: Ensure the Sidekick CA certificate is trusted in Spark's Java truststore if using self-signed certificates.

## Integration with Spark S3A and MinKMS (SSE-KMS Mode)

When using MinIO AIStor with MinKMS for server-side encryption, you can configure Spark S3A to use SSE-KMS encryption. This requires HTTPS and proper configuration.

### Prerequisites

- MinIO AIStor with MinKMS configured and running
- MinKMS enclave and identity created
- Encryption key configured in MinKMS
- Sidekick HTTPS frontend (required for SSE-KMS)

### Configuration Options

#### Option 1: Client-Side SSE-KMS Headers (Explicit Encryption)

Spark explicitly requests SSE-KMS encryption by sending encryption headers:

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("Spark-Sidekick-SSE-KMS") \
    .config("spark.hadoop.fs.s3a.endpoint", "https://sidekick.example.com:8090") \
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "true") \
    .config("spark.hadoop.fs.s3a.access.key", "your-access-key") \
    .config("spark.hadoop.fs.s3a.secret.key", "your-secret-key") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    # SSE-KMS Configuration
    .config("spark.hadoop.fs.s3a.server-side-encryption-algorithm", "SSE-KMS") \
    .config("spark.hadoop.fs.s3a.server-side-encryption.key", "spark-encryption-key") \
    .getOrCreate()
```

**Important Requirements:**
- ✅ **HTTPS is REQUIRED** - AWS SDK enforces HTTPS for SSE-KMS
- ✅ Encryption key must exist in MinKMS (e.g., `spark-encryption-key`)
- ✅ MinKMS must be accessible from MinIO AIStor

**Configuration Details:**
- `server-side-encryption-algorithm`: Set to `"SSE-KMS"` for Key Management Service encryption
- `server-side-encryption.key`: The key name in MinKMS (must match the key configured in MinKMS)

#### Option 2: Auto-Encryption (MinIO Handles Encryption)

With `MINIO_KMS_AUTO_ENCRYPTION=on` enabled on AIStor, you can let MinIO handle encryption automatically without sending headers from Spark:

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("Spark-Sidekick-Auto-Encrypt") \
    .config("spark.hadoop.fs.s3a.endpoint", "https://sidekick.example.com:8090") \
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "true") \
    .config("spark.hadoop.fs.s3a.access.key", "your-access-key") \
    .config("spark.hadoop.fs.s3a.secret.key", "your-secret-key") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    # Explicitly disable encryption headers to let AIStor handle it
    .config("spark.hadoop.fs.s3a.server-side-encryption-algorithm", "") \
    .config("spark.hadoop.fs.s3a.server-side-encryption.key", "") \
    .getOrCreate()
```

**Benefits:**
- ✅ Works with both HTTP and HTTPS (if encryption headers are disabled)
- ✅ AIStor automatically encrypts all data via MinKMS
- ✅ No client-side encryption configuration needed

**Note**: If you use this approach with HTTP Sidekick frontend, you must disable encryption headers, otherwise AWS SDK will enforce HTTPS and fail.

### MinKMS Configuration

Ensure MinKMS is properly configured:

1. **MinKMS Environment Variables** (on MinIO AIStor server):
   ```bash
   MINIO_KMS_SERVER=https://minkms.example.com:7373
   MINIO_KMS_ENCLAVE=aistor-deployment
   MINIO_KMS_API_KEY=k1:your-api-key-here
   MINIO_KMS_SSE_KEY=spark-encryption-key
   MINIO_KMS_TLS_CLIENT_CERT=/etc/ssl/certs/minkms-client.crt
   MINIO_KMS_TLS_CLIENT_KEY=/etc/ssl/private/minkms-client.key
   MINIO_KMS_AUTO_ENCRYPTION=on  # Optional: auto-encrypt all data
   ```

2. **MinKMS Key Creation**:
   ```bash
   # Create encryption key in MinKMS
   minkms create-key \
     -a k1:your-api-key \
     --enclave aistor-deployment \
     spark-encryption-key
   ```

3. **Verify MinKMS Connection**:
   ```bash
   # From MinIO AIStor server, test MinKMS connectivity
   curl -k -H "Authorization: Bearer k1:your-api-key" \
     https://minkms.example.com:7373/version
   ```

### Testing SSE-KMS Integration

1. **Write Test** (with SSE-KMS):
   ```python
   # Write data with SSE-KMS encryption
   data = [(1, "Alice", 100), (2, "Bob", 200)]
   df = spark.createDataFrame(data, ["id", "name", "amount"])
   df.write.mode("overwrite").parquet("s3a://your-bucket/test-data")
   ```

2. **Read Test**:
   ```python
   # Read encrypted data (decryption is automatic)
   df = spark.read.parquet("s3a://your-bucket/test-data")
   df.show()
   ```

3. **Verify Encryption**:
   ```bash
   # Check object metadata via MinIO client
   mc stat your-alias/your-bucket/test-data/part-00000-*.parquet
   
   # Look for encryption metadata:
   # - X-Amz-Server-Side-Encryption: aws:kms
   # - X-Amz-Server-Side-Encryption-Aws-Kms-Key-Id: spark-encryption-key
   ```

### Troubleshooting SSE-KMS

#### Issue: "HTTPS must be used when sending customer encryption keys"

**Cause**: Using HTTP endpoint with SSE-KMS headers.

**Solution**: 
- Use HTTPS Sidekick frontend (required for SSE-KMS)
- Or disable encryption headers and use auto-encryption

#### Issue: "Key not found" or "Invalid KMS key"

**Cause**: Encryption key doesn't exist in MinKMS.

**Solution**:
```bash
# List keys in MinKMS
minkms list-keys -a k1:your-api-key --enclave aistor-deployment

# Create key if missing
minkms create-key -a k1:your-api-key --enclave aistor-deployment spark-encryption-key
```

#### Issue: "MinKMS connection failed"

**Cause**: MinIO AIStor cannot reach MinKMS.

**Solution**:
- Verify MinKMS is running: `systemctl status minkms`
- Check network connectivity: `curl -k https://minkms.example.com:7373/version`
- Verify TLS certificates are valid
- Check MinIO logs: `journalctl -u minio -n 100`

#### Issue: Encryption not working

**Cause**: MinKMS not properly configured or auto-encryption disabled.

**Solution**:
- Verify `MINIO_KMS_AUTO_ENCRYPTION=on` is set (for auto-encryption)
- Or ensure SSE-KMS headers are sent from Spark (for explicit encryption)
- Check MinIO logs for KMS connection errors

## References

- [MinIO Sidekick GitHub](https://github.com/minio/sidekick)
- [Sidekick Documentation](https://github.com/minio/sidekick#readme)
- [OpenSSL Certificate Generation Guide](https://www.openssl.org/docs/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)

---

**Last Updated**: 2025-11-04  
**Purpose**: Production deployment guide for MinIO Sidekick as systemd service with HTTPS

