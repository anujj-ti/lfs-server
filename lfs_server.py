#!/usr/bin/env python3

import os
import json
import hashlib
import boto3
from botocore.exceptions import ClientError
from flask import Flask, request, jsonify, Response
import config

app = Flask(__name__)

# S3 versioning mapping: OID -> {path, version_id}
# Stores version information for proper LFS versioning
version_mapping = {}

# S3 Configuration
s3_client = boto3.client(
    's3',
    aws_access_key_id=config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
    region_name=config.AWS_DEFAULT_REGION
)

BUCKET_NAME = config.S3_BUCKET

def load_version_mapping():
    """Load version mapping from a JSON file"""
    mapping_file = "s3_version_mapping.json"
    global version_mapping
    try:
        if os.path.exists(mapping_file):
            with open(mapping_file, 'r') as f:
                version_mapping = json.load(f)
            print(f"📋 Loaded {len(version_mapping)} S3 version mappings")
    except Exception as e:
        print(f"❌ Error loading version mapping: {e}")
        version_mapping = {}

def save_version_mapping():
    """Save version mapping to a JSON file"""
    mapping_file = "s3_version_mapping.json"
    try:
        with open(mapping_file, 'w') as f:
            json.dump(version_mapping, f, indent=2)
        print(f"💾 Saved {len(version_mapping)} S3 version mappings")
    except Exception as e:
        print(f"❌ Error saving version mapping: {e}")

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
    """Get the S3 key for an object ID - uses only folder structure paths"""
    # Check if we have version mapping for this OID
    if oid in version_mapping:
        s3_path = version_mapping[oid]['path']
        print(f"📋 Using versioned path for {oid[:8]}...: {s3_path}")
        return s3_path
    
    # Try to find the file in lfs_storage directory to determine path
    file_path = get_file_path_from_local(oid)
    if file_path:
        print(f"🔍 Found local file for {oid[:8]}...: {file_path}")
        return file_path
    
    # No hash-based fallback - file must be in lfs_storage structure
    print(f"❌ Object {oid[:8]}... not found in lfs_storage/ directory")
    return None

def object_exists_in_s3(oid):
    """Check if object exists in S3"""
    s3_key = get_s3_key(oid)
    if s3_key is None:
        print(f"❌ Cannot check S3 - no valid path for {oid[:8]}...")
        return False
        
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
    """Upload object to S3 with versioning support"""
    s3_key = get_s3_key(oid)
    if s3_key is None:
        print(f"❌ Cannot upload - no valid path for {oid[:8]}...")
        return False
        
    print(f"🔄 Uploading to S3: {s3_key} ({len(data)} bytes)")
    try:
        response = s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=data,
            ContentType='application/octet-stream'
        )
        
        # Capture S3 version ID for proper versioning
        version_id = response.get('VersionId')
        etag = response.get('ETag', 'No ETag')
        
        # Store version mapping
        version_mapping[oid] = {
            'path': s3_key,
            'version_id': version_id,
            'etag': etag
        }
        save_version_mapping()
        
        print(f"✅ S3 upload successful: {etag} (Version: {version_id})")
        return True
    except ClientError as e:
        print(f"❌ Error uploading to S3: {e}")
        print(f"Error code: {e.response.get('Error', {}).get('Code', 'Unknown')}")
        print(f"Error message: {e.response.get('Error', {}).get('Message', 'Unknown')}")
        return False

def download_from_s3(oid):
    """Download object from S3 with version support"""
    s3_key = get_s3_key(oid)
    if s3_key is None:
        print(f"❌ Cannot download - no valid path for {oid[:8]}...")
        return None
    
    # Get version info if available
    version_info = version_mapping.get(oid)
    version_id = version_info.get('version_id') if version_info else None
    
    print(f"🔄 Downloading from S3: {s3_key} (Version: {version_id or 'latest'})")
    
    try:
        # Download specific version if available
        if version_id:
            response = s3_client.get_object(
                Bucket=BUCKET_NAME, 
                Key=s3_key, 
                VersionId=version_id
            )
        else:
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
        if s3_key:
            print(f"  📁 S3 path will be: {s3_key}")
        else:
            print(f"  ❌ No valid S3 path for {oid[:8]}...")
        
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
        'message': 'S3 Versioned Git LFS Server',
        'version': '4.0',
        'storage_backend': 's3',
        'bucket': BUCKET_NAME,
        'region': config.AWS_DEFAULT_REGION,
        'storage_method': 'folder-based with S3 versioning',
        'versioned_objects': len(version_mapping)
    })

if __name__ == '__main__':
    print("Starting S3 Versioned Git LFS server...")
    print(f"S3 Bucket: {BUCKET_NAME}")
    print(f"AWS Region: {config.AWS_DEFAULT_REGION}")
    print("Storage Method: Folder-based with S3 versioning")
    print("Server will run at: http://localhost:8123")
    print("Public URL: https://bf921069a201.ngrok-free.app")
    print()
    print("To use with git:")
    print("git config lfs.url https://bf921069a201.ngrok-free.app/lfs-server")
    print("git lfs track 'lfs_storage/**'")
    print()
    
    # Load existing version mappings
    load_version_mapping()
    
    # Test S3 connectivity
    try:
        s3_client.head_bucket(Bucket=BUCKET_NAME)
        print("✅ S3 bucket accessible")
    except ClientError as e:
        print(f"❌ S3 bucket not accessible: {e}")
        print("Please check your AWS credentials and bucket permissions")
    
    print()
    app.run(host='0.0.0.0', port=8123, debug=True)