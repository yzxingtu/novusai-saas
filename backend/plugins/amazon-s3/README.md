# S3 Compatible Storage Plugin

Object storage driver for [Amazon S3](https://aws.amazon.com/s3/) and S3-compatible services (AWS, MinIO, Cloudflare R2, Backblaze B2, etc.).

## Features

- **S3 Protocol** — Full S3 API compatibility for upload, download, delete, and list
- **Multi-Provider** — Works with AWS S3, MinIO, Cloudflare R2, Backblaze B2, and any S3-compatible endpoint
- **Signed URLs** — Time-limited presigned URLs for secure file access
- **Custom Endpoint** — Configurable endpoint URL for self-hosted or third-party S3 services
- **Path Style** — Support for both virtual-hosted and path-style addressing

## Configuration

Storage credentials are configured in **Platform Settings → Storage**, not in the plugin config. Required fields:

| Field | Description |
|-------|-------------|
| `access_key` | S3 Access Key ID |
| `secret_key` | S3 Secret Access Key |
| `bucket` | Bucket name |
| `region` | AWS region (e.g. `us-east-1`) |
| `endpoint` | Optional custom endpoint URL (for MinIO/R2/B2) |
| `custom_domain` | Optional CDN domain |
| `use_path_style` | Use path-style addressing (required for MinIO) |

## Architecture

- **Plugin name**: `amazon-s3`
- **Driver code**: `s3`
- **Driver class**: `S3StorageDriver`
- **Capabilities**: `storage:read`, `storage:write`
- **Pricing**: Free

## Dependencies

- `boto3` >= 1.35
