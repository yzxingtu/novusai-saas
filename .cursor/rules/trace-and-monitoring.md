# Trace ID、日志与监控规则

## Trace ID

- 每个请求必须携带或生成 `X-Trace-ID`
- 后端统一通过 `trace_id_var.get()` 读取当前链路 trace_id
- 前端请求自动注入 header，不要手工拼第二套 trace 机制
- Celery 通过 `BaseTask` 自动传播 trace_id，不要自行重复实现
- WebSocket 连接在 namespace `connect` 期间也要写入 trace context

## 日志

- 日志统一通过 `app.core.logging` 暴露的封装使用
- 常规模块优先 `get_logger(__name__)`
- Service 优先 `LoggerMixin` / `self.logger`
- 需要分类日志文件时使用 `LogManager.get_logger(...)` 或 `get_category_logger(...)`
- 禁止直接 `from loguru import logger`
- 禁止 `print()` 和 `logging.getLogger()`
- Loguru 参数格式统一使用 `{}`，不要 `%s` / `%d`

## 5xx 错误展示

- 全局 HTTP 5xx 错误必须用 `notification.error()`
- 错误提示需要展示响应头中的 `X-Trace-ID`
- 追踪 ID 应支持复制，不要自动消失

## Prometheus / Grafana

- 监控仅允许 Admin 端暴露
- 自定义指标定义在 `app/core/metrics.py`
- 新增 AI / Celery / WebSocket 关键路径时，必须同步埋点
- 所有指标写入必须包 `try/except`，不能影响主流程
- `/metrics` 受 IP 白名单控制

## AI 操作审计日志

- 新增 AI 工具执行、页面操作或确认流时，统一走 `write_ai_action_log()`
- 动作等级优先显式传入；需要推断时复用 `resolve_action_level()`
- 状态值固定 `success` / `failed` / `rejected` / `pending_confirm`
- 耗时字段统一为 `duration_ms`，不要另造 `execution_time_ms`
- 审计日志页是只读查询面板，不要加入编辑/删除能力

## 典型埋点位置

- `AIGateway`：调用量、token、延迟
- `BaseTask`：成功 / 失败计数
- Socket.IO namespace：连接数增减
- 采样型 Gauge：队列长度、DB 连接池、活跃企业数

## 参考

- `../skills/novusai-saas/references/trace-id-logging-spec.md`
- `../skills/novusai-saas/references/monitoring-spec.md`
- `../skills/novusai-saas/references/ai-action-log-spec.md`
