# CRUD 代码生成器规范 / CRUD Codegen Specification

> 通过 YAML 配置生成 Model / Schema / Repository / Service / Controller / Test 及前端骨架。
> Generates Model / Schema / Repository / Service / Controller / Test and frontend skeleton from YAML config.

---

## 一、使用方式

### 1.1 UI 管理页与 Builder

- **列表页**：`/admin/system/codegen`
- **新建页**：`/admin/system/codegen/new`
- **编辑页**：`/admin/system/codegen/:id/edit`
- **当前真实形态**：`builder.vue` 三栏可视化构建器（Palette + WYSIWYG + Property Panel），不是旧版 Step 1~6 向导
- **预览**：支持代码预览、预览 ZIP 下载、版本历史与恢复
- **草稿**：配置支持保存草稿（`status=draft`）

Builder 详细规范见 [codegen-builder-spec.md](codegen-builder-spec.md)。

### 1.2 CLI

```bash
cd backend  # 或项目根目录
novusai codegen --help
```

---

## 二、YAML 配置规范

### 2.1 顶级节点

| 节点 | 必填 | 说明 |
|------|------|------|
| `module` | 是 | 模块名，如 system / tenant / business |
| `resource` | 是 | 资源名（蛇形），如 category / notice |
| `display_name` | 是 | 中文显示名 |
| `display_name_en` | 是 | 英文显示名 |
| `model` | 是 | 模型配置（base_class、tree、selectable 等） |
| `fields` | 是 | 字段列表 |
| `endpoints` | 是 | 端点配置列表（scope、data_mode、route_prefix、permission、menu） |
| `relations` | 否 | 关联配置（BelongsTo / HasMany / M2M） |
| `workflow` | 否 | 状态工作流（status_field、transitions） |
| `actions` | 否 | 自定义操作 |
| `batch` | 否 | 批量操作 |
| `detail` | 否 | 详情页（groups） |
| `clone` | 否 | 克隆支持 |

### 2.2 字段属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | string | 字段名（必填） |
| `type` | string | 类型，如 String(100)、Integer、Boolean、Text、DateTime、Enum、ForeignKey(table) |
| `required` | bool | 非空 |
| `nullable` | bool | 可空 |
| `unique` | bool | 唯一约束 |
| `default` | any | 默认值 |
| `comment` | string | 注释 |
| `comment_en` | string | 英文注释（用于前端 en-US i18n） |
| `filterable` | bool | 可筛选 |
| `sortable` | bool | 可排序 |
| `searchable` | bool | 可搜索（或简写展开） |
| `form.component` | string | 表单组件覆盖（Input、Textarea、ApiSelect、RichText 等） |
| `dict_code` | string | 数据字典编码，填写后表单/搜索使用 useDictOptions；无 Dict 模块时占位返回空 |
| `column.visible` | bool | 列是否可见 |
| `column.cell_render` | string | 列渲染（CellTag、CellDateTime 等） |
| `enum_values` | list | 枚举选项，每项 `{ value, label_zh, label_en }`，用于前端 i18n enum 翻译 |

**comment / comment_en 自动拆分**：若 `comment` 格式为 `"中文 / English"` 且未显式配置 `comment_en`，codegen 会自动拆分为 `comment="中文"` 和 `comment_en="English"`。

**enum_values**：若字段有 `enum_values`，codegen 会生成前端 i18n 的 `enum` 区块，使用 `label_zh` / `label_en` 作为翻译；列头和表单会通过 `$t('...enum.{value}')` 引用。

### 2.3 类型映射（常用）

| YAML 类型 | SQLAlchemy | TypeScript | 默认表单组件 |
|-----------|------------|------------|-------------|
| String(n) | String(n) | string | Input |
| Text | Text | string | Textarea |
| Integer | Integer | number | InputNumber |
| Boolean | Boolean | boolean | Switch |
| DateTime | DateTime | string | DatePicker |
| Date | Date | string | DatePicker |
| Enum | Enum | string | Select |
| ForeignKey(t) | Integer + FK | number | ApiSelect |

### 2.4 简写展开

- `searchable: true` → `filterable: true` + `search.enabled: true` + `filter_op: ilike`
- `column: true` → `column.visible: true`
- `form: input` → `form.component: Input`

### 2.5 预设模板

位于 `backend/app/codegen/templates/presets/`：

- `simple.yaml` — 最简 CRUD，单端 Admin
- `tree.yaml` — 树形数据（department 示例）
- `dual_scope.yaml` — Admin + Tenant 双端
- `workflow.yaml` — 状态工作流（approval 示例）
- `sub_form_embedded.yaml` — 嵌入式主子表，子表字段以内联方式呈现在同一表单，适合轻量嵌套录入。
- `sub_form_standard.yaml` — 标准主从表布局，主表与子表共享提交节奏，适合订单类业务。
- `sub_form_erp.yaml` — 面向 ERP 流程的主子表模板，预装常见审批与权限校验片段。

---

## 三、CLI 命令参考

### 3.1 核心

| 命令 | 说明 | 选项 |
|------|------|------|
| `novusai codegen generate` | 生成代码 | `--config` / `--id` / `--resource` / `--stdin`，`--force`，`--auto-migrate`，`--dry-run` |
| `novusai codegen preview` | 预览（不写入） | `--config` / `--id`，`--verbose`，`--output-dir` |
| `novusai codegen validate` | 校验配置 | `--config` / `--stdin` |
| `novusai codegen rollback` | 回滚生成 | `--resource` / `--id`，`--force`，`--dry-run` |

### 3.2 配置管理

| 命令 | 说明 |
|------|------|
| `novusai codegen list` | 列出配置 |
| `novusai codegen show --id N` | 显示配置详情 |
| `novusai codegen import -c path` | 导入 YAML 到数据库 |
| `novusai codegen export --id N` / `-r resource` | 导出为 YAML |
| `novusai codegen delete --id N` | 删除配置 |
| `novusai codegen duplicate --id N` | 复制配置 |

### 3.3 DB 反射

| 命令 | 说明 |
|------|------|
| `novusai codegen db tables` | 列出数据库表 |
| `novusai codegen db columns -t table` | 获取表列定义 |
| `novusai codegen db import -t table` | 从表导入为 YAML |

### 3.4 辅助

| 命令 | 说明 |
|------|------|
| `novusai codegen init -t simple` | 从预设初始化配置 |
| `novusai codegen history` | 显示生成历史 |
| `novusai codegen download --id 5 -o out.zip` | 按配置 ID 下载生成代码 ZIP |
| `novusai codegen download --resource notice -o out.zip` | 按资源名下载生成代码 ZIP |
| `novusai codegen download --config codegen_configs/notice.yaml -o out.zip` | 按配置文件下载生成代码 ZIP |
| `novusai codegen download --stdin -o out.zip` | 从 stdin 配置下载生成代码 ZIP |

`download` 与 `preview` 一样，都要求来源选择器四选一：`--id` / `--resource` / `--config` / `--stdin`。

### 3.5 预设

| 命令 | 说明 |
|------|------|
| `novusai codegen presets list` | 列出可用预设及其元数据（label/category/tags/description） |
| `novusai codegen presets show --name preset_name` | 查看单个预设的 YAML 内容和解析结果，便于复制到 `codegen_configs/` |

---

## 四、生成物清单

| 类型 | 路径示例 |
|------|----------|
| Model | `backend/app/models/{module}/{resource}.py` |
| Schema | `backend/app/schemas/{module}/{resource}.py` |
| Repository | `backend/app/repositories/{module}/{resource}_repository.py` |
| Service | `backend/app/services/{module}/{resource}_service.py` |
| Controller (Admin) | `backend/app/api/admin/{resource}.py` |
| Controller (Tenant) | `backend/app/api/tenant/{resource}.py` |
| Test | `backend/tests/services/{module}/test_{resource}_service.py` |
| 后端 i18n (zh_CN) | `backend/app/locales/zh_CN/messages.json` (merge) |
| 后端 i18n (en) | `backend/app/locales/en/messages.json` (merge) |
| register_route | `api/{scope}/__init__.py` (auto-append) |
| register_model | `models/{module}/__init__.py` + `models/__init__.py` + `migrations/env.py` (auto-append) |

---

## 五、自动化能力

Codegen 现已自动完成以下操作，无需手动注册或合并：

| 能力 | 说明 |
|------|------|
| **自动注册路由** | 将 import、include_router、`__all__` 追加到 `api/admin/__init__.py` 或 `api/tenant/__init__.py` |
| **自动注册 Model** | 将 Model 的 import 和 `__all__` 追加到 `models/{module}/__init__.py`、`models/__init__.py`、`migrations/env.py` |
| **自动生成后端 i18n** | 深度合并 `module.resource`（not_found/created/updated）和 `action.{resource}`（list/create/update/delete）到 `messages.json`，供 RBAC 权限树翻译 |
| **子表 Model 自动注册** | sub_tables 中的子表 Model 同样自动注册到上述三个位置 |
| **数据库迁移** | CLI `--auto-migrate` 或 Web API `auto_migrate`（默认 `true`）时自动执行 alembic autogenerate |
| **前端 i18n 自动加载** | 生成的 `locales/langs/{zh-CN,en-US}/admin|tenant/{module}/{resource}.json` 被 `import.meta.glob` 自动扫描，无需手动注册 |
| **权限同步自动触发** | 生成后重启后端即可，`sync_permissions_on_startup` 在 lifespan 中自动执行，菜单自动出现在侧边栏 |
| **Manifest config_id 同步** | 通过 Web API 用 config_json 生成后创建 DB 配置时，自动更新 manifest 中的 config_id，确保按 ID 回滚可用 |

---

## 六、Auto-Migrate 迁移机制

### 6.1 完整周期

CLI `--auto-migrate`（默认开启）和 Web API `auto_migrate`（默认 `true`）执行以下 5 步完整周期：

| 步骤 | 操作 | 目的 |
|------|------|------|
| 1 | `purge_orphaned_alembic_stamps` | 清理无法对应到迁移文件的孤立 stamp |
| 2 | `alembic upgrade heads` | Pre-upgrade，确保 DB 处于最新 |
| 3 | `alembic revision --autogenerate -m "codegen_{resource}"` | 对比 Model 与 DB 生成迁移 |
| 4 | `inject_migration_metadata` | 注入 `codegen_source` / `codegen_resource` / `codegen_version` |
| 5 | `alembic upgrade heads` | Post-upgrade，实际建表 |

### 6.2 元数据注入

生成的迁移文件包含 codegen 元数据，用于标识来源和辅助回滚：

```python
codegen_source = 'codegen'
codegen_resource = 'stock_record'
codegen_version = '1'
```

### 6.3 Manifest 记录

迁移文件路径记录在 `codegen_manifest.json` 的 `migration_file` 字段：

```json
{
  "resource": "stock_record",
  "migration_file": "E:/git_clone/.../migrations/versions/20260319_codegen_stock_record.py"
}
```

### 6.4 env.py 过滤

`migrations/env.py` 中 `_include_object` 仅对 Model 注册表生成迁移，不干扰数据库中的未知表。

### 6.5 冲突防护

| 场景 | 系统防护 |
|------|----------|
| 插件卸载残留 stamp | `purge_orphaned_alembic_stamps` 自动清理 |
| DB 落后于 heads | Pre-upgrade 先执行 `upgrade heads` |
| 回滚时迁移文件已删 | 按表名扫描 + 强制 `DROP TABLE` |
| 多次 codegen 多 head | 生成前 purge + pre-upgrade 确保单 head |

---

## 七、回滚

- **Manifest**：`codegen_manifest.json` 记录每次生成的文件及 action（create / append / merge_json / register_route / register_model）
- **CLI 回滚**：`novusai codegen rollback --resource xxx` 或 `--id N`
- **代码逆向操作**：
  - create → 删除文件
  - append → 移除追加片段
  - merge_json → 移除合并的 key（支持嵌套路径如 `tenant.article`、`action.article`）
  - register_route → 移除 import、include_router、`__all__` 中的 Controller
  - register_model → 移除 import、`__all__` 中的 Model（支持行尾注释）
- **迁移回滚**（`--auto-migrate` 默认开启）：
  1. 从 manifest 获取 `migration_file` 路径
  2. 如果文件不存在，按表名扫描 `migrations/versions/`
  3. `purge_orphaned_alembic_stamps`
  4. `alembic downgrade {down_revision}`
  5. 删除迁移文件
  6. `DROP TABLE IF EXISTS`（兜底，无论 downgrade 是否成功）
- **空目录清理**：回滚后自动清理空目录

---

## 八、配置文件存放

- **推荐目录**：`backend/codegen_configs/`
- **命名规范**：`{resource}.yaml`，与 resource 对应
- **使用方式**：`novusai codegen generate --config codegen_configs/notice.yaml`（需在 `backend/` 下执行）
- **与 presets 区别**：`backend/app/codegen/templates/presets/` 为可复用模板，一般不直接修改；`codegen_configs/` 为业务模块配置，纳入版本控制

---

## 九、校验规则（部分）

- `BaseModel` 不可与 `tenant_only` / `cross_tenant` 搭配
- `tree` 需 `TenantModel` 或 `BaseModel`
- `fields` 至少包含一个字段，且每个字段必须有 `name`
