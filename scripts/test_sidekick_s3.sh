#!/bin/bash
# Simple S3 test script to verify Sidekick HTTPS frontend works
# Tests: list buckets, create bucket, upload, download, list objects

set -e

S3_ENDPOINT="${S3_ENDPOINT:-https://sidekick:8000}"
S3_ACCESS_KEY="${S3_ACCESS_KEY:-minioadmin}"
S3_SECRET_KEY="${S3_SECRET_KEY:-minioadmin}"
S3_BUCKET="${S3_BUCKET:-test-bucket}"

# Install Sidekick CA certificate if available
if [ -f /certs/ca.crt ]; then
    echo "Installing Sidekick CA certificate..."
    cp /certs/ca.crt /usr/local/share/ca-certificates/sidekick-ca.crt
    update-ca-certificates 2>&1 | grep -v "^WARNING" || true
    # Set environment variable for Python/boto3 to use the CA bundle
    export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
    export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
    export CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
    echo "✅ CA certificate installed"
fi

echo "============================================================"
echo "Sidekick HTTPS Frontend - S3 Operations Test"
echo "============================================================"
echo "Endpoint: $S3_ENDPOINT"
echo "Access Key: $S3_ACCESS_KEY"
echo "Bucket: $S3_BUCKET"
echo ""

# Test 1: List buckets
echo "Test 1: List Buckets"
echo "---------------------------------------------------"
python3 <<EOF
import boto3
import os
from botocore.exceptions import ClientError

# Use CA bundle - prefer cert.pem (Alpine's default) or fallback to ca-certificates.crt
# Also try Sidekick CA directly if available
if os.path.exists('/certs/ca.crt'):
    ca_bundle = '/certs/ca.crt'  # Use Sidekick CA directly
elif os.path.exists('/etc/ssl/cert.pem'):
    ca_bundle = '/etc/ssl/cert.pem'
elif os.path.exists('/etc/ssl/certs/ca-certificates.crt'):
    ca_bundle = '/etc/ssl/certs/ca-certificates.crt'
else:
    ca_bundle = True  # Fallback to system default

s3 = boto3.client(
    's3',
    endpoint_url='$S3_ENDPOINT',
    aws_access_key_id='$S3_ACCESS_KEY',
    aws_secret_access_key='$S3_SECRET_KEY',
    verify=ca_bundle
)

try:
    response = s3.list_buckets()
    buckets = [b['Name'] for b in response.get('Buckets', [])]
    print(f"✅ Success: Found {len(buckets)} bucket(s)")
    for bucket in buckets:
        print(f"   - {bucket}")
except Exception as e:
    print(f"❌ Failed: {e}")
    exit(1)
EOF

# Test 2: Create bucket (if doesn't exist)
echo ""
echo "Test 2: Create Bucket (if needed)"
echo "---------------------------------------------------"
python3 <<EOF
import boto3
import os
from botocore.exceptions import ClientError

# Use CA bundle - prefer cert.pem (Alpine's default) or fallback to ca-certificates.crt
# Also try Sidekick CA directly if available
if os.path.exists('/certs/ca.crt'):
    ca_bundle = '/certs/ca.crt'  # Use Sidekick CA directly
elif os.path.exists('/etc/ssl/cert.pem'):
    ca_bundle = '/etc/ssl/cert.pem'
elif os.path.exists('/etc/ssl/certs/ca-certificates.crt'):
    ca_bundle = '/etc/ssl/certs/ca-certificates.crt'
else:
    ca_bundle = True  # Fallback to system default

s3 = boto3.client(
    's3',
    endpoint_url='$S3_ENDPOINT',
    aws_access_key_id='$S3_ACCESS_KEY',
    aws_secret_access_key='$S3_SECRET_KEY',
    verify=ca_bundle
)

try:
    s3.head_bucket(Bucket='$S3_BUCKET')
    print(f"✅ Bucket '$S3_BUCKET' already exists")
except ClientError as e:
    if e.response['Error']['Code'] == '404':
        try:
            s3.create_bucket(Bucket='$S3_BUCKET')
            print(f"✅ Created bucket '$S3_BUCKET'")
        except Exception as e2:
            print(f"❌ Failed to create bucket: {e2}")
            exit(1)
    else:
        print(f"❌ Error checking bucket: {e}")
        exit(1)
EOF

# Test 3: Upload object
echo ""
echo "Test 3: Upload Object"
echo "---------------------------------------------------"
TEST_KEY="test-object.txt"
TEST_CONTENT="Hello from Sidekick HTTPS test! $(date)"

python3 <<EOF
import boto3
import os

# Use CA bundle - prefer cert.pem (Alpine's default) or fallback to ca-certificates.crt
# Also try Sidekick CA directly if available
if os.path.exists('/certs/ca.crt'):
    ca_bundle = '/certs/ca.crt'  # Use Sidekick CA directly
elif os.path.exists('/etc/ssl/cert.pem'):
    ca_bundle = '/etc/ssl/cert.pem'
elif os.path.exists('/etc/ssl/certs/ca-certificates.crt'):
    ca_bundle = '/etc/ssl/certs/ca-certificates.crt'
else:
    ca_bundle = True  # Fallback to system default

s3 = boto3.client(
    's3',
    endpoint_url='$S3_ENDPOINT',
    aws_access_key_id='$S3_ACCESS_KEY',
    aws_secret_access_key='$S3_SECRET_KEY',
    verify=ca_bundle
)

try:
    s3.put_object(
        Bucket='$S3_BUCKET',
        Key='$TEST_KEY',
        Body='$TEST_CONTENT'.encode('utf-8')
    )
    print(f"✅ Uploaded: s3://$S3_BUCKET/$TEST_KEY")
    print(f"   Content: $TEST_CONTENT")
except Exception as e:
    print(f"❌ Upload failed: {e}")
    exit(1)
EOF

# Test 4: List objects
echo ""
echo "Test 4: List Objects"
echo "---------------------------------------------------"
python3 <<EOF
import boto3
import os

# Use CA bundle - prefer cert.pem (Alpine's default) or fallback to ca-certificates.crt
# Also try Sidekick CA directly if available
if os.path.exists('/certs/ca.crt'):
    ca_bundle = '/certs/ca.crt'  # Use Sidekick CA directly
elif os.path.exists('/etc/ssl/cert.pem'):
    ca_bundle = '/etc/ssl/cert.pem'
elif os.path.exists('/etc/ssl/certs/ca-certificates.crt'):
    ca_bundle = '/etc/ssl/certs/ca-certificates.crt'
else:
    ca_bundle = True  # Fallback to system default

s3 = boto3.client(
    's3',
    endpoint_url='$S3_ENDPOINT',
    aws_access_key_id='$S3_ACCESS_KEY',
    aws_secret_access_key='$S3_SECRET_KEY',
    verify=ca_bundle
)

try:
    response = s3.list_objects_v2(Bucket='$S3_BUCKET', MaxKeys=10)
    count = response.get('KeyCount', 0)
    print(f"✅ Success: Found {count} object(s) in bucket")
    if count > 0:
        for obj in response.get('Contents', []):
            size = obj['Size']
            print(f"   - {obj['Key']} ({size} bytes)")
except Exception as e:
    print(f"❌ Failed: {e}")
    exit(1)
EOF

# Test 5: Download object
echo ""
echo "Test 5: Download Object"
echo "---------------------------------------------------"
python3 <<EOF
import boto3
import os

# Use CA bundle - prefer cert.pem (Alpine's default) or fallback to ca-certificates.crt
# Also try Sidekick CA directly if available
if os.path.exists('/certs/ca.crt'):
    ca_bundle = '/certs/ca.crt'  # Use Sidekick CA directly
elif os.path.exists('/etc/ssl/cert.pem'):
    ca_bundle = '/etc/ssl/cert.pem'
elif os.path.exists('/etc/ssl/certs/ca-certificates.crt'):
    ca_bundle = '/etc/ssl/certs/ca-certificates.crt'
else:
    ca_bundle = True  # Fallback to system default

s3 = boto3.client(
    's3',
    endpoint_url='$S3_ENDPOINT',
    aws_access_key_id='$S3_ACCESS_KEY',
    aws_secret_access_key='$S3_SECRET_KEY',
    verify=ca_bundle
)

try:
    response = s3.get_object(Bucket='$S3_BUCKET', Key='$TEST_KEY')
    content = response['Body'].read().decode('utf-8')
    print(f"✅ Downloaded: s3://$S3_BUCKET/$TEST_KEY")
    print(f"   Content: {content}")
    
    if content == '$TEST_CONTENT':
        print("   ✅ Content matches original")
    else:
        print("   ❌ Content mismatch!")
        exit(1)
except Exception as e:
    print(f"❌ Download failed: {e}")
    exit(1)
EOF

# Test 6: Delete object (cleanup)
echo ""
echo "Test 6: Delete Object (cleanup)"
echo "---------------------------------------------------"
python3 <<EOF
import boto3
import os

# Use CA bundle - prefer cert.pem (Alpine's default) or fallback to ca-certificates.crt
# Also try Sidekick CA directly if available
if os.path.exists('/certs/ca.crt'):
    ca_bundle = '/certs/ca.crt'  # Use Sidekick CA directly
elif os.path.exists('/etc/ssl/cert.pem'):
    ca_bundle = '/etc/ssl/cert.pem'
elif os.path.exists('/etc/ssl/certs/ca-certificates.crt'):
    ca_bundle = '/etc/ssl/certs/ca-certificates.crt'
else:
    ca_bundle = True  # Fallback to system default

s3 = boto3.client(
    's3',
    endpoint_url='$S3_ENDPOINT',
    aws_access_key_id='$S3_ACCESS_KEY',
    aws_secret_access_key='$S3_SECRET_KEY',
    verify=ca_bundle
)

try:
    s3.delete_object(Bucket='$S3_BUCKET', Key='$TEST_KEY')
    print(f"✅ Deleted: s3://$S3_BUCKET/$TEST_KEY")
except Exception as e:
    print(f"⚠️  Cleanup failed: {e}")
EOF

echo ""
echo "============================================================"
echo "✅ All Tests Completed Successfully!"
echo "============================================================"
echo "Sidekick HTTPS frontend is working correctly."
echo "  - HTTPS connection established"
echo "  - Certificate validation passed"
echo "  - S3 operations successful"
echo "============================================================"

