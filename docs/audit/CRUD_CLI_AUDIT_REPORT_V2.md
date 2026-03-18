# CRUD 与 CLI 二次审计报告 V2

## 1. 执行摘要

- **审计时间**：2026-03-19
- **审计范围**：CRUD 体系（后端 Model/Schema/Repository/Service/Controller、前端 data.ts/index.vue/form.vue、Codegen 模板）、CLI 体系（novusai 主 CLI、plugin_cli）
- **审计方法**：全量代码扫描、测试执行、多维度自动化审计、首次审计 6 项修复逐条验证
- **修复追踪**：首次审计 6 项 + 二次审计 7 项高优先级问题均已修复；中低优先级按计划后续迭代

### 测试结果

| 测试套件 | 通过 | 失败 | 总计 | 耗时 |
|----------|------|------|------|------|
| Codegen 测试 (`pytest tests/codegen/`) | 62 | 0 | 62 | 2.05s |
| 全量后端测试 (`pytest tests/`) | 738 | 11 | 749 | 35.10s |

- 11 项失败均为 mock 配置问题，非业务逻辑缺陷

### 首次审计 6 项修复验证

| # | 问题 | 状态 |
|---|------|------|
| 1 | CodegenConfig 缺失 `__delete_deps__` | **FIXED** |
| 2 | codegen list_configs 分页使用 getattr fallback | **FIXED** |
| 3 | PresetSelectModal 硬编码中文 | **FIXED** |
| 4 | WysiwygFormView mock 中文 | **FIXED** |
| 5 | codegen generate 参数优先级缺文档 | **FIXED** |
| 6 | license keygen 无安全提示 | **FIXED** |

### 新增发现统计

| 严重程度 | 数量 | 说明 | 修复状态 |
|----------|------|------|----------|
| 高 | 7 | `__delete_deps__` 遗漏 4 项 + get-by-id None 检查 4 处 | **已全部修复** |
| 中 | 18+ | 错误处理不一致、分页、前端 i18n、Codegen 模板健壮性 | 计划后续迭代 |
| 低 | 18+ | CLI 错误处理、测试 mock 问题 | 计划后续迭代 |

---

## 2. 首次审计 6 项修复验证（逐条佐证）

### Issue 1 (高): CodegenConfig 缺失 `__delete_deps__`

**状态**: **FIXED**

**证据**:

```python
# backend/app/models/system/codegen_config.py L42-50
__delete_deps__ = [
    DeletionDep(
        "CodegenConfigVersion",
        "config_id",
        DeletionStrategy.CASCADE_DELETE,
        label_field="id",
        i18n_key="codegen_config_version",
    ),
]
```

- i18n key `codegen_config_version` 已存在于 `backend/app/locales/en/messages.json` 与 `zh_CN/messages.json`
- 前端 `dependency-block-modal` 已配置 `codegen_config_version` 图标映射

---

### Issue 2 (中): codegen list_configs 分页使用 getattr fallback

**状态**: **FIXED**

**证据**:

```python
# backend/app/api/admin/codegen.py L98-105
items, total = await service.query_list(spec)
return paginated(
    items=[CodegenConfigResponse.from_model(x) for x in items],
    total=total,
    page=spec.page or 1,
    page_size=spec.size or 20,
)
```

已改为直接使用 `spec.page`、`spec.size`，不再使用 `getattr(spec, "size", None) or getattr(spec, "page_size", None)`。

---

### Issue 3 (中): PresetSelectModal 硬编码中文

**状态**: **FIXED**

**证据**:

```vue
<!-- frontend/apps/web-antd/src/views/admin/system/codegen/modules/PresetSelectModal.vue L138-143 -->
<span class="font-medium">{{ $t(card.labelKey) }}</span>
<span v-if="card.desc" class="mt-1 text-center text-xs text-muted-foreground">
  {{ $t(card.desc) }}
</span>
```

模板使用 `$t(card.labelKey)` 与 `$t(card.desc)` 展示，不再直接使用 `card.label`。

---

### Issue 4 (中): WysiwygFormView mock 函数硬编码中文

**状态**: **FIXED**

**证据**:

```typescript
// frontend/apps/web-antd/src/views/admin/system/codegen/modules/WysiwygFormView.vue L216+
{ label: `${code} ${$t('admin.system.codegen.preview.mockOptionA')}`, value: 'a' },
{ label: `${code} ${$t('admin.system.codegen.preview.mockOptionB')}`, value: 'b' },
// ...
label: `${table} ${$t(pre + '.mockParentA')}`,
```

mock 相关文案均使用 `$t(...)`，对应 key 已配置于 `admin/system.json` 的 `codegen.preview`。

---

### Issue 5 (低): codegen generate 参数优先级缺文档

**状态**: **FIXED**

**证据**:

```python
# backend/app/cli.py L599, L616
@click.option("--stdin", is_flag=True, help="Read config from stdin (priority: stdin > config > id/resource)")
# ...
"""Generate CRUD code. Config source priority: --stdin > --config > --id/--resource. / 生成 CRUD 代码。配置来源优先级：stdin > config > id/resource"""
```

help 与 docstring 已注明优先级：stdin > config > id/resource。

---

### Issue 6 (低): license keygen 无安全提示

**状态**: **FIXED**

**证据**:

```python
# backend/app/cli.py L533
"""Generate Ed25519 keypair. Private key is printed to stdout. For dev only; use secure storage in production. / 生成 Ed25519 密钥对，私钥输出到 stdout，仅用于开发环境"""
```

docstring 已明确私钥输出至 stdout 及生产环境使用安全存储的建议。

---

## 3. 新增发现列表（按严重程度）

### 3.1 HIGH - `__delete_deps__` 遗漏 (4 项) ✅ **已修复**

| 模型 | 文件 | 问题 | 修复状态 |
|------|------|------|----------|
| Agent | `backend/app/models/ai/agent.py` | AgentAccess、AgentVersion（FK agent_id） | ✅ 已补充，均为 CASCADE_DELETE |
| KnowledgeBase | `backend/app/models/ai/knowledge_base.py` | KnowledgeBaseTenantAccess、AgentKnowledgeBaseBinding（FK knowledge_base_id） | ✅ 已补充，均为 CASCADE_DELETE |
| SkillPackage | `backend/app/models/ai/skill_package.py` | AgentSkillBinding（FK skill_package_id） | ✅ 已补充 CASCADE_DELETE |
| Tenant | `backend/app/models/tenant/tenant.py` | `DeletionDep("TenantPlugin", ...)` 引用已不存在的模型 | ✅ 已移除（tenant_plugins 表在迁移 20260223 中已删除） |

**i18n 补充**：后端 `messages.json` 增加 `agent_access`、`agent_version`、`knowledge_base_tenant_access`（deletion.model）、`periodic_task.error.not_found`、`task_log.error.not_found`；前端 `common.json` 在 dependency.model 中增加上述 key；`dependency-block-modal/index.vue` 已为 agent_access、agent_version、knowledge_base_tenant_access 配置图标映射。

---

### 3.2 HIGH - get-by-id 端点缺少 None 检查 (4 处) ✅ **已修复**

| 文件 | 端点 | 修复状态 |
|------|------|----------|
| `backend/app/api/admin/plugins.py` | `get_plugin` | ✅ 若 plugin is None 则抛出 NotFoundException |
| `backend/app/api/admin/periodic_tasks.py` | `get_periodic_task` | ✅ 若 task is None 则抛出 NotFoundException |
| `backend/app/api/admin/tasks.py` | `task_detail`、`retry_task`、`cancel_task` | ✅ 若 task_log is None 则抛出 NotFoundException |

---

### 3.3 MEDIUM - 错误处理不一致

| 类别 | 文件 | 问题 | 建议 |
|------|------|------|------|
| HTTPException vs NotFoundException | `tenant/domains.py`, `admin/tenant_domains.py`, `admin/tenants.py`, `admin/tenant_admins.py`, `admin/operation_logs.py`, `admin/system_logs.py`, `public/tenant.py` | 使用 `HTTPException(404)` 而非 `NotFoundException` | 统一改用 `NotFoundException` |
| get_ssl_detail 逻辑错误 | `backend/app/api/tenant/domains.py` | 证书不存在返回 200 + null | 改为 `raise NotFoundException(...)` 或 HTTP 404 |
| 状态码常量 | `backend/app/api/admin/codegen.py` L53, 474, 493 | 使用裸数字 `403`、`400` | 改为 `status.HTTP_403_FORBIDDEN`、`status.HTTP_400_BAD_REQUEST` |
| BusinessException 导入 | `backend/app/api/admin/plugins.py` | `from app.exceptions.base import BusinessException` | 改为 `from app.exceptions import BusinessException` |
| 删除响应 | `backend/app/api/admin/system_logs.py` `delete_file` | 返回 `success(data=...)` 而非 `deleted()` | 改为 `return deleted()` |

---

### 3.4 MEDIUM - 分页参数非标准 (1 处)

| 文件 | 端点 | 行号 | 问题 |
|------|------|------|------|
| `backend/app/api/admin/plugins.py` | `marketplace_list` | L328, 348 | 使用原始 `page_size: int = 20` Query 参数，不走 `QueryParams` |

**说明**：marketplace 为外部代理接口，可视为合理例外；建议后续统一为 `QueryParams` 以保持一致性。

---

### 3.5 MEDIUM - 前端硬编码中文 (5 类)

| 文件 | 行号 | 类别 | 影响 |
|------|------|------|------|
| `frontend/apps/web-antd/src/components/business/preference-form/PreferenceForm.vue` | 365 | 语言选择器 `<option>简体中文</option>` | 用户可见 |
| `frontend/apps/web-antd/src/utils/common.ts` | 320-326 | `formatRelativeTime` 返回 "刚刚"、"分钟前" 等 | 用户可见 |
| `frontend/apps/web-antd/src/core/adapter/form/schema-helpers.ts` | 多处 | 表单 placeholder 模板 "请选择"、"请输入"、"搜索" 等 | 用户可见 |
| `frontend/apps/web-antd/src/views/admin/system/codegen/modules/infer.ts` | 320-333 | `FIELD_DISPLAY_NAMES` 14 处中文 | 设计时可见 |
| `frontend/apps/web-antd/src/components/business/rich-text-editor/ai/useEditorAI.ts` | 74 | AI 格式指令中文 | 发给 AI 的提示 |

---

### 3.6 MEDIUM - Codegen 模板健壮性 (4 项)

| 模板 | 问题 | 风险 |
|------|------|------|
| `api_tenant.ts.j2` / `api_admin.ts.j2` | `admin_ep.get(...)` 未防 `admin_ep` 为 None | 生成时 AttributeError |
| `detail.vue.j2` | `model.get('selectable')` 再 `.get('label')` 无空值检查 | 生成异常 |
| `detail.vue.j2` | 使用 `:open="visible"` 而非 `v-model:open` | 与项目惯例不一致 |
| 前端 API 文件命名 | 模板用 snake_case，项目用 kebab-case | 生成文件与命名约定不符 |

**修复建议**：generator 渲染前保证 `admin_ep`、`tenant_ep` 至少为 `{}`；对 `model.get('selectable')` 做空值判断。

---

### 3.7 LOW - CLI 错误处理

| 命令 | 问题 |
|------|------|
| `run` | `subprocess.run(check=True)` 无 try/except |
| `celery *` | `_run_celery()` 无异常捕获 |
| `db *` | Alembic 调用无异常捕获 |
| `plugin *` | `pc.cmd_*` 调用无统一异常处理 |
| `license generate` | `--private-key` 通过命令行传入，可被 ps 进程查看 |
| `codegen preview` / `codegen export` | `--id` 与 `--resource` 未做互斥校验 |
| 模块 docstring (L4-12) | 提到 `db init`、`db migrate`，实际为 `db upgrade`、`db revision` |

---

### 3.8 LOW - 测试 mock 问题 (11 项)

| 测试文件 | 失败数 | 根因 |
|----------|--------|------|
| `tests/plugins/test_contract_lifecycle.py` | 4 | SocketIO module mock 不匹配 |
| `tests/services/test_page_operation.py` | 3 | async emit mock 未正确触发 |
| `tests/tasks/test_registry_sync.py` | 4 | Celery task mock 链路未覆盖返回值 |

---

## 4. 全量扫描结果

### 4.1 `__delete_deps__` 审计

- **已声明模型**：CodegenConfig、Admin、AIModel、AdminRole、Attachment、TenantDomain、KnowledgeBase、Provider、TenantPlan、TablePolicy、Tenant、TenantAdmin、SkillPackage、Agent、AgentConversation、SystemConfig、Plugin、Permission、TenantAdminRole、TenantUserRole、KnowledgeDocument、AITablePolicy 等
- **已修复**：Agent 已补充 AgentAccess、AgentVersion；KnowledgeBase 已补充 KnowledgeBaseTenantAccess、AgentKnowledgeBaseBinding；SkillPackage 已补充 AgentSkillBinding；Tenant 已移除 TenantPlugin 错误引用

### 4.2 分页参数审计

- **paginated() 调用总数**：32
- **符合规范**：31（使用 `query.size` 或 `spec.size`）
- **非标准**：1（`admin/plugins.py` marketplace_list 使用原始 Query 参数）

### 4.3 权限装饰器审计

- **@permission_resource**：57 处均声明 `parent_resource`，**全部合规**
- **路由保护**：所有 CRUD 路由均有 `@action_*` 或 `@auth_only` / `@public`，**全部合规**

### 4.4 前端 i18n 审计

- **Codegen 模块**：PresetSelectModal、WysiwygFormView 已修复
- **待修复**：PreferenceForm.vue、common.ts、schema-helpers.ts、infer.ts、useEditorAI.ts（见 3.5）

### 4.5 错误处理审计

- **NotFoundException**：部分控制器仍使用 HTTPException 404，见 3.3（中优先级）
- **get-by-id None 检查**：✅ 已修复 admin/plugins.py、admin/periodic_tasks.py、admin/tasks.py

---

## 5. Codegen 模板一致性检查

### 5.1 后端模板

| 模板 | 与手写代码一致性 | 备注 |
|------|------------------|------|
| model.py.j2 | 基本一致 | 未生成 `__ai_policy__`，可选支持 |
| repository.py.j2 | 基本一致 | 未生成 `_scope_fields` |
| service.py.j2 | 一致 | 唯一约束校验、reorder 签名符合 |
| controller_tenant.py.j2 | 一致 | PageResponse.create、spec.page/spec.size 符合 |
| schema.py.j2 | 一致 | BaseCreateSchema、from_model 符合 |

### 5.2 前端模板

| 模板 | 与手写代码一致性 | 备注 |
|------|------------------|------|
| api_tenant.ts.j2 / api_admin.ts.j2 | 基本一致 | 需保护 admin_ep 为 None |
| data_table.ts.j2 / data_card.ts.j2 | 基本一致 | API 文件命名 snake_case vs kebab-case |
| index_table.vue.j2 / index_card.vue.j2 | 一致 | useCrudPage、useCrudList 符合 |
| detail.vue.j2 | 需改进 | selectable 空值检查、v-model:open |
| form.vue.j2 | 一致 | useVbenForm、useCrudDrawer 符合 |

---

## 6. CLI 逐命令审计

### 6.1 命令树

```
novusai
├── run
├── celery (worker, beat, dev, flower, purge)
├── db (upgrade, revision, current, heads, history, stamp, merge, autogenerate)
├── plugin (create, validate, pack, list, cleanup)
├── license (generate, verify, keygen)
├── codegen (generate, preview, validate, rollback, versions, restore, list, show, import, export, delete, duplicate, db, init, history, download)
├── check (all, db, redis, celery)
└── info
```

### 6.2 审计结论

| 命令组 | 结论 |
|--------|------|
| run | 功能正常，缺 try/except |
| celery | 功能正常，缺异常捕获 |
| db | Alembic 集成正常，docstring 提及不存在的 init/migrate |
| plugin | 委托 plugin_cli 正确 |
| license | keygen 安全提示已加；generate 的 --private-key 建议改用环境变量 |
| codegen | 参数优先级已文档化；preview/export 互斥未校验 |
| check | 健康检查完整，错误处理良好 |
| info | 敏感信息已脱敏 |

---

## 7. 测试执行结果

### Codegen 测试

```
pytest backend/tests/codegen/ -v
62 passed in 2.05s
```

- config_parser、db_introspector、file_writer、generator_snapshots、rollback、type_registry 全部通过

### 全量后端测试

```
pytest backend/tests/ -v
738 passed, 11 failed, 2 warnings in 35.10s
```

**失败用例**：

| 测试 | 原因 |
|------|------|
| test_contract_lifecycle.py (4) | SocketIO module mock 不匹配、AsyncMock 用法 |
| test_page_operation.py (3) | page operation invoke timeout、emit mock 未触发 |
| test_registry_sync.py (4) | Celery task mock 返回值类型未覆盖 |

**结论**：失败均源于 mock 配置，非业务逻辑问题。

---

## 8. 第三次修复验证（7 项高优先级）

以下 7 项高优先级问题已于后续迭代中全部修复，并经验证。

### 8.1 修复汇总

| 类别 | 修改内容 |
|------|----------|
| **3.1 __delete_deps__** | Agent 增加 AgentAccess、AgentVersion（CASCADE_DELETE）；KnowledgeBase 增加 KnowledgeBaseTenantAccess、AgentKnowledgeBaseBinding（CASCADE_DELETE）；SkillPackage 增加 AgentSkillBinding（CASCADE_DELETE）；Tenant 移除 TenantPlugin |
| **3.2 get-by-id None 检查** | admin/plugins.py get_plugin、admin/periodic_tasks.py get_periodic_task、admin/tasks.py task_detail/retry_task/cancel_task，均增加 None 检查并抛出 NotFoundException |
| **i18n** | 后端 messages.json：agent_access、agent_version、knowledge_base_tenant_access、periodic_task.error.not_found、task_log.error.not_found；前端 common.json dependency.model 增加上述 key；dependency-block-modal 增加图标映射 |

### 8.2 验证结果

- Codegen 测试：62 通过
- 模型加载：Agent、KnowledgeBase、SkillPackage、Tenant 的 `__delete_deps__` 可正确加载

### 8.3 待办（中低优先级）

3.3 错误处理统一、3.5 前端硬编码中文、3.6 Codegen 模板健壮性、3.7 CLI 错误处理等，可按计划在后续迭代中逐步修复。

---

## 9. 附录

### 9.1 审计方法

- **自底向上**：Model → Schema → Repository → Service → Controller
- **全量 grep**：`__delete_deps__`、`page_size=`、`parent_resource`、`ForeignKey`
- **子任务扫描**：delete_deps 引用关系、分页参数、权限装饰器、前端硬编码中文、错误处理模式
- **测试**：`pytest tests/codegen/`、`pytest tests/`
- **CLI**：逐命令阅读 cli.py，对照 docstring 与 help 输出

### 9.2 未覆盖区域

- 大批量操作限流与压测
- 空列表/空分页 UI 的浏览器自动化验证
- 插件 CLI 内部完整逻辑
- 前端非 codegen 视图的全量 i18n 扫描
