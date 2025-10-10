#!/bin/sh
set -e

echo "=========================================="
echo "Provisioning Certificates with Smallstep"
echo "=========================================="

# Wait for Step CA to be ready
echo "Waiting for Step CA..."
MAX_RETRIES=30
RETRY_COUNT=0
CA_URL="https://step-ca:9000"

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if nc -z step-ca 9000 2>/dev/null; then
        echo "Step CA is ready!"
        break
    fi
    echo "  Waiting for Step CA (attempt $((RETRY_COUNT+1))/$MAX_RETRIES)..."
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT+1))
done

# CA configuration
CA_PASSWORD="changeme"

# Bootstrap step-cli to trust the CA
echo "Bootstrapping step-cli..."
FINGERPRINT=$(step certificate fingerprint /ca-data/certs/root_ca.crt)
step ca bootstrap --ca-url "$CA_URL" --fingerprint "$FINGERPRINT" --force 2>&1 || true

# Create certificates directory structure
mkdir -p /certs/minkms /certs/aistor /certs/ca

# Copy root CA certificate
echo "Copying root CA certificate..."
cp /ca-data/certs/root_ca.crt /certs/ca/root_ca.crt

# Generate MinKMS certificate
echo "Generating MinKMS certificate..."
step ca certificate "minkms" \
  /certs/minkms/public.crt \
  /certs/minkms/private.key \
  --ca-url "$CA_URL" \
  --root /ca-data/certs/root_ca.crt \
  --provisioner admin \
  --provisioner-password-file <(echo "$CA_PASSWORD") \
  --san minkms \
  --san localhost \
  --san minkms.15332_default \
  --not-after 8760h

# Generate AIStor certificate
echo "Generating AIStor certificate..."
step ca certificate "aistor" \
  /certs/aistor/public.crt \
  /certs/aistor/private.key \
  --ca-url "$CA_URL" \
  --root /ca-data/certs/root_ca.crt \
  --provisioner admin \
  --provisioner-password-file <(echo "$CA_PASSWORD") \
  --san aistor \
  --san localhost \
  --san aistor.15332_default \
  --not-after 8760h

# Set permissions
chmod 644 /certs/minkms/public.crt /certs/aistor/public.crt /certs/ca/root_ca.crt
chmod 600 /certs/minkms/private.key /certs/aistor/private.key

echo ""
echo "=========================================="
echo "✅ Certificates provisioned successfully!"
echo "=========================================="
echo ""
echo "Certificates created:"
echo "  - MinKMS: /certs/minkms/"
echo "  - AIStor: /certs/aistor/"
echo "  - Root CA: /certs/ca/root_ca.crt"
echo ""
ls -lh /certs/minkms/
ls -lh /certs/aistor/
ls -lh /certs/ca/

