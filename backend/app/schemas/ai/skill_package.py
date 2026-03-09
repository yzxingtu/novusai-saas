"""
技能包相关 Schema

定义技能包的请求和响应数据结构
"""

from typing import Any

from pydantic import Field

from app.core.base_schema import (
    BaseCreateSchema,
    BaseResponseSchema,
    BaseUpdateSchema,
)
from app.core.i18n import _
from app.enums.common import AudienceEnum


class SkillPackageCreate(BaseCreateSchema):
    """创建技能包请求"""

    name: str = Field(..., max_length=100, description=_("skill_package.field.name"))
    description: str | None = Field(None, description=_("skill_package.field.description"))
    avatar: str | None = Field(None, max_length=255, description=_("skill_package.field.avatar"))
    scope: str = Field("all_tenants", description=_("skill_package.field.scope"))
    target_audience: str = Field(AudienceEnum.ALL.value, max_length=20, description=_("skill_package.field.target_audience"))
    is_recommended: bool = Field(False, description=_("skill_package.field.is_recommended"))
    bind_mode: str = Field("manual", description=_("skill_package.field.bind_mode"))
    tenant_id: int | None = Field(None, description="租户ID（scope=tenant 时必填）")
    is_active: bool = Field(True, description=_("skill_package.field.is_active"))
    sort_order: int = Field(0, ge=0, description=_("skill_package.field.sort_order"))
    tenant_ids: list[int] | None = Field(None, description="分配的租户 ID 列表（scope=assigned_tenants/admin_and_assigned 时使用）")


class SkillPackageUpdate(BaseUpdateSchema):
    """更新技能包请求"""

    name: str | None = Field(None, max_length=100, description=_("skill_package.field.name"))
    description: str | None = Field(None, description=_("skill_package.field.description"))
    avatar: str | None = Field(None, max_length=255, description=_("skill_package.field.avatar"))
    scope: str | None = Field(None, description=_("skill_package.field.scope"))
    target_audience: str | None = Field(None, max_length=20, description=_("skill_package.field.target_audience"))
    is_recommended: bool | None = Field(None, description=_("skill_package.field.is_recommended"))
    bind_mode: str | None = Field(None, description=_("skill_package.field.bind_mode"))
    is_active: bool | None = Field(None, description=_("skill_package.field.is_active"))
    sort_order: int | None = Field(None, ge=0, description=_("skill_package.field.sort_order"))
    tenant_ids: list[int] | None = Field(None, description="分配的租户 ID 列表（scope=assigned_tenants/admin_and_assigned 时使用）")


class SkillPackageResponse(BaseResponseSchema):
    """技能包响应"""

    tenant_id: int | None = Field(None, description="租户ID")
    name: str = Field(..., description=_("skill_package.field.name"))
    description: str | None = Field(None, description=_("skill_package.field.description"))
    avatar: str | None = Field(None, description=_("skill_package.field.avatar"))
    scope: str = Field(..., description=_("skill_package.field.scope"))
    target_audience: str = Field(AudienceEnum.ALL.value, description=_("skill_package.field.target_audience"))
    is_recommended: bool = Field(False, description=_("skill_package.field.is_recommended"))
    is_system: bool = Field(False, description=_("skill_package.field.is_system"))
    bind_mode: str = Field("manual", description=_("skill_package.field.bind_mode"))
    source_plugin: str | None = Field(None, description=_("skill_package.field.source_plugin"))
    valves_schema: dict[str, Any] | None = Field(None, description=_("skill_package.field.valves_schema"))
    valves_config: dict[str, Any] | None = Field(None, description=_("skill_package.field.valves_config"))
    is_active: bool = Field(..., description=_("skill_package.field.is_active"))
    sort_order: int = Field(..., description=_("skill_package.field.sort_order"))


__all__ = [
    "SkillPackageCreate",
    "SkillPackageUpdate",
    "SkillPackageResponse",
]
