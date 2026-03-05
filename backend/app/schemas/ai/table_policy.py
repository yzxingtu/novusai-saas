"""
AI 表策略相关 Schema

定义 AI 表策略的请求和响应数据结构
"""

from pydantic import Field

from app.core.base_schema import BaseResponseSchema, BaseUpdateSchema
from app.core.i18n import _


class AITablePolicyUpdate(BaseUpdateSchema):
    """更新 AI 表策略请求（管理员只编辑，不创建）"""

    label: str | None = Field(None, max_length=100, description=_("ai_table_policy.field.label"))
    description: str | None = Field(None, description=_("ai_table_policy.field.description"))
    keywords: list[str] | None = Field(None, description=_("ai_table_policy.field.keywords"))
    column_descriptions: dict[str, str] | None = Field(None, description=_("ai_table_policy.field.column_descriptions"))
    allow_read: bool | None = Field(None, description=_("ai_table_policy.field.allow_read"))
    allow_create: bool | None = Field(None, description=_("ai_table_policy.field.allow_create"))
    allow_update: bool | None = Field(None, description=_("ai_table_policy.field.allow_update"))
    allow_delete: bool | None = Field(None, description=_("ai_table_policy.field.allow_delete"))
    max_rows: int | None = Field(None, ge=1, le=10000, description=_("ai_table_policy.field.max_rows"))
    blocked_columns: list[str] | None = Field(None, description=_("ai_table_policy.field.blocked_columns"))
    readonly_columns: list[str] | None = Field(None, description=_("ai_table_policy.field.readonly_columns"))
    permission_code: str | None = Field(None, max_length=100, description=_("ai_table_policy.field.permission_code"))
    sort_order: int | None = Field(None, description=_("ai_table_policy.field.sort_order"))
    is_active: bool | None = Field(None, description=_("ai_table_policy.field.is_active"))


class AITablePolicyResponse(BaseResponseSchema):
    """AI 表策略响应"""

    table_name: str = Field(..., description=_("ai_table_policy.field.table_name"))
    label: str = Field(..., description=_("ai_table_policy.field.label"))
    description: str | None = Field(None, description=_("ai_table_policy.field.description"))
    keywords: list[str] | None = Field(None, description=_("ai_table_policy.field.keywords"))
    column_descriptions: dict[str, str] | None = Field(None, description=_("ai_table_policy.field.column_descriptions"))
    allow_read: bool = Field(..., description=_("ai_table_policy.field.allow_read"))
    allow_create: bool = Field(..., description=_("ai_table_policy.field.allow_create"))
    allow_update: bool = Field(..., description=_("ai_table_policy.field.allow_update"))
    allow_delete: bool = Field(..., description=_("ai_table_policy.field.allow_delete"))
    max_rows: int = Field(..., description=_("ai_table_policy.field.max_rows"))
    blocked_columns: list[str] | None = Field(None, description=_("ai_table_policy.field.blocked_columns"))
    readonly_columns: list[str] | None = Field(None, description=_("ai_table_policy.field.readonly_columns"))
    permission_code: str = Field(..., description=_("ai_table_policy.field.permission_code"))
    sort_order: int = Field(..., description=_("ai_table_policy.field.sort_order"))
    is_active: bool = Field(..., description=_("ai_table_policy.field.is_active"))


__all__ = [
    "AITablePolicyUpdate",
    "AITablePolicyResponse",
]
