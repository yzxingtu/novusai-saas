---
inclusion: fileMatch
fileMatchPattern: 'backend/app/tasks/**/*.py,backend/app/celery_app.py'
---

# 异步任务与定时任务开发规范

本项目使用 Celery + Redis 实现异步任务和定时任务。

## 核心规范

1. 必须使用 `@register_task` 装饰器，禁止直接用 `@celery_app.task`
2. 第一个参数始终是 `self`（装饰器自动设置 `bind=True`）
3. Celery Worker 是同步进程，必须用 `self.get_db_session()` 获取同步 Session
4. 返回值必须是 JSON 可序列化的 dict
5. 新任务模块必须注册到 `celery_app.py` 的 `task_modules` 列表

## 任务基类选择

| 基类 | 用途 |
|------|------|
| `BaseTask` | 平台级任务（默认） |
| `TenantTask` | 租户隔离任务（自动从 kwargs 提取 `tenant_id`） |

## 队列选择

| 队列 | 用途 |
|------|------|
| `default` | 一般后台处理 |
| `high_priority` | 需快速响应的用户操作 |
| `ai_gateway` | AI 模型调用 |
| `scheduled` | 定时触发的任务 |

## 代码模板

### 基础任务

```python
from app.tasks.base import register_task, BaseTask

@register_task(queue="default", description="任务描述", max_retries=3)
def my_task(self: BaseTask, param1: int, param2: str) -> dict:
    session = self.get_db_session()
    try:
        return {"success": True}
    except TemporaryError as e:
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
    finally:
        session.close()
```

### 租户隔离任务

```python
from app.tasks.base import register_task, TenantTask

@register_task(queue="default", description="租户数据同步", base=TenantTask)
def sync_tenant_data(self: TenantTask, tenant_id: int, data_type: str) -> dict:
    session = self.get_db_session()
    try:
        return {"tenant_id": self.tenant_id, "synced": True}
    finally:
        session.close()
```

### 调用任务

```python
my_task.delay(param1=1, param2="test")
sync_tenant_data.delay(tenant_id=42, data_type="quota")
```

## 定时任务

- scope: `platform`（平台级）/ `tenant`（指定租户）/ `all_tenants`（全租户）
- `is_locked=True`：禁止删除
- `is_editable=False`：仅允许切换启用状态

## 启动命令

```bash
python scripts/start_worker.py worker    # Worker
python scripts/start_worker.py beat      # Beat 调度器
python scripts/start_worker.py dev       # 开发模式
```

## 检查清单

- [ ] 使用 `@register_task` 装饰器
- [ ] 第一个参数是 `self: BaseTask` 或 `self: TenantTask`
- [ ] 使用 `self.get_db_session()` 获取同步 Session
- [ ] 返回值是 JSON 可序列化的 dict
- [ ] 新模块已注册到 `celery_app.py` 的 `task_modules`
- [ ] 租户任务使用 `TenantTask` 基类
