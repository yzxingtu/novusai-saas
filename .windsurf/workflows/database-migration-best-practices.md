# 数据库迁移最佳实践

## 核心机制：启动时自动迁移（实时迁移）

**本项目启动时自动执行 `alembic upgrade head`，无需手动运行迁移命令。**

流程（`app/core/database.py` → `init_database()` → `run_migrations()`）：
```
FastAPI 启动 (lifespan)
  → init_database()
    → create_database_if_not_exists()  # 检查/创建数据库
    → run_migrations()                 # 自动执行 alembic upgrade head
    → check_database_connection()      # 验证连接
```

**这意味着：**
1. 创建模型 + 生成迁移文件后，只需等待后端热重载（开发模式 uvicorn --reload），迁移会自动执行
2. **不需要手动运行** `alembic upgrade head`
3. 生产部署时，服务启动也会自动迁移
4. 如果迁移失败，服务启动会报错并退出

**开发流程：**
```
1. 创建/修改 Model 文件
2. 在 models/__init__.py 和 migrations/env.py 注册模型
3. 生成迁移文件：alembic revision --autogenerate -m "描述"
4. 清理迁移文件（删除不相关的 autogenerate 噪音）
5. 等待热重载自动执行迁移 ✅
```

---

## 常见问题

在开发过程中，经常遇到 Alembic 迁移相关的问题，主要包括：

1. **Multiple head revisions** - 多个迁移头导致迁移失败
2. **表已存在错误** - 迁移部分执行但版本未标记
3. **迁移依赖关系错误** - `down_revision` 设置不当

## 解决方案

### 1. 创建新迁移文件

使用标准的日期时间格式命名迁移文件：

```bash
cd backend
.venv\Scripts\alembic revision -m "描述信息"
```

**重要：**
- 迁移文件名格式：`YYYYMMDD_HHMM_描述.py`
- 例如：`20260208_0013_add_ai_provider_models.py`

### 2. 正确设置迁移依赖关系

创建迁移后，必须检查并修改 `down_revision`：

```python
"""add AI provider models

Revision ID: 20260208_0013_add_ai_provider_models
Revises: 676cbd976326  # 必须设置为最新的迁移版本号
Create Date: 2026-02-08 05:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260208_0013_add_ai_provider_models'
down_revision = '676cbd976326'  # 接在最新的迁移版本之后
branch_labels = None
depends_on = None
```

**检查当前最新版本：**
```bash
.venv\Scripts\alembic heads
.venv\Scripts\alembic history
```

### 3. 处理迁移失败问题

#### 情况 1：表已存在但版本未标记

如果迁移部分执行失败（表已创建），使用 `stamp` 命令标记版本：

```bash
.venv\Scripts\alembic stamp <revision_id>
```

例如：
```bash
.venv\Scripts\alembic stamp add_ai_provider_models
```

#### 情况 2：多个 head revisions

如果出现多个 head：

```bash
# 查看所有 heads
.venv\Scripts\alembic heads

# 查看迁移历史
.venv\Scripts\alembic history

# 修复：将新迁移的 down_revision 设置为最新的 head
# 然后重新运行迁移
.venv\Scripts\alembic upgrade head
```

### 4. 常见错误和解决方法

#### 错误 1：Multiple head revisions

**原因：** 新迁移的 `down_revision` 设置为 `None` 或错误的版本号

**解决：**
1. 找到最新的迁移版本号：`alembic heads`
2. 修改迁移文件的 `down_revision` 为最新版本号
3. 如果表已创建，运行：`alembic stamp <revision_id>`

#### 错误 2：表已存在

**原因：** 迁移部分执行失败，表已创建但版本未标记

**解决：**
```bash
# 标记当前版本
alembic stamp <revision_id>

# 验证
alembic current
```

#### 错误 3：保留字冲突

**原因：** 使用了 SQLAlchemy 保留字作为列名（如 `metadata`）

**解决：** 修改列名，例如：
- `metadata` → `request_metadata` 或 `meta_data`
- `table` → `data_table` 或 `table_name`

### 5. 迁移开发流程

#### 步骤 1：创建模型

```python
# backend/app/models/ai/provider.py
from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

class AIProvider(BaseModel):
    __tablename__ = "ai_providers"
    
    name: Mapped[str] = mapped_column(String(100), index=True)
    models = relationship("AIModel", back_populates="provider")
```

#### 步骤 2：创建迁移

```bash
cd backend
.venv\Scripts\alembic revision -m "add AI provider models"
```

#### 步骤 3：检查并修改迁移文件

```python
# backend/migrations/versions/20260208_0013_add_ai_provider_models.py

# 1. 检查 revision ID 格式
revision = '20260208_0013_add_ai_provider_models'

# 2. 设置正确的 down_revision（必须！）
down_revision = '676cbd976326'  # 最新的迁移版本号
```

#### 步骤 4：测试迁移

```bash
# 查看当前版本
.venv\Scripts\alembic current

# 运行迁移
.venv\Scripts\alembic upgrade head

# 验证表已创建
# 可以通过 psql 或其他数据库工具查看
```

#### 步骤 5：启动服务器验证

```bash
.venv\Scripts\python -m app.main
```

### 6. LabeledStrEnum 与 asyncpg 兼容性

**关键：** 本项目使用 asyncpg 驱动，`LabeledStrEnum` 枚举对象不能直接用在 SQLAlchemy 查询条件中，必须用 `.value` 获取字符串值。

```python
# ❌ 错误 — asyncpg 报错: expected str, got SslCertStatus
query = select(Model).where(Model.status == SslCertStatus.ACTIVE)

# ✅ 正确 — 使用 .value
query = select(Model).where(Model.status == SslCertStatus.ACTIVE.value)

# ❌ 错误 — update values 也一样
await self.update(id, {"status": SslCertStatus.FAILED})

# ✅ 正确
await self.update(id, {"status": SslCertStatus.FAILED.value})
```

**适用范围：** Repository 的 `where()` 条件 + Service 的 `create()`/`update()` dict 值中所有 `LabeledStrEnum` 引用。

**不受影响：** Model 字段的 `default=EnumValue` 可以用枚举对象（SQLAlchemy 自动处理）。

### 7. 最佳实践清单

- [ ] 使用日期时间格式命名迁移文件：`YYYYMMDD_HHMM_descriptive_name.py`
- [ ] 创建迁移后立即设置 `down_revision`
- [ ] 使用 `alembic heads` 检查是否有多个 head
- [ ] 使用 `alembic current` 检查当前版本
- [ ] 避免使用 SQLAlchemy 保留字作为列名或表名
- [ ] 确保所有 `relationship` 都正确导入
- [ ] 迁移文件中避免硬编码数据，使用 `op.execute()` 或 seed 文件

### 7. 快速参考命令

```bash
# 查看当前版本
alembic current

# 查看所有 heads
alembic heads

# 查看迁移历史
alembic history

# 创建新迁移
alembic revision -m "描述"

# 运行迁移
alembic upgrade head

# 回滚一个版本
alembic downgrade -1

# 标记版本（不执行迁移）
alembic stamp <revision_id>

# 验证迁移脚本
alembic check
```

### 8. 调试技巧

#### 问题：服务器启动失败，迁移错误

1. 查看完整错误信息
2. 检查是否有多个 head：`alembic heads`
3. 检查当前版本：`alembic current`
4. 如果表已存在，使用 `stamp` 标记版本
5. 修复 `down_revision` 后重新运行

#### 问题：模型字段类型不匹配

确保迁移文件中的字段类型与模型定义一致：
- 模型：`Mapped[int | None]` → 迁移：`sa.Column(Integer(), nullable=True)`
- 模型：`Mapped[dict | None]` → 迁移：`sa.Column(postgresql.JSON(), nullable=True)`

### 9. 示例：完整的迁移文件

```python
"""add AI provider models

Revision ID: 20260208_0013_add_ai_provider_models
Revises: 676cbd976326
Create Date: 2026-02-08 05:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260208_0013_add_ai_provider_models'
down_revision = '676cbd976326'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建表
    op.create_table(
        'ai_providers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('request_metadata', postgresql.JSON(), nullable=True),  # 注意：避免使用 metadata
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ai_providers_id', 'ai_providers', ['id'])


def downgrade() -> None:
    op.drop_index('ix_ai_providers_id', table_name='ai_providers')
    op.drop_table('ai_providers')
```

## 总结

遵循这些最佳实践可以避免 90% 的数据库迁移问题：

1. **始终设置 `down_revision`** 为最新的迁移版本号
2. **使用标准命名格式**：`YYYYMMDD_HHMM_description.py`
3. **避免使用保留字**：如 `metadata`, `table`, `user` 等
4. **导入所有必需的 SQLAlchemy 组件**：特别是 `relationship`
5. **验证迁移**：创建后立即测试 `alembic heads` 和 `alembic upgrade head`

记住：如果迁移部分执行失败，使用 `alembic stamp` 标记版本比手动删除表更安全。
