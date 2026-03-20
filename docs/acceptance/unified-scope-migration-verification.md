# 统一作用域迁移验证清单（手工回放）

用于在具备 PostgreSQL 的环境中对齐计划中的「可证明验证」。

- **一键脚本**（推荐）：在 `backend` 目录执行  
  `python scripts/fresh_install_migrate_test.py --database test`  
  默认连接与 `docker-compose.dev.yml` 一致（`localhost:5432`，用户/密码 `postgres`/`postgres`）。目标库应**空库或仅有干净 `public`**；若中途失败，请 `DROP DATABASE test; CREATE DATABASE test;` 后重跑。已有 `alembic_version` 时需加 `--yes-i-know`。
- 自动化测试：`backend/tests/migrations/test_alembic_plugin_paths_consistency.py` 等。

## 三条入口一致性

在相同 `DATABASE_URL` 下任选其一应能升到同一 revision 图：

- `cd backend && alembic upgrade heads`
- `novusai db upgrade`（默认 `heads`，与启动子进程一致）
- `novusai run`（启动时自动迁移，内部为 `command.upgrade(..., 'heads')`）

## Fresh install（空库）

1. 新建空库并配置 `DATABASE_URL`。
2. 执行 `alembic upgrade heads`（或 `novusai db upgrade`）。
3. 抽样校验：`agents` 无 `owner_type` / `distribution_mode`；无表 `knowledge_base_tenant_access`；`knowledge_bases` 无 `visibility`；相关资源表使用 `owner_tenant_id`（与当前 ORM 一致）。

## 坏库修复（误 stamp `20260320_urps`）

1. 在仍缺列/旧结构的库上执行 `alembic stamp 20260320_urps`（**不要**在正常环境随意操作）。
2. 再执行 `alembic upgrade heads`。
3. 预期：`20260321_akso` 中 `_repair_20260320_urps_skipped` 与 `20260324_pt_otid_repair` 幂等补跑后，应用可正常加载 `PeriodicTask` 等模型。
