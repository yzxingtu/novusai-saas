"""
工具类型定义

定义工具参数、工具定义、工具执行结果等数据类
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.common import UserRoleEnum

# JSON 兼容的标量值类型（用于工具参数默认值等场景）
JsonScalar = str | int | float | bool | None
# JSON 兼容的值类型（含嵌套）
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass
class ToolParameter:
    """
    工具参数定义

    描述工具函数的单个参数

    Attributes:
        name: 参数名
        type: 参数类型 (string/integer/number/boolean/array/object)
        description: 参数描述
        required: 是否必填
        default: 默认值
        enum: 可选值列表
    """

    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default: JsonScalar = None
    enum: list[str] | None = None

    def to_json_schema(self) -> dict[str, Any]:
        """转换为 JSON Schema 属性"""
        schema: dict[str, Any] = {
            "type": self.type,
            "description": self.description,
        }
        if self.enum is not None:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        return schema


@dataclass
class ToolDefinition:
    """
    工具定义

    描述一个可被智能体调用的工具

    Attributes:
        name: 工具唯一标识
        description: 工具功能描述（会传给 LLM）
        tool_type: 工具类型（对应 ToolTypeEnum）
        parameters: 参数列表
        config: 工具特有配置（如 HTTP 的 url/method/headers）
        enabled: 是否启用
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

    @property
    def input_schema(self) -> dict[str, Any]:
        """构建 JSON Schema（从 parameters 列表）"""
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
        转换为 OpenAI function calling 格式

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
    工具执行结果

    Attributes:
        tool_call_id: LLM 返回的 tool_call_id
        name: 工具名称
        success: 是否执行成功
        output: 输出内容（字符串）
        error: 错误信息
        duration_ms: 执行耗时（毫秒）
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

    @classmethod
    def error_result(
        cls,
        tool_call_id: str,
        error: str,
        name: str = "",
    ) -> ToolResult:
        """快捷构造错误结果"""
        return cls(
            tool_call_id=tool_call_id,
            name=name,
            success=False,
            error=error,
        )

    def to_message(self) -> dict[str, Any]:
        """
        转换为 OpenAI tool message 格式

        Returns:
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
    工具执行上下文

    封装当前执行环境的租户、用户、权限等信息，
    供 TextToSQLExecutor / CRUD Executor 等执行器使用。

    Attributes:
        tenant_id: 租户 ID
        agent_id: 智能体 ID
        user_id: 当前操作用户 ID（可为 None 表示匿名 / API 调用）
        user_role: 用户角色（platform_admin / tenant_admin / tenant_user）
        permissions: 用户权限码集合（用于 RBAC 校验）
        db: 异步数据库会话（可选，供需要 DB 访问的执行器使用）
    """

    tenant_id: int
    agent_id: int
    user_id: int | None = None
    user_role: str = UserRoleEnum.TENANT_ADMIN.value
    permissions: set[str] = field(default_factory=set)
    db: AsyncSession | None = None
    consented_actions: set[str] = field(default_factory=set)  # "read:agents", "create:agents"
    skill_id: int | None = None

    @property
    def is_platform_admin(self) -> bool:
        return self.user_role == UserRoleEnum.PLATFORM_ADMIN.value

    @property
    def is_superadmin(self) -> bool:
        return "*" in self.permissions


def to_openai_tools(definitions: list[ToolDefinition]) -> list[dict[str, Any]]:
    """
    批量转换为 OpenAI function calling 格式

    Args:
        definitions: 工具定义列表

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
