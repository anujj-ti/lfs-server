# S3-Backed LFS Files

Our large files are stored in Amazon S3 instead of GitHub LFS:

## my_personal_test.large
- **Direct URL**: https://alpha-learn-content-dev.s3.us-east-1.amazonaws.com/lfs-objects/2e/6618b11e11fe4e6f3322460354553bef9530459e0e90e3dd20a4f5ab23e0aa
- **Size**: 52 bytes
- **Download**: `curl "https://alpha-learn-content-dev.s3.us-east-1.amazonaws.com/lfs-objects/2e/6618b11e11fe4e6f3322460354553bef9530459e0e90e3dd20a4f5ab23e0aa" -o my_personal_test.large`

## debug_test.large
- **Direct URL**: https://alpha-learn-content-dev.s3.us-east-1.amazonaws.com/lfs-objects/7e/14fb8c794ac94c1e3cf6350556ca9c4d538e26c45eba6b8c2145ed26eaac83
- **Size**: 56 bytes

## test_s3.large
- **Direct URL**: https://alpha-learn-content-dev.s3.us-east-1.amazonaws.com/lfs-objects/60/7af587c38d2dd600710b5dfab2eb8a6365c93d4b36a2b00f91783b43bce844
- **Size**: 122 bytes

## test_large.large
- **Direct URL**: https://alpha-learn-content-dev.s3.us-east-1.amazonaws.com/lfs-objects/a1/22c151077610d63f147c81bf3081670010b46449a7e93e08ca9bc4793d1526
- **Size**: 156 bytes

## test.bin
- **Direct URL**: https://alpha-learn-content-dev.s3.us-east-1.amazonaws.com/lfs-objects/d7/5d76a1fd55949853cafed45942e8c7d717edd29126713c89654f4f14deb0b3
- **Size**: 21 bytes

## How to Download Any File
```bash
# Replace {URL} with the direct URL above
curl "{URL}" -o filename

# Or using AWS CLI
aws s3 cp s3://alpha-learn-content-dev/lfs-objects/{path} filename
```

## S3 Bucket Info
- **Bucket**: alpha-learn-content-dev
- **Region**: us-east-1
- **Prefix**: lfs-objects/

## workflow_test.large (NEW!)
- **Direct URL**: https://alpha-learn-content-dev.s3.us-east-1.amazonaws.com/lfs-objects/95/67dffb62c0736f47d699567057de851bd8a4fe9b552b8ad321ba04a03497fe
- **Size**: 73 bytes
- **Hash**: 9567dffb62c0736f47d699567057de851bd8a4fe9b552b8ad321ba04a03497fe
- **Download**: `curl "https://alpha-learn-content-dev.s3.us-east-1.amazonaws.com/lfs-objects/95/67dffb62c0736f47d699567057de851bd8a4fe9b552b8ad321ba04a03497fe" -o workflow_test.large`
- **Content**: Full S3-GitHub workflow test file
