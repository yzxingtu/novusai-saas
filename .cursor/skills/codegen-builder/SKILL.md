---
name: codegen-builder
description: NovusAI Codegen 可视化构建器技能。当需要开发或修复 `/admin/system/codegen/new|:id/edit` 三栏 Builder、WYSIWYG 预览、字段属性面板、DB 导入或版本恢复时，参考此技能。
---

# Codegen Builder 技能

## 何时使用

- 修改代码生成器可视化构建器 `builder.vue`
- 调整 WYSIWYG 列表/表单/详情预览
- 修改 `FieldPropertyPanel`、`ExpertModal`、`DbTableImportModal`
- 排查 `useCodegenBuilderStore`、undo/redo、preview cache、持久化问题

## 核心原则

- 当前真实实现是三栏 Builder，不是旧版 6 步向导
- 配置状态必须统一通过 `useCodegenBuilderStore`
- 字段编辑应围绕属性面板与 `field-utils` / `infer` 体系展开
- 保存/生成前先走校验 API，不要直接跳过验证

## 标准流程

1. 先判断问题在列表页还是 Builder 页
2. 检查是否触碰 `configJson`、`selectedFieldKey`、`previewCache`、`isDirty`
3. 检查改动应落在 Palette、WYSIWYG、PropertyPanel、ExpertModal 中哪一层
4. 检查保存/预览/生成/版本恢复是否仍沿用现有 API 流程
5. 检查是否继续扩散已删除的 `useCodegenWizardStore` 等历史旧命名

## 关键禁令

- 禁止把 Builder 文档或实现继续描述为 wizard/step
- 禁止绕过 store 直接深层 mutate `configJson`
- 禁止在多个组件里复制字段推断逻辑
- 禁止假设大配置一定会被 localStorage 完整持久化

## 参考

- [../novusai-saas/references/codegen-builder-spec.md](../novusai-saas/references/codegen-builder-spec.md)
- [../novusai-saas/references/codegen-spec.md](../novusai-saas/references/codegen-spec.md)
- [../crud-codegen-workflow/SKILL.md](../crud-codegen-workflow/SKILL.md)
