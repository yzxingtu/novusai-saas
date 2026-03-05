# 插件系统深度审计与里程碑（2026-03-03）

## 1. 审计范围

- 后端插件生命周期：`install/enable/disable/uninstall/startup restore`
- 插件 API 分发器事务边界与能力沙箱
- Marketplace 预览/安装流程一致性
- 前端插件动态加载并发与样式加载兼容
- 残留代码与可维护性风险

## 2. 审计结论概览

- 结论：插件系统核心链路有明显提升，但仍未达到“完全无风险”。
- 本轮已完成 4 个高优先级修复（2 个 P0，2 个 P1）并补充回归测试。
- 仍有 4 类中低优先级问题建议纳入后续里程碑。

## 3. 已完成修复（本轮）

### 3.1 P0-1 插件 API 失败未触发事务回滚

- 风险：handler 出错但被 `JSONResponse` 吞掉，`get_db()` 可能提交已写入数据。
- 修复：
  - `api_dispatcher` 中 handler 的 error dict 与运行时异常均改为抛 `AppException`。
  - 保留 `except AppException: raise`，确保错误向上冒泡。
- 代码：
  - `backend/app/plugins/api_dispatcher.py`
- 回归：
  - `tests/test_plugin_api_dispatcher_security.py` 新增 2 个异常路径用例。

### 3.2 P0-2 卸载表清理可能误删非插件表

- 风险：`LIKE prefix%` 未转义 `_/%`，存在误匹配；且缺少严格 DROP 前过滤。
- 修复：
  - 新增 `_escape_like_pattern` 与 `_is_safe_plugin_table_name`。
  - 查询与删除 `alembic_version` 均使用 `ESCAPE '\\'`。
  - DROP 前强制安全校验，不安全表仅记录 warning 不执行删除。
- 代码：
  - `backend/app/plugins/lifecycle.py`
- 回归：
  - 新增 `tests/test_plugin_lifecycle_cleanup_safety.py`。

### 3.3 P1-1 Marketplace 安装流程预拷贝脏目录风险

- 风险：confirm-install 先复制到 `PLUGINS_DIR`，失败回滚/重试时可能残留。
- 修复：
  - preview 不再写入 `PLUGINS_DIR/_market_*`。
  - confirm-install 直接从 staging 目录 `install_from_path(plugin_dir, ...)`。
  - 由 lifecycle 统一负责复制与回滚。
- 代码：
  - `backend/app/api/admin/plugins.py`
  - `backend/app/plugins/preview.py`

### 3.4 P1-2 生命周期锁 TTL 偏短

- 风险：`pip/npm/migration` 长耗时场景下锁提前过期。
- 修复：
  - `_LOCK_TTL` 从 `120s` 提升到 `900s`。
- 代码：
  - `backend/app/plugins/lifecycle.py`

## 4. 回归验证结果

已执行命令：

```bash
cd backend
pytest tests/test_plugin_api_dispatcher_security.py -q
pytest tests/test_plugin_lifecycle_cleanup_safety.py -q
pytest tests/plugins/test_contract_lifecycle.py -q

cd ../frontend/apps/web-antd
pnpm typecheck
```

结果：全部通过。

## 5. M589 收尾执行结果（2026-03-03）

### 5.1 T1：startup restore 多 worker 一致性加固（已完成）

- 改动：
  - `backend/app/main.py`
    - 新增 `plugin:startup:restore_lock` 分布式锁。
    - owner worker 执行 `restore_enabled_plugins(run_heavy=True, mutate_db_status=True)`。
    - non-owner worker 等待 owner 后执行 `restore_enabled_plugins(run_heavy=False, mutate_db_status=False)`（仅进程内扩展注册）。
  - `backend/app/plugins/startup.py`
    - `restore_enabled_plugins` 增加 `run_heavy` / `mutate_db_status` 参数。
    - 轻量模式不执行 alembic/pip/npm，不写插件状态，避免多 worker 抖动。
- 回归：
  - 新增 `backend/tests/test_plugin_startup_restore_modes.py`（2 个用例）。

### 5.2 T2：卸载链路事务语义统一（已完成）

- 改动：
  - `backend/app/plugins/backup.py`
    - 备份查询改为 `begin_nested()` savepoint 隔离。
    - 删除 helper 级 `db.rollback()`，避免回滚外层卸载流程。
  - `backend/app/plugins/lifecycle.py`
    - `_cleanup_plugin_database` 的残表清理与 `alembic_version` 清理改为 `begin_nested()`。
    - 删除 helper 级 `self._db.rollback()`。
- 回归：
  - 新增 `backend/tests/test_plugin_transaction_semantics.py`（2 个用例）。
  - 更新 `backend/tests/test_plugin_lifecycle_cleanup_safety.py`，兼容 savepoint 流程。

### 5.3 T4：残留接口/代码收敛（已完成）

- 改动：
  - 删除后端旧接口：`GET /admin/plugins/frontend-config`（文件：`backend/app/api/admin/plugins.py`）。
  - 前端调用链统一维持 `GET /admin/plugins/slots` 与 `GET /tenant/plugins/slots`。
- 结论：
  - `rg "frontend-config"` 仅剩历史文档引用，无运行时代码引用。

## 6. 最终验证结果

执行命令：

```bash
pytest backend/tests/plugins -q
pytest backend/tests/test_plugin_api_dispatcher_security.py \
  backend/tests/test_plugin_lifecycle_cleanup_safety.py \
  backend/tests/test_plugin_startup_restore_modes.py \
  backend/tests/test_plugin_transaction_semantics.py -q
pnpm typecheck  # frontend/apps/web-antd
```

结果：

- `tests/plugins`：31 passed
- 4 个插件安全/事务回归文件：16 passed
- 前端 `typecheck`：通过

## 7. 当前结论

- 插件系统并发恢复、卸载事务语义、残留接口收敛已完成 M589 收尾。
- 现阶段未发现新的 P0/P1 阻断项；后续可转入常规增强与监控观测优化。
