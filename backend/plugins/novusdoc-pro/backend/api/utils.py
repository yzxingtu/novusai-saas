"""NovusDoc Pro API 公共工具函数"""

from __future__ import annotations

from app.core.security import TOKEN_SCOPE_ADMIN

PLATFORM_TENANT_ID = 0


def safe_int(val, name: str = "id") -> tuple[int | None, dict | None]:
    """Safe int conversion for path params. Returns (value, error_dict)."""
    if val is None:
        return None, {"error": f"{name} required", "code": 4001, "status_code": 400}
    try:
        return int(val), None
    except (ValueError, TypeError):
        return None, {"error": f"invalid {name}", "code": 4001, "status_code": 400}


def resolve_tenant_id(ctx) -> int | None:
    """
    Resolve tenant_id for both tenant and admin requests.

    - tenant side: returns real tenant_id
    - admin side: returns platform tenant namespace 0
    - otherwise: returns None
    """
    tenant_id = ctx.get_current_tenant_id()
    if tenant_id is not None:
        return tenant_id

    if ctx.get_current_user_role() == TOKEN_SCOPE_ADMIN:
        return PLATFORM_TENANT_ID

    return None
