"""
技能相关 Schema / Skill Schema

定义技能的请求和响应数据结构
Defines skill request and response data structures.
"""

from typing import Any

from pydantic import Field, model_validator

from app.ai.skills.spec import validate_skill_markdown
from app.core.base_schema import (
    BaseCreateSchema,
    BaseResponseSchema,
    BaseSchema,
    BaseUpdateSchema,
)
from app.core.i18n import _
from app.enums.skill import SkillSourceTypeEnum, SkillStatusEnum


class SkillCreate(BaseCreateSchema):
    """创建技能请求 / Create skill request."""

    package_id: int = Field(..., description=_("skill.field.package_id"))
    name: str = Field(..., max_length=100, description=_("skill.field.name"))
    key: str | None = Field(None, max_length=100, description="Stable skill key")
    description: str | None = Field(None, description=_("skill.field.description"))
    avatar: str | None = Field(None, max_length=255, description=_("skill.field.avatar"))
    type: str = Field("toolkit", description=_("skill.field.type"))
    source_type: str = Field(
        SkillSourceTypeEnum.CUSTOM.value,
        description="Skill source type",
    )
    source_ref: str | None = Field(None, max_length=255, description="Skill source reference")
    skill_md: str | None = Field(None, description="AgentScope-style SKILL.md content")
    version: str = Field("1.0.0", max_length=50, description="Skill version")
    status: str = Field(SkillStatusEnum.ACTIVE.value, description="Skill status")
    is_readonly: bool = Field(False, description="Readonly managed skill")
    config: dict[str, Any] | None = Field(None, description=_("skill.field.config"))
    input_schema: dict[str, Any] | None = Field(None, description=_("skill.field.input_schema"))
    output_schema: dict[str, Any] | None = Field(None, description=_("skill.field.output_schema"))
    is_active: bool = Field(True, description=_("skill.field.is_active"))
    sort_order: int = Field(0, ge=0, description=_("skill.field.sort_order"))
    timeout: int = Field(30, ge=1, le=300, description=_("skill.field.timeout"))
    toolkit_content: str | None = Field(None, description=_("skill.field.toolkit_content"))
    toolkit_meta: dict[str, Any] | None = Field(None, description=_("skill.field.toolkit_meta"))

    @model_validator(mode="after")
    def validate_agentscope_skill_spec(self) -> "SkillCreate":
        if not self.skill_md:
            return self
        spec = validate_skill_markdown(self.skill_md)
        if self.key and self.key != spec.name:
            raise ValueError("Skill key must match SKILL.md frontmatter name")
        self.key = self.key or spec.name
        self.description = self.description or spec.description
        return self


class SkillUpdate(BaseUpdateSchema):
    """更新技能请求 / Update skill request."""

    name: str | None = Field(None, max_length=100, description=_("skill.field.name"))
    key: str | None = Field(None, max_length=100, description="Stable skill key")
    description: str | None = Field(None, description=_("skill.field.description"))
    avatar: str | None = Field(None, max_length=255, description=_("skill.field.avatar"))
    type: str | None = Field(None, description=_("skill.field.type"))
    source_type: str | None = Field(None, description="Skill source type")
    source_ref: str | None = Field(None, max_length=255, description="Skill source reference")
    skill_md: str | None = Field(None, description="AgentScope-style SKILL.md content")
    version: str | None = Field(None, max_length=50, description="Skill version")
    status: str | None = Field(None, description="Skill status")
    is_readonly: bool | None = Field(None, description="Readonly managed skill")
    config: dict[str, Any] | None = Field(None, description=_("skill.field.config"))
    input_schema: dict[str, Any] | None = Field(None, description=_("skill.field.input_schema"))
    output_schema: dict[str, Any] | None = Field(None, description=_("skill.field.output_schema"))
    is_active: bool | None = Field(None, description=_("skill.field.is_active"))
    sort_order: int | None = Field(None, ge=0, description=_("skill.field.sort_order"))
    timeout: int | None = Field(None, ge=1, le=300, description=_("skill.field.timeout"))
    toolkit_content: str | None = Field(None, description=_("skill.field.toolkit_content"))
    toolkit_meta: dict[str, Any] | None = Field(None, description=_("skill.field.toolkit_meta"))

    @model_validator(mode="after")
    def validate_agentscope_skill_spec(self) -> "SkillUpdate":
        if not self.skill_md:
            return self
        spec = validate_skill_markdown(self.skill_md)
        if self.key and self.key != spec.name:
            raise ValueError("Skill key must match SKILL.md frontmatter name")
        self.key = self.key or spec.name
        self.description = self.description or spec.description
        return self


class PluginToolInfo(BaseSchema):
    """插件工具信息（只读展示） / Plugin tool info (read-only display)."""

    name: str = Field(..., description="Tool name")
    description: str | None = Field(None, description="Tool description")
    parameters: list[dict[str, Any]] = Field(default_factory=list, description="Tool parameters")


class SkillResponse(BaseResponseSchema):
    """技能响应 / Skill response schema."""

    tenant_id: int | None = Field(None, description="企业ID")
    package_id: int = Field(..., description=_("skill.field.package_id"))
    name: str = Field(..., description=_("skill.field.name"))
    key: str | None = Field(None, description="Stable skill key")
    description: str | None = Field(None, description=_("skill.field.description"))
    avatar: str | None = Field(None, description=_("skill.field.avatar"))
    type: str = Field(..., description=_("skill.field.type"))
    source_type: str = Field(SkillSourceTypeEnum.CUSTOM.value, description="Skill source type")
    source_ref: str | None = Field(None, description="Skill source reference")
    skill_md: str | None = Field(None, description="AgentScope-style SKILL.md content")
    version: str = Field("1.0.0", description="Skill version")
    status: str = Field(SkillStatusEnum.ACTIVE.value, description="Skill status")
    is_readonly: bool = Field(False, description="Readonly managed skill")
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
