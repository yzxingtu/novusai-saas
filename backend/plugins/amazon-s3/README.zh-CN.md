# S3 兼容存储插件

[Amazon S3](https://aws.amazon.com/s3/) 及 S3 兼容服务（AWS、MinIO、Cloudflare R2、Backblaze B2 等）对象存储驱动插件。

## 功能

- **S3 协议** — 完整 S3 API 兼容，支持上传、下载、删除和列举
- **多服务商** — 支持 AWS S3、MinIO、Cloudflare R2、Backblaze B2 及任何 S3 兼容端点
- **签名 URL** — 限时签名 URL，安全访问文件
- **自定义端点** — 可配置端点 URL，适用于自建或第三方 S3 服务
- **路径风格** — 同时支持虚拟主机和路径风格寻址

## 配置

存储凭证在**平台设置 → 存储配置**中设置，无需在插件配置中填写。所需字段：

| 字段 | 说明 |
|------|------|
| `access_key` | S3 Access Key ID |
| `secret_key` | S3 Secret Access Key |
| `bucket` | 存储桶名称 |
| `region` | AWS 区域（如 `us-east-1`） |
| `endpoint` | 可选，自定义端点 URL（用于 MinIO/R2/B2） |
| `custom_domain` | 可选，CDN 自定义域名 |
| `use_path_style` | 使用路径风格寻址（MinIO 需要） |

## 架构

- **插件名**: `amazon-s3`
- **驱动代码**: `s3`
- **驱动类**: `S3StorageDriver`
- **能力声明**: `storage:read`、`storage:write`
- **定价**: 免费

## 依赖

- `boto3` >= 1.35
