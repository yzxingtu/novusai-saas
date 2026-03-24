"""
Generic CRUD Executor
通用 CRUD 执行器

Dynamically executes create/update/delete operations based on ai_table_policies.
基于 ai_table_policies 动态执行 create/update/delete 操作。
All write operations use a two-step confirmation flow:
所有写操作采用两步确认流程：
  Step 1: Return preview JSON (requires_confirmation=true)
          返回预览 JSON（requires_confirmation=true）
  Step 2: LLM re-calls with confirmed=true, executing the actual operation
          LLM 重新调用并带 confirmed=true，执行实际操作

Security policies / 安全策略：
- CRUD permission checks based on ai_table_policies / 基于 ai_table_policies 检查 CRUD 权限
- blocked_columns / readonly_columns are not writable / 不允许写入
- Tenant isolation: tenant-scoped tables auto-inject tenant_id / 企业隔离：自动注入 tenant_id
- Soft delete only (set is_deleted=True), no hard deletes / 仅软删除，不允许硬删除
- All operations are audited to ai_action_logs / 所有操作审计到 ai_action_logs
"""

from __future__ import annotations

import copy
import json
import re
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ExecutionContext, ToolDefinition, ToolResult
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import build_public_error_text
from app.enums.agent import (
    ActionLevelEnum,
    ActionStatusEnum,
    ActionTypeEnum,
    AgentStatusEnum,
)
from app.enums.common import ResourceScopeEnum
from app.configs.service import PLATFORM_TENANT_ID
from app.models.ai.table_policy import AITablePolicy
from app.repositories.system.resource_tenant_assignment_repository import (
    ResourceTenantAssignmentRepository,
)
from app.services.ai.action_log_service import write_ai_action_log
from app.services.ai.agent_service import AdminAgentService, AgentService

if TYPE_CHECKING:
    pass  # ExecutionContext already imported above  # 补充说明 / note

logger = LogManager.get_logger("ai.tool.crud")

# Only canonical ResourceScopeEnum values are accepted; no legacy aliases / 上文为英文说明 / English above
_RESOURCE_SCOPE_NORMALIZE: dict[str, str] = {
    e.value: e.value for e in ResourceScopeEnum
}
_VALID_RESOURCE_SCOPES: frozenset[str] = frozenset(e.value for e in ResourceScopeEnum)
_RESOURCE_SCOPES_NEEDING_ASSIGNMENT: frozenset[str] = frozenset({
    ResourceScopeEnum.SELECTED_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
})

# Table name whitelist regex: only lowercase letters, digits, underscores (prevent SQL injection)
# 表名白名单正则：仅允许小写字母、数字、下划线（防 SQL 注入）
_SAFE_TABLE_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
# Column name whitelist regex: same rules as table names (prevent SQL injection)
# 列名白名单正则：与表名规则一致（防 SQL 注入）
_SAFE_COLUMN_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def _validate_table_name(table_name: str) -> str | None:
    """Validate table name is safe, return error message or None. / 校验表名是否安全，返回错误消息或 None。"""
    if not _SAFE_TABLE_NAME_RE.match(table_name):
        return _("data_intelligence.crud.invalid_table_name").format(table=table_name)
    return None


def _validate_column_names(data: dict[str, Any]) -> str | None:
    """校验所有列名是否安全，返回错误消息或 None / Validate all column names are safe, return error message or None.

    Prevents LLM from passing malicious column names that could cause SQL injection.
    Column names only allow lowercase letters, digits, and underscores, and must start with a letter or underscore.
    防止 LLM 传入恶意列名导致 SQL 注入。
    列名仅允许小写字母、数字和下划线，且必须以字母或下划线开头。
    """
    invalid = [k for k in data if not _SAFE_COLUMN_NAME_RE.match(k)]
    if invalid:
        return _("data_intelligence.crud.invalid_column_names").format(
            columns=", ".join(sorted(invalid)),
        )
    return None


# Global safety: columns that are never writable / 全局安全：永远不允许写入的列
_NEVER_WRITABLE_COLUMNS: set[str] = {
    "id", "created_at", "updated_at", "is_deleted", "deleted_at",
    "password", "password_hash", "hashed_password",
    "secret", "secret_key", "api_key", "access_token",
    "refresh_token", "encrypted_key", "salt",
}


async def _load_policy(
    context: ExecutionContext,
    table_name: str,
) -> AITablePolicy | None:
    """Load table policy from database (with tenant override merging). / 从数据库加载表策略（含企业覆盖合并）。

    Loads the global policy, then finds and merges the corresponding tenant override.
    Overrides can only tighten, not loosen. Merged values are written directly to policy object attributes.
    加载全局策略后，查找对应的企业覆盖并合并。
    覆盖只能收紧，不能放开。合并后的值直接写入策略对象属性。
    """
    if not context.db:
        return None
    from app.repositories.ai.table_policy_repository import AITablePolicyRepository
    policy_repo = AITablePolicyRepository(context.db)
    policy = await policy_repo.get_active_by_table_name(table_name)
    if not policy:
        return None

    # Load tenant override and merge (tighten-only rules) / 加载企业覆盖并合并（收紧规则）
    if context.tenant_id:
        from app.repositories.ai.table_policy_override_repository import (
            AITablePolicyOverrideRepository,
        )
        override_repo = AITablePolicyOverrideRepository(context.db)
        ov = await override_repo.get_by_policy_and_tenant(policy.id, context.tenant_id)
        if ov:
            # Overrides can only tighten: True -> False OK, False -> True not allowed
            # 覆盖只能收紧：True -> False 可以，False -> True 不行
            if ov.allow_read is not None and not ov.allow_read:
                policy.allow_read = False
            if ov.allow_create is not None and not ov.allow_create:
                policy.allow_create = False
            if ov.allow_update is not None and not ov.allow_update:
                policy.allow_update = False
            if ov.allow_delete is not None and not ov.allow_delete:
                policy.allow_delete = False
            if ov.is_active is not None and not ov.is_active:
                policy.is_active = False
            # max_rows can only be smaller / max_rows 只能更小
            if ov.max_rows is not None and ov.max_rows < policy.max_rows:
                policy.max_rows = ov.max_rows
            # blocked_columns can only be appended / blocked_columns 只能追加
            if ov.blocked_columns:
                existing = set(policy.blocked_columns or [])
                existing.update(ov.blocked_columns)
                policy.blocked_columns = list(existing)

    # If disabled after merging, treat as non-existent / 合并后如果被禁用则视为不存在
    if not policy.is_active:
        return None

    return policy


def _get_blocked_columns(policy: AITablePolicy) -> set[str]:
    """Get the set of columns that are forbidden to write / 获取禁止写入的列集合"""
    blocked = set(_NEVER_WRITABLE_COLUMNS)
    if policy.blocked_columns:
        blocked.update(policy.blocked_columns)
    if policy.readonly_columns:
        blocked.update(policy.readonly_columns)
    return blocked


def _validate_write_data(
    data: dict[str, Any],
    blocked: set[str],
) -> str | None:
    """校验写入数据中是否包含禁止写入的列，返回错误消息或 None / Validate if write data contains forbidden columns, return error message or None."""
    violations = set(data.keys()) & blocked
    if violations:
        return _("data_intelligence.crud.blocked_columns_violation").format(
            columns=", ".join(sorted(violations)),
        )
    return None


def _derive_permission(permission_code: str, action: str) -> str | None:
    """从策略的 permission_code 推导写操作所需的权限码 / Derive required permission code for write operations from policy's permission_code.

    Examples / 例如: 'agent:read' + 'create' -> 'agent:create'
          '*' -> None (no extra permission needed / 不需要额外权限)
          'platform_only' -> 'platform_only' (platform admin only / 仅平台管理员)
    """
    if permission_code == "*":
        return None
    if permission_code == "platform_only":
        return "platform_only"
    if ":" in permission_code:
        resource = permission_code.split(":")[0]
        return f"{resource}:{action}"
    return f"{permission_code}:{action}"


def _check_rbac(
    context: ExecutionContext,
    policy: AITablePolicy,
    action: str,
) -> str | None:
    """检查用户 RBAC 权限，返回错误消息或 None / Check user RBAC permissions, return error message or None.

    CRUD switches (allow_create/update/delete) are already checked by the caller;
    this only validates user identity + permission code.
    CRUD 开关（allow_create/update/delete）已在调用方检查过，
    此处只做用户身份 + 权限码校验。

    Args:
        context: Execution context / 执行上下文
        policy: Table policy / 表策略
        action: Operation type (create/update/delete/read) / 操作类型
    """
    perm_code = policy.permission_code or "*"

    # platform_only: platform admin only / 仅平台管理员
    if perm_code == "platform_only":
        if not context.is_platform_admin:
            return _("data_intelligence.crud.permission_denied").format(
                action=action, table=policy.table_name,
            )
        return None

    # '*' permission code: any logged-in user can execute / 任何登录用户可执行
    if perm_code == "*":
        return None

    # Platform admins skip permission code derivation check (they have all RBAC permissions)
    # 平台管理员跳过权限码推导检查（他们有所有 RBAC 权限）
    if context.is_platform_admin:
        return None

    # Super/wildcard: "*" in permissions means all permissions (consistent with PermissionService.check_permission)
    # 超级权限：permissions 含 "*" 表示拥有所有权限（与 PermissionService.check_permission 一致）
    if "*" in (context.permissions or set()):
        return None

    # Derive required permission code and check / 推导所需权限码并检查
    # permissions 为空/None 时拒绝（防止越权）
    required = _derive_permission(perm_code, action)
    if required:
        if not context.permissions or required not in context.permissions:
            return _("data_intelligence.crud.permission_denied").format(
                action=action, table=policy.table_name,
            )

    return None


def _normalize_agent_data(data: dict[str, Any]) -> tuple[dict[str, Any], list[int] | None, bool]:
    """Normalize agent create data: resource scope, strip system fields, extract tenant_ids and publish flag."""
    data = copy.deepcopy(data)

    tenant_ids = data.pop("tenant_ids", None)
    if isinstance(tenant_ids, list):
        tenant_ids = [int(x) for x in tenant_ids if isinstance(x, (int, float))]
    else:
        tenant_ids = None

    want_publish = False
    if data.get("status") == AgentStatusEnum.PUBLISHED.value:
        want_publish = True
    data.pop("status", None)
    data.pop("published_version", None)
    data.pop("delete_level", None)
    data.pop("id", None)
    data.pop("created_at", None)
    data.pop("updated_at", None)
    data.pop("is_deleted", None)
    data.pop("deleted_at", None)
    data.pop("is_system", None)
    data.pop("target_audience", None)

    for rejected_field in ("distribution_mode", "owner_type", "legacy_scope"):
        if rejected_field in data:
            raise ValueError(
                _("data_intelligence.crud.rejected_legacy_field").format(field=rejected_field)
            )
    raw_scope = data.pop("scope", None)
    if raw_scope is not None:
        scope_val = _RESOURCE_SCOPE_NORMALIZE.get(
            str(raw_scope).lower().strip(),
            str(raw_scope).strip(),
        )
        if scope_val not in _VALID_RESOURCE_SCOPES:
            raise ValueError(
                _("data_intelligence.crud.agent_invalid_scope").format(
                    scope=scope_val,
                    valid=", ".join(sorted(_VALID_RESOURCE_SCOPES)),
                )
            )
        data["scope"] = scope_val

    return data, tenant_ids, want_publish


async def _execute_agent_create_via_service(
    context: ExecutionContext,
    data: dict[str, Any],
    tool_call_id: str,
    tool_name: str,
) -> ToolResult:
    """Create agent via AgentService/AdminAgentService instead of raw SQL."""
    try:
        payload, tenant_ids, want_publish = _normalize_agent_data(data)
    except ValueError as e:
        return ToolResult.error_result(tool_call_id, str(e), name=tool_name)

    if context.is_platform_admin:
        payload.pop("tenant_id", None)
        service = AdminAgentService(context.db)
        agent = await service.create(payload)
        if (
            agent.scope in _RESOURCE_SCOPES_NEEDING_ASSIGNMENT
            and tenant_ids is not None
        ):
            repo = ResourceTenantAssignmentRepository(context.db)
            await repo.sync_assignments("agent", agent.id, tenant_ids)
        if want_publish:
            pub_tid = agent.owner_tenant_id
            if pub_tid is None:
                pub_tid = PLATFORM_TENANT_ID
            pub_svc = AgentService(context.db, pub_tid)
            await pub_svc.publish_agent(
                agent.id,
                change_log="Published by AI data create",
                created_by=context.user_id,
            )
    else:
        service = AgentService(context.db, context.tenant_id)
        payload.pop("tenant_ids", None)
        agent = await service.create(payload)
        if want_publish:
            await service.publish_agent(
                agent.id,
                change_log="Published by AI data create",
                created_by=context.user_id,
            )

    await _audit_log(context, "create", "agents", agent.id, payload, success=True)
    return ToolResult(
        tool_call_id=tool_call_id,
        name=tool_name,
        success=True,
        output=json.dumps({
            "action": "create",
            "table": "agents",
            "id": agent.id,
            "success": True,
        }, ensure_ascii=False, default=str),
    )


async def _check_tenant_column(
    context: ExecutionContext,
    table_name: str,
) -> str | None:
    """检查表是否有 tenant_id 列，非平台用户禁止操作无隔离列的表 / Check if table has tenant_id column; non-platform users forbidden on tables without isolation.

    Returns error message or None (pass).
    返回错误消息或 None（通过）。
    Platform admins can operate on any table (including platform-level tables without tenant_id).
    平台管理员可操作任何表（含无 tenant_id 的平台级表）。
    """
    if context.is_platform_admin:
        return None

    if not context.db:
        return None

    # Query whether the target table has a tenant_id column / 查询目标表是否存在 tenant_id 列
    check_sql = text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :tbl AND column_name = 'tenant_id' "
        "LIMIT 1"
    )
    result = await context.db.execute(check_sql, {"tbl": table_name})
    if not result.scalar():
        return _("data_intelligence.crud.no_tenant_isolation").format(table=table_name)

    return None


def _enforce_tenant_isolation(
    context: ExecutionContext,
    policy: AITablePolicy,
    data: dict[str, Any],
) -> None:
    """强制注入 tenant_id 到写入数据（从上下文获取，永不信任 LLM 输入）/ Force inject tenant_id into write data (from context, never trust LLM input)."""
    if context.tenant_id:
        data["tenant_id"] = context.tenant_id
    elif "tenant_id" in data:
        # Platform admin doesn't need tenant_id, remove value possibly passed by LLM
        # 平台管理员无需 tenant_id，移除 LLM 可能传入的值
        data.pop("tenant_id", None)


# System-managed columns: silently stripped when passed by LLM, auto-injected by system
# 系统管理列：LLM 传入时静默剥离，由系统自动注入
_SYSTEM_MANAGED_COLUMNS: set[str] = {
    "tenant_id", "is_deleted", "deleted_at", "delete_level",
    "created_at", "updated_at",
}
# Columns never required from user (auto-generated or always injected) / 上文为英文说明 / English above
_CREATE_SKIP_REQUIRED: frozenset[str] = frozenset({
    "id", "created_at", "updated_at", "tenant_id", "is_deleted", "deleted_at",
})


def _strip_system_columns(data: dict[str, Any]) -> None:
    """剥离 LLM 可能传入的所有系统管理列（静默删除，不报错）/ Strip all system-managed columns that LLM may have passed (silent removal, no error).

    These columns are auto-injected by the system (e.g. tenant_id, is_deleted),
    or auto-handled by DB/raw SQL (e.g. created_at, updated_at).
    Called before validation to avoid triggering blocked_columns check failures.
    这些列由系统自动注入（如 tenant_id、is_deleted），
    或由数据库/raw SQL 自动处理（如 created_at、updated_at）。
    在验证之前调用，避免触发 blocked_columns 校验失败。
    """
    for col in _SYSTEM_MANAGED_COLUMNS:
        data.pop(col, None)


async def _get_required_columns_for_create(
    context: ExecutionContext,
    table_name: str,
) -> set[str]:
    """Get NOT NULL columns without default that user must provide for INSERT.
    获取 INSERT 时用户必须提供的 NOT NULL 且无默认值的列。"""
    if not context.db:
        return set()
    query = text("""
        SELECT c.column_name
        FROM information_schema.columns c
        WHERE c.table_schema = 'public' AND c.table_name = :tbl
          AND c.is_nullable = 'NO'
          AND (c.column_default IS NULL OR c.column_default = '')
    """)
    result = await context.db.execute(query, {"tbl": table_name})
    cols = {row[0] for row in result.fetchall()}
    return cols - _CREATE_SKIP_REQUIRED


def _serialize_for_sql(data: dict[str, Any]) -> None:
    """将 dict/list 值序列化为 JSON 字符串，供 asyncpg raw SQL 绑定 / Serialize dict/list values to JSON strings for asyncpg raw SQL binding.

    asyncpg cannot directly bind Python dict/list to JSONB columns;
    they must be converted to JSON strings first.
    asyncpg 不能直接绑定 Python dict/list 到 JSONB 列，
    必须先转换为 JSON 字符串。
    """
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            data[key] = json.dumps(value, ensure_ascii=False, default=str)


async def _audit_log(
    context: ExecutionContext,
    action: str,
    table_name: str,
    record_id: int | None,
    data: dict[str, Any] | None,
    success: bool,
    error: str | None = None,
) -> None:
    """Write AI operation audit log / 写入 AI 操作审计日志"""
    if not context.db:
        return
    try:
        action_level = (
            ActionLevelEnum.DANGEROUS.value
            if action == "delete"
            else ActionLevelEnum.SAFE_WRITE.value
        )
        await write_ai_action_log(
            context.db,
            tenant_id=context.tenant_id,
            agent_id=context.agent_id,
            operator_id=context.user_id,
            skill_id=context.skill_id,
            action_name=f"data_{action}",
            action_type=ActionTypeEnum.ACTION.value,
            action_level=action_level,
            request_data={
                "table_name": table_name,
                "record_id": record_id,
                "data": data or {},
            },
            response_data={
                "table_name": table_name,
                "record_id": record_id,
            },
            status=(
                ActionStatusEnum.SUCCESS.value
                if success
                else ActionStatusEnum.FAILED.value
            ),
            error_message=error,
        )
    except Exception as exc:
        logger.warning("Failed to write audit log: {}", str(exc))


# ============================================ / 上文为英文说明 / English above
# CreateRecordExecutor
# ============================================

class CreateRecordExecutor(BaseToolExecutor):
    """
    Generic record creation executor.
    通用记录创建执行器。

    LLM call arguments / LLM 调用参数: {table_name, data: {field: value, ...}, confirmed?: bool}
    """

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        _ = definition
        return bool(arguments.get("table_name") and arguments.get("data"))

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        _name = definition.name
        if not context or not context.db:
            return ToolResult.error_result(
                tool_call_id, _("data_intelligence.crud.no_context"), name=_name,
            )

        table_name = arguments["table_name"]
        data = arguments.get("data", {})
        confirmed = arguments.get("confirmed", False)

        # Table name safety validation / 表名安全校验
        table_err = _validate_table_name(table_name)
        if table_err:
            return ToolResult.error_result(tool_call_id, table_err, name=_name)

        # Load policy / 加载策略
        policy = await _load_policy(context, table_name)
        if not policy:
            return ToolResult.error_result(
                tool_call_id,
                _("data_intelligence.crud.table_not_found").format(table=table_name),
                name=_name,
            )

        if not policy.allow_create:
            return ToolResult.error_result(
                tool_call_id,
                _("data_intelligence.crud.operation_denied").format(
                    operation="create", table=table_name,
                ) + _("data_intelligence.crud.no_retry_hint").format(operation="create"),
                name=_name,
            )

        # RBAC: check if user has create permission / 检查用户是否有 create 权限
        rbac_error = _check_rbac(context, policy, "create")
        if rbac_error:
            return ToolResult.error_result(tool_call_id, rbac_error, name=_name)

        # Tenant isolation column check: non-platform users forbidden from tables without tenant_id
        # 企业隔离列检查：非平台用户禁止操作无 tenant_id 列的表
        tc_err = await _check_tenant_column(context, table_name)
        if tc_err:
            return ToolResult.error_result(tool_call_id, tc_err, name=_name)

        # Strip system-managed columns (tenant_id/is_deleted etc., injected by system)
        # 剥离系统管理列（tenant_id/is_deleted 等，由系统注入）
        _strip_system_columns(data)

        # Column name safety validation (prevent SQL injection)
        # 列名安全校验（防 SQL 注入）
        col_err = _validate_column_names(data)
        if col_err:
            return ToolResult.error_result(tool_call_id, col_err, name=_name)

        # Validate write data / 校验写入数据
        blocked = _get_blocked_columns(policy)
        violation = _validate_write_data(data, blocked)
        if violation:
            return ToolResult.error_result(tool_call_id, violation, name=_name)

        # Inject system defaults (after validation, ensure raw SQL doesn't miss NOT NULL columns)
        # 注入系统默认值（验证后，确保 raw SQL 不缺少 NOT NULL 列）
        _enforce_tenant_isolation(context, policy, data)
        data["is_deleted"] = False

        # Pre-validate required fields / 预校验必填字段
        required = await _get_required_columns_for_create(context, table_name)
        provided = set(data.keys())
        missing = required - provided
        if missing:
            return ToolResult.error_result(
                tool_call_id,
                _("data_intelligence.crud.missing_required_fields").format(
                    table=table_name,
                    columns=", ".join(sorted(missing)),
                ),
                name=_name,
            )

        # Confirmation flow / 确认流程
        if not confirmed:
            preview = {
                "action": "create",
                "table": table_name,
                "preview": data,
                "requires_confirmation": True,
            }
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=json.dumps(preview, ensure_ascii=False, default=str),
            )

        # Agents table: use service layer instead of raw SQL / 上文为英文说明 / English above
        if table_name == "agents":
            try:
                async with context.db.begin_nested():
                    return await _execute_agent_create_via_service(
                        context, data, tool_call_id, definition.name,
                    )
            except Exception as exc:
                await _audit_log(
                    context, "create", table_name, None, data,
                    success=False, error=str(exc),
                )
                return ToolResult.error_result(
                    tool_call_id,
                    build_public_error_text(
                        message="Create record failed",
                        exc=exc,
                    ),
                    name=definition.name,
                )

        # Serialize JSON values (dict/list -> JSON strings, for asyncpg binding)
        # 序列化 JSON 值（dict/list → JSON 字符串，供 asyncpg 绑定）
        _serialize_for_sql(data)

        # Execute creation (using savepoint isolation, doesn't affect outer transaction)
        # 执行创建（使用 savepoint 隔离，不影响外层事务）
        try:
            async with context.db.begin_nested():
                all_columns = list(data.keys()) + ["created_at", "updated_at"]
                all_placeholders = [f":{k}" for k in data] + ["NOW()", "NOW()"]
                raw_sql = text(
                    f"INSERT INTO {table_name} ({', '.join(all_columns)})"
                    f" VALUES ({', '.join(all_placeholders)}) RETURNING id"
                )
                result = await context.db.execute(raw_sql, data)
                new_id = result.scalar()

            await _audit_log(
                context, "create", table_name, new_id, data, success=True,
            )

            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=json.dumps({
                    "action": "create",
                    "table": table_name,
                    "id": new_id,
                    "success": True,
                }, ensure_ascii=False, default=str),
            )
        except Exception as exc:
            await _audit_log(
                context, "create", table_name, None, data,
                success=False, error=str(exc),
            )
            error_msg = str(exc)
            if "NotNullViolationError" in type(exc).__name__ or "not-null constraint" in error_msg:
                col_match = re.search(r'column "(\w+)"', error_msg)
                col_name = col_match.group(1) if col_match else "unknown"
                error_msg = (
                    f"Missing required field '{col_name}' for table '{table_name}'. "
                    f"Please include '{col_name}' in the data parameter."
                )
            else:
                error_msg = build_public_error_text(
                    message="Create record failed",
                    exc=exc,
                )
            return ToolResult.error_result(
                tool_call_id, error_msg, name=_name,
            )


# ============================================ / 上文为英文说明 / English above
# UpdateRecordExecutor
# ============================================

class UpdateRecordExecutor(BaseToolExecutor):
    """
    Generic record update executor.
    通用记录更新执行器。

    LLM call arguments / LLM 调用参数: {table_name, id, data: {field: value, ...}, confirmed?: bool}
    """

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        _ = definition
        return bool(
            arguments.get("table_name")
            and arguments.get("id")
            and arguments.get("data")
        )

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        _name = definition.name
        if not context or not context.db:
            return ToolResult.error_result(
                tool_call_id, _("data_intelligence.crud.no_context"), name=_name,
            )

        table_name = arguments["table_name"]
        record_id = arguments["id"]
        data = arguments.get("data", {})
        confirmed = arguments.get("confirmed", False)

        # Table name safety validation / 表名安全校验
        table_err = _validate_table_name(table_name)
        if table_err:
            return ToolResult.error_result(tool_call_id, table_err, name=_name)

        # Load policy / 加载策略
        policy = await _load_policy(context, table_name)
        if not policy:
            return ToolResult.error_result(
                tool_call_id,
                _("data_intelligence.crud.table_not_found").format(table=table_name),
                name=_name,
            )

        if not policy.allow_update:
            return ToolResult.error_result(
                tool_call_id,
                _("data_intelligence.crud.operation_denied").format(
                    operation="update", table=table_name,
                ) + _("data_intelligence.crud.no_retry_hint").format(operation="update"),
                name=_name,
            )

        # RBAC: check if user has update permission / 检查用户是否有 update 权限
        rbac_error = _check_rbac(context, policy, "update")
        if rbac_error:
            return ToolResult.error_result(tool_call_id, rbac_error, name=_name)

        # Tenant isolation column check: non-platform users forbidden from tables without tenant_id
        # 企业隔离列检查：非平台用户禁止操作无 tenant_id 列的表
        tc_err = await _check_tenant_column(context, table_name)
        if tc_err:
            return ToolResult.error_result(tool_call_id, tc_err, name=_name)

        # Strip system-managed columns / 剥离系统管理列
        _strip_system_columns(data)

        # Column name safety validation (prevent SQL injection)
        # 列名安全校验（防 SQL 注入）
        col_err = _validate_column_names(data)
        if col_err:
            return ToolResult.error_result(tool_call_id, col_err, name=_name)

        # Validate write data / 校验写入数据
        blocked = _get_blocked_columns(policy)
        violation = _validate_write_data(data, blocked)
        if violation:
            return ToolResult.error_result(tool_call_id, violation, name=_name)

        # Force tenant isolation (inject from context, never trust LLM input)
        # 强制企业隔离（从 context 注入，不信任 LLM 输入）
        _enforce_tenant_isolation(context, policy, data)

        # Query current record for diff preview / 查询当前记录用于 diff 预览
        try:
            tenant_filter = ""
            params: dict[str, Any] = {"record_id": record_id}
            if context.tenant_id:
                tenant_filter = " AND tenant_id = :tenant_id"
                params["tenant_id"] = context.tenant_id

            current_sql = text(
                f"SELECT * FROM {table_name} WHERE id = :record_id"
                f" AND is_deleted = false{tenant_filter} LIMIT 1"
            )
            result = await context.db.execute(current_sql, params)
            current_row = result.mappings().first()
        except Exception:
            current_row = None

        if not current_row:
            return ToolResult.error_result(
                tool_call_id,
                _("data_intelligence.crud.record_not_found").format(
                    table=table_name, id=record_id,
                ),
                name=_name,
            )

        # Confirmation flow / 确认流程
        if not confirmed:
            # Build diff preview / 构建 diff 预览
            diff = {}
            for key, new_val in data.items():
                old_val = current_row.get(key)
                diff[key] = {"old": old_val, "new": new_val}

            preview = {
                "action": "update",
                "table": table_name,
                "id": record_id,
                "diff": diff,
                "requires_confirmation": True,
            }
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=json.dumps(preview, ensure_ascii=False, default=str),
            )

        # Serialize JSON values (dict/list -> JSON strings, for asyncpg binding)
        # 序列化 JSON 值（dict/list → JSON 字符串，供 asyncpg 绑定）
        _serialize_for_sql(data)

        # Execute update (using savepoint isolation, doesn't affect outer transaction)
        # 执行更新（使用 savepoint 隔离，不影响外层事务）
        try:
            async with context.db.begin_nested():
                set_clauses = ", ".join(f"{k} = :{k}" for k in data)
                set_clauses += ", updated_at = NOW()"
                params = {**data, "record_id": record_id}
                where = "id = :record_id AND is_deleted = false"
                if context.tenant_id:
                    where += " AND tenant_id = :tenant_id"
                    params["tenant_id"] = context.tenant_id

                raw_sql = text(
                    f"UPDATE {table_name} SET {set_clauses} WHERE {where}"
                )
                await context.db.execute(raw_sql, params)

            await _audit_log(
                context, "update", table_name, record_id, data, success=True,
            )

            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=json.dumps({
                    "action": "update",
                    "table": table_name,
                    "id": record_id,
                    "success": True,
                }, ensure_ascii=False, default=str),
            )
        except Exception as exc:
            await _audit_log(
                context, "update", table_name, record_id, data,
                success=False, error=str(exc),
            )
            return ToolResult.error_result(
                tool_call_id,
                build_public_error_text(
                    message="Update record failed",
                    exc=exc,
                ),
                name=_name,
            )


# ============================================ / 上文为英文说明 / English above
# DeleteRecordExecutor
# ============================================

class DeleteRecordExecutor(BaseToolExecutor):
    """
    Generic record deletion executor (soft delete only).
    通用记录删除执行器（仅软删除）。

    LLM call arguments / LLM 调用参数: {table_name, id, confirmed?: bool}
    """

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        _ = definition
        return bool(arguments.get("table_name") and arguments.get("id"))

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        _name = definition.name
        if not context or not context.db:
            return ToolResult.error_result(
                tool_call_id, _("data_intelligence.crud.no_context"), name=_name,
            )

        table_name = arguments["table_name"]
        record_id = arguments["id"]
        confirmed = arguments.get("confirmed", False)

        # Table name safety validation / 表名安全校验
        table_err = _validate_table_name(table_name)
        if table_err:
            return ToolResult.error_result(tool_call_id, table_err, name=_name)

        # Load policy / 加载策略
        policy = await _load_policy(context, table_name)
        if not policy:
            return ToolResult.error_result(
                tool_call_id,
                _("data_intelligence.crud.table_not_found").format(table=table_name),
                name=_name,
            )

        if not policy.allow_delete:
            return ToolResult.error_result(
                tool_call_id,
                _("data_intelligence.crud.operation_denied").format(
                    operation="delete", table=table_name,
                ) + _("data_intelligence.crud.no_retry_hint").format(operation="delete"),
                name=_name,
            )

        # RBAC: check if user has delete permission / 检查用户是否有 delete 权限
        rbac_error = _check_rbac(context, policy, "delete")
        if rbac_error:
            return ToolResult.error_result(tool_call_id, rbac_error, name=_name)

        # Tenant isolation column check: non-platform users forbidden from tables without tenant_id
        # 企业隔离列检查：非平台用户禁止操作无 tenant_id 列的表
        tc_err = await _check_tenant_column(context, table_name)
        if tc_err:
            return ToolResult.error_result(tool_call_id, tc_err, name=_name)

        # Query record details for confirmation preview / 查询记录详情用于确认预览
        try:
            tenant_filter = ""
            params: dict[str, Any] = {"record_id": record_id}
            if context.tenant_id:
                tenant_filter = " AND tenant_id = :tenant_id"
                params["tenant_id"] = context.tenant_id

            # Only query non-blocked columns / 只查询非屏蔽列
            blocked = _get_blocked_columns(policy)
            current_sql = text(
                f"SELECT * FROM {table_name} WHERE id = :record_id"
                f" AND is_deleted = false{tenant_filter} LIMIT 1"
            )
            result = await context.db.execute(current_sql, params)
            current_row = result.mappings().first()
        except Exception:
            current_row = None

        if not current_row:
            return ToolResult.error_result(
                tool_call_id,
                _("data_intelligence.crud.record_not_found").format(
                    table=table_name, id=record_id,
                ),
                name=_name,
            )

        # Confirmation flow (delete always requires confirmation)
        # 确认流程（删除始终需要确认）
        if not confirmed:
            # Filter out sensitive columns before display / 过滤敏感列后展示
            safe_data = {
                k: v for k, v in dict(current_row).items()
                if k not in blocked
            }
            preview = {
                "action": "delete",
                "table": table_name,
                "id": record_id,
                "record": safe_data,
                "requires_confirmation": True,
                "warning": _("data_intelligence.crud.soft_delete_warning"),
            }
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=json.dumps(preview, ensure_ascii=False, default=str),
            )

        # Execute soft delete (using savepoint isolation, doesn't affect outer transaction)
        # 执行软删除（使用 savepoint 隔离，不影响外层事务）
        try:
            async with context.db.begin_nested():
                params = {"record_id": record_id}
                where = "id = :record_id AND is_deleted = false"
                if context.tenant_id:
                    where += " AND tenant_id = :tenant_id"
                    params["tenant_id"] = context.tenant_id

                raw_sql = text(
                    f"UPDATE {table_name} SET is_deleted = true, "
                    f"deleted_at = NOW() WHERE {where}"
                )
                await context.db.execute(raw_sql, params)

            await _audit_log(
                context, "delete", table_name, record_id, None, success=True,
            )

            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=json.dumps({
                    "action": "delete",
                    "table": table_name,
                    "id": record_id,
                    "success": True,
                    "soft_deleted": True,
                }, ensure_ascii=False, default=str),
            )
        except Exception as exc:
            await _audit_log(
                context, "delete", table_name, record_id, None,
                success=False, error=str(exc),
            )
            return ToolResult.error_result(
                tool_call_id,
                build_public_error_text(
                    message="Delete record failed",
                    exc=exc,
                ),
                name=_name,
            )


__all__ = [
    "CreateRecordExecutor",
    "UpdateRecordExecutor",
    "DeleteRecordExecutor",
]
