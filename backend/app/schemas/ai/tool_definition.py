"""
工具定义相关 Schema

定义工具的请求和响应数据结构
"""

from typing import Any

from pydantic import BaseModel, Field

from app.core.base_schema import (
    BaseCreateSchema,
    BaseUpdateSchema,
    TenantResponseSchema,
)
from app.core.i18n import _


class ToolDefinitionCreate(BaseCreateSchema):
    """创建工具定义请求"""

    name: str = Field(..., max_length=100, description=_("tool_definition.field.name"))
    description: str | None = Field(None, description=_("tool_definition.field.description"))
    type: str = Field("http", description=_("tool_definition.field.type"))
    input_schema: dict[str, Any] | None = Field(None, description=_("tool_definition.field.input_schema"))
    output_schema: dict[str, Any] | None = Field(None, description=_("tool_definition.field.output_schema"))
    config: dict[str, Any] | None = Field(None, description=_("tool_definition.field.config"))
    timeout: int = Field(30, ge=1, le=300, description=_("tool_definition.field.timeout"))
    is_active: bool = Field(True, description=_("tool_definition.field.is_active"))


class ToolDefinitionUpdate(BaseUpdateSchema):
    """更新工具定义请求"""

    name: str | None = Field(None, max_length=100, description=_("tool_definition.field.name"))
    description: str | None = Field(None, description=_("tool_definition.field.description"))
    type: str | None = Field(None, description=_("tool_definition.field.type"))
    input_schema: dict[str, Any] | None = Field(None, description=_("tool_definition.field.input_schema"))
    output_schema: dict[str, Any] | None = Field(None, description=_("tool_definition.field.output_schema"))
    config: dict[str, Any] | None = Field(None, description=_("tool_definition.field.config"))
    timeout: int | None = Field(None, ge=1, le=300, description=_("tool_definition.field.timeout"))
    is_active: bool | None = Field(None, description=_("tool_definition.field.is_active"))


class ToolDefinitionResponse(TenantResponseSchema):
    """工具定义响应"""

    name: str = Field(..., description=_("tool_definition.field.name"))
    description: str | None = Field(None, description=_("tool_definition.field.description"))
    type: str = Field(..., description=_("tool_definition.field.type"))
    input_schema: dict[str, Any] | None = Field(None, description=_("tool_definition.field.input_schema"))
    output_schema: dict[str, Any] | None = Field(None, description=_("tool_definition.field.output_schema"))
    config: dict[str, Any] | None = Field(None, description=_("tool_definition.field.config"))
    timeout: int = Field(..., description=_("tool_definition.field.timeout"))
    is_system: bool = Field(..., description=_("tool_definition.field.is_system"))
    is_active: bool = Field(..., description=_("tool_definition.field.is_active"))


class ToolTestRequest(BaseCreateSchema):
    """工具测试执行请求"""

    arguments: dict[str, Any] = Field(default_factory=dict, description=_("tool_definition.field.test_arguments"))


class ToolTestResponse(BaseModel):
    """工具测试执行响应"""

    success: bool = Field(..., description=_("tool_definition.field.test_success"))
    output: str = Field("", description=_("tool_definition.field.test_output"))
    error: str | None = Field(None, description=_("tool_definition.field.test_error"))
    duration_ms: int = Field(0, description=_("tool_definition.field.test_duration"))


__all__ = [
    "ToolDefinitionCreate",
    "ToolDefinitionUpdate",
    "ToolDefinitionResponse",
    "ToolTestRequest",
    "ToolTestResponse",
]
