---
inclusion: fileMatch
fileMatchPattern: 'backend/migrations/**/*.py,backend/app/models/**/*.py,backend/alembic.ini'
---

# 数据库迁移最佳实践

## 创建新迁移文件

```bash
cd backend
.venv\Scripts\alembic revision -m "描述信息"
```

迁移文件名格式：`YYYYMMDD_HHMM_描述.py`

## 正确设置迁移依赖关系

创建迁移后，必须检查并修改 `down_revision`：

```python
revision = '20260208_0013_add_ai_provider_models'
down_revision = '676cbd976326'  # 必须设置为最新的迁移版本号
```

检查当前最新版本：
```bash
.venv\Scripts\alembic heads
.venv\Scripts\alembic history
```

## 处理迁移失败

### 表已存在但版本未标记

```bash
.venv\Scripts\alembic stamp <revision_id>
```

### 多个 head revisions

```bash
.venv\Scripts\alembic heads
# 修改新迁移的 down_revision 为最新 head
.venv\Scripts\alembic upgrade head
```

## 关键注意

- **新增 Model 必须注册到两个地方**：
  1. `backend/app/models/__init__.py` — 添加 import 和 `__all__` 导出
  2. `backend/migrations/env.py` — 添加 import
- 避免使用 SQLAlchemy 保留字作为列名（如 `metadata` → `request_metadata`）
- 启动时自动执行 `alembic upgrade head`，无需手动

## 数据库会话获取方式

| 场景 | 方法 | 类型 |
|------|------|------|
| FastAPI 路由依赖注入 | `db: AsyncSession = Depends(get_db)` | 异步 |
| Service/非路由上下文 | `async with get_db_context() as db:` | 异步 |
| Celery Worker 内 | `self.get_db_session()` | 同步 |

## 快速参考命令

```bash
alembic current          # 查看当前版本
alembic heads            # 查看所有 heads
alembic history          # 查看迁移历史
alembic revision -m "描述"  # 创建新迁移
alembic upgrade head     # 运行迁移
alembic downgrade -1     # 回滚一个版本
alembic stamp <rev_id>   # 标记版本（不执行迁移）
```
