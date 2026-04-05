# AI 数据查询（Text-to-SQL）权限安全审计

> 审计日期：2026-03
> 审计范围：AI 对话中 data_query 工具的权限校验、表策略、多租户隔离

## 一、审计结论

**整体评价**：权限链路设计合理，存在 **1 个需修复问题** 和 **若干加固建议**。

---

## 二、权限链路梳理

```
API 层 (tenant/admin/user)
    ↓ permissions, user_role, tenant_id (来自 Auth Deps，服务端不可伪造)
AgentChatService.chat/stream_chat
    ↓
ExecutionRequest(permissions=..., user_role=..., tenant_id=...)
    ↓
ExecutionDispatcher → ToolSandbox(permissions=request.permissions)
    ↓
TextToSQLExecutor.execute(context)
    ↓ context.permissions, context.user_role
SchemaProvider.get_schema(permissions=..., user_role=...)
    ↓
_filter_by_permissions(tables, permissions, user_role)
    ↓
SQLSafetyValidator.validate(sql, allowed_tables)
TenantIsolationInjector.inject(sql, schema, tenant_id, user_role)
```

- `permissions`、`user_role`、`tenant_id` 均由服务端从认证上下文获取，**客户端无法篡改**。

---

## 三、已确认安全的设计

### 3.1 Schema 按权限过滤

- `_filter_by_permissions` 在返回 schema 前按 `permission_code` 与 `permissions` 做表级过滤。
- 未授权表不会出现在 schema 中，LLM 无法为其生成 SQL。

### 3.2 多重校验

| 层级 | 组件 | 作用 |
|------|------|------|
| 1 | SchemaProvider | 未授权表不进入 schema |
| 2 | SQLSafetyValidator | 表必须在 `allowed_tables` 中 |
| 3 | TenantIsolationInjector | 引用未知表时抛出 `unknown_table` |

### 3.3 非平台用户的平台表隔离

- `permission_code=platform_only` 的表对租户用户不可见。
- 无 `tenant_column` 的表对非平台用户不可见，避免跨租户泄露。

### 3.4 Schema 缓存

- 缓存 key：`ai:schema:{tenant_id}`，仅按租户区分。
- 缓存内容：策略合并后的完整 schema。
- 权限过滤在每次请求时执行（`_filter_by_permissions`），**不会因缓存导致跨用户越权**。

### 3.5 身份与上下文来源

- `tenant_id`：来自 `ActiveTenantAdmin.tenant_id` / `ActiveTenantUser.tenant_id` / `_get_agent_tenant_id(agent)`。
- `user_role`：根据使用的 API 固定为 `platform_admin` / `tenant_admin` / `tenant_user`。
- `permissions`：来自 `PermissionService.get_*_permissions()`，服务端权限查询结果。

---

## 四、发现的问题

### 4.1 【需修复】用户端 API 未传递租户用户权限

**位置**：`backend/app/api/user/agent_chat.py`（用户端 / C 端对话 API）

```python
# 当前实现
permissions=[],  # 硬编码空列表
```

**影响**：

- 租户用户进行 AI 对话时，`permissions` 始终为空。
- `_filter_by_permissions` 下，仅有 `permission_code="*"` 的表会通过。
- 当前 AI 策略表多为 `xxx:read`，因此租户用户几乎看不到任何可查表。
- 结果是：要么无法使用 data_query，要么只能查 `*` 表（若存在）。

**建议修复**：改为使用租户用户真实权限：

```python
perm_service = PermissionService(db)
user_perms = await perm_service.get_tenant_user_permissions(current_user)
# ...
permissions=user_perms,
```

**安全影响**：当前实现导致租户用户无法使用 data_query，属于“过度收紧”，无越权风险；但如需按角色正确开放能力，应完成上述修复。

---

## 五、加固建议

### 5.1 permission_code="*" 的管控

**现状**：`permission_code="*"` 表示任意登录用户可访问，`_filter_by_permissions` 中会直接放行。

**建议**：

- 避免对敏感表（含 PII、业务核心表）使用 `*`。
- 在表策略管理 UI 中，对 `*` 做明显风险提示。
- 定期审计 `ai_table_policies` 中 `permission_code='*'` 的表。

### 5.2 对 `allowed_tables` 为空的防御

**现状**：`get_schema` 在权限过滤后可能返回空列表，此时会返回 `no_accessible_tables`。

**建议**：在 `TextToSQLExecutor` 中显式检查 `allowed_tables` 非空，避免后续逻辑在异常分支下使用空集合。

### 5.3 审计与监控

**建议**：

- 对 `ai_query_logs` 做异常检测（如大量失败、高频表名错误等）。
- 定期抽查：用户实际权限与查询表是否匹配。
- 对 `table_not_allowed`、`unknown_table` 等错误做告警。

### 5.4 platform_admin 的作用范围

**现状**：平台管理员使用 `user_role=platform_admin` 时，`_filter_by_permissions` 不做权限过滤，返回全部表。

**说明**：符合平台管理员职责，但需确保：

- 平台管理员身份只能通过 `ActiveAdmin` 等强认证获取。
- 不存在可通过参数篡改将 `user_role` 设为 `platform_admin` 的入口。

---

## 六、权限码与表映射（摘要）

| 表名 | permission_code | 说明 |
|------|-----------------|------|
| agent_conversations | agent_conversation:read | 对话记录 |
| conversation_messages | agent_conversation:read | 对话消息 |
| knowledge_documents | knowledge_base:read | 知识库文档 |
| document_chunks | knowledge_base:read | 文档分块 |
| ai_query_logs | ai_query_log:read | 查询日志（含 SQL 脱敏） |

---

## 七、修复项汇总

| 优先级 | 项目 | 状态 |
|--------|------|------|
| P1 | 用户端传递租户用户权限 | ✅ 已修复：`api/user/agent_chat.py` 使用 `get_tenant_user_permissions()` |
| P2 | CRUD `_check_rbac` 空权限偏松 | ✅ 已修复：`permissions` 为空/None 时拒绝（`crud_executor.py`） |
| P3 | permission_code="*" 审计 | 建议：文档化管控要求，并在管理界面增加提示 |
| P4 | 监控与审计 | 建议：建立查询异常与权限异常的监控与告警 |

---

## 八、审计方法说明

- 代码审查：`schema_provider.py`、`text_to_sql_executor.py`、`tenant_isolation.py`、`sql_safety.py`、各 API 入口。
- 权限链路：从 API 到 `ExecutionContext` 的完整传递路径。
- 缓存：Redis schema 缓存的 key 设计与使用方式。
> **退役说明（2026-04）**：`data_query`、AI 表策略与 `data_intelligence` 运行链路已退役。本文仅保留为历史审计记录，不再代表当前实现。
