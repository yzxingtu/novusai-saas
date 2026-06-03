"""
企业用户角色 API 展示字段 / Tenant user role display fields for API responses.

内置角色（如 default_user）在库中可能为历史英文文案或创建时的单语言快照；
列表/详情响应按当前请求语言覆盖 name、description，与 role.* i18n 键一致。
Built-in roles may store stale locale in DB; list/detail override name/description per request.
"""

from __future__ import annotations

from app.core.i18n import _

DEFAULT_USER_ROLE_CODE = "default_user"


def localized_tenant_user_role_name_and_description(
    code: str,
    name: str,
    description: str | None,
) -> tuple[str, str | None]:
    """
    返回用于 JSON 响应的名称与描述 / Name and description for JSON serialization.

    Args:
        code: TenantUserRole.code
        name: DB name
        description: DB description (nullable)

    Returns:
        (display_name, display_description)
    """
    if code == DEFAULT_USER_ROLE_CODE:
        return _("role.default_user_name"), _("role.default_user_description")
    return name, description


__all__ = [
    "DEFAULT_USER_ROLE_CODE",
    "localized_tenant_user_role_name_and_description",
]
