"""
技能相关 Schema / Skill Schema

定义技能的请求和响应数据结构
Defines skill request and response data structures.
"""

from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.ai.skills.spec import validate_skill_markdown
from app.core.base_schema import (
    BaseCreateSchema,
    BaseResponseSchema,
    BaseSchema,
    BaseUpdateSchema,
)
from app.core.i18n import _
from app.enums.skill import SkillSourceTypeEnum, SkillStatusEnum
from app.schemas.ai.invalid_ai_runtime_input import (
    ensure_no_disallowed_ai_runtime_input,
    is_retired_online_search_catalog_reference,
)


def _validate_skill_runtime_payload(
    value: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if value is not None:
        ensure_no_disallowed_ai_runtime_input(value)
    return value


def _validate_toolkit_content(value: str | None) -> str | None:
    if value is not None and is_retired_online_search_catalog_reference(value):
        raise ValueError(_("skill.error.retired_online_search"))
    return value


class SkillCreate(BaseCreateSchema):
    """创建技能请求 / Create skill request."""

    model_config = ConfigDict(extra="forbid")

    package_id: int = Field(..., description=_("skill.field.package_id"))
    name: str = Field(..., max_length=100, description=_("skill.field.name"))
    key: str | None = Field(None, max_length=100, description="Stable skill key")
    description: str | None = Field(None, description=_("skill.field.description"))
    avatar: str | None = Field(
        None, max_length=255, description=_("skill.field.avatar")
    )
    type: str = Field("toolkit", description=_("skill.field.type"))
    source_type: str = Field(
        SkillSourceTypeEnum.CUSTOM.value,
        description="Skill source type",
    )
    source_ref: str | None = Field(
        None, max_length=255, description="Skill source reference"
    )
    skill_md: str | None = Field(None, description="AgentScope-style SKILL.md content")
    version: str = Field("1.0.0", max_length=50, description="Skill version")
    status: str = Field(SkillStatusEnum.ACTIVE.value, description="Skill status")
    is_readonly: bool = Field(False, description="Readonly managed skill")
    config: dict[str, Any] | None = Field(None, description=_("skill.field.config"))
    input_schema: dict[str, Any] | None = Field(
        None, description=_("skill.field.input_schema")
    )
    output_schema: dict[str, Any] | None = Field(
        None, description=_("skill.field.output_schema")
    )
    is_active: bool = Field(True, description=_("skill.field.is_active"))
    sort_order: int = Field(0, ge=0, description=_("skill.field.sort_order"))
    timeout: int = Field(30, ge=1, le=300, description=_("skill.field.timeout"))
    toolkit_content: str | None = Field(
        None, description=_("skill.field.toolkit_content")
    )
    toolkit_meta: dict[str, Any] | None = Field(
        None, description=_("skill.field.toolkit_meta")
    )

    _reject_retired_config = field_validator("config")(_validate_skill_runtime_payload)
    _reject_retired_input_schema = field_validator("input_schema")(
        _validate_skill_runtime_payload
    )
    _reject_retired_output_schema = field_validator("output_schema")(
        _validate_skill_runtime_payload
    )
    _reject_retired_toolkit_meta = field_validator("toolkit_meta")(
        _validate_skill_runtime_payload
    )
    _reject_retired_toolkit_content = field_validator("toolkit_content")(
        _validate_toolkit_content
    )

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

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, max_length=100, description=_("skill.field.name"))
    key: str | None = Field(None, max_length=100, description="Stable skill key")
    description: str | None = Field(None, description=_("skill.field.description"))
    avatar: str | None = Field(
        None, max_length=255, description=_("skill.field.avatar")
    )
    type: str | None = Field(None, description=_("skill.field.type"))
    source_type: str | None = Field(None, description="Skill source type")
    source_ref: str | None = Field(
        None, max_length=255, description="Skill source reference"
    )
    skill_md: str | None = Field(None, description="AgentScope-style SKILL.md content")
    version: str | None = Field(None, max_length=50, description="Skill version")
    status: str | None = Field(None, description="Skill status")
    is_readonly: bool | None = Field(None, description="Readonly managed skill")
    config: dict[str, Any] | None = Field(None, description=_("skill.field.config"))
    input_schema: dict[str, Any] | None = Field(
        None, description=_("skill.field.input_schema")
    )
    output_schema: dict[str, Any] | None = Field(
        None, description=_("skill.field.output_schema")
    )
    is_active: bool | None = Field(None, description=_("skill.field.is_active"))
    sort_order: int | None = Field(None, ge=0, description=_("skill.field.sort_order"))
    timeout: int | None = Field(
        None, ge=1, le=300, description=_("skill.field.timeout")
    )
    toolkit_content: str | None = Field(
        None, description=_("skill.field.toolkit_content")
    )
    toolkit_meta: dict[str, Any] | None = Field(
        None, description=_("skill.field.toolkit_meta")
    )

    _reject_retired_config = field_validator("config")(_validate_skill_runtime_payload)
    _reject_retired_input_schema = field_validator("input_schema")(
        _validate_skill_runtime_payload
    )
    _reject_retired_output_schema = field_validator("output_schema")(
        _validate_skill_runtime_payload
    )
    _reject_retired_toolkit_meta = field_validator("toolkit_meta")(
        _validate_skill_runtime_payload
    )
    _reject_retired_toolkit_content = field_validator("toolkit_content")(
        _validate_toolkit_content
    )

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
    parameters: list[dict[str, Any]] = Field(
        default_factory=list, description="Tool parameters"
    )


class SkillResponse(BaseResponseSchema):
    """技能响应 / Skill response schema."""

    tenant_id: int | None = Field(None, description="企业ID")
    package_id: int = Field(..., description=_("skill.field.package_id"))
    name: str = Field(..., description=_("skill.field.name"))
    key: str | None = Field(None, description="Stable skill key")
    description: str | None = Field(None, description=_("skill.field.description"))
    avatar: str | None = Field(None, description=_("skill.field.avatar"))
    type: str = Field(..., description=_("skill.field.type"))
    source_type: str = Field(
        SkillSourceTypeEnum.CUSTOM.value, description="Skill source type"
    )
    source_ref: str | None = Field(None, description="Skill source reference")
    skill_md: str | None = Field(None, description="AgentScope-style SKILL.md content")
    version: str = Field("1.0.0", description="Skill version")
    status: str = Field(SkillStatusEnum.ACTIVE.value, description="Skill status")
    is_readonly: bool = Field(False, description="Readonly managed skill")
    config: dict[str, Any] | None = Field(None, description=_("skill.field.config"))
    input_schema: dict[str, Any] | None = Field(
        None, description=_("skill.field.input_schema")
    )
    output_schema: dict[str, Any] | None = Field(
        None, description=_("skill.field.output_schema")
    )
    is_system: bool = Field(False, description=_("skill.field.is_system"))
    is_active: bool = Field(..., description=_("skill.field.is_active"))
    sort_order: int = Field(..., description=_("skill.field.sort_order"))
    timeout: int = Field(..., description=_("skill.field.timeout"))
    toolkit_content: str | None = Field(
        None, description=_("skill.field.toolkit_content")
    )
    toolkit_meta: dict[str, Any] | None = Field(
        None, description=_("skill.field.toolkit_meta")
    )

    # ---- 插件来源信息（仅插件注册的技能有值） ---- / Plugin source (only for plugin-registered skills) ----
    source_plugin: str | None = Field(
        None, description="Source plugin name (null for manual skills)"
    )
    plugin_tools: list[PluginToolInfo] | None = Field(
        None, description="Plugin-resolved tool list (null for manual skills)"
    )


__all__ = [
    "SkillCreate",
    "SkillUpdate",
    "SkillResponse",
]
