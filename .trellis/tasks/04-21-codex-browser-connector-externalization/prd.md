# Codex Browser Connector Externalization

## Goal

把 page/browser 执行继续外推成接近 codex-main 的 connector/MCP-like boundary。
聊天核心只认 canonical `ui_*` payload、consent/result evidence、以及
thin `page_context`；页面快照、surface graph、DOM/组件细节继续由 page runtime
owner 持有，而不是被聊天核心重新理解。

## Current Gap

当前系统已经有 shared UI runtime、thin `page_context`、canonical `ui_*` 工具名、
page action executor 和 navigation/page-runtime helper，但仍有剩余 gap：

1. page execution 还有部分 host-specific helper 味道，没有完全呈现为 connector owner。
2. connector evidence contract 还需要进一步固定，便于后续 page workflow / core loop 只做消费。
3. page/browser 细节不能再回流到 builtin executor 或聊天核心的兼容 glue。
4. Socket.IO `page_session` 传输层仍保留 `(scope, user_id, page_key) -> page_session_id`
   的活跃会话追踪与保守 fallback，这仍是 `page_key -> session_id` 身份链残留，
   不符合“page/session-first connector owner”的目标。

## Write Scope

- `frontend/apps/web-antd/src/components/business/ai-runtime/**`
- `frontend/apps/web-antd/src/utils/page-navigation.ts`
- `backend/app/ai/tools/page_runtime/**`
- `backend/app/ai/tools/executors/ui_action_executor.py`
- `backend/app/sio/page_session.py`
- page runtime websocket / page session related tests

## Requirements

1. thin `page_context` 必须继续只由 runtime bridge 产出；不得新增第二套
   page-context assembler 或 page-local payload builder。
2. `ui_get_snapshot`、`ui_read_*`、`ui_click`、`ui_open_surface`、
   `ui_fill_form`、`ui_submit_form` 的 payload/result contract 必须稳定，
   便于 page workflow 和 turn loop 后续只消费 connector evidence。
3. page execution 逻辑不得继续混入 generic builtin executor 或聊天核心入口。
4. connector boundary 必须保留 canonical `ui_*` 动作名、security/consent
   分类、surface/session/diff 证据；不得回退到 legacy page-op 名称。
5. route AI policy、runtime bridge、action executor、page-runtime tools
   必须共享同一套 live tool naming contract。
6. `page_session` transport 必须以 live `page_session_id` 为主身份链；
   不得继续让 `page_key -> active_session_id` fallback 充当运行时恢复 owner。

## Acceptance

1. chat core 不再需要知道页面 DOM / 组件细节，只消费 connector 产出的结构化证据。
2. page runtime 相关读写/提交动作都通过 canonical `ui_*` payload 流转，
   不再依赖 legacy page-op 或 builtin/page hybrid seam。
3. thin `page_context`、runtime bridge、ui action executor、page-runtime tools
   的 contract 在前后端测试中保持一致。
4. `backend/app/sio/page_session.py` 不再维持 `page_key -> session_id`
   作为 live transport fallback 主路径。
5. page-runtime policy、guards、runtime-bridge、page-session transport 回归保持绿灯。
