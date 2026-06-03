# 上传与存储系统规范

## 核心原则

**所有文件上传必须通过统一的附件系统（Attachment）完成，禁止自建上传逻辑。**

**所有图片显示必须通过 `/api/public/attachments/{id}/image` 端点，禁止在前端硬编码存储路径。**

## 后端架构

```
Controller (UploadFile) → AttachmentService.upload_file() → FileValidator → QuotaService → StorageDriver → Attachment 落库
```

### 秒传（Preflight）流程

```
前端 computeFileHash(file) → POST /attachments/preflight(hash, filename, size)
  → 命中：直接返回已有附件（零上传）
  → 未命中：走正常上传流程
```

- **前端哈希**：`computeFileHash(file, { onProgress, signal })` → `sha256:{hex_digest}`（Web Crypto API）
- **后端预检**：`AttachmentService.preflight_check(file_hash, filename, size)` → 同企业+同驱动查找
- **配额检查顺序**：先查哈希 → 命中则跳过配额 → 未命中才检查配额（秒传不消耗新空间）
- **去重 driver 过滤**：`get_by_hash(hash, driver=storage_config.driver)` — 切换存储驱动后不误命中旧驱动文件

| 层 | 文件 | 职责 |
|---|------|------|
| Controller | `api/admin/attachments.py` / `api/tenant/attachments.py` | 接收 `UploadFile`，调 Service |
| Service | `services/tenant/attachment_service.py` | 上传逻辑、配额检查、哈希去重、分片管理 |
| Service | `services/system/attachment_service.py` | 平台端上传（跨企业，无配额限制） |
| Validator | `services/common/file_validator.py` | 文件类型/大小验证（平台+企业两级配置） |
| Quota | `services/common/storage_quota_service.py` | 存储配额查询（企业套餐驱动） |
| Storage | `app/storage/` | 存储驱动抽象层（local / s3） |
| Model | `models/tenant/attachment.py` | Attachment ORM（TenantModel，含 hash/driver/base_url） |
| Task | `tasks/upload_cleanup.py` | 分片上传临时文件清理（Celery Beat，每 6h） |

## 前端统一组件

**禁止新建上传组件**，必须复用以下已有组件：

| 组件 | 路径 | 用途 | 默认 visibility |
|------|------|------|-----------------|
| `FilePicker` | `components/business/file-picker/FilePicker.vue` | 通用文件选择+上传（Modal 弹窗） | `private` |
| `ConfigImagePicker` | `components/business/config-image-picker/ConfigImagePicker.vue` | 系统配置图片选择（内部用 FilePicker，强制 `public`） | `public` |
| `ImageUpload` | `components/business/image-upload/ImageUpload.vue` | 图片上传（内联，头像/Logo 等展示用途） | `public` |
| `smartUploadFile` | `api/tenant/attachment.ts` | **唯一对外上传入口**（秒传+分片+进度） | 由调用方指定 |

### FilePicker 使用方式

```vue
<script setup lang="ts">
import { useVbenModal } from '@vben/common-ui';
const [FilePickerModal, filePickerApi] = useVbenModal({
  connectedComponent: () => import('#/components/business/file-picker/FilePicker.vue'),
});
function openPicker() { filePickerApi.open(); }
</script>
<template>
  <FilePickerModal @select="handleSelect" :image-only="false" :multiple="true" />
</template>
```

### ImageUpload 使用方式

```vue
<!-- 展示类图片（头像/Logo/图标）— 默认 public，无需额外传参 -->
<ImageUpload v-model="formValues.avatar" />

<!-- 敏感图片 — 明确传 private -->
<ImageUpload v-model="formValues.id_card" visibility="private" />
```

- 通过 `endpoint` prop 指定 API 端（`admin` / `tenant` / `user`），不传时从 URL 自动检测
- `visibility` 默认 `'public'`（图片上传场景天然用于展示）

### smartUploadFile 使用方式（程序化上传）

```typescript
import { smartUploadFile } from '#/api/tenant/attachment';
const result = await smartUploadFile(
  { file: myFile, visibility: 'private', business_type: 'avatar' },
  (progress) => { /* percent: 0-100 */ },
);
// result.attachment — AttachmentInfoRaw
// result.url — 访问 URL
```

**三阶段流程**（进度映射）：
1. **哈希计算** (0~5%)：`computeFileHash` 计算 SHA-256
2. **预检秒传** (5%)：`preflightCheckApi` 检查文件是否已存在，命中→直接返回，进度跳 100%
3. **实际上传** (5~100%)：未命中→根据文件大小选择普通/分片上传

- 文件 ≤ 10MB：自动走普通上传
- 文件 > 10MB：自动走分片上传（5MB/片，片内字节级实时进度）
- 支持 AbortController 取消
- 预检失败静默继续正常上传（不影响用户体验）

### computeFileHash 文件哈希工具

```typescript
import { computeFileHash } from '#/utils/file-hash';
const hash = await computeFileHash(file, {
  onProgress: (percent) => { /* 0-100 */ },
  signal: abortController.signal,
});
// => "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
```

- 小文件 (≤64MB)：一次性读入 ArrayBuffer + SubtleCrypto.digest
- 大文件 (>64MB)：分块读取（2MB/块）+ 合并后 digest
- 空文件返回固定哈希值
- 位置：`frontend/apps/web-antd/src/utils/file-hash.ts`

## 前端 API 层

| 端 | 文件 | 导出函数 |
|----|------|----------|
| tenant | `api/tenant/attachment.ts` | `smartUploadFile` / `preflightCheckApi` / `getUploadRulesApi` / `batchUploadAttachmentsApi` / `initChunkUploadApi` / `uploadChunkApi` / `completeChunkUploadApi` |
| admin | `api/admin/attachment.ts` | `smartUploadFile` / `preflightCheckApi` / `getUploadRulesApi` / `batchUploadAttachmentsApi` / `getAttachmentListApi` / `getAttachmentStatsApi` |

> **注意**：`uploadAttachmentApi` 已降级为模块内部函数（`@internal`），仅供 `smartUploadFile` 内部调用。业务页面与业务模块**禁止**直接使用。少数基础设施封装（如富文本编辑器上传适配层）如确需直连标准附件上传端点，必须保持仍走统一附件系统，禁止实现独立上传后端。

## FilePicker 智能上传特性

- **动态上传规则**：Modal 打开时调用 `getUploadRulesApi` 加载服务端配置（允许/禁止扩展名、最大文件大小），替代硬编码 prop 默认值
- **扩展名校验**：基于服务端白名单/黑名单验证文件扩展名
- **小文件批量打包**：≤5MB 且 ≥2 个文件自动走 `batchUploadAttachmentsApi`（每批最多 20 个），减少 HTTP 请求数
- **大文件分片上传**：>10MB 文件自动分片（5MB/片），支持断点续传、片内实时进度

## 禁止事项

- ❌ **禁止新建上传组件**（如 `MyUpload.vue`），必须复用 `FilePicker` / `ImageUpload`
- ❌ **禁止业务页面直接调用后端上传端点**（如 `requestClient.upload('/xxx/upload', ...)`），必须通过 `smartUploadFile`（`uploadAttachmentApi` 已降级为内部函数，禁止外部业务代码调用）
- ❌ **禁止绕过 FileValidator**（如后端直接写入存储而不经过 Service）
- ❌ **禁止硬编码存储路径**（如 `"/uploads/avatar.png"`），由 Service 自动生成 `{tenant_id}/{date}/{uuid}.ext`
- ❌ **禁止在前端硬编码上传 URL 前缀**（admin/tenant 由组件 props 或 API 函数区分）
- ❌ **禁止硬编码上传限制**（文件大小、扩展名），必须从服务端 `getUploadRulesApi` 动态获取
- ❌ **禁止 `get_by_hash` 不传 `driver` 参数**，必须传入当前存储驱动防止跨驱动误命中
- ✅ **框架级例外**：富文本编辑器等基础设施封装可在内部直接调用标准附件上传端点，但仍必须复用同一附件系统与后端校验链

## 知识库文档上传

知识库文档上传复用附件系统：
```python
attachment_service = AttachmentService(db, tenant_id)
upload_result = await attachment_service.upload_file(
    content=io.BytesIO(file_bytes),
    filename=filename,
    business_type="knowledge_document",
    business_id=kb_id,
)
```

## 文件可见性（Visibility）规范

### 公有 / 私有判定规则

| visibility | 适用场景 | 访问方式 | 典型用途 |
|-----------|---------|---------|---------|
| `public` | 展示类文件，需在 `<img>` 标签或未认证页面中显示 | 任何人可通过 `/api/public/attachments/{id}/image` 直接访问 | 头像、Logo、Favicon、AI Provider 图标、配置图片、品牌图片 |
| `private` | 敏感文件，不应公开访问 | 需 JWT access token（通过 `preview_url` 或认证端点） | 文档、合同、身份证照片、知识库文档 |

### 判定依据

**问自己一个问题：这个文件是否需要在 `<img>` 标签中直接显示？**

- **是** → 必须设为 `public`，因为 `<img>` 标签无法发送 Authorization header
- **否** → 设为 `private`，通过后端返回的 `preview_url`（含签名 token）访问

### 前端组件默认值

| 组件 | 默认 visibility | 原因 |
|------|----------------|------|
| `ImageUpload` | `public` | 图片上传场景天然用于展示（头像、Logo 等） |
| `FilePicker` | `private` | 通用文件选择器，保守默认，需要 public 时显式传参 |
| `ConfigImagePicker` | `public`（强制） | 配置图片用于登录页等未认证页面，必须公开 |

### 后端上传端点

三端上传端点（admin/tenant/user）均支持 `visibility` Form 参数：
- 传入 `public` 或 `private` → 使用该值
- 不传 → 使用平台默认值（`private`）

## 图片显示规范

### 展示类图片（public）

```
附件 ID → getProcessedImageUrl(id, { preset }) → /api/public/attachments/{id}/image?p=thumb
         → validate_access: public → 直接放行 → 返回处理后图片
```

前端工具函数（位于 `utils/image.ts`）：
- `getProcessedImageUrl(id, options?)` — 构建带图片处理参数的 URL（缩放、裁切、预设）
- `toAvatarDisplayUrl(id)` — 头像专用，自动加 `preset: 'avatar'`

### 敏感类图片（private）

```
后端 API 返回 attachment 含 preview_url（含 HMAC sign + JWT token）
  → 前端 getAttachmentUrl(attachment, { preset })
  → 优先使用 preview_url
  → validate_access: private + token 校验 → 放行
```

前端工具函数：
- `getAttachmentUrl(attachment, options?)` — 优先使用 `attachment.previewUrl`，回退到 ID 构建
- 只要上下文里已经有完整 `attachment` 对象（例如附件详情、附件库、文件预览弹窗），图片预览也必须走 `getAttachmentUrl(attachment, { preset })`，不要退化成 `getProcessedImageUrl(attachment.id)`；后者会丢掉私有文件 `preview_url` 自带的 token
- 对 AI chat / 消息流这类会把附件元数据持久化到 JSON 的场景，附件对象必须携带 `attachment_id`；私有文件的 `url` 只用于当次展示，历史消息回放时要基于 `attachment_id` 重新生成当前有效 URL，不能把一次上传返回的临时链接当成永久主键

### 禁止事项

- ❌ 禁止在前端使用 `attachment.path` 拼接 URL（路径可能暴露内部存储结构）
- ❌ 禁止在 `<img src>` 中直接使用后端返回的 `base_url + path`
- ❌ 禁止展示类图片设为 `private`（会导致 `<img>` 401 无法显示）
- ✅ 统一通过 `/api/public/attachments/{id}/image` 端点访问

## 安全机制

### 访问控制流程

```
请求 /api/public/attachments/{id}/image
  → 查询 Attachment 记录
  → validate_access:
      ├─ visibility = public → 直接放行
      └─ visibility = private → 检查 JWT token
          ├─ token 有效 → 放行
          └─ token 无效/缺失 → 401
  → 可选：HMAC 签名验证（有则验证，无则跳过）
```

### JWT Access Token

- 由 `AttachmentDownloadService.create_access_token(attachment, expires, preview)` 生成
- 包含 attachment_id 和 tenant_id，有时效性
- 用于 `preview_url` 中携带，使 `<img>` 标签能访问私有文件
- 前端不应手动构造，由后端 `build_preview_url` 自动生成

### HMAC 签名

- 由 `AttachmentDownloadService.create_access_sign(attachment_id, exp)` 生成
- 防止盲目枚举附件 ID（即使 public 文件，签名也能增加安全性）
- **"有则验证"模式**：URL 中有 `sign` 和 `exp` 参数时验证，没有时不强制
- `build_preview_url` 自动生成签名参数

### 关于 URL 中 ID 暴露

URL 中包含 attachment_id 是**行业标准做法**（AWS S3 pre-signed URL、Azure Blob SAS URL 均在 URL 中包含对象标识符）。安全保障来自：
- **公开文件**：内容本身就是公开的，ID 暴露无风险
- **私有文件**：即使知道 ID，没有有效 JWT token 也无法访问

### 企业隔离

- 存储路径自动按企业隔离：`tenants/{tenant_id}/{date}/{uuid}.ext`
- 平台端路径：`platform/{date}/{uuid}.ext`
- `validate_access` 不额外检查 tenant_id（通过 visibility + token 控制）
- 企业端 API（Safe Schema）不返回 `path`、`driver`、`base_url`、`hash` 等内部字段

## 对象存储兼容说明

### 支持的存储驱动

| 驱动 | 来源 | 说明 |
|------|------|------|
| `local` | 内置 | 本地文件系统，所有文件通过 API 代理访问 |
| `s3` | 内置 | 兼容 S3 协议（AWS S3、MinIO 等） |
| `tencent-cos` | 插件 | 腾讯云 COS，支持 imageMogr2 图片处理 |
| `qiniu-kodo` | 插件 | 七牛云 Kodo，支持 imageMogr2 图片处理 |
| `aliyun-oss` | 插件 | 阿里云 OSS，支持 image 图片处理 |

### 驱动对 visibility 的处理

- **本地存储**：所有文件（含 public）均通过 `/api/public/attachments/{id}/image` API 代理访问，`<img>` 标签不直接访问文件系统
- **云存储 public 文件**：可通过 CDN 直接访问或 302 重定向到 CDN URL
- **云存储 private 文件**：通过 pre-signed URL（各驱动自动生成临时访问链接）

### 驱动切换兼容

- 附件记录中存储了 `base_url` 和 `driver`，切换驱动后旧文件仍可访问
- `_build_direct_cdn_url` 回退机制保障已有 public 云文件可继续通过旧 CDN 访问
- `get_by_hash(hash, driver=storage_config.driver)` 秒传匹配按当前驱动过滤，防止跨驱动误命中

### 图片处理兼容

所有云存储驱动均支持 `supports_native_image_processing()` 检测：
- 返回 `True` 时：使用云端原生图片处理（URL 参数方式，无需服务端处理）
- 返回 `False` 时：回退到本地 Pillow 处理（`ImageProcessService`）
- 本地存储始终使用 Pillow 处理

## 完整上传-显示流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                         上传流程                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  前端组件 (ImageUpload/FilePicker)                                   │
│    │                                                                │
│    ├── visibility: props.visibility (ImageUpload 默认 public)        │
│    │                                                                │
│    └── smartUploadFile(file, { visibility })                        │
│          │                                                          │
│          ├── 1. computeFileHash(file) — SHA-256 哈希                │
│          ├── 2. preflightCheck(hash) — 秒传检测                     │
│          │     ├── 命中 → 直接返回已有附件                            │
│          │     └── 未命中 → 继续上传                                 │
│          └── 3. uploadFile(file, { visibility })                    │
│                │                                                    │
│                └── 后端返回:                                         │
│                    { attachment, url: "/api/public/attachments/{id}/access" } │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    显示流程（展示类 / public）                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  附件 ID                                                            │
│    │                                                                │
│    └── getProcessedImageUrl(id, { preset: 'thumb' })                │
│          │                                                          │
│          └── /api/public/attachments/{id}/image?p=thumb             │
│                │                                                    │
│                └── validate_access:                                  │
│                    visibility = public → 放行 → 返回处理后图片        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    显示流程（敏感类 / private）                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  后端 API 返回 attachment 含 preview_url                             │
│    │                                                                │
│    └── getAttachmentUrl(attachment, { preset })                     │
│          │                                                          │
│          └── 优先使用 preview_url（含 HMAC sign + JWT token）        │
│                │                                                    │
│                └── validate_access:                                  │
│                    private + token 校验 → 放行                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 存储驱动

当前内置驱动：`LocalDriver`（本地文件系统）、`S3Driver`（兼容 S3 协议）。
云存储驱动通过插件提供：`TencentCosDriver`、`QiniuKodoDriver`、`AliyunOssDriver`、`AmazonS3Driver`。

## 关键文件索引

| 文件 | 说明 |
|------|------|
| `backend/app/api/admin/attachments.py` | 平台端附件 Controller（上传/分片/管理/统计） |
| `backend/app/api/tenant/attachments.py` | 企业端附件 Controller（上传/分片/管理/配额），使用 Safe Schema |
| `backend/app/api/user/attachments.py` | 用户端附件 Controller（头像等），使用 Safe Schema |
| `backend/app/api/public/attachments.py` | 公开端点（访问/图片处理），含 HMAC 签名验证 |
| `backend/app/services/tenant/attachment_service.py` | 企业端上传 Service（配额+去重+分片），返回 API 代理 URL |
| `backend/app/services/system/attachment_service.py` | 平台端上传 Service（跨企业），返回 API 代理 URL |
| `backend/app/services/tenant/attachment_download_service.py` | 下载/预览服务（validate_access、JWT token、HMAC 签名、build_preview_url） |
| `backend/app/services/common/file_validator.py` | 文件类型/大小验证（两级配置） |
| `backend/app/services/common/storage_quota_service.py` | 存储配额查询 |
| `backend/app/models/tenant/attachment.py` | Attachment ORM 模型 |
| `backend/app/schemas/tenant/attachment.py` | 上传/配额响应 Schema（含 Safe Schema 和 preview_url 字段） |
| `backend/app/enums/attachment.py` | AttachmentVisibility / AttachmentStatus / AttachmentSource |
| `backend/app/tasks/upload_cleanup.py` | 分片上传临时文件清理 Celery 任务 |
| `frontend/.../api/tenant/attachment.ts` | 企业端上传 API（含 smartUploadFile） |
| `frontend/.../api/admin/attachment.ts` | 平台端上传 API |
| `frontend/.../components/business/file-picker/FilePicker.vue` | 通用文件选择+上传组件（visibility prop，默认 private） |
| `frontend/.../components/business/image-upload/ImageUpload.vue` | 图片上传组件（visibility prop，默认 public） |
| `frontend/.../components/business/config-image-picker/ConfigImagePicker.vue` | 配置图片选择器（强制 public） |
| `frontend/.../types/attachment.ts` | AttachmentInfo / StorageQuotaInfo 类型定义 |
| `frontend/.../utils/image.ts` | getProcessedImageUrl / getAttachmentUrl / toAvatarDisplayUrl 图片 URL 工具 |
| `frontend/.../utils/file-hash.ts` | computeFileHash — SHA-256 哈希计算（Web Crypto API） |
