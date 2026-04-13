"""Snapshot and serialization helpers for AI action logs."""

import inspect
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import PLATFORM_TENANT_ID
from app.core.identity_snapshot import (
    build_identity_snapshot,
    load_identity_snapshot,
    snapshot_has_key,
    snapshot_value,
)
from app.models.ai.agent import Agent
from app.services.ai.action_log_service_parts.normalization import _normalize_operator_type


def _default_agent_meta() -> dict[str, Any]:
    return {
        "agent_avatar": None,
        "agent_name": None,
    }


def _default_operator_meta() -> dict[str, Any]:
    return {
        "operator_avatar": None,
        "operator_display_name": None,
        "operator_display_role_name": None,
        "operator_name": None,
        "operator_nickname": None,
        "operator_org_node_id": None,
        "operator_org_node_name": None,
        "operator_role_name": None,
        "operator_is_active": None,
        "operator_is_leader": None,
        "operator_is_owner": None,
        "operator_type": None,
    }


def _build_operator_meta(
    *,
    operator_type: str,
    username: str | None,
    nickname: str | None,
    avatar: str | None,
    org_node_id: int | None = None,
    org_node_name: str | None = None,
    role_name: str | None = None,
    is_active: bool | None = None,
    is_leader: bool | None = None,
    is_owner: bool | None = None,
) -> dict[str, Any]:
    snapshot = build_identity_snapshot(
        identity_id=None,
        user_type=operator_type,
        username=username,
        nickname=nickname,
        avatar=avatar,
        org_node_id=org_node_id,
        org_node_name=org_node_name,
        role_name=role_name,
        is_active=is_active,
        is_leader=is_leader,
        is_owner=is_owner,
    )
    return {
        "operator_avatar": avatar,
        "operator_display_name": snapshot.get("display_name"),
        "operator_display_role_name": snapshot.get("display_role_name"),
        "operator_name": username,
        "operator_nickname": nickname,
        "operator_org_node_id": org_node_id,
        "operator_org_node_name": org_node_name,
        "operator_role_name": role_name,
        "operator_is_active": is_active,
        "operator_is_leader": is_leader,
        "operator_is_owner": is_owner,
        "operator_type": operator_type,
    }


async def _execute_first(
    db: AsyncSession,
    stmt: Any,
) -> Any:
    result = await db.execute(stmt)
    row = result.first()
    if inspect.isawaitable(row):
        row = await row
    return row


def _resolve_agent_meta(
    item: dict[str, Any],
    live_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    live_meta = live_meta or {}
    return {
        "agent_avatar": item.get("agent_avatar_snapshot")
        or live_meta.get("agent_avatar"),
        "agent_name": item.get("agent_name_snapshot") or live_meta.get("agent_name"),
    }


def _resolve_operator_meta(
    item: dict[str, Any],
    live_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    live_meta = live_meta or {}
    snapshot = (
        item.get("operator_snapshot")
        if isinstance(item.get("operator_snapshot"), dict)
        else {}
    )
    operator_name = (
        snapshot_value(snapshot, "username")
        or item.get("operator_name_snapshot")
        or live_meta.get("operator_name")
    )
    operator_nickname = (
        snapshot_value(snapshot, "nickname")
        or item.get("operator_nickname_snapshot")
        or live_meta.get("operator_nickname")
    )
    operator_display_name = (
        snapshot_value(snapshot, "display_name")
        or operator_nickname
        or operator_name
        or live_meta.get("operator_display_name")
    )
    if snapshot_has_key(snapshot, "display_role_name"):
        operator_role_name = snapshot.get("display_role_name")
    elif snapshot_has_key(snapshot, "role_name"):
        operator_role_name = snapshot.get("role_name")
    else:
        operator_role_name = live_meta.get("operator_role_name")
    return {
        "operator_avatar": snapshot_value(
            snapshot,
            "avatar",
            item.get("operator_avatar_snapshot") or live_meta.get("operator_avatar"),
        ),
        "operator_display_name": operator_display_name,
        "operator_name": operator_name,
        "operator_nickname": operator_nickname,
        "operator_display_role_name": (
            snapshot.get("display_role_name")
            if snapshot_has_key(snapshot, "display_role_name")
            else live_meta.get("operator_display_role_name")
        ),
        "operator_org_node_id": (
            snapshot.get("org_node_id")
            if snapshot_has_key(snapshot, "org_node_id")
            else live_meta.get("operator_org_node_id")
        ),
        "operator_org_node_name": (
            snapshot.get("org_node_name")
            if snapshot_has_key(snapshot, "org_node_name")
            else live_meta.get("operator_org_node_name")
        ),
        "operator_role_name": operator_role_name,
        "operator_is_active": (
            snapshot.get("is_active")
            if snapshot_has_key(snapshot, "is_active")
            else live_meta.get("operator_is_active")
        ),
        "operator_is_leader": (
            snapshot.get("is_leader")
            if snapshot_has_key(snapshot, "is_leader")
            else live_meta.get("operator_is_leader")
        ),
        "operator_is_owner": (
            snapshot.get("is_owner")
            if snapshot_has_key(snapshot, "is_owner")
            else live_meta.get("operator_is_owner")
        ),
        "operator_type": _normalize_operator_type(snapshot.get("user_type"))
        or _normalize_operator_type(item.get("operator_type"))
        or _normalize_operator_type(live_meta.get("operator_type")),
    }


async def _load_agent_snapshot(
    db: AsyncSession,
    agent_id: int,
) -> dict[str, Any]:
    if not agent_id or agent_id <= 0:
        return {}

    stmt = select(Agent.name, Agent.avatar).where(
        Agent.id == agent_id,
        Agent.is_deleted.is_(False),
    )
    row = await _execute_first(db, stmt)
    if not row:
        return {}
    return {
        "agent_avatar_snapshot": row.avatar,
        "agent_name_snapshot": row.name,
    }


async def _load_operator_snapshot(
    db: AsyncSession,
    *,
    tenant_id: int,
    operator_id: int,
    operator_type: str | None,
) -> dict[str, Any]:
    normalized_type = _normalize_operator_type(operator_type)
    if not operator_id:
        return {"operator_type": normalized_type}

    snapshot = await load_identity_snapshot(
        db,
        user_type=normalized_type,
        user_id=operator_id,
        tenant_id=None if tenant_id == PLATFORM_TENANT_ID else tenant_id,
    )
    if not snapshot:
        return {"operator_type": normalized_type}

    return {
        "operator_snapshot": snapshot,
        "operator_type": snapshot.get("user_type") or normalized_type,
        "operator_name_snapshot": snapshot.get("username"),
        "operator_nickname_snapshot": snapshot.get("nickname"),
        "operator_avatar_snapshot": snapshot.get("avatar"),
    }


__all__ = [
    "_build_operator_meta",
    "_default_agent_meta",
    "_default_operator_meta",
    "_load_agent_snapshot",
    "_load_operator_snapshot",
    "_resolve_agent_meta",
    "_resolve_operator_meta",
]
