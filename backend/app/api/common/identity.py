"""
Common serializers shared by identity-focused endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.identity import (
    resolve_identity_display_name,
    resolve_identity_display_role_name,
)
from app.core.response import serialize_datetime_for_api


def _normalize_datetime(value: datetime | None) -> str | None:
    return serialize_datetime_for_api(value)


def _extract_attribute(obj: Any, attr: str) -> Any:
    return getattr(obj, attr, None)


def _build_identity_payload(
    *,
    id: int | str,
    username: str | None,
    email: str | None,
    phone: str | None,
    nickname: str | None,
    avatar: str | None,
    is_active: bool | None,
    is_owner: bool,
    is_leader: bool,
    user_type: str,
    role_attr: Any,
    org_attr: Any,
    tenant_id: int | None,
    created_at: datetime | None,
    updated_at: datetime | None,
    last_login_at: datetime | None,
    last_login_ip: str | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    role_id = _extract_attribute(role_attr, "id")
    role_name = _extract_attribute(role_attr, "name")
    org_node_id = _extract_attribute(org_attr, "id")
    org_node_name = _extract_attribute(org_attr, "name")

    display_name = resolve_identity_display_name(id, nickname, username)
    payload = {
        "id": id,
        "display_name": display_name,
        "username": username,
        "email": email,
        "phone": phone,
        "nickname": nickname,
        "avatar": avatar,
        "is_active": is_active,
        "is_owner": is_owner,
        "is_leader": is_leader,
        "user_type": user_type,
        "role_id": role_id,
        "role_name": role_name,
        "display_role_name": resolve_identity_display_role_name(
            role_name,
            org_node_name,
        ),
        "org_node_id": org_node_id,
        "org_node_name": org_node_name,
        "tenant_id": tenant_id,
        "created_at": _normalize_datetime(created_at),
        "updated_at": _normalize_datetime(updated_at),
        "last_login_at": _normalize_datetime(last_login_at),
        "last_login_ip": last_login_ip,
    }

    if extra:
        payload.update(extra)

    return payload


def serialize_admin_identity_detail(admin: Any) -> dict[str, Any]:
    org_node = getattr(admin, "org_node", None)
    role = getattr(admin, "role", None)
    is_leader = bool(org_node and getattr(org_node, "leader_id", None) == admin.id)
    extra = {
        "is_super": getattr(admin, "is_super", False),
    }
    return _build_identity_payload(
        id=admin.id,
        username=admin.username,
        email=getattr(admin, "email", None),
        phone=getattr(admin, "phone", None),
        nickname=admin.nickname,
        avatar=admin.avatar,
        is_active=admin.is_active,
        is_owner=False,
        is_leader=is_leader,
        user_type="admin",
        role_attr=role,
        org_attr=org_node,
        tenant_id=None,
        created_at=admin.created_at,
        updated_at=admin.updated_at,
        last_login_at=admin.last_login_at,
        last_login_ip=admin.last_login_ip,
        extra=extra,
    )


def serialize_tenant_admin_identity_detail(admin: Any) -> dict[str, Any]:
    org_node = getattr(admin, "org_node", None)
    role = getattr(admin, "role", None)
    is_leader = bool(org_node and getattr(org_node, "leader_id", None) == admin.id)
    extra = {
        "permission_role_id": getattr(role, "id", None),
        "permission_role_name": getattr(role, "name", None),
    }
    return _build_identity_payload(
        id=admin.id,
        username=admin.username,
        email=admin.email,
        phone=admin.phone,
        nickname=admin.nickname,
        avatar=admin.avatar,
        is_active=admin.is_active,
        is_owner=bool(admin.is_owner),
        is_leader=is_leader,
        user_type="tenant_admin",
        role_attr=role,
        org_attr=org_node,
        tenant_id=getattr(admin, "tenant_id", None),
        created_at=admin.created_at,
        updated_at=admin.updated_at,
        last_login_at=admin.last_login_at,
        last_login_ip=admin.last_login_ip,
        extra=extra,
    )


def serialize_tenant_user_identity_detail(user: Any) -> dict[str, Any]:
    org_node = getattr(user, "org_node", None)
    role = getattr(user, "role", None)
    extra = {
        "approval_status": getattr(user, "approval_status", None),
        "gender": getattr(user, "gender", None),
    }
    return _build_identity_payload(
        id=user.id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        nickname=user.nickname,
        avatar=user.avatar,
        is_active=user.is_active,
        is_owner=False,
        is_leader=False,
        user_type="tenant_user",
        role_attr=role,
        org_attr=org_node,
        tenant_id=getattr(user, "tenant_id", None),
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        last_login_ip=user.last_login_ip,
        extra=extra,
    )


__all__ = [
    "serialize_admin_identity_detail",
    "serialize_tenant_admin_identity_detail",
    "serialize_tenant_user_identity_detail",
]
