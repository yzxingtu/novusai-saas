# 阿里云 OSS 存储插件

[阿里云对象存储服务（OSS）](https://www.aliyun.com/product/oss)驱动插件，支持原生图片处理。

## 功能

- **对象存储** — 通过阿里云 OSS 上传、下载、删除和列举文件
- **图片处理** — OSS 原生图片处理（缩放、裁剪、水印、格式转换）
- **签名 URL** — 限时签名 URL，安全访问文件
- **自定义域名** — 支持绑定 CDN 自定义域名

## 配置

存储凭证在**平台设置 → 存储配置**中设置，无需在插件配置中填写。所需字段：

| 字段 | 说明 |
|------|------|
| `access_key_id` | 阿里云 AccessKey ID |
| `access_key_secret` | 阿里云 AccessKey Secret |
| `bucket` | OSS 存储桶名称 |
| `endpoint` | OSS 端点（如 `oss-cn-hangzhou.aliyuncs.com`） |
| `custom_domain` | 可选，CDN 自定义域名 |

## 架构

- **插件名**: `aliyun-oss`
- **驱动代码**: `aliyun-oss`
- **驱动类**: `OssStorageDriver`
- **能力声明**: `storage:read`、`storage:write`
- **定价**: 免费

## 依赖

- `alibabacloud-oss-v2` >= 1.0.0
