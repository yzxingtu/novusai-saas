---
name: database-migration-best-practices
description: 数据库迁移技能。当需要创建或修改 SQLAlchemy Model、生成 Alembic 迁移、清理 autogenerate 噪音，或排查多 head / DuplicateTable / stamp 恢复场景时使用。
---

# 数据库迁移技能

> 本技能聚焦迁移流程与排错。迁移脚本硬性写法仍以 [../../rules/alembic-migration-authoring.md](../../rules/alembic-migration-authoring.md) 为准。

## 先记住这几条

- 项目启动时会自动执行 `alembic upgrade heads`，你通常不需要手动跑 upgrade。
- 日常开发只需要生成迁移文件，并确保它能被启动流程自动应用。
- `stamp heads` 不是通用修复手段，只允许在 `alembic_version` 为空且库结构已经完整存在的恢复场景使用。
- `alembic revision --autogenerate` 生成后必须人工清理噪音。
- 枚举写入查询条件或 update dict 时，`LabeledStrEnum` 要用 `.value`。
- 迁移里的 raw SQL 必须 `text(...).bindparams(...)`，不要 `text(f"...")`。

## 按任务读取

- 日常迁移流程、常见失败、恢复命令、codegen 共存：
  读 [references/recovery-and-troubleshooting.md](references/recovery-and-troubleshooting.md)
- 新建迁移文件、命名、`down_revision`、autogenerate 清理、作者检查清单：
  读 [references/authoring-and-cleanup.md](references/authoring-and-cleanup.md)
- 迁移脚本的事务、安全写法、种子与 FK 约束硬规则：
  读 [../../rules/alembic-migration-authoring.md](../../rules/alembic-migration-authoring.md)

## 何时不该用这个技能

- 只是做 codegen CRUD，不先从这里入手，优先看 [../crud-codegen-workflow/SKILL.md](../crud-codegen-workflow/SKILL.md)
- 只是查项目级约束，优先看 [../novusai-saas/SKILL.md](../novusai-saas/SKILL.md)
