# 富文本专用 Tools 整改 DoD 验收记录

> 对应计划：仓库内「富文本专用 tools 整改」实施计划（文件名随工具导出而变化，此处不绑定固定路径）。

## 一、整改目标

- 富文本页不再让模型通过通用 `invoke_page_operation` 去「猜」参数
- 富文本核心操作改为运行时专用动态 tools
- 对非富文本页面继续保留 `invoke_page_operation` wrapper
- 明确页面操作模式与草稿采纳模式边界
- 参数错误显式报错，不再伪装成 `operation_name` 缺失

## 二、实施进度

### P0 止血：修复「假缺参」与错误循环

| 执行项 | 状态 | 说明 |
|--------|------|------|
| parse_arguments 显式 parse failure | ✅ | `tool_processor.py`：JSONDecodeError 返回 `(None, "invalid_tool_arguments_json")`，不再静默 `{}` |
| stream_handler JSON 校验 | ✅ | 聚合后 arguments 解析失败时不执行工具，推送错误 ToolResult |
| 删除 content→replace_content 危险推断 | ✅ | `sandbox.py`：`_infer_operation_name` 已移除该分支 |
| 顶层字段白名单 | ✅ | `invoke_page_operation` 仅允许 page_key/operation_name/params/requires_confirmation，未知字段返回 invalid_input |
| operation_name 在 params 内报错 | ✅ | 返回「operation_name 必须在顶层」结构化错误 |
| 连续同类错误中止 | ✅ | stream_handler：3 次连续 pageop_*/invoke 失败即中止 |
| parse error 分支熔断 | ✅ | parse error 也计入连续失败，达阈值后中止并输出恢复提示 |

### P0/P1 主改：富文本专用动态 tools

| 执行项 | 状态 | 说明 |
|--------|------|------|
| PageToolExpander 展开逻辑 | ✅ | `page_tool_expander.py`：available_operations 含编辑操作时注入 pageop_* |
| 专用 tools 列表 | ✅ | pageop_get_editor_html、get_editor_text、replace_section、replace_content、insert_content、append_content、update_title |
| optimizer 保护富文本 tools | ✅ | pageop_* 加入保护名单，不被优化掉 |
| sandbox 重定向 | ✅ | pageop_* 执行时重写为 invoke_page_operation |
| 提示词 _build_page_operations_hint | ✅ | 存在 pageop_* 时用 tool-first 表述，禁止向用户展示 HTML/JSON |
| AIChatSlidePanel 注入 params | ✅ | available_operations 含 `params`（op.params 有则注入） |

### P1 语义与上下文

| 执行项 | 状态 |
|--------|------|
| DocumentEditor 合并上下文 | ✅ | 改用 registerPageContextExtras，只传 document 相关字段 |
| update_title 语义澄清 | ✅ | entity_description_append 说明 update_title 修改元数据标题 |
| page_context_executor 输出 available_operations | ✅ | has_editor 时显式输出操作摘要 |
| 统一正文编辑契约 | ✅ | content_format (html\|markdown)，默认 HTML 不自动转换 |
| 迁移 params 描述修正 | ✅ | 20260316：format→content_format，与前端契约一致 |

### P1 提示词统一

| 执行项 | 状态 |
|--------|------|
| _build_page_operations_hint 重写 | ✅ | 已存在 pageop_* 时 tool-first |
| 禁止向用户展示 HTML/JSON | ✅ | base.py _inject_tool_awareness + executor 恢复信息 |
| NovusDoc Writer 解耦 | ✅ | 迁移更新 system_prompt，tool-first + 草稿模式 Markdown |

### P2 测试与验收

| 执行项 | 状态 |
|--------|------|
| test_tool_argument_recovery.py | ✅ | 10 用例：parse、白名单、PageToolExpander、optimizer 保留 pageop_* |
| test_page_operation target_not_found 恢复 | ✅ | 新增 test_target_not_found_recovery_guidance |
| test_agent_chat_page_context editor 操作摘要 | ✅ | 新增 test_editor_operations_summary_when_has_editor |
| pageContextEditorOps.test.ts | ✅ | available_operations 含 params、registerPageContextExtras 合并、payload shape 断言、DocumentEditor appendPageOperations |
| test_parse_error_abort_after_consecutive_page_op_failures | ✅ | parse error 熔断触发、output 含恢复提示 |
| DocumentEditorPageAwareness.test.ts | ✅ | DocumentEditor.vue 挂载层：registerPageContextExtras、appendPageOperations 调用与 entity_description_append 语义 |

## 三、测试执行

```bash
# 工具参数恢复测试
cd backend && python -m pytest tests/ai/test_tool_argument_recovery.py -v

# 流式熔断（含 parse error）测试
cd backend && python -m pytest tests/services/test_stream_handler_real_stream.py -v

# 页面操作原有测试
cd backend && python -m pytest tests/services/test_page_operation.py -v

# DocumentEditor 专项组件测试
cd backend/plugins/novusdoc/frontend && pnpm test
```

## 四、修改文件清单

- `backend/app/ai/engine/tool_processor.py`：parse_arguments 返回 (dict|None, error_type|None)
- `backend/app/ai/engine/stream_handler.py`：JSON 解析失败时推送错误、不执行
- `backend/app/ai/engine/base.py`：expand_page_tools 前置、_build_page_operations_hint 页面 tool-first
- `backend/app/ai/tools/sandbox.py`：顶层白名单、移除 content 推断、pageop_* 重定向
- `backend/app/ai/tools/page_tool_expander.py`：新增
- `backend/app/ai/tools/optimizer.py`：pageop_* 保护
- `backend/tests/ai/test_tool_argument_recovery.py`：新增（10 用例）
- `frontend/.../AIChatSlidePanel.vue`：available_operations 注入 `params`
- `frontend/.../page-context-registry.ts`：`registerPageContextExtras`、`mergeExtrasIntoContext`
- `frontend/.../plugin-shared.ts`：导出 `registerPageContextExtras`
- `backend/plugins/novusdoc/frontend/.../DocumentEditor.vue`：改用 extras 合并，补充 update_title 语义
- `frontend/.../useEditorPageOps.ts`：content_format 参数（html\|markdown）、默认 HTML 不自动转换
- `frontend/.../pageContextEditorOps.test.ts`：新增（params、extras 合并）
- `backend/app/ai/tools/executors/page_operation_executor.py`：恢复指引、禁止回显、get_editor_html 短片段提示
- `backend/app/ai/tools/executors/page_context_executor.py`：has_editor 时输出 available_operations 摘要
- `backend/app/ai/engine/stream_handler.py`：连续 pageop 失败中止
- `frontend/.../useEditorPageOps.ts`：replace_section error_type (target_not_found, non_unique_match, invalid_html)、get_editor_html _hint
- `backend/migrations/.../20260316_novusdoc_writer_scope_admin_and_all.py`：NovusDoc Writer 作用域调整为 `global_shared`（迁移文件名仍含历史 `admin_and_all` 字样）、system_prompt 解耦
- `backend/migrations/.../20260316_update_invoke_page_operation_desc.py`：params 描述 content_format（html|markdown）
- `backend/tests/services/test_stream_handler_real_stream.py`：parse error 熔断测试
- `backend/plugins/novusdoc/frontend/src/views/__tests__/DocumentEditorPageAwareness.test.ts`：DocumentEditor 组件级页面感知测试
