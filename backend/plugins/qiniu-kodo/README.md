# Qiniu Kodo Storage Plugin

Object storage driver for [Qiniu Kodo](https://www.qiniu.com/products/kodo), with native imageView2 image processing support.

## Features

- **Object Storage** — Upload, download, delete, and list files via Qiniu Kodo
- **Image Processing** — Native imageView2 image processing (resize, crop, watermark, format conversion)
- **Signed URLs** — Time-limited presigned URLs for secure file access
- **Custom Domain** — Support for custom CDN domain binding

## Configuration

Storage credentials are configured in **Platform Settings → Storage**, not in the plugin config. Required fields:

| Field | Description |
|-------|-------------|
| `access_key` | Qiniu AccessKey |
| `secret_key` | Qiniu SecretKey |
| `bucket` | Kodo Bucket name |
| `domain` | Bucket domain (e.g. `cdn.example.com`) |

## Architecture

- **Plugin name**: `qiniu-kodo`
- **Driver code**: `qiniu-kodo`
- **Driver class**: `KodoStorageDriver`
- **Capabilities**: `storage:read`, `storage:write`
- **Pricing**: Free

## Dependencies

- `qiniu` >= 7.14
