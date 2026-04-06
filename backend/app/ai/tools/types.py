"""
Tool Type Definitions. / 工具类型定义。

Defines data classes for tool parameters, tool definitions, and tool execution results.
定义工具参数、工具定义、工具执行结果等数据类。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.common import UserRoleEnum

# JSON-compatible scalar value type (for tool parameter defaults, etc.) / JSON 兼容的标量值类型
JsonScalar = str | int | float | bool | None
# JSON-compatible value type (with nesting) / JSON 兼容的值类型（含嵌套）
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass
class ToolParameter:
    """
    Tool Parameter Definition / 工具参数定义

    Describes a single parameter of a tool function.
    描述工具函数的单个参数。

    Attributes:
        name: Parameter name / 参数名
        type: Parameter type (string/integer/number/boolean/array/object) / 参数类型
        description: Parameter description / 参数描述
        required: Whether required / 是否必填
        default: Default value / 默认值
        enum: Enum value list / 可选值列表
        items: Array item schema when type=array / type=array 时的数组元素 schema
    """

    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default: JsonValue = None
    enum: list[str] | None = None
    items: dict[str, Any] | None = None

    def to_json_schema(self) -> dict[str, Any]:
        """Convert to JSON Schema property / 转换为 JSON Schema 属性"""
        schema: dict[str, Any] = {
            "type": self.type,
            "description": self.description,
        }
        if self.enum is not None:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        if self.items is not None:
            schema["items"] = self.items
        return schema


@dataclass
class ToolDefinition:
    """
    Tool Definition / 工具定义

    Describes a tool that can be invoked by an agent.
    描述一个可被智能体调用的工具。

    Attributes:
        name: Tool unique identifier / 工具唯一标识
        description: Tool function description (passed to LLM) / 工具功能描述
        tool_type: Tool type (corresponds to ToolTypeEnum) / 工具类型
        parameters: Parameter list / 参数列表
        config: Tool-specific config (e.g. HTTP url/method/headers) / 工具特有配置
        enabled: Whether enabled / 是否启用
    """

    name: str
    description: str = ""
    tool_type: str = "builtin"
    parameters: list[ToolParameter] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    timeout: int = 30
    source_skill_id: int | None = None
    source_skill_name: str | None = None
    source_skill_type: str | None = None
    source_package_name: str | None = None
    source_plugin: str | None = None
    semantic_family: str | None = None
    semantic_tags: list[str] = field(default_factory=list)

    @property
    def input_schema(self) -> dict[str, Any]:
        """Build JSON Schema (from parameters list) / 构建 JSON Schema"""
        properties: dict[str, Any] = {}
        required: list[str] = []
        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)
        schema: dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        return schema

    def to_openai_schema(self) -> dict[str, Any]:
        """
        Convert to OpenAI function calling format / 转换为 OpenAI function calling 格式

        Returns:
            OpenAI tool schema dict
        """
        properties: dict[str, Any] = {}
        required: list[str] = []

        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)

        schema: dict[str, Any] = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                },
            },
        }

        if required:
            schema["function"]["parameters"]["required"] = required

        return schema


@dataclass
class ToolResult:
    """
    Tool Execution Result / 工具执行结果

    Attributes:
        tool_call_id: tool_call_id returned by LLM / LLM 返回的 tool_call_id
        name: Tool name / 工具名称
        success: Whether execution succeeded / 是否执行成功
        output: Output content (string) / 输出内容
        error: Error message / 错误信息
        duration_ms: Execution duration (milliseconds) / 执行耗时
        error_type: Error type for classification (timeout, user_cancelled, etc.) / 错误分类
    """

    tool_call_id: str
    name: str
    success: bool = True
    output: str = ""
    error: str = ""
    duration_ms: int = 0
    display_name: str | None = None
    summary: str | None = None
    result_link: str | None = None
    error_type: str = ""
    attachments: list[dict[str, Any]] | None = None
    summary_payload: dict[str, Any] | None = None

    @classmethod
    def error_result(
        cls,
        tool_call_id: str,
        error: str,
        name: str = "",
    ) -> ToolResult:
        """Shortcut to construct error result / 快捷构造错误结果"""
        return cls(
            tool_call_id=tool_call_id,
            name=name,
            success=False,
            error=error,
        )

    def to_message(self) -> dict[str, Any]:
        """
        Convert to OpenAI tool message format / 转换为 OpenAI tool message 格式

        Returns:
            Dict that can be appended directly to messages list
            可直接追加到 messages 列表的 dict
        """
        content = self.output if self.success else f"Error: {self.error}"
        return {
            "role": "tool",
            "tool_call_id": self.tool_call_id,
            "content": content,
        }


@dataclass
class ExecutionContext:
    """
    Tool Execution Context / 工具执行上下文

    Encapsulates tenant, user, permission info of the current execution environment,
    used by TextToSQLExecutor / CRUD Executor and other executors.
    封装当前执行环境的企业、用户、权限等信息。

    Attributes:
        tenant_id: Tenant ID / 企业 ID
        agent_id: Agent ID / 智能体 ID
        user_id: Current user ID (None for anonymous/API calls) / 当前操作用户 ID
        user_role: User role (platform_admin / tenant_admin / tenant_user) / 用户角色
        permissions: User permission code set (for RBAC validation) / 用户权限码集合
        db: Async database session (optional) / 异步数据库会话
    """

    tenant_id: int
    agent_id: int
    user_id: int | None = None
    user_role: str = UserRoleEnum.TENANT_ADMIN.value
    permissions: set[str] = field(default_factory=set)
    db: AsyncSession | None = None
    consented_actions: set[str] = field(
        default_factory=set
    )  # "read:agents", "create:agents" / 示例：已同意的 action 权限串
    trust_policy_ref: dict[str, Any] | None = None
    skill_id: int | None = None
    variables: dict[str, Any] = field(default_factory=dict)
    page_session_id: str | None = None
    conversation_id: int | None = None
    interaction_mode: str = "confirm"
    runtime_provider_id: int | None = None
    runtime_provider_name: str | None = None
    runtime_model_id: int | None = None
    runtime_model_name: str | None = None
    runtime_model_code: str | None = None

    @property
    def is_platform_admin(self) -> bool:
        return self.user_role == UserRoleEnum.PLATFORM_ADMIN.value

    @property
    def is_superadmin(self) -> bool:
        return "*" in self.permissions


def to_openai_tools(definitions: list[ToolDefinition]) -> list[dict[str, Any]]:
    """
    Batch convert to OpenAI function calling format / 批量转换为 OpenAI function calling 格式

    Args:
        definitions: Tool definition list / 工具定义列表

    Returns:
        OpenAI tools schema list
    """
    return [d.to_openai_schema() for d in definitions if d.enabled]


__all__ = [
    "ToolParameter",
    "ToolDefinition",
    "ToolResult",
    "ExecutionContext",
    "to_openai_tools",
]
