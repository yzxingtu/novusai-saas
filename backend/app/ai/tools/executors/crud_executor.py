"""
通用 CRUD 执行器

基于 ai_table_policies 动态执行 create/update/delete 操作。
所有写操作采用两步确认流程：
  Step 1: 返回预览 JSON（requires_confirmation=true）
  Step 2: LLM 重新调用并带 confirmed=true，执行实际操作

安全策略：
- 基于 ai_table_policies 检查 CRUD 权限
- blocked_columns / readonly_columns 不允许写入
- 租户隔离：tenant-scoped 表自动注入 tenant_id
- 仅软删除（set is_deleted=True），不允许硬删除
- 所有操作审计到 ai_action_logs
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from sqlalchemy import text, update

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.i18n import _
from app.core.logging import LogManager
from app.models.ai.table_policy import AITablePolicy

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.crud")

# 表名白名单正则：仅允许小写字母、数字、下划线（防 SQL 注入）
_SAFE_TABLE_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
# 列名白名单正则：与表名规则一致（防 SQL 注入）
_SAFE_COLUMN_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def _validate_table_name(table_name: str) -> str | None:
    """校验表名是否安全，返回错误消息或 None"""
    if not _SAFE_TABLE_NAME_RE.match(table_name):
        return _("data_intelligence.crud.invalid_table_name").format(table=table_name)
    return None


def _validate_column_names(data: dict[str, Any]) -> str | None:
    """校验所有列名是否安全，返回错误消息或 None

    防止 LLM 传入恶意列名导致 SQL 注入。
    列名仅允许小写字母、数字和下划线，且必须以字母或下划线开头。
    """
    invalid = [k for k in data.keys() if not _SAFE_COLUMN_NAME_RE.match(k)]
    if invalid:
        return _("data_intelligence.crud.invalid_column_names").format(
            columns=", ".join(sorted(invalid)),
        )
    return None


# 全局安全：永远不允许写入的列
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
    """从数据库加载表策略（含租户覆盖合并）

    加载全局策略后，查找对应的租户覆盖并合并。
    覆盖只能收紧，不能放开。合并后的值直接写入策略对象属性。
    """
    if not context.db:
        return None
    from app.repositories.ai.table_policy_repository import AITablePolicyRepository
    policy_repo = AITablePolicyRepository(context.db)
    policy = await policy_repo.get_active_by_table_name(table_name)
    if not policy:
        return None

    # 加载租户覆盖并合并（收紧规则）
    if context.tenant_id:
        from app.repositories.ai.table_policy_override_repository import AITablePolicyOverrideRepository
        override_repo = AITablePolicyOverrideRepository(context.db)
        ov = await override_repo.get_by_policy_and_tenant(policy.id, context.tenant_id)
        if ov:
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
            # max_rows 只能更小
            if ov.max_rows is not None and ov.max_rows < policy.max_rows:
                policy.max_rows = ov.max_rows
            # blocked_columns 只能追加
            if ov.blocked_columns:
                existing = set(policy.blocked_columns or [])
                existing.update(ov.blocked_columns)
                policy.blocked_columns = list(existing)

    # 合并后如果被禁用则视为不存在
    if not policy.is_active:
        return None

    return policy


def _get_blocked_columns(policy: AITablePolicy) -> set[str]:
    """获取禁止写入的列集合"""
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
    """校验写入数据中是否包含禁止写入的列，返回错误消息或 None"""
    violations = set(data.keys()) & blocked
    if violations:
        return _("data_intelligence.crud.blocked_columns_violation").format(
            columns=", ".join(sorted(violations)),
        )
    return None


def _derive_permission(permission_code: str, action: str) -> str | None:
    """从策略的 permission_code 推导写操作所需的权限码

    例如: 'agent:read' + 'create' -> 'agent:create'
          '*' -> None（不需要额外权限）
          'platform_only' -> 'platform_only'（仅平台管理员）
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
    """检查用户 RBAC 权限，返回错误消息或 None

    CRUD 开关（allow_create/update/delete）已在调用方检查过，
    此处只做用户身份 + 权限码校验。

    Args:
        context: 执行上下文
        policy: 表策略
        action: 操作类型 (create/update/delete/read)
    """
    perm_code = policy.permission_code or "*"

    # platform_only: 仅平台管理员
    if perm_code == "platform_only":
        if not context.is_platform_admin:
            return _("data_intelligence.crud.permission_denied").format(
                action=action, table=policy.table_name,
            )
        return None

    # '*' 权限码: 任何登录用户可执行
    if perm_code == "*":
        return None

    # 平台管理员跳过权限码推导检查（他们有所有 RBAC 权限）
    if context.is_platform_admin:
        return None

    # 推导所需权限码并检查
    required = _derive_permission(perm_code, action)
    if required and context.permissions and required not in context.permissions:
        return _("data_intelligence.crud.permission_denied").format(
            action=action, table=policy.table_name,
        )

    return None


async def _check_tenant_column(
    context: ExecutionContext,
    table_name: str,
) -> str | None:
    """检查表是否有 tenant_id 列，非平台用户禁止操作无隔离列的表

    返回错误消息或 None（通过）。
    平台管理员可操作任何表（含无 tenant_id 的平台级表）。
    """
    if context.is_platform_admin:
        return None

    if not context.db:
        return None

    # 查询目标表是否存在 tenant_id 列
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
    """强制注入 tenant_id 到写入数据（从上下文获取，永不信任 LLM 输入）"""
    if context.tenant_id:
        data["tenant_id"] = context.tenant_id
    elif "tenant_id" in data:
        # 平台管理员无需 tenant_id，移除 LLM 可能传入的值
        data.pop("tenant_id", None)


# 系统管理列：LLM 传入时静默剥离，由系统自动注入
_SYSTEM_MANAGED_COLUMNS: set[str] = {
    "tenant_id", "is_deleted", "deleted_at", "delete_level",
    "created_at", "updated_at",
}


def _strip_system_columns(data: dict[str, Any]) -> None:
    """剥离 LLM 可能传入的所有系统管理列（静默删除，不报错）

    这些列由系统自动注入（如 tenant_id、is_deleted），
    或由数据库/raw SQL 自动处理（如 created_at、updated_at）。
    在验证之前调用，避免触发 blocked_columns 校验失败。
    """
    for col in _SYSTEM_MANAGED_COLUMNS:
        data.pop(col, None)


def _serialize_for_sql(data: dict[str, Any]) -> None:
    """将 dict/list 值序列化为 JSON 字符串，供 asyncpg raw SQL 绑定

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
    """写入 AI 操作审计日志"""
    if not context.db:
        return
    try:
        from app.models.ai.action_log import AIActionLog
        log = AIActionLog(
            tenant_id=context.tenant_id,
            agent_id=context.agent_id,
            user_id=context.user_id,
            skill_id=context.skill_id,
            action_name=f"data_{action}",
            action_type=action,
            target_table=table_name,
            target_id=record_id,
            input_data=data or {},
            status="success" if success else "failed",
            error_message=error,
        )
        context.db.add(log)
    except Exception as exc:
        logger.warning("Failed to write audit log: %s", str(exc))


# ============================================
# CreateRecordExecutor
# ============================================

class CreateRecordExecutor(BaseToolExecutor):
    """
    通用记录创建执行器

    LLM 调用参数: {table_name, data: {field: value, ...}, confirmed?: bool}
    """

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
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

        # 表名安全校验
        table_err = _validate_table_name(table_name)
        if table_err:
            return ToolResult.error_result(tool_call_id, table_err, name=_name)

        # 加载策略
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

        # RBAC: 检查用户是否有 create 权限
        rbac_error = _check_rbac(context, policy, "create")
        if rbac_error:
            return ToolResult.error_result(tool_call_id, rbac_error, name=_name)

        # 租户隔离列检查：非平台用户禁止操作无 tenant_id 列的表
        tc_err = await _check_tenant_column(context, table_name)
        if tc_err:
            return ToolResult.error_result(tool_call_id, tc_err, name=_name)

        # 剥离系统管理列（tenant_id/is_deleted 等，由系统注入）
        _strip_system_columns(data)

        # 列名安全校验（防 SQL 注入）
        col_err = _validate_column_names(data)
        if col_err:
            return ToolResult.error_result(tool_call_id, col_err, name=_name)

        # 校验写入数据
        blocked = _get_blocked_columns(policy)
        violation = _validate_write_data(data, blocked)
        if violation:
            return ToolResult.error_result(tool_call_id, violation, name=_name)

        # 注入系统默认值（验证后，确保 raw SQL 不缺少 NOT NULL 列）
        _enforce_tenant_isolation(context, policy, data)
        data["is_deleted"] = False

        # 确认流程
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

        # 序列化 JSON 值（dict/list → JSON 字符串，供 asyncpg 绑定）
        _serialize_for_sql(data)

        # 执行创建（使用 savepoint 隔离，不影响外层事务）
        try:
            async with context.db.begin_nested():
                all_columns = list(data.keys()) + ["created_at", "updated_at"]
                all_placeholders = [f":{k}" for k in data.keys()] + ["NOW()", "NOW()"]
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
            return ToolResult.error_result(
                tool_call_id, str(exc), name=_name,
            )


# ============================================
# UpdateRecordExecutor
# ============================================

class UpdateRecordExecutor(BaseToolExecutor):
    """
    通用记录更新执行器

    LLM 调用参数: {table_name, id, data: {field: value, ...}, confirmed?: bool}
    """

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
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

        # 表名安全校验
        table_err = _validate_table_name(table_name)
        if table_err:
            return ToolResult.error_result(tool_call_id, table_err, name=_name)

        # 加载策略
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

        # RBAC: 检查用户是否有 update 权限
        rbac_error = _check_rbac(context, policy, "update")
        if rbac_error:
            return ToolResult.error_result(tool_call_id, rbac_error, name=_name)

        # 租户隔离列检查：非平台用户禁止操作无 tenant_id 列的表
        tc_err = await _check_tenant_column(context, table_name)
        if tc_err:
            return ToolResult.error_result(tool_call_id, tc_err, name=_name)

        # 剥离系统管理列
        _strip_system_columns(data)

        # 列名安全校验（防 SQL 注入）
        col_err = _validate_column_names(data)
        if col_err:
            return ToolResult.error_result(tool_call_id, col_err, name=_name)

        # 校验写入数据
        blocked = _get_blocked_columns(policy)
        violation = _validate_write_data(data, blocked)
        if violation:
            return ToolResult.error_result(tool_call_id, violation, name=_name)

        # 强制租户隔离（从 context 注入，不信任 LLM 输入）
        _enforce_tenant_isolation(context, policy, data)

        # 查询当前记录用于 diff 预览
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

        # 确认流程
        if not confirmed:
            # 构建 diff 预览
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

        # 序列化 JSON 值（dict/list → JSON 字符串，供 asyncpg 绑定）
        _serialize_for_sql(data)

        # 执行更新（使用 savepoint 隔离，不影响外层事务）
        try:
            async with context.db.begin_nested():
                set_clauses = ", ".join(f"{k} = :{k}" for k in data.keys())
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
                tool_call_id, str(exc), name=_name,
            )


# ============================================
# DeleteRecordExecutor
# ============================================

class DeleteRecordExecutor(BaseToolExecutor):
    """
    通用记录删除执行器（仅软删除）

    LLM 调用参数: {table_name, id, confirmed?: bool}
    """

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
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

        # 表名安全校验
        table_err = _validate_table_name(table_name)
        if table_err:
            return ToolResult.error_result(tool_call_id, table_err, name=_name)

        # 加载策略
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

        # RBAC: 检查用户是否有 delete 权限
        rbac_error = _check_rbac(context, policy, "delete")
        if rbac_error:
            return ToolResult.error_result(tool_call_id, rbac_error, name=_name)

        # 租户隔离列检查：非平台用户禁止操作无 tenant_id 列的表
        tc_err = await _check_tenant_column(context, table_name)
        if tc_err:
            return ToolResult.error_result(tool_call_id, tc_err, name=_name)

        # 查询记录详情用于确认预览
        try:
            tenant_filter = ""
            params: dict[str, Any] = {"record_id": record_id}
            if context.tenant_id:
                tenant_filter = " AND tenant_id = :tenant_id"
                params["tenant_id"] = context.tenant_id

            # 只查询非屏蔽列
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

        # 确认流程（删除始终需要确认）
        if not confirmed:
            # 过滤敏感列后展示
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
                tool_call_id, str(exc), name=_name,
            )


__all__ = [
    "CreateRecordExecutor",
    "UpdateRecordExecutor",
    "DeleteRecordExecutor",
]
