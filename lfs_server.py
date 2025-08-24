#!/usr/bin/env python3

import os
import json
import hashlib
from flask import Flask, request, jsonify, send_file
from werkzeug.exceptions import NotFound

app = Flask(__name__)

# Directory to store LFS objects
STORAGE_DIR = "lfs_storage"
os.makedirs(STORAGE_DIR, exist_ok=True)

def get_object_path(oid):
    """Get the file path for an object ID"""
    # Store in subdirectories like Git does: first 2 chars / rest
    return os.path.join(STORAGE_DIR, oid[:2], oid[2:])

def ensure_object_dir(oid):
    """Ensure the directory exists for an object"""
    obj_path = get_object_path(oid)
    os.makedirs(os.path.dirname(obj_path), exist_ok=True)
    return obj_path

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
        obj_path = get_object_path(oid)
        
        print(f"Processing object: {oid}, size: {size}")
        
        if operation == 'download':
            # Check if object exists
            if os.path.exists(obj_path):
                # Return download URL
                response_objects.append({
                    'oid': oid,
                    'size': size,
                    'actions': {
                        'download': {
                            'href': f'http://localhost:8123/{repo_path}/objects/{oid}',
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
                        'href': f'http://localhost:8123/{repo_path}/objects/{oid}',
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
    """Handle object upload"""
    print(f"Upload object: {oid} for repo: {repo_path}")
    
    obj_path = ensure_object_dir(oid)
    
    # Write the uploaded data
    with open(obj_path, 'wb') as f:
        f.write(request.data)
    
    # Verify the uploaded file
    with open(obj_path, 'rb') as f:
        actual_hash = hashlib.sha256(f.read()).hexdigest()
    
    if actual_hash != oid:
        print(f"Hash mismatch! Expected: {oid}, Got: {actual_hash}")
        os.remove(obj_path)
        return jsonify({'error': 'Hash mismatch'}), 400
    
    print(f"Successfully uploaded object: {oid}")
    return '', 200

@app.route('/<path:repo_path>/objects/<oid>', methods=['GET'])
def download_object(repo_path, oid):
    """Handle object download"""
    print(f"Download object: {oid} for repo: {repo_path}")
    
    obj_path = get_object_path(oid)
    
    if not os.path.exists(obj_path):
        print(f"Object not found: {oid}")
        return jsonify({'error': 'Object not found'}), 404
    
    return send_file(obj_path, as_attachment=True, download_name=oid)

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
        'message': 'Simple Git LFS Server',
        'version': '1.0',
        'storage_dir': STORAGE_DIR
    })

if __name__ == '__main__':
    print("Starting simple Git LFS server...")
    print(f"Storage directory: {os.path.abspath(STORAGE_DIR)}")
    print("Server will run at: http://localhost:8123")
    print()
    print("To use with git:")
    print("git config lfs.url http://localhost:8123/myrepo")
    print("git lfs track '*.bin'")
    print()
    
    app.run(host='0.0.0.0', port=8123, debug=True)
