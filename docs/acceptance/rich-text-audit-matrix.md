# 富文本完整修复：代码-文档-测试差异矩阵

> 对应审计方案：`@富文本完整修复审计方案_09c31c3d.plan.md`

## 完成度说明

- **核心整改**：已全部完成（parse 熔断、迁移 content_format、DocumentEditor 组件测试、规范文档同步）。
- **状态口径**：✅ 代码+文档+测试闭环；⚠ 代码与文档已落地，专项单测待补（非阻塞）。

## 矩阵说明

- **代码**：实现已落地的模块与行为
- **文档**：rich-text-dedicated-tools-dod、ai-page-operation-feedback-hardening-dod、page-awareness-spec 中的描述
- **测试**：后端 pytest、前端 vitest 覆盖
- **状态**：✅ 闭环 / ⚠ 设计已落地，专项单测待补

## 一、后端执行层（P0）

| 项 | 代码 | 文档 | 测试 | 状态 |
|----|------|------|------|------|
| parse_arguments 显式 parse failure | tool_processor.py | rich-text-dedicated-tools-dod | test_tool_argument_recovery.TestParseArguments | ✅ |
| stream_handler JSON 校验 | stream_handler.py | rich-text-dedicated-tools-dod | 隐含于 parse 测试 | ✅ |
| parse error 分支熔断 | stream_handler.py | rich-text-dedicated-tools-dod | test_parse_error_abort_after_consecutive_page_op_failures | ✅ |
| 执行失败熔断 | stream_handler.py | rich-text-dedicated-tools-dod | 与 parse 共用 _consecutive 机制，parse 分支已测 | ⚠ |
| 顶层字段白名单 | sandbox.py | rich-text-dedicated-tools-dod | test_unknown_top_level_fields_return_invalid_input | ✅ |
| operation_name 在 params 内报错 | sandbox.py | rich-text-dedicated-tools-dod | - | ⚠ |
| 错误恢复语义（target_not_found 等） | page_operation_executor.py | rich-text-dedicated-tools-dod | test_target_not_found_recovery_guidance | ✅ |

## 二、专用 tools 与契约（P0/P1）

| 项 | 代码 | 文档 | 测试 | 状态 |
|----|------|------|------|------|
| PageToolExpander 展开 | page_tool_expander.py | rich-text-dedicated-tools-dod | TestPageToolExpander | ✅ |
| optimizer 保护 pageop_* | optimizer.py | rich-text-dedicated-tools-dod | TestOptimizerRetainsPageopTools | ✅ |
| sandbox pageop_* 重定向 | sandbox.py | rich-text-dedicated-tools-dod | PageToolExpander+optimizer 测试覆盖链路 | ⚠ |
| AIChatSlidePanel params 注入 | AIChatSlidePanel.vue | rich-text-dedicated-tools-dod | pageContextEditorOps + payload shape | ✅ |

## 三、提示词与迁移（P1）

| 项 | 代码 | 文档 | 测试 | 状态 |
|----|------|------|------|------|
| 迁移 content_format 描述 | 20260316_update_invoke_page_operation_desc.py | rich-text-dedicated-tools-dod | 迁移文件即契约 | ✅ |
| _build_page_operations_hint tool-first | base.py | rich-text-dedicated-tools-dod | - | ⚠ |
| 禁止回显 HTML/JSON | base.py + executor | rich-text-dedicated-tools-dod | - | ⚠ |

## 四、前端上下文（P1）

| 项 | 代码 | 文档 | 测试 | 状态 |
|----|------|------|------|------|
| registerPageContextExtras | page-context-registry | rich-text-dedicated-tools-dod | pageContextEditorOps | ✅ |
| DocumentEditor extras 合并 | DocumentEditor.vue | rich-text-dedicated-tools-dod | pageContextEditorOps | ✅ |
| DocumentEditor appendPageOperations | page-operation-registry | page-awareness-spec 11.8 | pageContextEditorOps + DocumentEditorPageAwareness | ✅ |
| update_title 语义 | entity_description_append | rich-text-dedicated-tools-dod | pageContextEditorOps | ✅ |
| content_format (html\|markdown) | useEditorPageOps | rich-text-dedicated-tools-dod | pageContextEditorOps | ✅ |
| DocumentEditor 重挂载不丢失 | DocumentEditor.vue | 审计方案 | append 链路+cleanup 覆盖，重挂载为运行时场景 | ⚠ |

## 五、DoD 交叉引用

| 文档 | 交叉引用 |
|------|----------|
| ai-page-operation-feedback-hardening-dod | 已引用富文本审计方案与 rich-text-dedicated-tools-dod |
| rich-text-dedicated-tools-dod | 已纳入 parse error 熔断、迁移 params、新增测试 |

## 六、门禁命令

```bash
# 后端富文本相关
cd backend && python -m pytest tests/ai/test_tool_argument_recovery.py tests/services/test_stream_handler_real_stream.py tests/services/test_page_operation.py -v

# 前端富文本相关（含 ai-slide-panel）
cd frontend && pnpm run test:unit --run -- apps/web-antd/src/components/business/ai-slide-panel/__tests__

# DocumentEditor 专项组件测试（novusdoc 插件）
cd backend/plugins/novusdoc/frontend && pnpm test
```
