"""
Internal Ops Meta-Tool Definitions / 内部操作元工具定义

Defines the three meta-tools exposed to copilot agents. Keeping schemas in
code (instead of DB JSON) lets them evolve without data migrations.
定义暴露给 Copilot 智能体的三个元工具。Schema 放在代码中（而非 DB JSON），
后续演进无需数据迁移。
"""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition, ToolParameter
from app.enums.agent import ToolTypeEnum

# Stable tool names / 稳定工具名
TOOL_LIST_OPERATIONS = "list_internal_operations"
TOOL_DESCRIBE_OPERATION = "describe_internal_operation"
TOOL_INVOKE_OPERATION = "invoke_internal_operation"

INTERNAL_OPS_BUILTIN_TYPE = "internal_ops"

# Semantic family for intent routing / 意图路由所用语义家族
INTERNAL_OPS_SEMANTIC_FAMILY = "internal_ops"

# Discovery vocabulary matched against user queries by the intent planner.
# Only copilot agents hold these tools, so a broad vocabulary is intentional.
# 意图规划器用该词表与用户提问做匹配；仅 Copilot 智能体持有这些工具，
# 因此刻意使用宽泛词表。
INTERNAL_OPS_SEMANTIC_TAGS: list[str] = [
    "后台管理",
    "平台管理",
    "运营管理",
    "后台操作",
    "系统管理",
    "租户管理",
    "企业管理",
    "企业租户",
    "套餐订阅",
    "用户管理",
    "成员管理",
    "组织架构",
    "部门管理",
    "角色权限",
    "权限管理",
    "系统配置",
    "平台设置",
    "操作日志",
    "审计日志",
    "智能体管理",
    "模型管理",
    "知识库管理",
    "插件管理",
    "公告通知",
    "统计报表",
    "新建创建",
    "修改更新",
    "删除停用",
    "启用禁用",
    "admin console",
    "backoffice",
    "tenant management",
    "user management",
    "role permission",
    "plan subscription",
    "system config",
    "operation log",
]


def build_internal_ops_tool_definitions(
    *,
    skill: Any | None = None,
    config: dict[str, Any] | None = None,
) -> list[ToolDefinition]:
    """Build the three meta-tool definitions / 构建三个元工具定义"""
    base_config = dict(config or {})
    base_config["builtin_type"] = INTERNAL_OPS_BUILTIN_TYPE

    common: dict[str, Any] = {
        "tool_type": ToolTypeEnum.INTERNAL_API.value,
        "config": base_config,
        "enabled": True,
        "source_skill_id": getattr(skill, "id", None),
        "source_skill_name": getattr(skill, "name", None) or "internal_operations",
        "source_skill_type": getattr(skill, "type", None) or "builtin",
        "semantic_family": INTERNAL_OPS_SEMANTIC_FAMILY,
        "semantic_tags": list(INTERNAL_OPS_SEMANTIC_TAGS),
    }

    list_tool = ToolDefinition(
        name=TOOL_LIST_OPERATIONS,
        description=(
            "Search the management-console operation catalog available to the "
            "current user. Every backend operation (query/create/update/delete "
            "for tenants, users, roles, plans, agents, plugins, configs, logs, "
            "etc.) is listed here. Always call this first to discover the "
            "operation you need; then call describe_internal_operation before "
            "invoking. Supports keyword search (matches path, module, summary) "
            "and module/method filters."
        ),
        parameters=[
            ToolParameter(
                name="keyword",
                type="string",
                description=(
                    "Space-separated keywords matched against path, module, "
                    "summary and permission code, e.g. 'tenant list' or '套餐'."
                ),
                required=False,
            ),
            ToolParameter(
                name="module",
                type="string",
                description="Exact module (RBAC resource) filter, e.g. 'tenant'.",
                required=False,
            ),
            ToolParameter(
                name="method",
                type="string",
                description="HTTP method filter.",
                required=False,
                enum=["GET", "POST", "PUT", "PATCH", "DELETE"],
            ),
            ToolParameter(
                name="offset",
                type="integer",
                description="Pagination offset, default 0.",
                required=False,
            ),
        ],
        timeout=15,
        **common,
    )

    describe_tool = ToolDefinition(
        name=TOOL_DESCRIBE_OPERATION,
        description=(
            "Get the full parameter specification of one internal operation: "
            "path params, query params and request-body JSON schema. Always "
            "call this before invoke_internal_operation so the arguments you "
            "build match the schema exactly."
        ),
        parameters=[
            ToolParameter(
                name="operation_id",
                type="string",
                description=(
                    "Operation id from list_internal_operations, "
                    "e.g. 'GET:/admin/tenants'."
                ),
                required=True,
            ),
        ],
        timeout=15,
        **common,
    )

    invoke_tool = ToolDefinition(
        name=TOOL_INVOKE_OPERATION,
        description=(
            "Invoke one internal operation on behalf of the current user. "
            "GET operations execute immediately. Write operations (POST/PUT/"
            "PATCH/DELETE) first return a confirmation preview that the user "
            "must approve in the UI before the call is executed — never claim "
            "a write succeeded until the confirmed invocation returns. The "
            "call runs with the current user's own permissions; a 403 means "
            "the user lacks that permission."
        ),
        parameters=[
            ToolParameter(
                name="operation_id",
                type="string",
                description="Operation id, e.g. 'POST:/admin/tenants'.",
                required=True,
            ),
            ToolParameter(
                name="path_params",
                type="object",
                description=(
                    "Values for {placeholders} in the path, "
                    "e.g. {\"tenant_id\": 3}."
                ),
                required=False,
            ),
            ToolParameter(
                name="query_params",
                type="object",
                description="Query string parameters as a flat object.",
                required=False,
            ),
            ToolParameter(
                name="body",
                type="object",
                description=(
                    "JSON request body matching the schema returned by "
                    "describe_internal_operation."
                ),
                required=False,
            ),
            ToolParameter(
                name="confirmed",
                type="boolean",
                description=(
                    "Top-level flag (never inside body). Set true ONLY when "
                    "replaying a write operation after the user explicitly "
                    "approved its confirmation preview; keep all other "
                    "arguments identical to the previewed call."
                ),
                required=False,
            ),
        ],
        timeout=60,
        **common,
    )

    return [list_tool, describe_tool, invoke_tool]


__all__ = [
    "INTERNAL_OPS_BUILTIN_TYPE",
    "TOOL_DESCRIBE_OPERATION",
    "TOOL_INVOKE_OPERATION",
    "TOOL_LIST_OPERATIONS",
    "build_internal_ops_tool_definitions",
]
