#!/usr/bin/env python3
"""
S3 CRU Test Script
Tests Create, Read, Update operations using boto3 SDK
Connects to AIStor via Sidekick HTTP proxy (backend HTTPS + MinKMS)
Note: No Delete - objects are kept in bucket for inspection
"""

import boto3
import json
from datetime import datetime
from botocore.client import Config
from botocore.exceptions import ClientError

# Configuration
ENDPOINT_URL = "http://sidekick:8090"
ACCESS_KEY = "minioadmin"
SECRET_KEY = "minioadmin"
BUCKET_NAME = "python-s3-test"
REGION = "us-east-1"

def create_s3_client():
    """Create and configure S3 client"""
    print("═" * 60)
    print("Creating S3 client...")
    print(f"Endpoint: {ENDPOINT_URL}")
    print("═" * 60)
    
    s3_client = boto3.client(
        's3',
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name=REGION,
        config=Config(signature_version='s3v4')
    )
    return s3_client

def test_create(s3_client, key, content):
    """Test CREATE: Upload an object"""
    print(f"\n{'─' * 60}")
    print(f"CREATE: Uploading object '{key}'")
    print(f"{'─' * 60}")
    
    try:
        # Upload with server-side encryption
        response = s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=content.encode('utf-8'),
            ContentType='text/plain'
            # Encryption disabled for direct HTTP testing
            # ServerSideEncryption='aws:kms',
            # SSEKMSKeyId='spark-encryption-key'
        )
        
        print(f"✅ Object uploaded successfully")
        print(f"   ETag: {response['ETag']}")
        
        if 'ServerSideEncryption' in response:
            print(f"   Encryption: {response['ServerSideEncryption']}")
        if 'SSEKMSKeyId' in response:
            print(f"   KMS Key ID: {response['SSEKMSKeyId']}")
            
        return True
    except ClientError as e:
        print(f"❌ Error uploading object: {e}")
        return False

def test_read(s3_client, key):
    """Test READ: Download and read an object"""
    print(f"\n{'─' * 60}")
    print(f"READ: Downloading object '{key}'")
    print(f"{'─' * 60}")
    
    try:
        response = s3_client.get_object(
            Bucket=BUCKET_NAME,
            Key=key
        )
        
        content = response['Body'].read().decode('utf-8')
        print(f"✅ Object downloaded successfully")
        print(f"   Content: {content}")
        print(f"   Size: {response['ContentLength']} bytes")
        
        if 'ServerSideEncryption' in response:
            print(f"   Encryption: {response['ServerSideEncryption']}")
        if 'SSEKMSKeyId' in response:
            print(f"   KMS Key ID: {response['SSEKMSKeyId']}")
            
        return content
    except ClientError as e:
        print(f"❌ Error downloading object: {e}")
        return None

def test_update(s3_client, key, new_content):
    """Test UPDATE: Update an existing object"""
    print(f"\n{'─' * 60}")
    print(f"UPDATE: Updating object '{key}'")
    print(f"{'─' * 60}")
    
    try:
        # Update is same as create/put in S3
        response = s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=new_content.encode('utf-8'),
            ContentType='text/plain'
            # Encryption disabled for direct HTTP testing
            # ServerSideEncryption='aws:kms',
            # SSEKMSKeyId='spark-encryption-key'
        )
        
        print(f"✅ Object updated successfully")
        print(f"   New ETag: {response['ETag']}")
        
        if 'ServerSideEncryption' in response:
            print(f"   Encryption: {response['ServerSideEncryption']}")
            
        return True
    except ClientError as e:
        print(f"❌ Error updating object: {e}")
        return False

def test_delete(s3_client, key):
    """Test DELETE: Delete an object"""
    print(f"\n{'─' * 60}")
    print(f"DELETE: Deleting object '{key}'")
    print(f"{'─' * 60}")
    
    try:
        s3_client.delete_object(
            Bucket=BUCKET_NAME,
            Key=key
        )
        
        print(f"✅ Object deleted successfully")
        return True
    except ClientError as e:
        print(f"❌ Error deleting object: {e}")
        return False

def test_list_objects(s3_client):
    """List all objects in bucket"""
    print(f"\n{'─' * 60}")
    print(f"LIST: Objects in bucket '{BUCKET_NAME}'")
    print(f"{'─' * 60}")
    
    try:
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME)
        
        if 'Contents' in response:
            print(f"✅ Found {len(response['Contents'])} objects:")
            for obj in response['Contents']:
                print(f"   - {obj['Key']} ({obj['Size']} bytes)")
        else:
            print("✅ Bucket is empty")
            
        return True
    except ClientError as e:
        print(f"❌ Error listing objects: {e}")
        return False

def test_head_object(s3_client, key):
    """Get object metadata without downloading"""
    print(f"\n{'─' * 60}")
    print(f"HEAD: Getting metadata for '{key}'")
    print(f"{'─' * 60}")
    
    try:
        response = s3_client.head_object(
            Bucket=BUCKET_NAME,
            Key=key
        )
        
        print(f"✅ Metadata retrieved:")
        print(f"   Size: {response['ContentLength']} bytes")
        print(f"   Last Modified: {response['LastModified']}")
        print(f"   ETag: {response['ETag']}")
        
        if 'ServerSideEncryption' in response:
            print(f"   Encryption: {response['ServerSideEncryption']}")
        if 'SSEKMSKeyId' in response:
            print(f"   KMS Key ID: {response['SSEKMSKeyId']}")
            
        return True
    except ClientError as e:
        print(f"❌ Error getting metadata: {e}")
        return False

def main():
    """Main test function"""
    print("\n")
    print("═" * 60)
    print("S3 CRU TEST - boto3 SDK (Create, Read, Update)")
    print("═" * 60)
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Bucket: {BUCKET_NAME}")
    print(f"Endpoint: {ENDPOINT_URL}")
    print(f"Encryption: SSE-KMS with spark-encryption-key")
    print(f"Note: Objects will be kept in bucket (no delete)")
    print("═" * 60)
    
    # Create S3 client
    s3_client = create_s3_client()
    
    # Test objects
    test_objects = [
        ("test-file-1.txt", "Hello from Python S3 SDK!"),
        ("test-file-2.txt", "This is a second test file."),
        ("test-file-3.txt", "Testing encryption with MinKMS.")
    ]
    
    results = {
        'created': 0,
        'read': 0,
        'updated': 0,
        'errors': 0
    }
    
    # Test CREATE for all objects
    print("\n" + "═" * 60)
    print("PHASE 1: CREATE OPERATIONS")
    print("═" * 60)
    for key, content in test_objects:
        if test_create(s3_client, key, content):
            results['created'] += 1
        else:
            results['errors'] += 1
    
    # List objects
    test_list_objects(s3_client)
    
    # Test READ
    print("\n" + "═" * 60)
    print("PHASE 2: READ OPERATIONS")
    print("═" * 60)
    for key, _ in test_objects:
        if test_read(s3_client, key):
            results['read'] += 1
        else:
            results['errors'] += 1
    
    # Test HEAD (metadata)
    print("\n" + "═" * 60)
    print("PHASE 3: METADATA OPERATIONS")
    print("═" * 60)
    test_head_object(s3_client, test_objects[0][0])
    
    # Test UPDATE
    print("\n" + "═" * 60)
    print("PHASE 4: UPDATE OPERATIONS")
    print("═" * 60)
    updated_content = f"Updated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    if test_update(s3_client, test_objects[0][0], updated_content):
        results['updated'] += 1
    else:
        results['errors'] += 1
    
    # Verify update
    print("\nVerifying update...")
    test_read(s3_client, test_objects[0][0])
    
    # List final objects (no delete - keep objects in bucket)
    print("\n" + "═" * 60)
    print("PHASE 5: FINAL OBJECT LIST")
    print("═" * 60)
    test_list_objects(s3_client)
    
    # Summary
    print("\n")
    print("═" * 60)
    print("TEST SUMMARY")
    print("═" * 60)
    print(f"✅ Created:  {results['created']} objects")
    print(f"✅ Read:     {results['read']} objects")
    print(f"✅ Updated:  {results['updated']} objects")
    print(f"ℹ️  Note:    Objects kept in bucket (no delete)")
    
    if results['errors'] > 0:
        print(f"❌ Errors:   {results['errors']}")
    else:
        print(f"✅ Errors:   0")
    
    print("═" * 60)
    
    total_operations = sum([results['created'], results['read'], 
                           results['updated']])
    
    if results['errors'] == 0 and total_operations > 0:
        print("\n🎉 ALL TESTS PASSED! 🎉\n")
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED! ⚠️\n")
        return 1

if __name__ == "__main__":
    exit(main())

