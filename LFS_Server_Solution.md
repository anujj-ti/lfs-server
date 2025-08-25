# Git LFS Server with S3 Backend

## Architecture

```
Git Client ←→ LFS Server ←→ S3 Bucket (Versioned)
                ↓
            Database Mapping
```

**Flow**: Git LFS calculates SHA256 → Server maps to folder path → S3 stores with version ID

## Storage Strategy

### Standard LFS (Hash-based)
```
S3: lfs-objects/ab/cd1234567890abcdef...
❌ Unreadable paths, no folder structure
```

### Folder-based + Versioning
```
S3: documents/contracts/lease.pdf
✅ Readable paths, folder organization, version preservation, can easily host through cloudfront
```

## Implementation Overview

### LFS Server Requirements
```
Endpoints:
  POST /<repo>/objects/batch  → Return upload/download URLs
  PUT  /<repo>/objects/<oid>  → Upload file to S3
  GET  /<repo>/objects/<oid>  → Download file from S3

Process:
  1. Scan lfs_storage/ directory to find file path by OID
  2. Upload to S3 using folder path (not hash path)
  3. Store OID → {path, version_id} mapping
  4. Download using stored version_id for exact history
```

### Key Requirements
- **S3 versioning enabled** (preserves file history)
- **OID mapping** to folder paths and S3 version IDs
- **File scanning** of lfs_storage/ directory structure

## Version Mapping Storage

Store OID → S3 location mapping:

```json
{
  "sha256_hash": {
    "path": "folder/subfolder/file.ext",
    "version_id": "s3_version_id"
  }
}
```

**Development**: JSON file  
**Production**: Database (DynamoDB, PostgreSQL, Redis)

### Configuration Files
```
.lfsconfig: Point to your LFS server URL
.gitattributes: Track folders/extensions with LFS
.gitignore: Exclude mapping files and credentials
```

### Team Workflow
Standard Git workflow - no changes needed!  
Files upload to your S3, appear as pointers in GitHub

## How Versioning Works

### File Upload
1. Git LFS calculates SHA256 hash (OID) for file
2. Server finds file path in lfs_storage/ directory
3. Upload to S3 using folder path → S3 returns version_id  
4. Store mapping: OID → {path, version_id}

### File Updates
1. File edit → NEW OID (different hash)
2. Upload to SAME S3 path → NEW version_id
3. Store NEW mapping: NEW_OID → {path, new_version_id}
4. Both versions preserved in S3

### Git History
`git checkout HEAD~1` → Git needs old OID → Server returns old version_id → Download exact historical version from S3

## Why Build This

- **Readable S3 paths**: `documents/contract.pdf` vs `ab/cd1234...`
- **Cost savings**: Cheaper than GitHub LFS
- **Folder organization**: Maintain logical file structure  
- **Team workflow**: Zero changes to `git push/pull`

## Production Considerations

### Security
- Add authentication to LFS server endpoints
- Private S3 bucket (LFS server acts as proxy)
- IAM roles with minimal permissions

### Monitoring
- Upload/download success rates
- S3 storage usage and costs
- Database performance metrics
- Error rates and response times

### Backup
- S3 versioning (built-in file history)  
- Database backups (DynamoDB point-in-time recovery)
- Cross-region replication for disaster recovery
