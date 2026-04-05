# CRUD 与 CLI 全面审计报告

## 1. 执行摘要

- **审计时间**：2025-03-19
- **审计范围**：CRUD 体系（后端 Model/Schema/Repository/Service/Controller、前端 data.ts/index.vue/form.vue、Codegen 模板与生成逻辑）、CLI 体系（novusai 主 CLI、plugin_cli）
- **测试结果**：Codegen 62 项测试全部通过；后端全量测试 749 项执行中（抽查通过）

### 发现的问题总数（按严重程度）

| 严重程度 | 数量 | 说明 |
|----------|------|------|
| 高 | 1 | CodegenConfig 缺失 `__delete_deps__` |
| 中 | 3 | 分页参数不一致、Codegen 前端潜在硬编码 |
| 低 | 2 | CLI 互斥提示、license keygen 输出建议 |

### 优先修复建议

1. **CodegenConfig** 补充 `__delete_deps__`（CodegenConfigVersion 引用）
2. **Codegen API** `list_configs` 统一使用 `spec.size` 与 `spec.page`
3. 审查 **Codegen 前端** PresetSelectModal / WysiwygFormView / infer.ts 中的中文字符串，改为 i18n

---

## 2. CRUD 体系审计

### 2.1 后端

#### 2.1.1 深度审计模块（tenant_user、agent、codegen）

| 模块 | 层级 | 结论 |
|------|------|------|
| tenant_user | Model | 正确：TenantModel、`__filterable__`、`__sortable__`、`__selectable__`、`__ai_policy__`（已退役） |
| tenant_user | Repository | 正确：TenantRepository、`_scope_fields`、企业内唯一性校验 |
| tenant_user | Service | 正确：TenantService、配额检查、BusinessException |
| tenant_user | Controller | 正确：parent_resource、@action_*、paginated(page_size=query.size) |
| agent | Model | 正确：`__delete_deps__` 声明完整、tenant_id 可空（scope 场景） |
| agent | Controller | 正确：parent_resource、MenuConfig、回收站路由 |
| codegen | Model | **问题**：CodegenConfig 无 `__delete_deps__`，CodegenConfigVersion 通过 FK 引用 |
| codegen | Controller | 正确：parent_resource、DEBUG 守卫、@action_* |

#### 2.1.2 问题列表

| 文件 | 行号 | 描述 | 影响 | 建议 |
|------|------|------|------|------|
| `backend/app/models/system/codegen_config.py` | — | CodegenConfig 未声明 `__delete_deps__`，CodegenConfigVersion 有 config_id FK 引用 | 删除 CodegenConfig 时 DB 级 CASCADE 会物理删除版本记录，应用层无法在软删场景下做依赖检查 | 添加 `__delete_deps__ = [DeletionDep("CodegenConfigVersion", "config_id", DeletionStrategy.CASCADE_DELETE, label_field="id", i18n_key="codegen_config_version")]` |
| `backend/app/api/admin/codegen.py` | 102-103 | `page_size=getattr(spec, "size", None) or getattr(spec, "page_size", None) or 20`，与规范 `query.size` 不一致 | 与其他 Controller 使用 `query.size` 风格不统一；QueryParams 实际有 `size` 属性，fallback 冗余 | 改为 `page_size=spec.size or 20`，`page=spec.page or 1`，与其他端点一致 |

#### 2.1.3 全量扫描结果

- **`query.size` / `query.page_size`**：除 codegen 外，所有分页端点正确使用 `page_size=query.size`
- **`parent_resource`**：所有 `@permission_resource` 均声明 `parent_resource`，无孤立权限节点
- **`@action_*`**：所有 CRUD 端点有权限装饰
- **`__delete_deps__`**：已声明模型：Admin、AIModel、AdminRole、Attachment、TenantDomain、KnowledgeBase、Provider、TenantPlan、TablePolicy、Tenant、TenantAdmin、SkillPackage、Agent、AgentConversation、SystemConfig、Plugin、Permission、TenantAdminRole、TenantUserRole、KnowledgeDocument 等；**缺失**：CodegenConfig

### 2.2 前端

#### 2.2.1 抽样审计（agents、knowledge-bases、codegen）

| 模块 | 结论 |
|------|------|
| admin/ai/agents | 正确：useCrudList、getScopeOptions、useScopeFields、$t()、RecycleBinDrawer、handleMenuAction |
| admin/ai/knowledge-bases | 正确：useCrudList、getScopeOptions、useFormSchema、useGridFormSchema、$t() |
| admin/system/codegen | 正确：useCrudPage、useColumns、useGridFormSchema、data.ts 辅助函数、$t() |

#### 2.2.2 潜在问题

| 文件 | 描述 | 建议 |
|------|------|------|
| `frontend/.../codegen/modules/PresetSelectModal.vue` | 可能存在中文字符串 | 改用 $t() |
| `frontend/.../codegen/modules/WysiwygFormView.vue` | 同上 | 改用 $t() |
| `frontend/.../codegen/modules/infer.ts` | 含中文（14 处） | 抽取为 i18n key |

### 2.3 Codegen

#### 2.3.1 链审计（config_parser → generator → 模板）

| 组件 | 结论 |
|------|------|
| config_parser | 正确：RESERVED_NAMES、FIELD_NAME_PATTERN、简写展开（searchable/column/form）、验证规则 |
| generator | 正确：场景 A/B/C/D 判断、Jinja2 过滤器、step 分步生成 |
| rollback | 正确：create→删除、append→移除、merge_json→移除 key、hash 校验 |
| 模板 controller_tenant | 正确：parent_resource 默认、MenuConfig、action_* |
| 模板 model/schema/repo/service | 正确：与手写模式一致 |

#### 2.3.2 测试

- 62 个 Codegen 测试全部通过（config_parser、db_introspector、file_writer、generator_snapshots、rollback、type_registry）

---

## 3. CLI 体系审计

### 3.1 主 CLI (app/cli.py)

#### 3.1.1 命令覆盖

| 命令组 | 子命令 | 审计结论 |
|--------|--------|----------|
| run | — | host/port/reload/workers 正常 |
| celery | worker, beat, dev, flower, purge | 队列、Windows 模式（dev 双线程）正常 |
| db | upgrade, revision, current, heads, history, stamp, merge, autogenerate | 插件迁移路径注入正常 |
| plugin | create, validate, pack, list, cleanup | 委托 plugin_cli，参数传递正确 |
| license | generate, verify, keygen | keygen 输出私钥到 stdout，存在安全建议空间 |
| codegen | generate, preview, validate, rollback 等 | 互斥检查：rollback 已检查 `--resource` OR `--id` |
| check | all, db, redis, celery | 健康检查正常 |
| info | — | 版本、环境摘要正常 |

#### 3.1.2 问题列表

| 命令 | 描述 | 影响 | 建议 |
|------|------|------|------|
| codegen generate | `--config`、`--id`、`--resource`、`--stdin` 可多选，优先顺序为 stdin > config > id/resource，文档未明确 | 用户可能混用导致意外行为 | 在 --help 中说明互斥与优先级 |
| license keygen | 私钥直接 echo 到终端 | 生产环境可能误用导致泄露 | 建议在帮助中提示“仅用于开发环境，生产环境应使用安全存储” |

#### 3.1.3 错误处理

- `sys.exit(1)` 在失败路径正确使用
- `click.echo(..., err=True)` 用于错误输出
- `--json` 模式下输出结构化 JSON

### 3.2 插件 CLI (scripts/plugin_cli.py)

- 已标记 DEPRECATED，主 CLI 通过 `novusai plugin` 委托
- create/validate/pack 参数正确传递

### 3.3 其他 CLI 相关

- `novusai` 入口定义于 `pyproject.toml` 的 `[project.scripts]`
- Windows 路径处理：celery 使用 `os.name == "nt"` 判断，venv Python 路径正确

---

## 4. 跨模块一致性问题

| 类型 | 描述 |
|------|------|
| 分页参数 | 规范要求 `query.size`，codegen `list_configs` 使用 `getattr(spec, "size", None) or getattr(spec, "page_size", None)`，建议统一 |
| 命名 | Model/Schema/Repository/Service/Controller 命名整体一致 |
| API 路径 | 前端 `/admin/ai/agents`、`/admin/ai/knowledge-bases` 与后端路由一致 |

---

## 5. 附录

### 5.1 审计方法

- **自底向上**：Model → Schema → Repository → Service → Controller
- **抽样模块**：tenant_user、agent、codegen（深度）
- **全量 grep**：parent_resource、__delete_deps__、query.size、ForeignKey
- **CLI**：按 `novusai --help` 逐命令阅读 cli.py
- **测试**：`pytest tests/codegen/`、`pytest tests/`

### 5.2 未覆盖区域及原因

- **大批量操作限流**：未对导入、批量删除做压测
- **空列表/空分页 UI**：未做浏览器自动化验证
- **插件 CLI 完整路径**：仅确认主 CLI 委托逻辑，未逐行审计 plugin_cli 内部
- **前端全量 i18n**：仅对 codegen 相关做了 grep，其他 admin 视图未逐文件扫
