"""
AI 表策略企业覆盖 Schema / AI Table Policy Tenant Override Schema
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.i18n import _


class AITablePolicyOverrideUpdate(BaseModel):
    """企业覆盖更新（NULL = 使用全局值）"""

    allow_read: bool | None = Field(None, description=_("ai_table_policy_override.field.allow_read"))
    allow_create: bool | None = Field(None, description=_("ai_table_policy_override.field.allow_create"))
    allow_update: bool | None = Field(None, description=_("ai_table_policy_override.field.allow_update"))
    allow_delete: bool | None = Field(None, description=_("ai_table_policy_override.field.allow_delete"))
    max_rows: int | None = Field(None, description=_("ai_table_policy_override.field.max_rows"))
    blocked_columns: list[str] | None = Field(None, description=_("ai_table_policy_override.field.blocked_columns"))
    is_active: bool | None = Field(None, description=_("ai_table_policy_override.field.is_active"))


__all__ = ["AITablePolicyOverrideUpdate"]
