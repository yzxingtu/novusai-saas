# Alibaba Cloud OSS Storage Plugin

Object storage driver for [Alibaba Cloud OSS](https://www.alibabacloud.com/product/object-storage-service), with native image processing support.

## Features

- **Object Storage** — Upload, download, delete, and list files via Alibaba Cloud OSS
- **Image Processing** — Native OSS image processing (resize, crop, watermark, format conversion)
- **Signed URLs** — Time-limited presigned URLs for secure file access
- **Custom Domain** — Support for custom CDN domain binding

## Configuration

Storage credentials are configured in **Platform Settings → Storage**, not in the plugin config. Required fields:

| Field | Description |
|-------|-------------|
| `access_key_id` | Alibaba Cloud AccessKey ID |
| `access_key_secret` | Alibaba Cloud AccessKey Secret |
| `bucket` | OSS Bucket name |
| `endpoint` | OSS endpoint (e.g. `oss-cn-hangzhou.aliyuncs.com`) |
| `custom_domain` | Optional CDN domain |

## Architecture

- **Plugin name**: `aliyun-oss`
- **Driver code**: `aliyun-oss`
- **Driver class**: `OssStorageDriver`
- **Capabilities**: `storage:read`, `storage:write`
- **Pricing**: Free

## Dependencies

- `alibabacloud-oss-v2` >= 1.0.0
