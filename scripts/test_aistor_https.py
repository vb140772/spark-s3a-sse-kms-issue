#!/usr/bin/env python3
"""
Test script to verify HTTPS connectivity from Spark to AIStor
Tests SSL/TLS certificate validation and S3 API functionality
"""

import sys
import ssl
import socket
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

def test_dns_resolution():
    """Test 1: DNS resolution for aistor hostname"""
    print("=" * 60)
    print("Test 1: DNS Resolution")
    print("=" * 60)
    try:
        ip = socket.gethostbyname('aistor')
        print(f"✅ DNS Resolution: aistor resolves to {ip}")
        return True
    except socket.gaierror as e:
        print(f"❌ DNS Resolution Failed: {e}")
        return False

def test_tcp_connection():
    """Test 2: TCP connection to AIStor on port 9000"""
    print("\n" + "=" * 60)
    print("Test 2: TCP Connection")
    print("=" * 60)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('aistor', 9000))
        sock.close()
        if result == 0:
            print("✅ TCP Connection: Successfully connected to aistor:9000")
            return True
        else:
            print(f"❌ TCP Connection Failed: Error code {result}")
            return False
    except Exception as e:
        print(f"❌ TCP Connection Failed: {e}")
        return False

def test_ssl_handshake():
    """Test 3: SSL/TLS handshake and certificate validation"""
    print("\n" + "=" * 60)
    print("Test 3: SSL/TLS Handshake & Certificate")
    print("=" * 60)
    try:
        # Create SSL context with default verification
        context = ssl.create_default_context()
        
        # Connect and perform SSL handshake
        with socket.create_connection(('aistor', 9000), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname='aistor') as ssock:
                print(f"✅ SSL/TLS Handshake: Success")
                print(f"   Protocol: {ssock.version()}")
                print(f"   Cipher: {ssock.cipher()[0]}")
                
                # Get certificate info
                cert = ssock.getpeercert()
                print(f"   Certificate Subject: {dict(x[0] for x in cert['subject'])}")
                print(f"   Certificate Issuer: {dict(x[0] for x in cert['issuer'])}")
                return True
    except ssl.SSLError as e:
        print(f"❌ SSL/TLS Error: {e}")
        return False
    except Exception as e:
        print(f"❌ SSL Connection Failed: {e}")
        return False

def test_https_endpoint():
    """Test 4: HTTPS endpoint accessibility"""
    print("\n" + "=" * 60)
    print("Test 4: HTTPS Endpoint (MinIO Health Check)")
    print("=" * 60)
    try:
        # Try to access MinIO health endpoint
        url = "https://aistor:9000/minio/health/live"
        req = Request(url, method='GET')
        
        with urlopen(req, timeout=10) as response:
            status = response.status
            print(f"✅ HTTPS Endpoint: Accessible (HTTP {status})")
            return True
    except HTTPError as e:
        # Some status codes are OK (like 403 if auth is required)
        if e.code in [200, 403]:
            print(f"✅ HTTPS Endpoint: Accessible (HTTP {e.code})")
            return True
        else:
            print(f"❌ HTTPS Request Failed: HTTP {e.code}")
            return False
    except URLError as e:
        print(f"❌ HTTPS Request Failed: {e.reason}")
        return False
    except Exception as e:
        print(f"❌ HTTPS Request Failed: {e}")
        return False

def test_s3_with_boto3():
    """Test 5: S3 API with boto3 (if available)"""
    print("\n" + "=" * 60)
    print("Test 5: S3 API with boto3")
    print("=" * 60)
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        # Create S3 client
        s3_client = boto3.client(
            's3',
            endpoint_url='https://aistor:9000',
            aws_access_key_id='minioadmin',
            aws_secret_access_key='minioadmin',
            verify=True  # Use system CA certificates
        )
        
        # Try to list buckets
        response = s3_client.list_buckets()
        buckets = [bucket['Name'] for bucket in response.get('Buckets', [])]
        print(f"✅ S3 API: Connected successfully")
        print(f"   Buckets found: {len(buckets)}")
        if buckets:
            print(f"   Bucket names: {', '.join(buckets)}")
        return True
        
    except ImportError:
        print("⚠️  boto3 not installed (skipping)")
        return None
    except ClientError as e:
        print(f"❌ S3 API Error: {e}")
        return False
    except Exception as e:
        print(f"❌ S3 API Failed: {e}")
        return False

def test_java_truststore():
    """Test 6: Check if CA cert is in Java truststore"""
    print("\n" + "=" * 60)
    print("Test 6: Java Truststore Verification")
    print("=" * 60)
    try:
        import subprocess
        import os
        
        # Find Java home
        java_home = os.environ.get('JAVA_HOME')
        if not java_home:
            # Try to find it from java executable
            result = subprocess.run(['which', 'java'], capture_output=True, text=True)
            if result.returncode == 0:
                java_path = result.stdout.strip()
                java_home = os.path.dirname(os.path.dirname(os.path.realpath(java_path)))
        
        if not java_home:
            print("⚠️  JAVA_HOME not found")
            return None
        
        truststore_path = os.path.join(java_home, 'lib', 'security', 'cacerts')
        print(f"   Java Home: {java_home}")
        print(f"   Truststore: {truststore_path}")
        
        # Check if our CA is in the truststore
        result = subprocess.run(
            ['keytool', '-list', '-keystore', truststore_path, '-storepass', 'changeit', '-alias', 'minio-ca'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Java Truststore: minio-ca certificate found")
            # Print certificate details
            for line in result.stdout.split('\n')[:5]:
                if line.strip():
                    print(f"   {line.strip()}")
            return True
        else:
            print("❌ Java Truststore: minio-ca certificate NOT found")
            return False
            
    except Exception as e:
        print(f"⚠️  Java Truststore check failed: {e}")
        return None

def main():
    print("\n" + "=" * 60)
    print("AIStor HTTPS Connectivity Test Suite")
    print("Testing from Spark container to AIStor over HTTPS")
    print("=" * 60 + "\n")
    
    results = {}
    
    # Run all tests
    results['DNS Resolution'] = test_dns_resolution()
    results['TCP Connection'] = test_tcp_connection()
    results['SSL/TLS Handshake'] = test_ssl_handshake()
    results['HTTPS Endpoint'] = test_https_endpoint()
    results['S3 API'] = test_s3_with_boto3()
    results['Java Truststore'] = test_java_truststore()
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    
    for test_name, result in results.items():
        if result is True:
            print(f"✅ {test_name}: PASSED")
        elif result is False:
            print(f"❌ {test_name}: FAILED")
        else:
            print(f"⚠️  {test_name}: SKIPPED")
    
    print("\n" + "=" * 60)
    print(f"Total: {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 60 + "\n")
    
    # Exit with appropriate code
    if failed > 0:
        print("❌ Some tests failed. HTTPS connection may not work properly.")
        sys.exit(1)
    elif passed == 0:
        print("⚠️  No tests passed. Cannot verify HTTPS connectivity.")
        sys.exit(2)
    else:
        print("✅ All critical tests passed. HTTPS connection is working!")
        sys.exit(0)

if __name__ == "__main__":
    main()



