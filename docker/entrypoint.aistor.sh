#!/bin/bash
set -e

# Configure MinIO/AIStor TLS
export MINIO_CERTS_DIR=/etc/minio/certs

# Ensure cert directory exists
mkdir -p $MINIO_CERTS_DIR

# Copy certificates if not already present
if [ ! -f "$MINIO_CERTS_DIR/public.crt" ]; then
    cp /certs/server.crt $MINIO_CERTS_DIR/public.crt
    cp /certs/server.key $MINIO_CERTS_DIR/private.key
    chmod 644 $MINIO_CERTS_DIR/public.crt
    chmod 600 $MINIO_CERTS_DIR/private.key
fi

# Start MinIO/AIStor
exec /usr/bin/docker-entrypoint.sh "$@"

