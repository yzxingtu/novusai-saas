# 异步任务与定时任务开发规范

本项目使用 Celery + Redis 实现异步任务和定时任务；规范以本文件及仓库内 `async-notification-websocket` 规则为准。

---

## 核心规范

### 任务编写

1. **业务任务模块必须使用 `@register_task` 装饰器**（`app/tasks/base.py`），禁止直接写 `@celery_app.task`
2. **第一个参数始终是 `self`**（装饰器自动设置 `bind=True`）
3. **Celery Worker 是同步进程**。业务任务优先用 `self.get_db_session()` 获取同步 Session；底层桥接任务、bootstrap 任务或当前已有的独立写库任务也可以直接使用 `sync_session_factory()`，但禁止使用 `async`
4. **返回值必须是 JSON 可序列化的 dict**
5. **新任务模块**必须注册到 `celery_app.py` 的 `celery_app.conf.include` 列表，并确保 `_import_task_modules()` 会导入它

### 任务基类选择

| 基类 | 用途 | 说明 |
|------|------|------|
| `BaseTask` | 平台级任务 | 默认基类，自动记录日志和耗时 |
| `TenantTask` | 企业隔离任务 | 自动从 kwargs 提取 `tenant_id`，调用时必须传 `tenant_id` |

### 队列选择

| 队列 | 路由规则 | 用途 |
|------|----------|------|
| `default` | 默认 | 一般后台处理 |
| `high_priority` | `app.tasks.high_priority.*` | 需快速响应的用户操作 |
| `ai_gateway` | `app.tasks.ai.*` | AI 模型调用（可能较慢） |
| `scheduled` | `app.tasks.scheduled.*` | 定时触发的任务 |
| `notification` | `app.tasks.notification.*` | 通知邮件、站内信等通知相关任务 |

### 禁止事项

- **禁止业务任务模块使用 `@shared_task` 或 `@celery_app.task`**（插件注册器等框架桥接层内部动态注册 Celery task 属于例外；`ai.py` 当前已经迁移到 `@register_task`）
- **禁止在 `@register_task` 中传 `bind=True` 或 `base=BaseTask`**（装饰器已自动设置）
- **禁止在任务函数内直接写 `async def`**（Celery Worker 是同步进程）
- **禁止使用异步 DB Session**（应使用 `self.get_db_session()` 或明确的 `sync_session_factory()` 同步 Session）

---

## 代码模板

### 基础任务

```python
# app/tasks/my_module.py

from app.tasks.base import register_task, BaseTask

@register_task(
    queue="default",
    description="任务描述（必填）",
    max_retries=3,
)
def my_task(self: BaseTask, param1: int, param2: str) -> dict:
    session = self.get_db_session()
    try:
        # 业务逻辑
        return {"success": True}
    except TemporaryError as e:
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
    finally:
        session.close()
```

### 企业隔离任务

```python
from app.tasks.base import register_task, TenantTask

@register_task(
    queue="default",
    description="企业数据同步",
    base=TenantTask,
)
def sync_tenant_data(self: TenantTask, tenant_id: int, data_type: str) -> dict:
    # self.tenant_id 自动可用
    session = self.get_db_session()
    try:
        return {"tenant_id": self.tenant_id, "synced": True}
    finally:
        session.close()
```

### 包装异步代码（当必须调用 async 函数时）

```python
@register_task(
    queue="scheduled",
    description="需要调用异步代码的任务",
    max_retries=1,
)
def task_with_async(self: BaseTask) -> dict:
    import asyncio

    async def _async_work():
        # 异步业务逻辑（如 Redis 操作、DNS 查询等）
        from app.core.redis import get_redis_client
        client = get_redis_client()
        return await client.get("some_key")

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_async_work())
        return {"result": result}
    finally:
        loop.close()
```

### 调用任务

```python
# Service 层调用
from app.tasks.my_module import my_task

# 立即异步执行
result = my_task.delay(param1=1, param2="test")

# 高级选项
result = my_task.apply_async(
    kwargs={"param1": 1, "param2": "test"},
    queue="high_priority",     # 覆盖默认队列
    countdown=10,              # 延迟执行
    expires=3600,              # 过期时间
)

# 通过任务名称调用（适用于跨模块/动态触发）
from app.celery_app import celery_app
celery_app.send_task(
    "app.tasks.ssl_tasks.task_provision_ssl",
    args=[domain_id],
    queue="default",
)

# 企业任务必须传 tenant_id
sync_tenant_data.delay(tenant_id=42, data_type="quota")
```

---

## 定时任务

### PeriodicTask 模型关键字段

| 字段 | 说明 |
|------|------|
| `name` | 任务名称（企业内唯一） |
| `task_path` | 任务路径，如 `app.tasks.scheduled.clean_expired_captchas` |
| `schedule_type` | `cron` / `interval` |
| `cron_expression` | Cron 表达式（分 时 日 月 周） |
| `interval_seconds` | 间隔秒数 |
| `scope` | `ResourceScopeEnum` 五类之一（DB 驱动定时任务投放面） |
| `owner_tenant_id` | 企业自有任务时非空；平台任务为 `NULL`（`TenantRepository` 仍可用 `tenant_id` 别名） |
| `is_locked` | 禁止删除保护 |
| `is_editable` | 禁止编辑保护 |

### 作用范围（与 Celery `TenantTask` 区分）

- **DB `PeriodicTask`**：用 **`scope` + `owner_tenant_id` + RTA** 表达与平台其它资源一致；禁止再写「platform/tenant/all_tenants 三分法」旧语义。
- **Celery 任务**：`TenantTask` 仍通过 **kwargs `tenant_id`** 做运行隔离，与 `PeriodicTask.scope` 不是同一概念。

### 保护机制

- `is_locked=True`：禁止删除（Service `_before_delete` 钩子校验）
- `is_editable=False`：仅允许切换启用状态（Service `_before_update` 钩子校验）
- 系统内置任务建议设置 `is_locked=True, is_editable=False`

### Beat 调度注册（两种方式）

**方式 1：代码级静态注册**（`celery_app.py` 的 `beat_schedule`）

适用于系统内置、不需要运行时修改的任务。

```python
# celery_app.py beat_schedule 中添加
from celery.schedules import crontab

"check-ssl-renewals": {
    "task": "app.tasks.ssl_tasks.task_check_ssl_renewals",
    "schedule": crontab(hour=3, minute=0),  # 每天凌晨 3:00
    "options": {"queue": "scheduled"},
},
```

**方式 2：DB 动态注册**（`PeriodicTask` 表 + Alembic 种子数据）

适用于需要管理员在后台管理界面查看/启停/修改的任务。

```python
# Alembic 迁移中插入种子数据
PeriodicTask(
    name="check-ssl-renewals",
    task_path="app.tasks.ssl_tasks.task_check_ssl_renewals",
    schedule_type="cron",
    cron_expression="0 3 * * *",     # 分 时 日 月 周
    is_active=True,
    scope="admin_only",              # 示例：平台级调度，与 ResourceScopeEnum 一致
    owner_tenant_id=None,
    is_locked=True,
    is_editable=False,
    description="每日检查 SSL 证书续期",
    max_retries=1,
    timeout=1800,
    notify_on_failure=True,
)
```

**最佳实践**：两种方式同时注册。Beat 静态注册保证兜底执行，DB 注册提供管理界面可见性。`scheduler.py` 的 `setup_periodic_tasks()` 会用 DB 配置覆盖同名静态配置。

### crontab vs interval 选择

| 场景 | 推荐 | 示例 |
|------|------|------|
| 每天固定时间执行 | `cron` | `0 3 * * *`（凌晨 3:00） |
| 固定间隔（健康检查等） | `interval` | `300`（5 分钟） |
| 一次性异步任务 | 不注册 Beat | `task.delay()` 或 `send_task()` |

---

## 现有任务清单

| 任务 | 文件 | 队列 | 调度 |
|------|------|------|------|
| `system_health_check` | `scheduled.py` | `scheduled` | interval 300s |
| `clean_expired_captchas` | `scheduled.py` | `scheduled` | interval 3600s |
| `clean_expired_task_logs` | `scheduled.py` | `scheduled` | interval 86400s |
| `reset_agent_daily_quotas` | `scheduled.py` | `scheduled` | interval 86400s |
| `reset_agent_daily_stats` | `scheduled.py` | `scheduled` | interval 86400s |
| `ai_provider_health_check` | `ai_health_check.py` | `scheduled` | interval 300s |
| `cleanup_recycle_bin` | `recycle_bin.py` | `scheduled` | interval 86400s |
| `cleanup_chunk_uploads` | `upload_cleanup.py` | `scheduled` | interval 21600s |
| `log_ai_call_task` | `ai.py` | `ai_gateway` | 一次性（API 触发） |
| `execute_batch_run` | `agent_batch.py` | `ai_gateway` | 一次性（API 触发） |

---

## Redis 缓存工具

```python
from app.core.redis import cache_get, cache_set, cache_delete, cache_exists

await cache_set("key", {"data": "value"}, ttl=3600)  # 自动 JSON 序列化
data = await cache_get("key")                          # 自动 JSON 反序列化
await cache_delete("key")
exists = await cache_exists("key")
```

---

## 启动命令

```bash
python scripts/start_worker.py worker              # Worker（所有队列）
python scripts/start_worker.py worker -Q default    # Worker（指定队列）
python scripts/start_worker.py beat                 # Beat 调度器（全局只启动一个）
python scripts/start_worker.py dev                  # 开发模式（Worker + Beat）
```

---

## 检查清单

- [ ] 使用 `@register_task` 装饰器
- [ ] 第一个参数是 `self: BaseTask` 或 `self: TenantTask`
- [ ] 业务任务优先使用 `self.get_db_session()`；若使用 `sync_session_factory()`，说明这是底层/桥接型任务而非普通业务任务
- [ ] 返回值是 JSON 可序列化的 dict
- [ ] 新模块已注册到 `celery_app.py` 的 `celery_app.conf.include`
- [ ] 企业任务使用 `TenantTask` 基类
- [ ] 合理选择队列
- [ ] 设置合适的 `max_retries` 和 `description`
- [ ] 临时错误使用 `self.retry()`，永久错误直接返回
