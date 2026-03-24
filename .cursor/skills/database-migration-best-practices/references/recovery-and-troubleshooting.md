# 迁移恢复与排错

## 目录

- [启动迁移模型](#启动迁移模型)
- [标准开发流程](#标准开发流程)
- [常见失败](#常见失败)
- [快速命令](#快速命令)
- [Codegen 与手写迁移共存](#codegen-与手写迁移共存)

## 启动迁移模型

项目启动流程会自动执行：

```text
FastAPI startup
  -> init_database()
  -> run_migrations()
  -> alembic upgrade heads
```

因此日常开发通常不需要手动 `alembic upgrade heads`，除非你在单独调试迁移链路。

## 标准开发流程

1. 创建或修改 Model
2. 在 `models/__init__.py` 与 `migrations/env.py` 注册
3. 执行 `alembic revision --autogenerate -m "desc"`
4. 清理 autogenerate 噪音
5. 检查 `down_revision`
6. 启动应用或手动 `alembic upgrade heads` 验证

## 常见失败

### Multiple head revisions

原因：

- `down_revision` 错了
- 两人并行生成迁移

处理：

1. `alembic heads`
2. `alembic history`
3. 修正 `down_revision`，必要时 `alembic merge -m "merge"`
4. 再执行 `alembic upgrade heads`

### DuplicateTable / 表已存在

优先判断是不是恢复场景：

- 如果 `alembic_version` 为空，且库结构已经完整存在，可以谨慎 `alembic stamp heads`
- 如果 `alembic_version` 已有记录，不要直接 stamp，先修迁移本身

### revision 丢失 / orphan stamp

常见于插件卸载或误删迁移文件后。

处理原则：

- 不要继续删除链上的迁移文件
- 中间失效迁移宁可改成 no-op，也不要直接删
- 先恢复 revision 图，再升级

### 保留字或驱动兼容问题

- 保留字字段名改成安全名字，例如 `metadata -> request_metadata`
- `LabeledStrEnum` 在查询条件或 update dict 里必须用 `.value`

## 快速命令

```bash
alembic current
alembic heads
alembic history
alembic revision --autogenerate -m "desc"
alembic upgrade heads
alembic downgrade -1
alembic stamp heads
```

## Codegen 与手写迁移共存

- codegen 会在生成前做 `upgrade heads`
- codegen 回滚只应处理 codegen 自己的迁移
- 不要一边 codegen，一边手工 autogenerate 同一资源
- 多人协作出现多 head 时，统一用 `alembic merge`
