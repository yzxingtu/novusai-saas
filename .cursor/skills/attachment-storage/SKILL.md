---
name: attachment-storage
description: NovusAI 附件上传与存储技能。当需要实现文件上传、图片显示、附件下载、秒传、分片上传或排查可见性/存储驱动问题时，参考此技能。
---

# 附件上传与存储技能

## 何时使用

- 实现或修复附件上传
- 排查 `public` / `private` 可见性问题
- 实现图片显示、文件下载、导出
- 处理秒传、分片上传、哈希预检、存储驱动切换

## 核心原则

- 上传统一通过 `AttachmentService`
- 前端统一通过 `smartUploadFile` / `FilePicker` / `ImageUpload` / `ConfigImagePicker`
- 下载统一通过 `requestClient.download` + `downloadBlob`
- 展示类图片统一通过 `/api/public/attachments/{id}/image`
- 富文本编辑器等基础设施封装允许内部直连标准附件上传端点，但不能脱离附件系统单独建上传后端

## 快速检查

- 是否绕过了 `FileValidator`
- 是否在业务页面里错误使用 `requestClient.upload` 直连端点
- 是否把展示图片错误设成 `private`
- 是否在前端拼接了 `base_url + path`
- 是否下载时绕开了 `requestClient.download`

## 关键禁令

- 禁止新建上传组件
- 禁止直接拼存储路径
- 禁止插件手写 `a.click()` 下载
- 禁止不带 driver 做哈希去重查询

## 参考

- [../novusai-saas/references/upload-storage-spec.md](../novusai-saas/references/upload-storage-spec.md)
- [../novusai-saas/references/download-spec.md](../novusai-saas/references/download-spec.md)
- [../novusai-saas/references/platform-infrastructure.md](../novusai-saas/references/platform-infrastructure.md)
