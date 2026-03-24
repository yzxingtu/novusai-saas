# Trace ID、日志与监控规则

## Trace ID 与日志

- `TraceIdMiddleware`（`backend/app/middleware/trace.py`）在 HTTP/WebSocket 请求期间生成或传递 `X-Trace-ID`，并通过 `trace_id_var.set()` 让 `app.core.logging` 的 Loguru patcher 自动注入到每条日志中，也回写响应头。
- 后端统一读 `trace_id_var.get()`；Celery 任务请依赖 `BaseTask`/`register_task` 的 header 传播，禁止手工再实现一套链路。
- Service、Controller、Celery、Socket.IO handler 统一用 `get_logger(__name__)` 或 `LoggerMixin` 写日志，禁止 `print()`、`logging.getLogger()` 或直接 `from loguru import logger`。
- 错误日志里要包含 `[trace_id=xxx]`，便于前端与运维定位请求链路。

## Trace ID 排查入口

- 拿到 `trace_id` 后，标准排障入口不是人工全库翻日志，而是 CLI：`novusai trace show <trace_id>`
- `novusai trace show` 通过 `TraceLookupService` 聚合两类来源：
  - `system.operation_logs` 中的同 trace 审计记录
  - `LOG_DIR` 下 `*.log*` 文件里的 `[trace_id=xxx]` 命中块
- 默认 `--source auto`：
  - 优先查 DB + 文件日志
  - 若 DB lookup 失败，则自动回退到仅日志文件扫描
- 常用参数：
  - `--source auto|db|logs|all`
  - `--context 20`
  - `--max-blocks 10`
  - `--since-hours 72`
  - `--json`
- 输出重点包括：
  - `primary_error`：优先返回包含 `Traceback`、`ERROR`、`CRITICAL` 的主错误块
  - `operation_logs`
  - `log_matches`
- 如果只是页面层辅助核对，也可在 admin / tenant 操作日志列表按 `filter[trace_id]=xxx` 精确筛选，但 CLI 仍是首选排障路径

## 生产环境安全边界

- `novusai trace show` 默认会对 token、password、cookie、dsn、authorization 等敏感信息做脱敏
- 在 `production` / `staging` 环境中，禁止直接用 `--no-redact` 输出未脱敏内容
- 如确需未脱敏输出，必须同时满足：
  - 传 `--unsafe`
  - 设置 `NOVUSAI_ALLOW_UNSAFE_TRACE=1`
- 不满足条件时，CLI 会返回 `unsafe_output_blocked`，并以退出码 `2` 失败
- 规则、工单和用户支持流程都应默认以“脱敏输出”为基线，不要把未脱敏 trace 输出当常规做法

## 5xx 错误展示

- 全局 5xx 由前端 `notification.error()` 展示；提示里需包含响应头的 `X-Trace-ID`，并提供“复制”按钮，不可自动消失。
- 由 `TraceIdMiddleware` 保证所有 5xx 响应都带 trace_id，前端无需再拼 header。

## 页面级请求错误显示

- `requestClient` 默认会处理失败信息，若页面要自行 `catch`，必须先设置 `showErrorMessage: false` + `showCodeMessage: false`。
- 自定义错误展示请复用 `showRequestError(error, fallbackKey)` 或 `getErrorMessage(error, fallbackKey)`，不要直接写 `message.error()` 覆盖真实信息。
- 生产环境的用户界面应显示“响应提示 + trace_id”，开发环境可额外显示 `debugMessage`。

## 请求错误 owner 与软失败治理

- 同一次请求错误只能有一个前端展示 owner：
  - 要么由 `requestClient` / 拦截器负责展示
  - 要么页面显式关闭默认弹错后，自行调用 `showRequestError()` / `getErrorMessage()`
- 页面本地校验、复制失败、非请求型 UI 错误可以直接本地提示；但只要是 HTTP 请求错误，就应优先进入统一 `AppError` / `trace_id` 链路
- **常规 HTTP API 失败不应以 `200 + success=false + error/message/errors` 作为长期契约**
- 若历史接口暂时保留软失败协议：
  - 页面必须明确知道该接口绕过了统一错误拦截链路
  - 本地处理时仍应尽量保留后端给出的 `trace_id`
  - 禁止在各页面散落手写 `message.error(result.message)` 形成第二套治理
- 审计前端请求错误时，优先检查：
  - 是否出现双 toast
  - 是否直接读取 `error.message`
  - 是否在 `catch` 里写死 `message.error($t('common.requestFailed'))`
  - 是否把统一 `trace_id` 文案覆盖掉

## 可观测性/监控

- 当前主干仓库没有统一的 `app/core/metrics.py`，也没有专门的 `/admin/monitoring/*` 路由；现有可观测性主要通过分类日志、`X-Trace-ID`、`/admin/system-logs/*`、`/admin/ai/health*`、`/admin|tenant/ws/presence*` 完成。
- CLI 观测入口也属于当前实际已落地能力的一部分：`novusai trace show <trace_id>`，不能再把 trace 排查描述成“只能手工翻文件日志”。
- 若后续新增 Prometheus 指标，必须把定义放在实际业务模块旁边，并用 `try/except` 包裹，不能再假设存在一套中心化 `metrics.py`。
- 可观察数据端点包括：
  - `/admin/system-logs/*`（`backend/app/api/admin/system_logs.py`）：统计、分类、分页内容、下载、删除。
  - `/admin/ai/health` 与 `/admin/ai/health/{provider_id}/history`（`backend/app/api/admin/ai_health.py`）：AI 供应商健康 + 历史。
  - `/admin/ws/presence`、`/admin/ws/presence/tenant/{tenant_id}`、`/tenant/ws/presence`、`/tenant/ws/presence/users`（`PresenceManager`）：Socket.IO 在线状态与连接数。
- 当前主干未见专用 Grafana iframe 配置页或 `/metrics` 管理端端点；若分支后续接入 Prometheus / Grafana，必须显式补齐路由、配置项与文档，而不是沿用过时说法。

## AI 操作审计日志

- `write_ai_action_log()` + `resolve_action_level()` 仍是 AI 工具、页面操作、确认流写入 `AIActionLog` 的唯一入口，状态固定在 `success`/`failed`/`rejected`/`pending_confirm`，耗时字段统一 `duration_ms`。
- 审计日志仅供只读显示，后台禁止再新增编辑/删除能力。

## 参考

- [../skills/novusai-saas/references/trace-id-logging-spec.md](../skills/novusai-saas/references/trace-id-logging-spec.md)
- [../skills/novusai-saas/references/monitoring-spec.md](../skills/novusai-saas/references/monitoring-spec.md)
- [../skills/novusai-saas/references/ai-action-log-spec.md](../skills/novusai-saas/references/ai-action-log-spec.md)
