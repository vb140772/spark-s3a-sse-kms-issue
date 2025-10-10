#!/bin/bash
set -e

echo "=========================================="
echo "MinKMS: Creating Enclave and Identity"
echo "=========================================="

# Wait for MinKMS to be ready
echo "Waiting for MinKMS API..."
MAX_RETRIES=60
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -k -s -f https://minkms:7373/version > /dev/null 2>&1; then
        echo "✅ MinKMS API is ready!"
        break
    fi
    echo "  Waiting for MinKMS (attempt $((RETRY_COUNT+1))/$MAX_RETRIES)..."
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT+1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ MinKMS did not become ready in time"
    exit 1
fi

# MinKMS root API key (from minkms.env)
ROOT_API_KEY="k1:t4TG5iG22LEUP2Y6dLWBCfTNquxzrVxuR_6yx16fATw"

echo ""
echo "Creating enclave 'aistor-deployment' using minkms CLI..."

# Set environment for minkms CLI
export MINIO_KMS_SERVER=https://minkms:7373

# Try to create enclave - it's OK if it already exists
if minkms add-enclave -k -a "$ROOT_API_KEY" aistor-deployment 2>&1 | tee /tmp/enclave.log; then
    echo "✅ Enclave created successfully"
elif grep -q "already exists" /tmp/enclave.log; then
    echo "✅ Enclave already exists (OK)"
else
    echo "⚠️  Enclave creation had issues, but continuing..."
    cat /tmp/enclave.log
fi

echo ""
echo "Creating identity 'aistor-identity' with admin privileges..."

# Use timeout to prevent hanging
# If this hangs, it's OK - we can use root API key
timeout 30 minkms add-identity -k -a "$ROOT_API_KEY" \
    --enclave aistor-deployment \
    --admin aistor-identity 2>&1 | tee /tmp/identity.log || {
    echo "⚠️  Identity creation timed out or failed"
    echo "This is OK - AIStor can use the root API key"
}

# Try to extract API key if identity was created
API_KEY=$(grep -oE 'k[0-9]+:[A-Za-z0-9_-]+' /tmp/identity.log 2>/dev/null | tail -1)

echo ""
echo "=========================================="
echo "✅ MinKMS Initialization Complete"
echo "=========================================="
echo ""
echo "Enclave: aistor-deployment"
echo "Root API Key: $ROOT_API_KEY"

if [ -n "$API_KEY" ] && [ "$API_KEY" != "$ROOT_API_KEY" ]; then
    echo "Identity API Key: $API_KEY"
    echo ""
    echo "⚠️  To use identity API key, update docker-compose.yml:"
    echo "    MINIO_KMS_API_KEY: $API_KEY"
else
    echo ""
    echo "ℹ️  Using root API key for AIStor (already configured)"
fi

echo ""
echo "AIStor can now connect to MinKMS!"
echo "=========================================="

# Signal completion
touch /tmp/minkms-init-complete
exit 0
