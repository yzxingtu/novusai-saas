# 附件上传、下载与存储规则

## 核心原则

**所有文件上传、图片显示、文件预览都必须通过统一附件系统（Attachment）完成，禁止自建上传链路或直拼存储 URL。**

这条规则不仅约束业务页面，也约束：

- 共享 API 封装
- composable
- 富文本编辑器
- AI chat / 页面截图 / 剪贴板上传
- 任何“基础设施层”上传包装

只要语义上属于业务附件上传，就必须复用平台附件体系，而不是自己 `requestClient.upload(...)`。

## 后端标准链路

```text
Controller (UploadFile)
  -> AttachmentService.upload_file() / complete_chunk_upload()
  -> FileValidator
  -> QuotaService
  -> StorageDriver
  -> Attachment 落库
```

- Controller 只接收 `UploadFile` / `Form` 并调用 Service
- 上传校验必须经过 `FileValidator`
- 配额检查、哈希秒传、分片合并都在 `AttachmentService` / `AdminAttachmentService` 里做
- 知识库文档、聊天附件、配置图片、头像上传都复用附件系统，不能单独绕过

## 前端唯一合法入口

业务上传只允许通过以下入口：

- `smartUploadFile`
- `FilePicker`
- `ImageUpload`
- `ConfigImagePicker`
- 封装了 `smartUploadFile` 的共享 helper

端点必须匹配当前端：

- admin: `/admin/attachments/*`
- tenant: `/tenant/attachments/*`
- user: `/api/user/attachments/*`

额外约束：

- admin 端平台级附件上传必须显式带 `tenant_id=0`
- 共享组件 / composable 必须端点感知，不能写死 tenant API
- 前端上传限制必须以服务端 `upload-rules` 为准，不能只靠本地常量

**禁止事项：**

- 禁止新建绕过附件体系的上传组件
- 禁止业务页面、共享 API、composable 直接 `requestClient.upload('/xxx/upload', ...)`
- 禁止前端拼接存储路径、bucket、prefix、`base_url`
- 禁止用“为了通用”作为理由绕过 `smartUploadFile`

## 秒传、去重与哈希

- 文件哈希统一用 `computeFileHash(file, { onProgress, signal })`
- 秒传流程必须先做 preflight，命中后直接复用附件
- `get_by_hash` 必须同时带：
  - 当前企业（tenant 场景）
  - 当前存储驱动
  - 当前可见性 `visibility`
- `visibility` 是附件身份的一部分，`public` / `private` 不能互相复用
- 分片上传完成后的秒传复用，同样必须按 `driver + visibility` 命中

## 图片字段语义

图片类字段默认语义如下：

- 头像、Logo、品牌图、Provider 图标、配置图片等字段，默认存 **附件 ID**
- 历史数据允许兼容旧 URL 字符串，但新代码必须按“附件 ID 优先、旧 URL 兼容”处理

前端处理规则：

- 使用 `parseAttachmentId()` / `toAttachmentImageUrl()` / `toAvatarDisplayUrl()`
- 禁止对 avatar/icon/image 这类字段随手 `Number(...)`、`parseInt(...)`
- 禁止假设字段一定是数字或一定是 URL

## 图片显示与预览

### 展示类图片

- 展示类图片统一走 `/api/public/attachments/{id}/image`
- 前端优先使用：
  - `getProcessedImageUrl()`
  - `toAttachmentImageUrl()`
  - `toAvatarDisplayUrl()`
  - `getAttachmentUrl()`

### 非图片或私有预览

- 非图片文件预览统一走 `preview-url` 签名接口
- 共享 `FilePreview` 之类组件必须按 `admin / tenant / user` 选择正确 API
- 若附件对象已有 `preview_url` / `previewUrl`，优先复用，不重复硬编码接口
- 若手上拿到的是完整附件对象（如详情抽屉、文件选择器、附件列表），图片预览必须走 `getAttachmentUrl(attachment, { preset })`，不要只拿 `attachment.id` 去调用 `getProcessedImageUrl()`；否则私有图片会丢失 `preview_url` 里的签名 token
- 对 AI chat 这类会把附件元数据持久化到消息 JSON 的场景，附件对象必须同时保留 `attachment_id`；私有文件的 `url` 只能视为临时展示值，消息读取时必须根据 `attachment_id` 刷新当前有效 URL，并兼容旧消息里只有 `/api/public/attachments/{id}/access` 的存量格式
- 页面截图、工具返回的多模态图片附件即使不落库，也应尽量保留 `attachment_id`；LLM 侧图片解析必须同时兼容 `/access` 与 `/image` 相对路径，不能隐式依赖 `APP_INTERNAL_BASE_URL` 才能读取私有图片

### 严禁

- 禁止在 `<img src>` 中拼 `base_url + path`
- 禁止把展示类图片错误标成 `private`
- 禁止共享图片/预览组件只兼容 tenant 端

## 可见性规则

- `public`：头像、Logo、Favicon、品牌图、Provider 图标等展示类资源
- `private`：合同、文档、证件、知识库原文、用户敏感附件等

判断原则：

- “是否公开展示”决定 `visibility`
- 不要因为当前页面能访问，就把本质应私有的文件标成 `public`
- 不要为了省预签名逻辑，把本应公开展示的图片留成 `private`

## 下载规则

前端主应用：

- 必须使用 `requestClient.download(url)` 获取 Blob
- 必须使用 `downloadBlob(blob, { filename })` 触发下载

插件：

- 必须使用 `NovusPluginShared.requestClient.download`
- 必须使用 `NovusPluginShared.downloadBlob`

**禁止事项：**

- 禁止 `window.open(exportUrl)` 触发下载
- 禁止直接 `requestClient.get(..., { responseType: 'blob' })`
- 禁止插件手写 `URL.createObjectURL` + `a.click()`

## 对象存储驱动规则

### 原生图片处理能力

- `supports_native_image_processing()` 必须考虑 `visibility`
- 公开 CDN 图片处理能力不能用于私有文件
- 云驱动若对私有文件不支持原生图像处理，必须回退到签名原图 URL 或本地处理

### Provider 特性约束

- 像 Qiniu Kodo 这类桶级可见性 provider，必须 fail fast，不得伪装成支持单文件 public/private 混用
- 私有桶不应保存可用于不安全直连 fallback 的 `base_url`
- 公开图片 CDN 处理能力若只适用于 public，对 private 必须显式禁用，而不是“碰巧能访问”
- 云驱动 `copy()` / `move()` 不能只追求“复制成功”，必须显式保留源对象的 public/private 语义；public 对象复制后不能悄悄掉成默认私有 ACL

### 存储迁移

- 存储迁移写入目标驱动时，`visibility` / `mime_type` / `metadata` 必须以附件表记录为准，不要信任源对象头信息作为唯一真值
- 原因：旧对象可能缺少 metadata，或 provider 返回的头信息不完整；若只看源对象头，会把目标对象迁成错误的 public/private 或丢失正确 MIME / metadata
- 对已有附件解析存储配置时，必须优先使用 `attachment.tenant_id`，不能在 admin/public 上下文里偷懒写成 `self.tenant_id or PLATFORM_TENANT_ID`
- 当 platform 与 tenant 使用相同驱动名（如都为 `s3`）时，禁止仅凭 `driver` 选择当前配置；必须结合附件落库时的存储快照，或共享桶路径语义（`platform/...`、`tenants/{tenant_id}/...`）判定真实来源配置
- 附件 `meta` 中允许保留非敏感内部存储快照（scope/root_path/base_url/driver）用于后续解析，但这些内部字段不得透传到对象存储的 object metadata

## 后端文件响应

- 文件响应必须设置正确 `media_type`
- `Content-Disposition` 必须兼容非 ASCII 文件名
- 需要附件下载时统一返回 attachment header，不要让前端猜测文件名

## 最低验证要求

凡是改到上传、图片显示、预览、存储插件，至少做这些检查：

- `rg "requestClient\\.upload\\(" frontend/apps/web-antd/src`
- `rg "Number\\(|parseInt\\(" frontend/apps/web-antd/src` 并人工确认 avatar/icon/image 相关字段未被脆弱强转
- 前端：`pnpm exec vue-tsc --noEmit --skipLibCheck --pretty false -p apps/web-antd/tsconfig.json`
- 后端上传/可见性/存储改动：`pytest backend/tests/test_storage_plugins.py backend/tests/services/test_attachment_service.py`

## 参考

- [../skills/novusai-saas/references/download-spec.md](../skills/novusai-saas/references/download-spec.md)
- [../skills/novusai-saas/references/platform-infrastructure.md](../skills/novusai-saas/references/platform-infrastructure.md)
