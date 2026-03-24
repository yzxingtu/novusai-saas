# 异步任务、通知、邮件与实时通信规则

## Celery 任务

- 业务任务模块必须使用 `@register_task`
- 禁止在业务任务模块直接写 `@celery_app.task`、`@shared_task`
- 任务函数第一个参数固定为 `self`
- Worker 是同步进程。业务任务优先用 `BaseTask` / `TenantTask` 提供的 `self.get_db_session()`；底层桥接任务、bootstrap 任务或独立写库任务可直接用 `sync_session_factory()`，但禁止使用异步 Session
- 返回值必须是 JSON 可序列化对象
- 新任务模块必须注册到 `celery_app.py` 的 `celery_app.conf.include` 列表（并保持 `_import_task_modules()` 能导入到）
- 插件注册器、消费者桥接器这类基础设施可在内部动态调用 `celery_app.task(...)`，但不对业务模块开放

## 任务基类与队列

- 平台级任务使用 `BaseTask`
- 企业隔离任务使用 `TenantTask`，调用时必须显式传 `tenant_id`
- 常用队列：`default`、`high_priority`、`ai_gateway`、`scheduled`、`notification`

## AI 调用日志与账本

- AI 调用日志默认不是在 HTTP 进程内直接 INSERT，而是通过 `CallLogService.log_call_async()` 投递到 `tasks.ai.log_ai_call`
- `tasks.ai.log_ai_call` 固定消费 `ai_gateway` 队列；调用日志页无数据但对话成功时，先查 worker 是否真的消费该队列
- 调用日志与用量统计的事实表是 `AICallLog` / `ai_call_logs`；不要再按旧 `ai_usage_stats` 心智排查
- `billing_context`、账本快照列、任务签名一旦变更，**API 与 Worker 必须同版本并重启 Worker**
- 若出现 `unexpected keyword billing_context`、日志页为空、统计无数据，优先怀疑：
  - Worker 仍跑旧代码
  - `ai_gateway` 队列无人消费
  - `task_logs` 中 `tasks.ai.log_ai_call` 失败
- 流式对话的调用日志通常在生成器尾部入队；客户端提前断开导致尾部逻辑未跑完时，允许出现“回答成功但无日志”的现象，先查流式生命周期，再怀疑 DB

## 定时任务

- 管理端可运维的定时任务统一落 `periodic_tasks` 表
- `is_locked=True` 的任务禁止删除
- `is_editable=False` 的任务只能切换启用状态
- 代码级 `beat_schedule` 只做系统级兜底，不应承载全部业务配置

## 邮件发送

- 所有业务邮件默认通过 Celery 异步发送
- 普通业务邮件使用 `send_email_task.delay()`
- 通知邮件不要直接调用邮件任务，必须走通知系统
- 禁止在 Controller / Service 直接调用同步发信逻辑

## 通知系统

- 业务通知统一走 `NotificationService.send()` / `notify()`
- 同步上下文（如 Celery）使用 `notify_sync()`
- 模板编码格式固定为 `{category}.{event_name}`
- 渠道选择由模板 `channels` + 用户偏好共同决定，禁止业务代码硬编码渠道
- 禁止直接操作 Notification 表

## 通知偏好治理

- admin / tenant 端通知偏好统一走 `NotificationPreferenceService`
- 前端统一复用 `NotificationSettings.vue`，不要在偏好页分散手写开关矩阵
- 读取优先级固定为 `individual -> global -> default`
- 更新全局偏好后，必须精确清除受影响分类的个人覆盖
- 全局偏好更新广播事件固定为 `notification_preference:global_updated`

## WebSocket / Socket.IO

- namespace 固定为 `/admin`、`/tenant`、`/user`
- 后端异步上下文用 `sio.emit(...)`
- Celery / 同步上下文用 `sio_bridge` 的 `notify_*_sync()`
- room 规范：`user:{user_id}`、`tenant:{tenant_id}`、`admins`
- 新事件统一使用 `命名空间:动作` 命名，全部小写

## 强制下线

- Token 吊销统一走 `revoke_token`
- 强制下线必须同时推送 Socket.IO `force_logout` 事件
- 不要只删除前端 token 而不写入 blacklist

## 禁止事项

- 禁止在任务中直接使用异步 DB Session
- 禁止在业务代码里直接发通知邮件
- 禁止在 Celery 同步环境直接调用异步 `sio.emit`
- 禁止新增与现有 namespace 冲突的事件命名

## 参考

- [../skills/novusai-saas/references/async-tasks.md](../skills/novusai-saas/references/async-tasks.md)
- [../skills/novusai-saas/references/notification-spec.md](../skills/novusai-saas/references/notification-spec.md)
- [../skills/novusai-saas/references/notification-preference-spec.md](../skills/novusai-saas/references/notification-preference-spec.md)
- [../skills/novusai-saas/references/email-spec.md](../skills/novusai-saas/references/email-spec.md)
- [../skills/websocket-guide/SKILL.md](../skills/websocket-guide/SKILL.md)
- [../skills/novusai-saas/references/token-force-logout-spec.md](../skills/novusai-saas/references/token-force-logout-spec.md)
- [../skills/ai-call-log-usage-ledger/SKILL.md](../skills/ai-call-log-usage-ledger/SKILL.md)
