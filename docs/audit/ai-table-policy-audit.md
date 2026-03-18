# AI 表策略功能全面审计报告

**审计日期**：2026-03-17  
**范围**：平台端 AI 表策略管理、企业端覆盖、前端/后端/API/权限/i18n

---

## 1. 架构概览

AI 表策略（`ai_table_policies`）为平台级配置，控制 AI 可访问的数据库表及 CRUD 权限。策略由 sync 服务从声明了 `__ai_policy__` 的 Model 自动创建，管理员仅做编辑和同步触发。

- **平台端**：`/admin/ai/table-policies` — 策略列表、编辑、同步、声明表列表
- **企业端**：`/tenant/ai/table-policies` — 查看有效策略、创建/更新/删除覆盖（仅收紧）
- **关联**：技能包「数据智能」类型技能通过 `config.table_policy_ids` 绑定表策略

---

## 2. 后端审计

### 2.1 API 路由与顺序 ✅

**文件**：`backend/app/api/admin/ai_table_policies.py`

| 路由 | 方法 | 说明 |
|------|------|------|
| `""` | GET | 列表（分页） |
| `"/declared-tables"` | GET | 声明了 __ai_policy__ 的表名列表 |
| `"/{policy_id}"` | GET | 详情 |
| `"/{policy_id}"` | PUT | 更新 |
| `"/{policy_id}/columns"` | GET | 表列信息（blocked/readonly 选择器） |
| `"/sync"` | POST | 触发表策略同步 |

**路由顺序**：`/declared-tables` 在 `/{policy_id}` 之前，避免 `"declared-tables"` 被解析为 `policy_id`。✅

**POST /sync** 与 `GET /{policy_id}` 方法不同，无冲突。✅

### 2.2 权限与 RBAC ✅

- `permission_resource`: `ai_table_policy`，`scope=ADMIN_ONLY`，`parent=ai_infra`
- `action_read`: list, detail, columns, declared-tables
- `action_update`: update, sync
- 后端 locale：`action.ai_table_policy.list/detail/update/columns/sync` 已定义

### 2.3 Service / Repository / Model ✅

- **Service**：`AITablePolicyService` — `get_or_raise`、`get_table_columns`，与业务一致
- **Repository**：`get_table_columns` 通过 `information_schema` 查询，返回 `{name, type, comment}`
- **Model**：`AITablePolicy` 字段与 Schema 一致，`__filterable__`、`__sortable__` 正确

### 2.4 Sync 服务 ✅

- `sync_table_policies` 仅处理声明 `__ai_policy__` 的 Model
- 返回 `{ new, new_count, existing, existing_count, skipped, skipped_count, declared_tables }`
- 前端兼容 `result.new ?? result.new_count` 等

### 2.5 Schema 缓存失效 ✅ **已修复**

**原问题**：更新策略或执行 sync 后，仅调用 `SchemaProvider.invalidate_cache(0)`，只清除了 `tenant_id=0` 的缓存。

**修复**：在 `SchemaProvider` 中新增 `invalidate_all_schema_caches()`，使用 Redis `SCAN` 匹配 `ai:schema:*` 删除所有企业缓存。平台 update/sync 接口已改为调用该方法。

### 2.6 Tenant API ✅

- `TenantAITablePolicyController`：`list_effective`、`upsert_override`、`remove_override`
- 企业覆盖写入/删除后正确调用 `schema_cache_key(tenant_admin.tenant_id)` 清除该企业缓存

---

## 3. 前端审计

### 3.1 API 对接 ✅

**文件**：`frontend/apps/web-antd/src/api/admin/ai.ts`

- `getAITablePolicyListApi` → `GET /admin/ai/table-policies`，返回 `PageResponse<AITablePolicyInfo>`（`items` + `total`）
- `getAITablePolicyDetailApi` → `GET /admin/ai/table-policies/{id}`
- `updateAITablePolicyApi` → `PUT /admin/ai/table-policies/{id}`
- `getAITablePolicyColumnsApi` → `GET /admin/ai/table-policies/{id}/columns`
- `syncAITablePoliciesApi` → `POST /admin/ai/table-policies/sync`
- `getAITablePolicyDeclaredTablesApi` → `GET /admin/ai/table-policies/declared-tables`

VXE Table 配置 `result: 'items', total: 'total'` 与后端 `PageResponse` 一致。✅

### 3.2 列表页 `index.vue` ✅

- `useCrudPage` 使用 `getAITablePolicyListApi`、`resource: '/admin/ai/table-policies'`
- CRUD 权限列（R/C/U/D）支持行内切换，无需确认弹窗
- 启用状态通过 `Switch` + `Modal.confirm`
- 未声明 `__ai_policy__` 的表显示 ⚠️ 图标（基于 `declaredTables`）
- 展开行：屏蔽列、只读列、已描述列数、跳转技能
- `goToSkillsWithPolicy(policyId)` 跳转 `/admin/ai/skill-packages?table_policy_id={id}`

### 3.3 编辑表单 `form.vue` ✅

- 仅编辑模式（无新建），策略由 sync 创建
- `toFormValues` / `transform` 覆盖所有可编辑字段，包含 `column_descriptions`
- `loadColumnOptions` 动态加载列选项，用于 blocked_columns / readonly_columns
- 列描述通过 `columnList` + `Input` 列表编辑，并同步到 `columnDescs`

### 3.4 关联跳转：技能包筛选 ✅

**文件**：`frontend/apps/web-antd/src/views/admin/ai/skill-packages/index.vue`

- `tablePolicyIdFilter` 从 `route.query.table_policy_id` 读取
- `filteredSkills` 按 `config.table_policy_ids` 包含该 `policy_id` 过滤
- 存在筛选时显示 `tablePolicyFilterHint` 提示
- `clearTablePolicyFilter` 清除 query

### 3.5 i18n ✅

**admin.ai.tablePolicy** 下已定义：

- `name`、`pageDesc`、`tableName`、`label`、`crud`、`maxRows`、`isActive` 等
- `sync`、`syncSuccess`、`syncConfirm`
- `expandBlockedColumns`、`expandReadonlyColumns`、`expandDescribedColumns`、`expandViewSkills`
- `notDeclaredWarning`
- `placeholder.*`、`messages.*`
- `admin.ai.skillPackage.tablePolicyFilterHint`

### 3.6 页面操作注册 ✅

- `registerPageContext`：`admin/ai/table-policies`，`page_key: admin.ai.table-policies`
- `registerPageOperations`：`refresh_list`、`sync_policies`、`search`、`formAiOperations`
- `onSync` 的 handler 仅调用 `onSync()` 打开确认弹窗，符合设计（非同步完成后才返回）

---

## 4. 类型与字段一致性 ✅

| 字段 | 后端 Model | 后端 Response | 前端 AITablePolicyInfo |  form 字段 |
|------|------------|---------------|------------------------|-----------|
| table_name | ✅ | ✅ | ✅ | 只读 |
| label | ✅ | ✅ | ✅ | ✅ |
| description | ✅ | ✅ | ✅ | ✅ |
| keywords | ✅ | ✅ | ✅ | ✅ |
| column_descriptions | ✅ | ✅ | ✅ | 单独区块 |
| allow_read/create/update/delete | ✅ | ✅ | ✅ | ✅ |
| max_rows | ✅ | ✅ | ✅ | ✅ |
| blocked_columns | ✅ | ✅ | ✅ | 动态选项 |
| readonly_columns | ✅ | ✅ | ✅ | 动态选项 |
| permission_code | ✅ | ✅ | ✅ | ✅ |
| sort_order | ✅ | ✅ | ✅ | ✅ |
| is_active | ✅ | ✅ | ✅ | ✅ |

---

## 5. 问题汇总

| 级别 | 描述 | 状态 |
|------|------|------|
| P2 | Schema 缓存仅清除 tenant_id=0，平台策略变更后其他企业缓存未失效 | **已修复** |
| P3 | 无 | - |

---

## 6. 已实施修复

### 6.1 Schema 缓存全局失效（P2）✅

- **SchemaProvider**：新增 `invalidate_all_schema_caches()`，使用 `redis.scan_iter(match="ai:schema:*")` 删除所有企业缓存
- **ai_table_policies**：update、sync 接口改为调用 `invalidate_all_schema_caches()`，不再调用 `invalidate_cache(0)`

---

## 7. 审计结论

AI 表策略实现正确，前后端对接正常，权限与 i18n 完整。P2 Schema 缓存清除范围问题已修复，平台策略变更后所有企业均可获取最新 schema。
