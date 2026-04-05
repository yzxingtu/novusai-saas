"""
Identity presentation helpers shared across API contracts.
"""

from __future__ import annotations

from typing import Any


def normalize_identity_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def resolve_identity_display_name(
    identity_id: int | str | None,
    *candidates: Any,
) -> str:
    for candidate in candidates:
        normalized = normalize_identity_text(candidate)
        if normalized:
            return normalized
    return f"#{identity_id}" if identity_id not in (None, "") else "-"


def resolve_identity_display_role_name(
    role_name: Any,
    org_node_name: Any,
) -> str | None:
    normalized_role_name = normalize_identity_text(role_name)
    if not normalized_role_name:
        return None

    normalized_org_node_name = normalize_identity_text(org_node_name)
    if normalized_org_node_name == normalized_role_name:
        return None

    return normalized_role_name


def build_identity_select_extra(
    *,
    display_name: str,
    username: str | None,
    nickname: str | None,
    avatar: str | None,
    org_node_id: int | None,
    org_node_name: str | None,
    role_name: str | None,
    user_type: str,
    is_active: bool | None,
    is_leader: bool,
    is_owner: bool,
) -> dict[str, Any]:
    return {
        "display_name": display_name,
        "username": username,
        "nickname": nickname,
        "avatar": avatar,
        "org_node_id": org_node_id,
        "org_node_name": org_node_name,
        "role_name": role_name,
        "display_role_name": resolve_identity_display_role_name(
            role_name,
            org_node_name,
        ),
        "user_type": user_type,
        "is_active": is_active,
        "is_leader": is_leader,
        "is_owner": is_owner,
    }


__all__ = [
    "build_identity_select_extra",
    "normalize_identity_text",
    "resolve_identity_display_name",
    "resolve_identity_display_role_name",
]
