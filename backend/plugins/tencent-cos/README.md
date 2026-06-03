# Tencent Cloud COS Storage Plugin

Object storage driver for [Tencent Cloud COS](https://cloud.tencent.com/product/cos), with native imageMogr2 image processing support.

## Features

- **Object Storage** — Upload, download, delete, and list files via Tencent Cloud COS
- **Image Processing** — Native imageMogr2 image processing (resize, crop, watermark, format conversion)
- **Signed URLs** — Time-limited presigned URLs for secure file access
- **Custom Domain** — Support for custom CDN domain binding

## Configuration

Storage credentials are configured in **Platform Settings → Storage**, not in the plugin config. Required fields:

| Field | Description |
|-------|-------------|
| `secret_id` | Tencent Cloud SecretId |
| `secret_key` | Tencent Cloud SecretKey |
| `bucket` | COS Bucket name (e.g. `mybucket-1250000000`) |
| `region` | COS region (e.g. `ap-guangzhou`) |
| `custom_domain` | Optional CDN domain |

## Architecture

- **Plugin name**: `tencent-cos`
- **Driver code**: `tencent-cos`
- **Driver class**: `CosStorageDriver`
- **Capabilities**: `storage:read`, `storage:write`
- **Pricing**: Free

## Dependencies

- `cos-python-sdk-v5` >= 1.9
