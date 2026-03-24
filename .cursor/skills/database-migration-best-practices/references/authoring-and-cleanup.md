# 迁移编写与噪音清理

## 目录

- [命名与骨架](#命名与骨架)
- [创建后立即检查](#创建后立即检查)
- [autogenerate 噪音](#autogenerate-噪音)
- [SQL 与枚举写法](#sql-与枚举写法)
- [作者检查清单](#作者检查清单)

## 命名与骨架

推荐格式：

- 文件名：`YYYYMMDD_HHMM_description.py`
- `revision`：与文件主标识一致
- `down_revision`：明确接在当前最新 head 后

示例：

```python
revision = "20260324_1030_add_notice_table"
down_revision = "676cbd976326"
branch_labels = None
depends_on = None
```

## 创建后立即检查

生成迁移后，先检查：

- `down_revision` 是否正确
- `upgrade()` / `downgrade()` 是否对称
- FK 约束是否显式命名
- 是否混入无关表的 schema 变更

## autogenerate 噪音

以下经常应该删除：

- 只改 comment 的 `alter_column`
- 无关表的 `alter_column`
- 只是索引名变化的 `drop_index` + `create_index`
- 只是默认值显示差异、但本次业务并未改模型的操作

标准动作：

1. 生成迁移
2. 打开文件
3. 删除无关操作
4. 删除未使用 import
5. 重新检查 `upgrade` / `downgrade`

## SQL 与枚举写法

raw SQL 必须参数化：

```python
from sqlalchemy import text

op.execute(text("UPDATE t SET x = :v").bindparams(v=value))
```

不要这样写：

```python
op.execute(text(f"UPDATE t SET x = '{value}'"))
```

`LabeledStrEnum` 在查询与 update dict 中要用 `.value`：

```python
query = select(Model).where(Model.status == StatusEnum.ACTIVE.value)
await repo.update(id, {"status": StatusEnum.FAILED.value})
```

## 作者检查清单

- [ ] 命名格式正确
- [ ] `down_revision` 正确
- [ ] `upgrade` / `downgrade` 对称
- [ ] FK 约束显式命名
- [ ] autogenerate 噪音已清理
- [ ] raw SQL 已参数化
- [ ] 枚举比较使用 `.value`
- [ ] 启动或手动 `alembic upgrade heads` 验证通过
