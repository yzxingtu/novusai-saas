# 异步任务与定时任务开发规范

本项目使用 Celery + Redis 实现异步任务和定时任务。完整文档见 DevGenius MCP 文档《P1-1 异步队列与定时任务 - 使用指南》。

---

## 核心规范

### 任务编写

1. **必须使用 `@register_task` 装饰器**（`app/tasks/base.py`），禁止直接用 `@celery_app.task`
2. **第一个参数始终是 `self`**（装饰器自动设置 `bind=True`）
3. **Celery Worker 是同步进程**，必须用 `self.get_db_session()` 获取同步 Session，禁止使用 `async`
4. **返回值必须是 JSON 可序列化的 dict**
5. **新任务模块**必须注册到 `celery_app.py` 的 `task_modules` 列表

### 任务基类选择

| 基类 | 用途 | 说明 |
|------|------|------|
| `BaseTask` | 平台级任务 | 默认基类，自动记录日志和耗时 |
| `TenantTask` | 租户隔离任务 | 自动从 kwargs 提取 `tenant_id`，调用时必须传 `tenant_id` |

### 队列选择

| 队列 | 路由规则 | 用途 |
|------|----------|------|
| `default` | 默认 | 一般后台处理 |
| `high_priority` | `app.tasks.high_priority.*` | 需快速响应的用户操作 |
| `ai_gateway` | `app.tasks.ai.*` | AI 模型调用（可能较慢） |
| `scheduled` | `app.tasks.scheduled.*` | 定时触发的任务 |

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

### 租户隔离任务

```python
from app.tasks.base import register_task, TenantTask

@register_task(
    queue="default",
    description="租户数据同步",
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

# 租户任务必须传 tenant_id
sync_tenant_data.delay(tenant_id=42, data_type="quota")
```

---

## 定时任务

### PeriodicTask 模型关键字段

| 字段 | 说明 |
|------|------|
| `name` | 任务名称（租户内唯一） |
| `task_path` | 任务路径，如 `app.tasks.scheduled.clean_expired_captchas` |
| `schedule_type` | `cron` / `interval` |
| `cron_expression` | Cron 表达式（分 时 日 月 周） |
| `interval_seconds` | 间隔秒数 |
| `scope` | `platform`（平台级）/ `tenant`（指定租户）/ `all_tenants`（全租户） |
| `tenant_id` | scope=tenant 时必填 |
| `is_locked` | 禁止删除保护 |
| `is_editable` | 禁止编辑保护 |

### 作用范围

- **platform**：平台级，管理员创建，tenant_id=NULL
- **tenant**：指定租户，必须关联 tenant_id
- **all_tenants**：全租户，管理员创建，自动对所有租户执行

### 保护机制

- `is_locked=True`：禁止删除（Service `_before_delete` 钩子校验）
- `is_editable=False`：仅允许切换启用状态（Service `_before_update` 钩子校验）
- 系统内置任务建议设置 `is_locked=True, is_editable=False`

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
- [ ] 使用 `self.get_db_session()` 获取同步 Session
- [ ] 返回值是 JSON 可序列化的 dict
- [ ] 新模块已注册到 `celery_app.py` 的 `task_modules`
- [ ] 租户任务使用 `TenantTask` 基类
- [ ] 合理选择队列
- [ ] 设置合适的 `max_retries` 和 `description`
- [ ] 临时错误使用 `self.retry()`，永久错误直接返回
