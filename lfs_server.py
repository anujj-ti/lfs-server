#!/usr/bin/env python3

import os
import json
import hashlib
import boto3
from botocore.exceptions import ClientError
from flask import Flask, request, jsonify, Response
import config

app = Flask(__name__)

# Path mapping: OID -> relative file path from lfs_storage/
# This gets populated when files are scanned
path_mapping = {}

# S3 Configuration
s3_client = boto3.client(
    's3',
    aws_access_key_id=config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
    region_name=config.AWS_DEFAULT_REGION
)

BUCKET_NAME = config.S3_BUCKET

def load_path_mapping():
    """Load path mapping from a JSON file"""
    mapping_file = "oid_to_path_mapping.json"
    global path_mapping
    try:
        if os.path.exists(mapping_file):
            with open(mapping_file, 'r') as f:
                path_mapping = json.load(f)
            print(f"📋 Loaded {len(path_mapping)} path mappings")
    except Exception as e:
        print(f"❌ Error loading path mapping: {e}")
        path_mapping = {}

def save_path_mapping():
    """Save path mapping to a JSON file"""
    mapping_file = "oid_to_path_mapping.json"
    try:
        with open(mapping_file, 'w') as f:
            json.dump(path_mapping, f, indent=2)
        print(f"💾 Saved {len(path_mapping)} path mappings")
    except Exception as e:
        print(f"❌ Error saving path mapping: {e}")

def get_file_path_from_local(oid):
    """Find the file path for an OID by scanning lfs_storage directory"""
    lfs_storage_dir = "lfs_storage"
    if not os.path.exists(lfs_storage_dir):
        return None
    
    # Scan all files in lfs_storage and calculate their hashes
    for root, dirs, files in os.walk(lfs_storage_dir):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                    if file_hash == oid:
                        # Return relative path from lfs_storage/
                        relative_path = os.path.relpath(file_path, lfs_storage_dir)
                        return relative_path.replace('\\', '/')  # Normalize path separators
            except Exception as e:
                continue
    return None

def get_s3_key(oid):
    """Get the S3 key for an object ID - uses path mapping for path-based storage"""
    # First try the mapping
    if oid in path_mapping:
        file_path = path_mapping[oid]
        print(f"📋 Using cached path for {oid[:8]}...: {file_path}")
        return file_path
    
    # If not in mapping, scan lfs_storage directory
    file_path = get_file_path_from_local(oid)
    if file_path:
        # Save this mapping for future use
        path_mapping[oid] = file_path
        save_path_mapping()
        print(f"🔍 Found and cached path for {oid[:8]}...: {file_path}")
        return file_path
    
    # Fallback to old hash-based approach if file not found locally
    fallback_path = f"lfs-objects/{oid[:2]}/{oid[2:]}"
    print(f"⚠️  Using fallback hash-based path for {oid[:8]}...: {fallback_path}")
    return fallback_path

def object_exists_in_s3(oid):
    """Check if object exists in S3"""
    s3_key = get_s3_key(oid)
    print(f"🔍 Checking if object exists in S3: {s3_key}")
    try:
        s3_client.head_object(Bucket=BUCKET_NAME, Key=s3_key)
        print(f"✅ Object exists in S3: {s3_key}")
        return True
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == '404':
            print(f"📭 Object not found in S3: {s3_key}")
        else:
            print(f"❌ Error checking S3 object: {e}")
        return False

def upload_to_s3(oid, data):
    """Upload object to S3"""
    s3_key = get_s3_key(oid)
    print(f"🔄 Uploading to S3: {s3_key} ({len(data)} bytes)")
    try:
        response = s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=data,
            ContentType='application/octet-stream'
        )
        print(f"✅ S3 upload successful: {response.get('ETag', 'No ETag')}")
        return True
    except ClientError as e:
        print(f"❌ Error uploading to S3: {e}")
        print(f"Error code: {e.response.get('Error', {}).get('Code', 'Unknown')}")
        print(f"Error message: {e.response.get('Error', {}).get('Message', 'Unknown')}")
        return False

def download_from_s3(oid):
    """Download object from S3"""
    s3_key = get_s3_key(oid)
    print(f"🔄 Downloading from S3: {s3_key}")
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        data = response['Body'].read()
        print(f"✅ S3 download successful: {len(data)} bytes")
        return data
    except ClientError as e:
        print(f"❌ Error downloading from S3: {e}")
        print(f"Error code: {e.response.get('Error', {}).get('Code', 'Unknown')}")
        return None

@app.route('/<path:repo_path>/objects/batch', methods=['POST'])
def batch_objects(repo_path):
    """Handle Git LFS batch API requests"""
    print(f"Batch request for repo: {repo_path}")
    
    data = request.get_json()
    operation = data.get('operation', 'download')
    objects = data.get('objects', [])
    
    print(f"Operation: {operation}, Objects: {len(objects)}")
    
    response_objects = []
    
    for obj in objects:
        oid = obj['oid']
        size = obj['size']
        
        print(f"Processing object: {oid}, size: {size}")
        s3_key = get_s3_key(oid)
        print(f"  📁 S3 path will be: {s3_key}")
        
        if operation == 'download':
            # Check if object exists in S3
            if object_exists_in_s3(oid):
                # Return download URL (using our server endpoint)
                response_objects.append({
                    'oid': oid,
                    'size': size,
                    'actions': {
                        'download': {
                            'href': f'https://bf921069a201.ngrok-free.app/{repo_path}/objects/{oid}',
                            'header': {},
                            'expires_in': 3600
                        }
                    }
                })
            else:
                # Object not found
                response_objects.append({
                    'oid': oid,
                    'size': size,
                    'error': {
                        'code': 404,
                        'message': 'Object not found'
                    }
                })
        
        elif operation == 'upload':
            # Always allow upload
            response_objects.append({
                'oid': oid,
                'size': size,
                'actions': {
                    'upload': {
                        'href': f'https://bf921069a201.ngrok-free.app/{repo_path}/objects/{oid}',
                        'header': {},
                        'expires_in': 3600
                    }
                }
            })
    
    response = {
        'transfer': 'basic',
        'objects': response_objects
    }
    
    return jsonify(response)

@app.route('/<path:repo_path>/objects/<oid>', methods=['PUT'])
def upload_object(repo_path, oid):
    """Handle object upload to S3"""
    print(f"Upload object: {oid} for repo: {repo_path}")
    
    # Get the uploaded data
    uploaded_data = request.data
    
    # Verify the hash
    actual_hash = hashlib.sha256(uploaded_data).hexdigest()
    
    if actual_hash != oid:
        print(f"Hash mismatch! Expected: {oid}, Got: {actual_hash}")
        return jsonify({'error': 'Hash mismatch'}), 400
    
    # Upload to S3
    if upload_to_s3(oid, uploaded_data):
        print(f"Successfully uploaded object: {oid} to S3")
        return '', 200
    else:
        print(f"Failed to upload object: {oid} to S3")
        return jsonify({'error': 'Upload failed'}), 500

@app.route('/<path:repo_path>/objects/<oid>', methods=['GET'])
def download_object(repo_path, oid):
    """Handle object download from S3"""
    print(f"Download object: {oid} for repo: {repo_path}")
    
    # Download from S3
    data = download_from_s3(oid)
    
    if data is None:
        print(f"Object not found: {oid}")
        return jsonify({'error': 'Object not found'}), 404
    
    # Return the data as a response
    return Response(
        data,
        mimetype='application/octet-stream',
        headers={'Content-Disposition': f'attachment; filename={oid}'}
    )

@app.route('/<path:repo_path>/objects', methods=['POST'])  
def legacy_objects(repo_path):
    """Handle legacy single object requests (some clients use this)"""
    print(f"Legacy object request for repo: {repo_path}")
    data = request.get_json()
    
    # Convert to batch format
    batch_data = {
        'operation': 'download',
        'objects': [data]
    }
    
    request._cached_json = batch_data
    return batch_objects(repo_path)

@app.route('/info')
def info():
    """Basic info endpoint"""
    return jsonify({
        'message': 'Path-based S3 Git LFS Server',
        'version': '3.0',
        'storage_backend': 's3',
        'bucket': BUCKET_NAME,
        'region': config.AWS_DEFAULT_REGION,
        'storage_method': 'path-based',
        'tracked_paths': len(path_mapping)
    })

if __name__ == '__main__':
    print("Starting Path-based S3 Git LFS server...")
    print(f"S3 Bucket: {BUCKET_NAME}")
    print(f"AWS Region: {config.AWS_DEFAULT_REGION}")
    print("Storage Method: Path-based (lfs_storage/ → S3)")
    print("Server will run at: http://localhost:8123")
    print()
    print("To use with git:")
    print("git config lfs.url http://localhost:8123/myrepo")
    print("git lfs track 'lfs_storage/**'")
    print()
    
    # Load existing path mappings
    load_path_mapping()
    
    # Test S3 connectivity
    try:
        s3_client.head_bucket(Bucket=BUCKET_NAME)
        print("✅ S3 bucket accessible")
    except ClientError as e:
        print(f"❌ S3 bucket not accessible: {e}")
        print("Please check your AWS credentials and bucket permissions")
    
    print()
    app.run(host='0.0.0.0', port=8123, debug=True)