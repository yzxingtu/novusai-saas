---
name: crud-codegen-workflow
description: CRUD 代码生成与 CLI 工作流。当需要新增 CRUD 模块、使用 novusai codegen 命令生成代码、编写 YAML 配置、或使用 CLI 管理项目（run/celery/db/plugin/license/check）时，参考此技能。
---

# CRUD 开发与 Codegen 优先工作流

> 新增 CRUD 模块时，**必须优先使用 CLI 代码生成器**，禁止从零手写全套 CRUD 代码。
> When adding new CRUD modules, always use the CLI codegen first. Do NOT hand-write full CRUD boilerplate from scratch.

## 目录

- [核心原则：Codegen-First](#核心原则codegen-first)
- [一、Codegen 标准流程](#一codegen-标准流程)
- [二、YAML 配置编写](#二yaml-配置编写)
- [三、CLI 代码生成器](#三cli-代码生成器)
- [四、生成物与目录结构](#四生成物与目录结构)
- [五、生成后人工步骤](#五生成后人工步骤)
- [六、手写 CRUD（codegen 不适用时）](#六手写-crudcodegen-不适用时)
- [七、CLI 完整命令速查](#七cli-完整命令速查)
- [八、开发场景速查表](#八开发场景速查表)
- [九、Auto-Migrate 内部机制](#九auto-migrate-内部机制)
- [十、迁移冲突防护](#十迁移冲突防护)

→ CLI 完整命令参考：[references/cli-commands.md](references/cli-commands.md)
→ 手写 CRUD 完整代码示例：[references/crud-handwrite.md](references/crud-handwrite.md)

---

## 核心原则：Codegen-First

**标准流程：**

```
1. 编写 YAML 配置（或用 UI 向导）
2. novusai codegen generate 生成骨架
3. 人工审查 + 补充业务逻辑
4. 生成迁移文件
5. 前端路由 + i18n 补全
```

**禁止行为：**
- 禁止不经 codegen 直接手写 Model + Schema + Repository + Service + Controller 全套
- 禁止复制粘贴其他模块代码创建新模块
- 仅纯配置面板、Dashboard 聚合页等无标准 CRUD 的场景允许手写

---

## 一、Codegen 标准流程

### 方式 A：从 YAML 文件生成（推荐新模块）

```bash
novusai codegen validate --config codegen_configs/notice.yaml   # 校验
novusai codegen preview --config codegen_configs/notice.yaml    # 预览（不写入）
novusai codegen generate --config codegen_configs/notice.yaml   # 生成
novusai codegen generate --config codegen_configs/notice.yaml --auto-migrate  # 生成 + 自动迁移
```

### 方式 B：从数据库表反射

```bash
novusai codegen db tables                    # 查看表
novusai codegen db columns -t notices        # 查看列
novusai codegen db import -t notices         # 导入为 YAML 配置
```

### 方式 C：从 UI 向导保存的配置

```bash
novusai codegen list                         # 列出配置
novusai codegen generate --id 5              # 按 ID 生成
novusai codegen generate --resource notice   # 按资源名生成
```

### 方式 D：stdin 管道

```bash
cat codegen_configs/notice.yaml | novusai codegen generate --stdin
```

**配置来源优先级**：`--stdin > --config > --id/--resource`

### 回滚

```bash
novusai codegen rollback --resource notice   # 撤销生成
novusai codegen rollback --resource notice --dry-run  # 预览回滚
```

---

## 二、YAML 配置编写

### 配置结构

```yaml
module: tenant              # system / tenant / business
resource: notice             # snake_case 单数
display_name: 公告
display_name_en: Notice

model:
  base_class: TenantModel    # TenantModel 或 BaseModel
  tree: false
  selectable:
    label: title
    value: id
    search: [title]

fields:
  - name: title
    type: String(200)
    required: true
    comment: "标题 / Title"   # 格式 "中文 / English" 会自动拆为 comment + comment_en
    searchable: true         # → filterable + ilike 搜索
    column: true
    form: input

  - name: content
    type: Text
    required: true
    form: textarea

  - name: status
    type: Enum
    enum_values:                    # label_zh/label_en 用于前端 i18n enum 翻译
      - { value: draft, label_zh: 草稿, label_en: Draft }
      - { value: published, label_zh: 已发布, label_en: Published }
    default: draft
    filterable: true
    column:
      cell_render: CellTag

  - name: category_id
    type: ForeignKey(categories)
    filterable: true
    form:
      component: ApiSelect
      search: true

  - name: sort_order
    type: Integer
    default: 0
    sortable: true

endpoints:
  - scope: admin
    data_mode: tenant_only
    route_prefix: notices
    permission:
      resource: notice
      parent_resource: system_config
    menu:
      parent: system_config
      icon: lucide:megaphone

  - scope: tenant            # 双端场景添加第二个
    data_mode: tenant_only
    route_prefix: notices
    permission:
      resource: notice
      parent_resource: system_mgmt

relations:                    # 可选
  - type: BelongsTo
    target: Category
    foreign_key: category_id

detail:                       # 可选
  groups:
    - label: 基本信息
      fields: [title, status, category_id]
    - label: 内容
      fields: [content]
```

### 字段类型速查

| YAML 类型 | SQLAlchemy | TypeScript | 默认表单组件 |
|-----------|------------|------------|-------------|
| String(n) | String(n) | string | Input |
| Text | Text | string | Textarea |
| Integer | Integer | number | InputNumber |
| Float | Float | number | InputNumber |
| Boolean | Boolean | boolean | Switch |
| DateTime | DateTime | string | DatePicker |
| Enum | Enum | string | Select |
| ForeignKey(t) | Integer + FK | number | ApiSelect |

### 简写展开

- `searchable: true` → filterable + search.enabled + filter_op: ilike
- `column: true` → column.visible: true
- `form: input` → form.component: Input

### 预设模板

```bash
novusai codegen init -t simple       # 最简 CRUD
novusai codegen init -t tree         # 树形数据
novusai codegen init -t dual_scope   # Admin + Tenant 双端
novusai codegen init -t workflow     # 状态工作流
```

---

## 三、CLI 代码生成器

### 配置管理

```bash
novusai codegen import -c config.yaml   # 导入到数据库
novusai codegen export --id 5           # 导出 YAML
novusai codegen duplicate --id 5        # 复制配置
novusai codegen delete --id 5           # 删除
novusai codegen show --id 5             # 查看详情
novusai codegen versions --id 5         # 历史版本
novusai codegen restore --id 5 --version 3  # 恢复版本
novusai codegen history                 # 生成历史
novusai codegen download --id 5 -o out.zip  # 下载 ZIP
```

所有命令支持 `--json` 输出结构化 JSON。

---

## 四、生成物与目录结构

```
backend/app/
├── models/{module}/{resource}.py              # Model
├── schemas/{module}/{resource}.py             # Schema
├── repositories/{module}/{resource}_repository.py  # Repository
├── services/{module}/{resource}_service.py    # Service
└── api/
    ├── admin/{resource_plural}.py             # Admin Controller
    └── tenant/{resource_plural}.py            # Tenant Controller

frontend/apps/web-antd/src/
├── views/admin/{module}/{resource_plural}/
│   ├── index.vue                              # 列表页
│   ├── data.ts                                # 列/搜索/表单定义
│   └── modules/form.vue                       # 表单抽屉
├── composables/use-{resource}-apis.ts         # API
└── locales/langs/{zh-CN,en-US}/admin/{module}.json  # i18n（merge）
```

---

## 五、生成后人工步骤

### 后端（codegen 已自动完成）

以下步骤 codegen 已自动处理，仅需确认：

1. ~~注册 Model~~ — **自动完成**（register_model 到 module/__init__、root/__init__、env.py）
2. ~~注册到 migrations/env.py~~ — **自动完成**
3. **生成迁移** — CLI `--auto-migrate`（默认开启）或 Web API `auto_migrate`（默认 `true`）可自动完成
4. ~~注册路由~~ — **自动完成**（register_route 到 api/__init__.py，含 import + include_router + __all__）
5. ~~权限翻译~~ — **自动完成**（merge 到 messages.json）

### 前端

1. **路由注册** — 动态菜单页面无需手动注册，Controller 的 MenuConfig 会在重启后通过权限同步自动显示
2. **i18n** — codegen 已生成 zh-CN/en-US 文件，`import.meta.glob` 自动加载，无需手动注册
3. **菜单检查** — 重启后端后，`sync_permissions_on_startup` 自动执行，菜单出现在侧边栏；启动前端检查控制台无 `[MenuCheck]` / `[DynamicMenu]` 警告

### 业务逻辑补充

生成的是骨架，以下需人工补充：

```python
class NoticeService(TenantService):
    async def _before_create(self, data: dict) -> dict:
        # 配额检查、关联校验等
        return data
    async def _before_update(self, obj, data: dict) -> dict:
        # 状态流转校验、权限检查等
        return data
    async def _before_delete(self, obj) -> None:
        # 依赖检查、级联清理等
        pass
```

```python
class Notice(TenantModel):
    # 补充 AI 策略（若需 Text-to-SQL 可见）
    __ai_policy__ = {
        "label": "公告",
        "keywords": ["公告", "notice"],
        "allow_read": True,
    }
    # 补充 __delete_deps__（若有子表 FK 引用）
```

---

## 六、手写 CRUD（codegen 不适用时）

以下场景允许手写：纯配置面板、Dashboard 聚合页、复杂多表联合查询、已有模块增量修改。

### 后端 7 步速览

1. **Model** — 继承 `TenantModel`/`BaseModel`，声明 `__filterable__`/`__sortable__`/`__delete_deps__`
2. **Schema** — 继承 `BaseCreateSchema`/`BaseUpdateSchema`/`BaseResponseSchema`
3. **Repository** — 继承 `TenantRepository`/`BaseRepository`
4. **Service** — 继承 `TenantService`/`BaseService`
5. **Controller** — 继承 `TenantController`/`GlobalController`，声明 `@permission_resource` + `@action_*`
6. **注册路由** — import router
7. **生成迁移** — `novusai db autogenerate -m "xxx"`

### 前端模式选择

| 场景 | Composable | 说明 |
|------|-----------|------|
| 表格列表 | `useCrudPage` | VxeTable 标准表格 |
| 卡片网格 | `useCrudList` | 自定义卡片模板 |
| Master-Detail | `useCrudList` × 2 | 分栏布局 |

→ 完整手写代码示例：[references/crud-handwrite.md](references/crud-handwrite.md)

---

## 七、CLI 完整命令速查

| 命令组 | 常用命令 | 说明 |
|--------|---------|------|
| `novusai run` | `--port 8000 --reload` | 启动 FastAPI |
| `novusai celery` | `worker` / `beat` / `dev` / `flower` / `purge` | Celery 管理 |
| `novusai db` | `upgrade` / `autogenerate -m "..."` / `history` | 迁移管理 |
| `novusai plugin` | `create` / `validate` / `pack` / `list` | 插件管理 |
| `novusai license` | `keygen` / `generate` / `verify` | License |
| `novusai check` | `db` / `redis` / `celery` | 环境检查 |
| `novusai codegen` | `generate` / `preview` / `validate` / `rollback` | 代码生成 |
| `novusai info` | - | 版本/环境摘要 |

→ 完整命令参考与参数说明：[references/cli-commands.md](references/cli-commands.md)

---

## 八、开发场景速查表

| 场景 | 推荐方式 | 命令 |
|------|---------|------|
| 全新 CRUD 模块 | **CLI codegen** | `novusai codegen generate -c codegen_configs/xxx.yaml --auto-migrate` |
| 从数据库表创建 | **CLI DB 反射** | `novusai codegen db import -t table` → 编辑 → `generate` |
| UI 向导创建 | **Web UI** | `/admin/system/codegen` |
| 已有模块加字段 | 手动修改 | 改 Model+Schema → `novusai db autogenerate -m "..."` |
| 已有模块加端点 | 手动修改 | Controller 中添加路由 |
| 纯配置/Dashboard | 手写 | 不涉及标准 CRUD |
| 撤销生成 | CLI 回滚 | `novusai codegen rollback -r resource` |
| 启动开发环境 | CLI | `novusai run` + `novusai celery dev` |

---

## 九、Auto-Migrate 内部机制

### 完整迁移周期

无论 CLI 还是 Web API，`--auto-migrate` 执行以下 **5 步完整周期**：

```
1. purge_orphaned_alembic_stamps
   清理 alembic_version 中无法对应到迁移文件的孤立 stamp
   （解决插件卸载、手动删除迁移文件等残留问题）

2. alembic upgrade head（Pre-upgrade）
   确保数据库处于最新状态，autogenerate 才能正确 diff

3. alembic revision --autogenerate -m "codegen_{resource}"
   对比 Model 元数据与数据库 schema，生成迁移脚本

4. inject_migration_metadata
   向生成的迁移文件注入 codegen_source / codegen_resource / codegen_version 元数据
   （用于标识迁移来源，辅助回滚定位）

5. alembic upgrade head（Post-upgrade）
   执行新生成的迁移，实际建表
```

### 生成的迁移文件示例

```python
revision = '20260319_1030_codegen_stock_record'
down_revision = '676cbd976326'

# Codegen metadata / 代码生成器元数据
codegen_source = 'codegen'
codegen_resource = 'stock_record'
codegen_version = '1'

def upgrade() -> None:
    op.create_table('stock_records', ...)

def downgrade() -> None:
    op.drop_table('stock_records')
```

### Manifest 记录

迁移文件路径记录在 `codegen_manifest.json` 的 `migration_file` 字段，回滚时自动定位。

---

## 十、迁移冲突防护

### 安全防护机制一览

| 防护 | 实现位置 | 说明 |
|------|----------|------|
| **Per-resource 文件锁** | `codegen.py` API 端点 | `filelock` 防止并发 generate/rollback 对同一资源操作 |
| **Head 校验** | `migration_helper.py` | 回滚前检查 codegen 迁移是否为当前 head，拒绝级联 downgrade |
| **Orphan stamp 清理** | `database.py` | 清理无对应迁移文件的 alembic_version stamp |
| **Stamp 清理安全阀** | `database.py` | 迁移文件读取失败时跳过 purge，防止误删 |
| **FK 引用检查** | `migration_helper.py` | DROP TABLE 前检查外键引用，避免 CASCADE 破坏其他表 |
| **文件优先回滚** | `codegen.py` API | 先回滚文件再执行 migration cleanup，避免文件回滚失败仍删表 |
| **Manifest 保留** | `rollback.py` | 部分回滚（有 skipped 文件）时保留 manifest，允许重试 |
| **Auto-migrate 失败传播** | `codegen.py` API | auto_migrate 失败时整体标记为失败，避免用户误判 |
| **相对路径存储** | `codegen_service.py` / `cli.py` | manifest 中 migration_file 存相对路径，项目目录迁移后不失效 |

### 可能的冲突场景

| 场景 | 风险 | 系统防护 |
|------|------|----------|
| 插件卸载后残留 stamp | `alembic revision` 报 "Can't locate revision" | `purge_orphaned_alembic_stamps` 自动清理 |
| DB 落后于 head | autogenerate 产生重复的 CREATE TABLE | Pre-upgrade 先执行 `upgrade head` |
| 生成迁移后未执行 | 表不存在，后端报错 | Post-upgrade 自动执行 |
| 多次 codegen 产生多 head | `alembic upgrade head` 报 "Multiple head revisions" | 生成前 purge + pre-upgrade 确保单 head |
| 回滚时迁移文件已删 | downgrade 找不到文件 | 按表名 + `codegen_resource` 扫描 + 强制 DROP TABLE |
| 手写迁移与 codegen 迁移交叉 | down_revision 链断裂 | autogenerate 自动接在当前 head 后面 |
| 回滚非 head 迁移 | 级联 downgrade 后续迁移 | Head 校验：拒绝 downgrade 非 head 迁移 |
| 并发 generate/rollback | 文件损坏、重复迁移 | Per-resource 文件锁互斥 |
| DROP TABLE 破坏其他表 FK | 其他模块数据完整性受损 | FK 引用检查 + 无 FK 时才 CASCADE |
| 迁移文件部分读取失败 | 误删有效 stamp | 安全阀：有读取失败时跳过 purge |

### 回滚执行流程

```
novusai codegen rollback --resource stock_record
```

```
1. 获取 per-resource 文件锁（防并发）
2. 从 manifest 获取 migration_file 路径
3. 如果文件不存在，按表名 + codegen_resource 扫描 migrations/versions/
4. 校验目标迁移是否为当前 head（非 head 则拒绝 downgrade）
5. purge_orphaned_alembic_stamps
6. alembic downgrade {down_revision}
7. 删除迁移文件
8. 检查 FK 引用，安全 DROP TABLE
9. 回滚生成的代码文件（逆向 manifest 操作）
10. 有 skipped 文件时保留 manifest 允许重试
11. 释放文件锁
```

### env.py 过滤机制

`migrations/env.py` 中的 `_include_object` 仅对 Model 注册的表生成迁移，忽略数据库中未知的表：

```python
def _include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table" and reflected and name not in _known_model_tables:
        return False
    return True
```

这确保：
- codegen 生成的 Model 注册后，autogenerate 才会 diff 该表
- 回滚时移除 Model 注册后，autogenerate 不会再生成对该表的操作
- 数据库中手动创建的表不会被 autogenerate 干扰

### 开发者注意事项

1. **先 commit 再 codegen** — 生成前先 `git commit`，确保可以 `git checkout` 回退
2. **不要手动编辑 codegen 迁移文件** — 回滚依赖文件内容匹配
3. **多人协作时注意 head** — 两人同时 codegen 可能产生多 head，用 `novusai db merge -m "merge"` 合并
4. **codegen 迁移不要混入手写变更** — 手写迁移用 `novusai db autogenerate -m "..."` 或 `novusai db revision -m "..."`，与 codegen 迁移保持独立
5. **回滚必须在迁移为 head 时执行** — 如果后续有其他迁移，需要先手动回滚后续迁移
6. **并发操作自动互斥** — Web API 对同一 resource 的 generate/rollback 通过文件锁串行化

---

## 常见问题

**Q: codegen 生成代码和手写风格一致吗？**
是的。模板与手写代码使用相同基类、装饰器、响应格式。

**Q: 生成后可以修改吗？**
必须修改。生成的是骨架，业务逻辑需人工补充。

**Q: 修改后还能回滚吗？**
内容变更后回滚会跳过（hash 不匹配），用 `--force` 可强制。skipped 文件存在时 manifest 保留，可重试。

**Q: 支持增量生成吗？**
目前全量生成。已有模块的增量变更建议手动修改。

**Q: 双端（Admin + Tenant）怎么生成？**
YAML `endpoints` 配置两个 scope 即可。参考 `dual_scope.yaml` 预设。

**Q: UI 向导在哪？**
管理端 → 系统管理 → 代码生成器（仅 `DEBUG=True` 可用）。

**Q: codegen 迁移会和系统自带迁移冲突吗？**
不会。codegen 使用 `alembic revision --autogenerate` 自动接在当前 head 后面，执行前会 purge 孤立 stamp 并 pre-upgrade。多人协作产生多 head 时用 `novusai db merge` 合并。

**Q: 回滚后数据库表还在吗？**
不在。回滚会执行 `alembic downgrade` + `DROP TABLE IF EXISTS` 双重保险（有 FK 引用时会警告并跳过 CASCADE）。

**Q: codegen 迁移文件怎么识别？**
迁移文件内嵌 `codegen_source` / `codegen_resource` 元数据变量，消息前缀为 `codegen_`。

**Q: 两个人同时 codegen 会怎样？**
Web API 使用 per-resource 文件锁（`filelock`），同一资源的 generate/rollback 自动串行化。CLI 无锁，需人工协调。

**Q: 回滚报 "NOT the current head" 怎么办？**
说明 codegen 迁移之后有了新的手写迁移。需要先手动回滚后续迁移（`alembic downgrade`），再重试 codegen rollback。
