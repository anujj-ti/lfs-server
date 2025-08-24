# Testing Your S3-Backed Git LFS Server

## Prerequisites
- ✅ Server running: `python lfs_server.py`
- ✅ Git LFS configured: `git config lfs.url http://localhost:8123/lfs-server`
- ✅ File tracking: `git lfs track "*.large"`

## Step-by-Step Testing Guide

### 1. Start the LFS Server
```bash
python lfs_server.py
```
You should see:
```
Starting S3-backed Git LFS server...
S3 Bucket: alpha-learn-content-dev
AWS Region: us-east-1
✅ S3 bucket accessible
Server will run at: http://localhost:8123
```

### 2. Create a Test File
```bash
# Create a large test file
echo "This is my test file - $(date)" > my_test_file.large

# Or create a larger binary file
dd if=/dev/zero of=big_file.large bs=1024 count=100  # 100KB file
```

### 3. Add and Commit (Creates LFS Pointer)
```bash
git add my_test_file.large
git commit -m "Add my test LFS file"
```

**Check the pointer:**
```bash
git show HEAD:my_test_file.large
# Should show:
# version https://git-lfs.github.com/spec/v1
# oid sha256:abc123...
# size 123
```

### 4. Upload to S3 (The Key Step!)
```bash
# This uploads to your LFS server, which stores in S3
git lfs push --all origin main
```

You should see:
```
Uploading LFS objects: 100% (1/1), XXX B | 0 B/s, done.
```

In the server logs, you'll see:
```
🔄 Uploading to S3: lfs-objects/ab/c123... (XX bytes)
✅ S3 upload successful: "abc123def..."
```

### 5. Verify Upload in S3
```bash
python -c "
import boto3, config
s3 = boto3.client('s3', aws_access_key_id=config.AWS_ACCESS_KEY_ID, aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY, region_name=config.AWS_DEFAULT_REGION)
resp = s3.list_objects_v2(Bucket=config.S3_BUCKET, Prefix='lfs-objects/')
if 'Contents' in resp:
    print(f'Found {len(resp[\"Contents\"])} files in S3:')
    for obj in resp['Contents']: print(f'  📁 {obj[\"Key\"]} - {obj[\"Size\"]} bytes')
else: print('No files found')
"
```

### 6. Test Download from S3
```bash
# Delete the local file
rm my_test_file.large

# Download it back from S3 via LFS
git checkout my_test_file.large

# Verify content
cat my_test_file.large
```

In the server logs, you'll see:
```
🔍 Checking if object exists in S3: lfs-objects/ab/c123...
✅ Object exists in S3: lfs-objects/ab/c123...
🔄 Downloading from S3: lfs-objects/ab/c123...
✅ S3 download successful: XX bytes
```

### 7. Check LFS Status
```bash
# List all LFS files
git lfs ls-files

# Check LFS configuration
git config -l | grep lfs
```

## Quick Test Script

Run this for an automated test:
```bash
#!/bin/bash
echo "=== Starting LFS Server Test ==="

# Start server in background
python lfs_server.py &
SERVER_PID=$!
sleep 3

# Create test file
echo "Test file created at $(date)" > auto_test.large

# Add and commit
git add auto_test.large
git commit -m "Automated test file"

# Upload to S3
git lfs push --all origin main

# Test download
rm auto_test.large
git checkout auto_test.large
cat auto_test.large

# Check S3
python -c "import boto3,config; print('Files in S3:', len(boto3.client('s3', aws_access_key_id=config.AWS_ACCESS_KEY_ID, aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY, region_name=config.AWS_DEFAULT_REGION).list_objects_v2(Bucket=config.S3_BUCKET, Prefix='lfs-objects/').get('Contents', [])))"

# Cleanup
kill $SERVER_PID
echo "=== Test Complete ==="
```

## Expected Results

✅ **Upload**: File appears in S3 bucket `alpha-learn-content-dev/lfs-objects/`
✅ **Download**: File restored from S3 when checked out
✅ **Git**: Only LFS pointers stored in Git, not actual files
✅ **Server**: Debug logs show S3 operations working

## Troubleshooting

**Server not starting?**
- Check port 8123 is available: `lsof -i :8123`
- Verify AWS credentials in `config.py`

**Upload not working?**
- Must run `git lfs push` - regular `git push` won't upload LFS files
- Check server logs for S3 errors

**Download not working?**
- Server must be running when you `git checkout`
- Check S3 bucket permissions
