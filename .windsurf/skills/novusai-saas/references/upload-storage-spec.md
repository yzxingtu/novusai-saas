# 上传与存储系统规范

## 核心原则

**所有文件上传必须通过统一的附件系统（Attachment）完成，禁止自建上传逻辑。**

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
- **后端预检**：`AttachmentService.preflight_check(file_hash, filename, size)` → 同租户+同驱动查找
- **配额检查顺序**：先查哈希 → 命中则跳过配额 → 未命中才检查配额（秒传不消耗新空间）
- **去重 driver 过滤**：`get_by_hash(hash, driver=storage_config.driver)` — 切换存储驱动后不误命中旧驱动文件

| 层 | 文件 | 职责 |
|---|------|------|
| Controller | `api/admin/attachments.py` / `api/tenant/attachments.py` | 接收 `UploadFile`，调 Service |
| Service | `services/tenant/attachment_service.py` | 上传逻辑、配额检查、哈希去重、分片管理 |
| Service | `services/system/attachment_service.py` | 平台端上传（跨租户，无配额限制） |
| Validator | `services/common/file_validator.py` | 文件类型/大小验证（平台+租户两级配置） |
| Quota | `services/common/storage_quota_service.py` | 存储配额查询（租户套餐驱动） |
| Storage | `app/storage/` | 存储驱动抽象层（local / s3） |
| Model | `models/tenant/attachment.py` | Attachment ORM（TenantModel，含 hash/driver/base_url） |
| Task | `tasks/upload_cleanup.py` | 分片上传临时文件清理（Celery Beat，每 6h） |

## 前端统一组件

**禁止新建上传组件**，必须复用以下已有组件：

| 组件 | 路径 | 用途 | 使用方式 |
|------|------|------|----------|
| `FilePicker` | `components/business/file-picker/FilePicker.vue` | 通用文件选择+上传（Modal 弹窗） | 选择已有附件或拖拽上传新文件 |
| `ConfigImagePicker` | `components/business/config-image-picker/ConfigImagePicker.vue` | 系统配置图片选择（内部用 FilePicker） | ConfigForm 中 `value_type='image'` 自动渲染 |
| `ImageUpload` | `components/business/image-upload/ImageUpload.vue` | 图片上传（内联） | `<ImageUpload v-model="form.avatar" />` |
| `smartUploadFile` | `api/tenant/attachment.ts` | **唯一对外上传入口**（秒传+分片+进度） | 在自定义场景中调用 |

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
<ImageUpload v-model="formValues.avatar" upload-url="/tenant/attachments/upload" />
```

- 默认 `uploadUrl` 为 `/admin/attachments/upload`
- 租户端使用时需传 `upload-url="/tenant/attachments/upload"`

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

> **注意**：`uploadAttachmentApi` 已降级为模块内部函数（`@internal`），仅供 `smartUploadFile` 内部调用。外部代码**禁止**直接使用。

## FilePicker 智能上传特性

- **动态上传规则**：Modal 打开时调用 `getUploadRulesApi` 加载服务端配置（允许/禁止扩展名、最大文件大小），替代硬编码 prop 默认值
- **扩展名校验**：基于服务端白名单/黑名单验证文件扩展名
- **小文件批量打包**：≤5MB 且 ≥2 个文件自动走 `batchUploadAttachmentsApi`（每批最多 20 个），减少 HTTP 请求数
- **大文件分片上传**：>10MB 文件自动分片（5MB/片），支持断点续传、片内实时进度

## 禁止事项

- ❌ **禁止新建上传组件**（如 `MyUpload.vue`），必须复用 `FilePicker` / `ImageUpload`
- ❌ **禁止直接调用后端上传端点**（如 `requestClient.upload('/xxx/upload', ...)`），必须通过 `smartUploadFile`（`uploadAttachmentApi` 已降级为内部函数，禁止外部调用）
- ❌ **禁止绕过 FileValidator**（如后端直接写入存储而不经过 Service）
- ❌ **禁止硬编码存储路径**（如 `"/uploads/avatar.png"`），由 Service 自动生成 `{tenant_id}/{date}/{uuid}.ext`
- ❌ **禁止在前端硬编码上传 URL 前缀**（admin/tenant 由组件 props 或 API 函数区分）
- ❌ **禁止硬编码上传限制**（文件大小、扩展名），必须从服务端 `getUploadRulesApi` 动态获取
- ❌ **禁止 `get_by_hash` 不传 `driver` 参数**，必须传入当前存储驱动防止跨驱动误命中

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

## 存储驱动

当前内置驱动：`LocalDriver`（本地文件系统）、`S3Driver`（兼容 S3 协议）。

## 关键文件索引

| 文件 | 说明 |
|------|------|
| `backend/app/api/admin/attachments.py` | 平台端附件 Controller（上传/分片/管理/统计） |
| `backend/app/api/tenant/attachments.py` | 租户端附件 Controller（上传/分片/管理/配额） |
| `backend/app/services/tenant/attachment_service.py` | 租户端上传 Service（配额+去重+分片） |
| `backend/app/services/system/attachment_service.py` | 平台端上传 Service（跨租户） |
| `backend/app/services/common/file_validator.py` | 文件类型/大小验证（两级配置） |
| `backend/app/services/common/storage_quota_service.py` | 存储配额查询 |
| `backend/app/models/tenant/attachment.py` | Attachment ORM 模型 |
| `backend/app/schemas/tenant/attachment.py` | 上传/配额响应 Schema |
| `backend/app/enums/attachment.py` | AttachmentVisibility / AttachmentStatus / AttachmentSource |
| `backend/app/tasks/upload_cleanup.py` | 分片上传临时文件清理 Celery 任务 |
| `frontend/.../api/tenant/attachment.ts` | 租户端上传 API（含 smartUploadFile） |
| `frontend/.../api/admin/attachment.ts` | 平台端上传 API |
| `frontend/.../components/business/file-picker/FilePicker.vue` | 通用文件选择+上传组件 |
| `frontend/.../components/business/image-upload/ImageUpload.vue` | 图片上传组件 |
| `frontend/.../types/attachment.ts` | AttachmentInfo / StorageQuotaInfo 类型定义 |
| `frontend/.../utils/file-hash.ts` | computeFileHash — SHA-256 哈希计算（Web Crypto API） |
