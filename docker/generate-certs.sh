#!/bin/bash
set -e

echo "=========================================="
echo "Generating CA and Service Certificates"
echo "=========================================="

# Create directories
mkdir -p certs/{ca,minkms,aistor}
cd certs

# 1. Generate Root CA
echo "1. Creating Root CA..."
openssl genrsa -out ca/ca.key 4096
openssl req -new -x509 -days 3650 -key ca/ca.key -out ca/ca.crt \
  -subj "/C=US/ST=CA/L=SF/O=MinIO/CN=MinIO Root CA"

# 2. Generate MinKMS certificate
echo "2. Creating MinKMS certificate..."
openssl genrsa -out minkms/server.key 2048
openssl req -new -key minkms/server.key -out minkms/server.csr \
  -subj "/C=US/ST=CA/L=SF/O=MinIO/CN=minkms"

# Create MinKMS SAN config
cat > minkms/san.cnf << EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = minkms

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = minkms
DNS.2 = localhost
DNS.3 = minkms.15332_default
IP.1 = 127.0.0.1
EOF

# Sign MinKMS cert
openssl x509 -req -in minkms/server.csr -CA ca/ca.crt -CAkey ca/ca.key \
  -CAcreateserial -out minkms/server.crt -days 365 \
  -extensions v3_req -extfile minkms/san.cnf

# 3. Generate AIStor certificate
echo "3. Creating AIStor certificate..."
openssl genrsa -out aistor/server.key 2048
openssl req -new -key aistor/server.key -out aistor/server.csr \
  -subj "/C=US/ST=CA/L=SF/O=MinIO/CN=aistor"

# Create AIStor SAN config
cat > aistor/san.cnf << EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = aistor

[v3_req]
keyUsage = digitalSignature, keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth, clientAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = aistor
DNS.2 = localhost
DNS.3 = aistor.15332_default
IP.1 = 127.0.0.1
EOF

# Sign AIStor cert
openssl x509 -req -in aistor/server.csr -CA ca/ca.crt -CAkey ca/ca.key \
  -CAcreateserial -out aistor/server.crt -days 365 \
  -extensions v3_req -extfile aistor/san.cnf

# 4. Generate AIStor client certificate for mTLS to MinKMS
echo "4. Creating AIStor client certificate for MinKMS mTLS..."
openssl genrsa -out aistor/client.key 2048
openssl req -new -key aistor/client.key -out aistor/client.csr \
  -subj "/C=US/ST=CA/L=SF/O=MinIO/CN=aistor-client"

# Create client cert config (clientAuth extension)
cat > aistor/client.cnf << EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = aistor-client

[v3_req]
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = clientAuth
EOF

# Sign AIStor client cert
openssl x509 -req -in aistor/client.csr -CA ca/ca.crt -CAkey ca/ca.key \
  -CAcreateserial -out aistor/client.crt -days 365 \
  -extensions v3_req -extfile aistor/client.cnf

# Set permissions
chmod 644 ca/ca.crt minkms/server.crt aistor/server.crt aistor/client.crt
chmod 600 ca/ca.key minkms/server.key aistor/server.key aistor/client.key

# Cleanup
rm -f minkms/*.csr minkms/*.cnf aistor/*.csr aistor/*.cnf ca/*.srl

echo ""
echo "=========================================="
echo "✅ Certificates generated successfully!"
echo "=========================================="
echo ""
echo "Files created:"
ls -lh ca/ minkms/ aistor/
echo ""
echo "Verify MinKMS server cert:"
openssl verify -CAfile ca/ca.crt minkms/server.crt
echo ""
echo "Verify AIStor server cert:"
openssl verify -CAfile ca/ca.crt aistor/server.crt
echo ""
echo "Verify AIStor client cert:"
openssl verify -CAfile ca/ca.crt aistor/client.crt

