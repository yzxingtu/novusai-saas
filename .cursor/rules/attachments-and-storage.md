# 附件上传、下载与存储规则

## 核心原则

**所有文件上传必须通过统一的附件系统（Attachment）完成，禁止自建上传链路。**

## 上传链路

后端标准链路：

```text
Controller (UploadFile)
  -> AttachmentService.upload_file()
  -> FileValidator
  -> QuotaService
  -> StorageDriver
  -> Attachment 落库
```

- Controller 只接收 `UploadFile` 并调用 Service
- 上传校验必须经过 `FileValidator`
- 配额检查、哈希秒传、分片合并都在 `AttachmentService` 里做
- 知识库文档上传也复用附件系统，不能单独绕过

## 前端唯一合法入口

- `smartUploadFile`
- `FilePicker`
- `ImageUpload`
- `ConfigImagePicker`

允许的框架级例外：

- 富文本编辑器等基础设施封装可在内部直接调用标准附件上传端点，但必须仍然走附件系统，不能自建独立上传后端

**禁止事项：**

- 禁止新建上传组件
- 禁止业务页面直接 `requestClient.upload('/xxx/upload', ...)` 直连上传端点
- 禁止在前端硬编码上传限制，必须使用服务端返回的规则
- 禁止在前端拼接存储路径或上传 URL 前缀

## 秒传与哈希

- 文件哈希统一用 `computeFileHash(file, { onProgress, signal })`
- 秒传流程必须先做 preflight，命中后直接复用附件
- `get_by_hash` 必须带当前存储驱动，防止跨驱动误命中

## 可见性与图片显示

可见性规则：

- `public`：头像、Logo、Favicon、品牌图等展示类资源
- `private`：合同、文档、证件、知识库原文等敏感资源

显示规则：

- 展示类图片统一走 `/api/public/attachments/{id}/image`
- 前端优先使用 `getProcessedImageUrl()`、`toAvatarDisplayUrl()`、`getAttachmentUrl()`
- 禁止在 `<img src>` 中拼 `base_url + path`
- 禁止把展示类图片错误标为 `private`

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

## 后端文件响应

- 文件响应必须设置正确 `media_type`
- `Content-Disposition` 必须兼容非 ASCII 文件名
- 需要附件下载时统一返回 attachment header，不要让前端猜测文件名

## 参考

- `../skills/novusai-saas/references/upload-storage-spec.md`
- `../skills/novusai-saas/references/download-spec.md`
- `../skills/novusai-saas/references/platform-infrastructure.md`
