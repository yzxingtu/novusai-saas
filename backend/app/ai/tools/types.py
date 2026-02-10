"""
工具类型定义

定义工具参数、工具定义、工具执行结果等数据类
"""

from dataclasses import dataclass, field
from typing import Any


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
    default: Any = None
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


__all__ = [
    "ToolParameter",
    "ToolDefinition",
    "ToolResult",
]
