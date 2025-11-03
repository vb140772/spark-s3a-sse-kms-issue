#!/bin/bash
# Generate ECDSA certificates for Sidekick HTTPS frontend
# Based on the openssl method with complete manual control

set -e

CERT_DIR="${1:-certs/sidekick}"
CA_NAME="${2:-MinIO Sidekick CA}"
DOMAIN="${3:-sidekick.local}"

echo "============================================================"
echo "Generating ECDSA Certificates for Sidekick"
echo "============================================================"
echo "Certificate Directory: $CERT_DIR"
echo "CA Name: $CA_NAME"
echo "Domain: $DOMAIN"
echo ""

# Create certificate directory
mkdir -p "$CERT_DIR"
cd "$CERT_DIR"

echo "Part 1: Creating ECDSA Certificate Authority (CA)"
echo "---------------------------------------------------"

# Generate CA private key
echo "1. Generating CA private key..."
openssl ecparam -name prime256v1 -genkey -out ca.key

# Create self-signed CA root certificate
echo "2. Creating CA root certificate..."
openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 -out ca.crt \
    -subj "/CN=$CA_NAME"

echo ""
echo "Part 2: Creating ECDSA Server Certificate"
echo "---------------------------------------------------"

# Generate server private key
echo "3. Generating server private key..."
openssl ecparam -name prime256v1 -genkey -out private.key

# Create SAN configuration file
echo "4. Creating SAN configuration..."
cat > san.conf <<EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req

[req_distinguished_name]

[v3_req]
subjectAltName = @alt_names
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth

[alt_names]
DNS.1 = $DOMAIN
DNS.2 = *.${DOMAIN#*.}
DNS.3 = localhost
DNS.4 = sidekick
IP.1 = 127.0.0.1
IP.2 = ::1
EOF

# Create Certificate Signing Request (CSR)
echo "5. Creating Certificate Signing Request..."
openssl req -new -key private.key -out server.csr \
    -subj "/CN=$DOMAIN" -config san.conf

# Sign the server certificate with CA
echo "6. Signing server certificate with CA..."
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out public.crt -days 730 -sha256 -extfile san.conf -extensions v3_req

echo ""
echo "Part 3: Converting Private Key to PKCS#8 Format"
echo "---------------------------------------------------"

# Convert private.key to PKCS#8 format
echo "7. Converting private key to PKCS#8 format..."
openssl pkcs8 -topk8 -nocrypt -in private.key -out private.pkcs8.key
mv private.key private.key.ec
mv private.pkcs8.key private.key

echo ""
echo "Part 4: Validation"
echo "---------------------------------------------------"

# Verify certificates are ECDSA
echo "8. Verifying CA certificate is ECDSA..."
openssl x509 -in ca.crt -text -noout | grep "Public Key Algorithm" || echo "   CA: ECDSA"

echo "9. Verifying server certificate is ECDSA..."
openssl x509 -in public.crt -text -noout | grep "Public Key Algorithm" || echo "   Server: ECDSA"

# Verify chain of trust
echo "10. Verifying certificate chain..."
if openssl verify -CAfile ca.crt public.crt > /dev/null 2>&1; then
    echo "   ✅ Certificate chain verified: public.crt: OK"
else
    echo "   ❌ Certificate chain verification failed"
    exit 1
fi

# Clean up intermediate files
echo ""
echo "11. Cleaning up intermediate files..."
rm -f server.csr san.conf ca.srl private.key.ec

echo ""
echo "============================================================"
echo "✅ Certificate Generation Complete!"
echo "============================================================"
echo "Generated files in $CERT_DIR:"
echo "  - ca.crt          (CA certificate - trust this in clients)"
echo "  - public.crt      (Server certificate for Sidekick)"
echo "  - private.key     (Server private key for Sidekick)"
echo ""
echo "Certificate Details:"
openssl x509 -in public.crt -text -noout | grep -E "(Subject:|Issuer:|Not Before|Not After|DNS:|IP:)" | head -10
echo ""
echo "Next steps:"
echo "  1. Trust ca.crt in your clients (Java keystore, system CA store)"
echo "  2. Configure Sidekick with --cert public.crt --key private.key"
echo "  3. Use https://$DOMAIN:8000 to connect to Sidekick"
echo "============================================================"

