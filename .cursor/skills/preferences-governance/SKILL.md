---
name: preferences-governance
description: NovusAI 偏好设置治理技能。当需要开发或修复 admin/tenant 偏好设置、全局偏好实时预览、个人偏好同步、`preference:global_updated` WebSocket 事件或 `useUserPreferenceStore` 时，参考此技能。
---

# 偏好设置治理技能

## 何时使用

- 修改 `/admin/preferences/*`、`/tenant/preferences/*`
- 调整全局偏好页、个人偏好同步、Vben preferences 映射
- 修复 `preference:global_updated` 事件处理
- 处理 watermark、主题、布局、语言等 UI 偏好治理

## 核心原则

- 偏好是“三层模型”：系统默认 -> 全局 -> 个人覆盖
- 全局更新会精确清除个人覆盖中的同 key
- 前端统一使用 `useUserPreferenceStore` + `usePreferenceSync`
- 全局页实时预览必须可回滚

## 标准流程

1. 先确认是 UI 偏好，不是通知偏好
2. 检查 scope 属于 admin 还是 tenant
3. 检查变更是否涉及 `GLOBAL_ONLY_KEYS`
4. 检查是否会触发 WS 事件与个人偏好防抖同步冲突
5. 检查 live preview 离开页面时能否回滚

## 关键禁令

- 禁止直接把 localStorage 当作偏好权威来源
- 禁止绕过 `UserPreferenceService` 直接写偏好表
- 禁止把全局更新又回写成个人偏好
- 禁止个人偏好覆盖 watermark 全局键

## 参考

- [../novusai-saas/references/preferences-spec.md](../novusai-saas/references/preferences-spec.md)
- [../novusai-saas/references/notification-spec.md](../novusai-saas/references/notification-spec.md)
