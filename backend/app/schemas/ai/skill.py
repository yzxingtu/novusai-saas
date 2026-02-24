"""
技能相关 Schema

定义技能的请求和响应数据结构
"""

from typing import Any

from pydantic import Field

from app.core.base_schema import (
    BaseCreateSchema,
    BaseResponseSchema,
    BaseSchema,
    BaseUpdateSchema,
)
from app.core.i18n import _


class SkillCreate(BaseCreateSchema):
    """创建技能请求"""

    package_id: int = Field(..., description=_("skill.field.package_id"))
    name: str = Field(..., max_length=100, description=_("skill.field.name"))
    description: str | None = Field(None, description=_("skill.field.description"))
    avatar: str | None = Field(None, max_length=255, description=_("skill.field.avatar"))
    type: str = Field("toolkit", description=_("skill.field.type"))
    config: dict[str, Any] | None = Field(None, description=_("skill.field.config"))
    input_schema: dict[str, Any] | None = Field(None, description=_("skill.field.input_schema"))
    output_schema: dict[str, Any] | None = Field(None, description=_("skill.field.output_schema"))
    is_active: bool = Field(True, description=_("skill.field.is_active"))
    sort_order: int = Field(0, ge=0, description=_("skill.field.sort_order"))
    timeout: int = Field(30, ge=1, le=300, description=_("skill.field.timeout"))
    toolkit_content: str | None = Field(None, description=_("skill.field.toolkit_content"))
    toolkit_meta: dict[str, Any] | None = Field(None, description=_("skill.field.toolkit_meta"))


class SkillUpdate(BaseUpdateSchema):
    """更新技能请求"""

    name: str | None = Field(None, max_length=100, description=_("skill.field.name"))
    description: str | None = Field(None, description=_("skill.field.description"))
    avatar: str | None = Field(None, max_length=255, description=_("skill.field.avatar"))
    type: str | None = Field(None, description=_("skill.field.type"))
    config: dict[str, Any] | None = Field(None, description=_("skill.field.config"))
    input_schema: dict[str, Any] | None = Field(None, description=_("skill.field.input_schema"))
    output_schema: dict[str, Any] | None = Field(None, description=_("skill.field.output_schema"))
    is_active: bool | None = Field(None, description=_("skill.field.is_active"))
    sort_order: int | None = Field(None, ge=0, description=_("skill.field.sort_order"))
    timeout: int | None = Field(None, ge=1, le=300, description=_("skill.field.timeout"))
    toolkit_content: str | None = Field(None, description=_("skill.field.toolkit_content"))
    toolkit_meta: dict[str, Any] | None = Field(None, description=_("skill.field.toolkit_meta"))


class PluginToolInfo(BaseSchema):
    """插件工具信息（只读展示）"""

    name: str = Field(..., description="Tool name")
    description: str | None = Field(None, description="Tool description")
    parameters: list[dict[str, Any]] = Field(default_factory=list, description="Tool parameters")


class SkillResponse(BaseResponseSchema):
    """技能响应"""

    tenant_id: int | None = Field(None, description="租户ID")
    package_id: int = Field(..., description=_("skill.field.package_id"))
    name: str = Field(..., description=_("skill.field.name"))
    description: str | None = Field(None, description=_("skill.field.description"))
    avatar: str | None = Field(None, description=_("skill.field.avatar"))
    type: str = Field(..., description=_("skill.field.type"))
    config: dict[str, Any] | None = Field(None, description=_("skill.field.config"))
    input_schema: dict[str, Any] | None = Field(None, description=_("skill.field.input_schema"))
    output_schema: dict[str, Any] | None = Field(None, description=_("skill.field.output_schema"))
    is_system: bool = Field(False, description=_("skill.field.is_system"))
    is_active: bool = Field(..., description=_("skill.field.is_active"))
    sort_order: int = Field(..., description=_("skill.field.sort_order"))
    timeout: int = Field(..., description=_("skill.field.timeout"))
    toolkit_content: str | None = Field(None, description=_("skill.field.toolkit_content"))
    toolkit_meta: dict[str, Any] | None = Field(None, description=_("skill.field.toolkit_meta"))

    # ---- 插件来源信息（仅插件注册的技能有值） ----
    source_plugin: str | None = Field(None, description="Source plugin name (null for manual skills)")
    plugin_tools: list[PluginToolInfo] | None = Field(None, description="Plugin-resolved tool list (null for manual skills)")


__all__ = [
    "SkillCreate",
    "SkillUpdate",
    "SkillResponse",
]
