# 腾讯云 COS 存储插件

[腾讯云对象存储（COS）](https://cloud.tencent.com/product/cos)驱动插件，支持 imageMogr2 原生图片处理。

## 功能

- **对象存储** — 通过腾讯云 COS 上传、下载、删除和列举文件
- **图片处理** — imageMogr2 原生图片处理（缩放、裁剪、水印、格式转换）
- **签名 URL** — 限时签名 URL，安全访问文件
- **自定义域名** — 支持绑定 CDN 自定义域名

## 配置

存储凭证在**平台设置 → 存储配置**中设置，无需在插件配置中填写。所需字段：

| 字段 | 说明 |
|------|------|
| `secret_id` | 腾讯云 SecretId |
| `secret_key` | 腾讯云 SecretKey |
| `bucket` | COS 存储桶名称（如 `mybucket-1250000000`） |
| `region` | COS 区域（如 `ap-guangzhou`） |
| `custom_domain` | 可选，CDN 自定义域名 |

## 架构

- **插件名**: `tencent-cos`
- **驱动代码**: `tencent-cos`
- **驱动类**: `CosStorageDriver`
- **能力声明**: `storage:read`、`storage:write`
- **定价**: 免费

## 依赖

- `cos-python-sdk-v5` >= 1.9
