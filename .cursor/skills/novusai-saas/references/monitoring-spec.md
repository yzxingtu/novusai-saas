# 可观测性与监控规范 / Observability & Monitoring Specification

> 本规范总结当前仓库实际存在的可观测性管道（日志、系统日志 API、AI 健康/Rosputin、WebSocket 在线度）以及 Trace ID 传播/指标埋点的落地方式。

## 一、日志体系

- `app/core/logging.py` 通过 `LogManager` 统一配置 Loguru：默认控制台 + 本地文件（app.log、error.log、db.log 等），格式里自带 `[trace_id=xxx]`。
- `LogCategoryEnum` 确保不同模块写入不同日志文件（app / error / db / queue / task / captcha / storage / auth / impersonate）。
- Service 里优先使用 `LoggerMixin` / `self.logger`，其他模块用 `get_logger(__name__)`；禁止直接 `from loguru import logger` 或 `print()`。
- `TraceIdMiddleware`（`backend/app/middleware/trace.py`）在 HTTP + WebSocket 请求/响应里注入 `X-Trace-ID`，记录到 `trace_id_var`，LogManager 的 patcher 会自动将其加入每条日志。
- 所有 5xx 错误由前端 `notification.error()` 展示，响应里必须回传 `X-Trace-ID` 以便用户复制，前端不可自动消失。
- CLI 侧已提供 `novusai trace show <trace_id>`，通过 `TraceLookupService` 聚合 `operation_logs` 与文件日志，是当前仓库里 trace 级排障的标准入口。

## 二、系统日志管理

- `backend/app/services/system/system_log_service.py` 聚合日志分类统计、文件列表、内容分页、下载/删除，避免前端直接读磁盘。
- `backend/app/api/admin/system_logs.py` 对应 `GET /admin/system-logs/*` 接口暴露统计、分类、分页内容、文件下载和删除，权限由 `system_log` 资源控制。
- 任何前端调试页面（例如 `/admin/system-mgmt/system-logs`）必须通过上述 API 获取信息，不允许前端直接访问 `logs/` 目录。

## 三、AI 运行态健康监控

- `app.ai.failover.FailoverService` 从 Redis（`ai:provider:{id}:health` / `ai:provider:{id}:health_history`）读取每个 provider 的健康度，并判断是否切换备用模型。
- `backend/app/api/admin/ai_health.py` 将这些健康度和历史展示给平台管理员（`GET /admin/ai/health`、`GET /admin/ai/health/{provider_id}/history`）。
- Health 数据的记录点在 Celery 异常捕获/AI Gateway 调用失败路径里写入 Redis（见 `app/tasks/ssl_tasks.py`、`app/tasks/base.py`等），这些记录宜包 `try/except` 防止影响主流程。

## 四、WebSocket 在线度与 presence

- `app/sio/presence.py` 维护 Redis Hash，`PresenceManager` 提供 `set_online`/`set_offline`/`get_online_details` 等接口。
- API `GET /admin/ws/presence`、`GET /admin/ws/presence/tenant/{tenant_id}`、`GET /tenant/ws/presence`、`GET /tenant/ws/presence/users` 供页面初始化拉取在线 ID 列表与连接数；数据以 `details` 字典返回（key 是 `user_id`）。
- WebSocket 连接/断开处（`app/sio/*_ns.py`）必须调用 `PresenceManager`，确保 Redis 数据始终与 `AsyncServer` 的 sid 对齐。

## 五、Trace ID 在 Celery / sync 场景的传播

- Celery 任务使用 `BaseTask`（`app/tasks/base.py`）自带 `trace_id` header 传播，`before_start`/`after_return` 里自动调用 `trace_id_var.set()`。
- 同步上下文（如 Celery Worker）如果需要发 Socket.IO 事件，应走 `app/core/sio_bridge.py`：`sio_emit_sync`/`notify_*_sync()` 复用 RedisManager，避免直接 import AsyncServer。
- `notify_sync()` 也从 `trace_id_var` 提取 trace_id，确保通知链路的日志能关联到原始请求。

## 六、Trace CLI 查询能力

当前仓库已落地：

```bash
novusai trace show <trace_id> [--source auto|db|logs|all] [--json]
```

- 默认 `--source auto`
- 默认 `--context 20`
- 默认 `--max-blocks 10`
- 默认 `--since-hours 72`
- 输出包含：
  - `primary_error`
  - `operation_logs`
  - `log_matches`
  - `summary`
- 生产 / 预发环境默认强制脱敏；如需未脱敏输出，必须同时满足 `--unsafe` 与 `NOVUSAI_ALLOW_UNSAFE_TRACE=1`

## 七、指标埋点指引

- 当前主干仓库没有统一的 `app/core/metrics.py`，也没有可确认存在的 `/admin/monitoring/*` 管理端监控路由。
- 如果未来需要新增 Prometheus / OpenTelemetry / 自定义计数器，请遵循：
  - 指标定义紧邻实际业务模块
  - 指标调用必须包 `try/except`
  - 同步更新规则文档与可观测性入口
- 不要在文档里虚构尚未落地的 `/metrics` 白名单、Grafana iframe、Dashboard 页面或 `monitoring/index.vue`。

## 八、扩展性规则

- 新增监控路径（AI、Celery、WebSocket）必须同步更新 `trace-and-monitoring` 规则、`monitoring-spec` 文档、以及能观察到的数据端点（`system_logs`、`ai_health`、`ws/presence`）中的一项。
- 监控相关的配置文档（如 `configs/definitions/platform_monitoring.py`）应只在 admin scope 里暴露，避免租户或 user 端访问。
