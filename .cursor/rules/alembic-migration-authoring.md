# Alembic 迁移脚本写法规范（空库安装 / `upgrade heads` 必过）

本规则针对 **`backend/migrations/versions/*.py`** 及 **`backend/plugins/*/backend/migrations/versions/*.py`**。目标是：**全新 PostgreSQL 空库执行 `alembic upgrade heads`（或 `novusai db upgrade` / 启动自动迁移）必须一次成功**，不因历史分支、种子数据或列宽假设而中断。

配套文档：[../../docs/acceptance/unified-scope-migration-verification.md](../../docs/acceptance/unified-scope-migration-verification.md)；验证脚本：[../../backend/scripts/fresh_install_migrate_test.py](../../backend/scripts/fresh_install_migrate_test.py)。

---

## 1. 事务与 PostgreSQL：`except` 不能救活已失败的事务

- Alembic 默认在**单条迁移的一个事务**里执行 `upgrade()`。
- 任一条 SQL 失败后，连接进入 **`InFailedSqlTransaction`**，后续语句全部无效，直到回滚。
- **禁止**：在 `try/except` 里执行可能失败的 `INSERT/UPDATE`，失败后用 `pass` 忽略并继续写同一连接——会导致后续语句莫名失败。

**正确做法**：

- 对「可选步骤」使用 **`with conn.begin_nested():`**（保存点），失败只回滚子事务；或
- 先 **`inspect` / 查询 `information_schema`** 判断表/列/索引是否存在再执行；或
- 将可选逻辑改为**幂等**且**不依赖失败过的语句**。

---

## 2. SQL 标识符：白名单静态语句 + 参数绑定

- **禁止**用 f-string / `%` 拼接 **表名、列名、索引名**（例：`f"UPDATE {table} SET ..."`）。
- **允许**：整句 SQL 为**字面量**，仅对 **值** 使用 `sa.text("... WHERE scope = :old").bindparams(...)` 或 `execute(..., {"old_scope": x})`。
- `downgrade()` 同样遵守；需要多条表时写多条静态 `UPDATE`，或 `DROP INDEX IF EXISTS ix_xxx`。

与项目总规则一致：`text(f"...")` 拼接 SQL **一律禁止**。

---

## 3. 列宽与枚举字符串：先扩列再 `UPDATE`

- 若将 `scope` 等字段从短枚举改为 **`admin_and_selected_tenants`**（26 字符）等长值，必须先 **`ALTER COLUMN ... TYPE VARCHAR(40)`**（或足够长度），再执行 `UPDATE`。
- 禁止假设历史库一直是 `VARCHAR(255)`；空库往往仍是 **`VARCHAR(20)`**。

---

## 4. 加列 / 加约束前的存在性与数据卫生

- **`op.add_column`**：若更早的迁移可能已加过同一列（分支合并、重复修复），应用 **`inspect.get_columns`** 判断 **`if "col" not in cols`** 再添加。
- **`CREATE UNIQUE CONSTRAINT`**：若种子可能重复插入相同业务键，应先 **`DELETE` 去重**（如按 `task_path` 保留 `MIN(id)`），再加唯一约束。
- **`DROP INDEX` / `DROP TABLE`**：若不同分支创建的索引名不一致，用 **`IF EXISTS`** 或先查 `pg_indexes` / `information_schema`。

---

## 5. 种子数据与空库：禁止写入违反 NOT NULL 的行

- 空库通常 **无 `ai_models`、无已发布智能体**。任何 **`agents.model_id` NOT NULL** 的 `INSERT` 必须在 **无可用模型时跳过**，并打印 **WARNING**，禁止写 `NULL` 再依赖「以后补」。
- 依赖「其他表必有数据」的 `INSERT`，应先 `SELECT`；无数据则 **return**，保证迁移 **仍提交成功**。

---

## 6. 已删除的列：禁止盲写 `UPDATE`

- 若某列在**更早迁移**中已 `drop_column`（如 **`skills.scope`**），后续迁移中 **不得**再 `UPDATE skills SET scope = ...`。
- 应使用 **`inspect` 判断列是否存在** 再执行；或把逻辑合并到仍存在的列/表上。

---

## 7. Revision 图（`down_revision` / merge）：顺序即语义

- **约束、索引、数据修复** 依赖某张表时，该迁移的 **`down_revision` 必须排在「建表」迁移之后**，不能与建表迁移 **从同一父节点并行分叉** 除非明确 `merge` 且顺序对空库仍确定。
- 错误并行会导致：**空库上先跑「加唯一约束」、后跑「建表」** → `UndefinedTable`。
- 新增迁移后本地必跑：
  - `python -m alembic heads`（应 **单一 head**，除非刻意多 head 且文档说明）
  - **`python scripts/fresh_install_migrate_test.py --database <空库>`**（或与 CI 等价流程）

---

## 8. 插件迁移

- 与主库相同规范；路径在 **`backend/plugins/<name>/backend/migrations/versions/`**。
- 主应用 **`env.py` / `run_migrations` / CLI** 会扫描插件目录；插件迁移勿使用 **动态表名拼接**。

---

## 9. 唯一约束列的值重命名：使用 `migrations.helpers`

当迁移需要把唯一约束列（如 `permissions.code + scope`）的值从 A 改为 B 时：

- **禁止**直接 `UPDATE ... SET code = REPLACE(code, 'old', 'new')`——应用启动时 `@permission_resource` 等自动种子机制可能**已创建了新值的行**，`REPLACE` 会撞上 `UniqueViolation`。
- **必须使用** `migrations.helpers` 中的封装函数：

```python
# 权限资源重命名（最常见场景）
from migrations.helpers import safe_rename_permission_resource

def upgrade() -> None:
    safe_rename_permission_resource("ai_skill_registry", "plugin_skill_registry")

def downgrade() -> None:
    safe_rename_permission_resource("plugin_skill_registry", "ai_skill_registry")
```

```python
# 通用唯一约束列值重命名
from migrations.helpers import safe_rename_unique_column_value

def upgrade() -> None:
    safe_rename_unique_column_value(
        "configs", "key", "old_key", "new_key",
        unique_columns=["scope"],
    )
```

- **`scripts/lint_migrations.py`** 会自动检测裸 `REPLACE` 和 f-string SQL，CI 或本地可运行：
  ```bash
  python scripts/lint_migrations.py                  # 全量扫描
  python scripts/lint_migrations.py --since HEAD~3   # 增量扫描
  ```

---

## 10. 合并前自检清单（PR 前）

- [ ] 无 `f"…{table}…"` / 无未绑定标识符拼接
- [ ] 无「失败 SQL + `except: pass`」后继续同一 `conn.execute`
- [ ] 长枚举 / 新 scope 值已考虑 **列长度**
- [ ] 唯一约束前有 **去重** 或种子 **ON CONFLICT** 幂等
- [ ] 空库无模型时 **不插入** `model_id` 为空的 agent
- [ ] `down_revision` / merge 保证 **建表先于依赖它的变更**
- [ ] 唯一约束列的值重命名已使用 **`migrations.helpers`** 封装函数
- [ ] `python scripts/lint_migrations.py` 无新增 warning
- [ ] 在干净库上跑通 **`fresh_install_migrate_test.py`** 或等价 `alembic upgrade heads`

---

## 11. 与现有技能的关系

更完整的流程与历史问题排查见：[../skills/database-migration-best-practices/SKILL.md](../skills/database-migration-best-practices/SKILL.md)。
**本规则侧重「写法底线 + 空库必过」**；与技能文档冲突时，以 **空库可安装** 为优先。
