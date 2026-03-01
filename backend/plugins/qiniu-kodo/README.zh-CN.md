# 七牛云 Kodo 存储插件

[七牛云对象存储（Kodo）](https://www.qiniu.com/products/kodo)驱动插件，支持 imageView2 原生图片处理。

## 功能

- **对象存储** — 通过七牛云 Kodo 上传、下载、删除和列举文件
- **图片处理** — imageView2 原生图片处理（缩放、裁剪、水印、格式转换）
- **签名 URL** — 限时签名 URL，安全访问文件
- **自定义域名** — 支持绑定 CDN 自定义域名

## 配置

存储凭证在**平台设置 → 存储配置**中设置，无需在插件配置中填写。所需字段：

| 字段 | 说明 |
|------|------|
| `access_key` | 七牛 AccessKey |
| `secret_key` | 七牛 SecretKey |
| `bucket` | Kodo 存储桶名称 |
| `domain` | 存储桶域名（如 `cdn.example.com`） |

## 架构

- **插件名**: `qiniu-kodo`
- **驱动代码**: `qiniu-kodo`
- **驱动类**: `KodoStorageDriver`
- **能力声明**: `storage:read`、`storage:write`
- **定价**: 免费

## 依赖

- `qiniu` >= 7.14
