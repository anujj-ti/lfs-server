# Simple Git LFS Server

A minimal Git LFS server for local testing and development.

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python lfs_server.py
```

The server will start at `http://localhost:8123`

## Usage with Git

1. In your Git repo, configure LFS to use this server:
```bash
git config lfs.url http://localhost:8123/myrepo
```

2. Track large files:
```bash
git lfs track "*.bin" 
git add .gitattributes
```

3. Add and commit large files normally - they'll be stored on the LFS server

## How it works

- The server implements the Git LFS batch API
- Files are stored locally in the `lfs_storage/` directory
- Uses SHA256 hashes for file integrity
- Supports both upload and download operations

## Endpoints

- `POST /{repo}/objects/batch` - Main LFS batch API
- `PUT /{repo}/objects/{oid}` - Upload objects  
- `GET /{repo}/objects/{oid}` - Download objects
- `GET /info` - Server info
