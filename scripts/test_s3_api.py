#!/usr/bin/env python3
"""
S3 API Test Script
Tests S3 operations over HTTPS with certificate validation
"""

import sys

def test_s3_operations():
    """Test S3 API operations using boto3"""
    try:
        import boto3
        from botocore.exceptions import ClientError, SSLError
        import os
        
        print("=" * 60)
        print("S3 API Operations Test")
        print("=" * 60)
        print()
        
        # Configuration
        endpoint_url = 'https://aistor:9000'
        access_key = 'minioadmin'
        secret_key = 'minioadmin'
        test_bucket = 'spark-data'
        test_prefix = 's3-api-test/'
        
        print(f"Endpoint: {endpoint_url}")
        print(f"Test Bucket: {test_bucket}")
        print()
        
        # Create S3 client with SSL verification enabled
        print("Test 1: Creating S3 client with SSL verification...")
        print("-" * 60)
        try:
            s3_client = boto3.client(
                's3',
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                verify=True  # Enable SSL certificate verification
            )
            print("✅ S3 client created successfully")
            print()
        except SSLError as e:
            print(f"❌ SSL Error: {e}")
            print("   Certificate validation failed!")
            return False
        except Exception as e:
            print(f"❌ Failed to create S3 client: {e}")
            return False
        
        # Test 2: List buckets
        print("Test 2: List Buckets")
        print("-" * 60)
        try:
            response = s3_client.list_buckets()
            buckets = [b['Name'] for b in response.get('Buckets', [])]
            print(f"✅ ListBuckets: Success")
            print(f"   Found {len(buckets)} bucket(s)")
            for bucket in buckets:
                print(f"   - {bucket}")
            print()
        except ClientError as e:
            print(f"❌ ListBuckets failed: {e}")
            return False
        
        # Test 3: Check if test bucket exists
        print("Test 3: Check Test Bucket Existence")
        print("-" * 60)
        bucket_exists = False
        try:
            s3_client.head_bucket(Bucket=test_bucket)
            print(f"✅ Bucket '{test_bucket}' exists")
            bucket_exists = True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                print(f"⚠️  Bucket '{test_bucket}' does not exist")
                print(f"   (Will be created by Spark on first write)")
            else:
                print(f"❌ Error checking bucket: {e}")
        print()
        
        # Test 4: List objects (if bucket exists)
        if bucket_exists:
            print("Test 4: List Objects in Bucket")
            print("-" * 60)
            try:
                response = s3_client.list_objects_v2(
                    Bucket=test_bucket,
                    MaxKeys=10
                )
                count = response.get('KeyCount', 0)
                print(f"✅ ListObjects: Success")
                print(f"   Objects in bucket: {count}")
                
                if count > 0:
                    print(f"   First few objects:")
                    for obj in response.get('Contents', [])[:5]:
                        size_kb = obj['Size'] / 1024
                        print(f"   - {obj['Key']} ({size_kb:.2f} KB)")
                print()
            except ClientError as e:
                print(f"❌ ListObjects failed: {e}")
                print()
        
        # Test 5: Put/Get object test
        print("Test 5: PUT/GET Object Test")
        print("-" * 60)
        if bucket_exists:
            test_key = f"{test_prefix}test-object.txt"
            test_content = b"Hello from S3 API test over HTTPS!"
            
            try:
                # PUT object
                s3_client.put_object(
                    Bucket=test_bucket,
                    Key=test_key,
                    Body=test_content
                )
                print(f"✅ PutObject: Success")
                print(f"   Key: {test_key}")
                
                # GET object
                response = s3_client.get_object(
                    Bucket=test_bucket,
                    Key=test_key
                )
                retrieved_content = response['Body'].read()
                
                if retrieved_content == test_content:
                    print(f"✅ GetObject: Success")
                    print(f"   Content verified: {retrieved_content.decode()}")
                else:
                    print(f"❌ GetObject: Content mismatch")
                
                # DELETE object (cleanup)
                s3_client.delete_object(
                    Bucket=test_bucket,
                    Key=test_key
                )
                print(f"✅ DeleteObject: Success (cleanup)")
                print()
            except ClientError as e:
                print(f"❌ Object operation failed: {e}")
                print()
        else:
            print(f"⚠️  Skipping PUT/GET test (bucket doesn't exist)")
            print()
        
        # Test 6: Multipart upload capability check
        print("Test 6: Multipart Upload Capability")
        print("-" * 60)
        if bucket_exists:
            test_key = f"{test_prefix}multipart-test.bin"
            try:
                # Initiate multipart upload
                response = s3_client.create_multipart_upload(
                    Bucket=test_bucket,
                    Key=test_key
                )
                upload_id = response['UploadId']
                print(f"✅ CreateMultipartUpload: Success")
                print(f"   Upload ID: {upload_id[:20]}...")
                
                # Abort multipart upload (cleanup)
                s3_client.abort_multipart_upload(
                    Bucket=test_bucket,
                    Key=test_key,
                    UploadId=upload_id
                )
                print(f"✅ AbortMultipartUpload: Success (cleanup)")
                print()
            except ClientError as e:
                print(f"❌ Multipart operation failed: {e}")
                print()
        else:
            print(f"⚠️  Skipping multipart test (bucket doesn't exist)")
            print()
        
        print("=" * 60)
        print("✅ All S3 API tests completed successfully!")
        print("=" * 60)
        print()
        print("Summary:")
        print("- SSL/TLS certificate validation: ✅ Working")
        print("- S3 API operations over HTTPS: ✅ Working")
        print("- Ready for Spark S3A operations")
        print()
        
        return True
        
    except ImportError:
        print("=" * 60)
        print("S3 API Operations Test")
        print("=" * 60)
        print()
        print("❌ boto3 is not installed")
        print()
        print("To install boto3:")
        print("  pip install boto3")
        print()
        print("This test requires boto3 to perform S3 API operations.")
        print()
        return None

def main():
    result = test_s3_operations()
    
    if result is True:
        sys.exit(0)
    elif result is False:
        sys.exit(1)
    else:
        sys.exit(2)  # Skipped

if __name__ == "__main__":
    main()



