# Auto-Migrate 与回滚

## 目录

- [generate --auto-migrate 周期](#generate-auto-migrate-周期)
- [manifest 与迁移元数据](#manifest-与迁移元数据)
- [回滚流程](#回滚流程)
- [冲突防护](#冲突防护)

## generate --auto-migrate 周期

完整周期：

```text
1. purge orphaned alembic stamps
2. alembic upgrade heads
3. alembic revision --autogenerate
4. inject codegen metadata
5. validation (has_ops check)
6. lint_migrations (检测裸 REPLACE、f-string SQL 等危险模式)
7. alembic upgrade heads
```

这意味着：

- 生成前先把数据库拉到最新
- 迁移文件生成后会自动应用
- 语义是 `upgrade heads`，不是旧的 `upgrade head`
- 步骤 6 由 `CodegenService._lint_migration_file()` 执行，若检出 warning 则中止并返回 `phase: "lint"` 错误

## manifest 与迁移元数据

codegen 会记录：

- `migration_file`
- `codegen_source`
- `codegen_resource`
- `codegen_version`

回滚和版本恢复都依赖这些元数据，不要手工篡改。

## 回滚流程

```text
1. 读取 manifest
2. 获取目标 migration_file
3. 校验目标是否为当前 head
4. downgrade 到 down_revision
5. 回滚生成文件
6. 清理必要的表或产物
```

常用命令：

```bash
novusai codegen rollback --resource notice
novusai codegen rollback --resource notice --dry-run
```

## 冲突防护

- 同一资源 generate / rollback 要串行化
- 多人协作产生多 head 时，用 `novusai db merge -m "merge"`
- codegen 迁移不要混入手写迁移逻辑
- 迁移文件缺失时，不要盲删 stamp，先恢复 revision 图
