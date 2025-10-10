#!/bin/bash
set -e

echo "=========================================="
echo "MinKMS: Quick Enclave Setup"
echo "=========================================="

# Wait for MinKMS
echo "Waiting for MinKMS..."
sleep 10

ROOT_API_KEY="k1:t4TG5iG22LEUP2Y6dLWBCfTNquxzrVxuR_6yx16fATw"

echo ""
echo "Attempting to create enclave 'aistor-deployment'..."
# Use curl to create enclave via API
curl -k -X PUT "https://minkms:7373/v1/enclave/aistor-deployment" \
  -H "Authorization: Bearer $ROOT_API_KEY" \
  --cacert /certs/ca/ca.crt 2>&1 || echo "  (Enclave may already exist or created automatically)"

echo ""
echo "=========================================="
echo "✅ MinKMS Setup Attempted"
echo "=========================================="
echo ""
echo "Note: MinKMS may auto-create enclave on first use"
echo "Check AIStor logs to verify connection"
echo ""

