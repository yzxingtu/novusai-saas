"""
Internal enrichment helpers for AI call log repository.
AI 调用日志 Repository 内部富化辅助函数。
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.identity import resolve_identity_display_role_name
from app.models.ai import AICallLog
from app.models.ai.agent import Agent
from app.models.ai.model import AIModel
from app.models.ai.provider import AIProvider
from app.models.auth.admin_role import AdminRole
from app.models.auth.tenant_admin_role import TenantAdminRole
from app.models.auth.tenant_user_role import TenantUserRole
from app.models.org.admin_org_node import AdminOrgNode
from app.models.org.tenant_org_node import TenantOrgNode
from app.models.system.admin import Admin
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_admin import TenantAdmin
from app.models.tenant.tenant_user import TenantUser
from app.repositories.ai.call_log_repository_normalizers import (
    actor_type_fallback_name,
    display_name,
    effective_item_tenant_id,
    normalize_actor_type,
    normalize_call_log_dict_datetimes,
    normalize_caller_snapshot,
    normalize_optional_int,
)


def _serialize_log(item: AICallLog) -> dict:
    if hasattr(item, "to_dict"):
        return item.to_dict()
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "model_id": item.model_id,
        "provider_id": item.provider_id,
        "request_type": item.request_type,
        "input_tokens": item.input_tokens,
        "output_tokens": item.output_tokens,
        "total_tokens": item.total_tokens,
        "cost": float(item.cost or 0),
        "latency_ms": item.latency_ms,
        "status": item.status,
        "error_message": item.error_message,
        "user_id": item.user_id,
        "user_type": item.user_type,
        "created_at": item.created_at,
    }


def _collect_enrichment_ids(
    items: list[AICallLog],
    *,
    include_tenant_names: bool,
    include_caller_names: bool,
) -> tuple[set[int], set[int], set[int], set[int], set[int], set[int], set[int]]:
    model_ids = {
        normalized_id
        for item in items
        for normalized_id in (
            normalize_optional_int(item.model_id),
            normalize_optional_int(getattr(item, "routed_model_id", None)),
        )
        if normalized_id is not None
    }
    agent_ids = {
        normalized_id
        for item in items
        for normalized_id in (
            normalize_optional_int(item.agent_id),
            normalize_optional_int(getattr(item, "agent_id_snapshot", None)),
        )
        if normalized_id is not None
    }
    provider_ids = {
        normalized_id
        for item in items
        for normalized_id in (normalize_optional_int(item.provider_id),)
        if normalized_id is not None
    }
    tenant_ids = {
        tenant_id
        for item in items
        for tenant_id in (effective_item_tenant_id(item),)
        if include_tenant_names and tenant_id is not None
    }

    tenant_admin_ids: set[int] = set()
    tenant_user_ids: set[int] = set()
    platform_admin_ids: set[int] = set()
    if include_caller_names:
        for item in items:
            caller_snapshot = normalize_caller_snapshot(
                getattr(item, "request_metadata", None)
            )
            if caller_snapshot.get("display_name") or caller_snapshot.get("username"):
                continue

            actor_id = normalize_optional_int(getattr(item, "actor_user_id", None))
            if actor_id is None:
                actor_id = normalize_optional_int(getattr(item, "user_id", None))
            actor_type = normalize_actor_type(
                getattr(item, "actor_user_type", None),
                getattr(item, "user_type", None),
            )
            if not actor_id or not actor_type:
                continue
            if actor_type == "tenant_admin":
                tenant_admin_ids.add(actor_id)
            elif actor_type == "tenant_user":
                tenant_user_ids.add(actor_id)
            elif actor_type == "platform_admin":
                platform_admin_ids.add(actor_id)

    return (
        model_ids,
        agent_ids,
        provider_ids,
        tenant_ids,
        tenant_admin_ids,
        tenant_user_ids,
        platform_admin_ids,
    )


async def _load_model_map(db, model_ids: set[int]) -> dict[int, str]:
    if not model_ids:
        return {}
    rows = (
        await db.execute(
            select(AIModel.id, AIModel.name).where(AIModel.id.in_(model_ids))
        )
    ).all()
    return {
        int(row_id): str(row_name)
        for row in rows
        if (row_id := getattr(row, "id", None)) is not None
        and (row_name := getattr(row, "name", None)) is not None
    }


async def _load_agent_meta_map(
    db, agent_ids: set[int]
) -> dict[int, dict[str, str | None]]:
    if not agent_ids:
        return {}
    rows = (
        await db.execute(
            select(Agent.id, Agent.name, Agent.avatar).where(
                Agent.id.in_(agent_ids),
                Agent.is_deleted.is_(False),
            )
        )
    ).all()
    return {
        row.id: {
            "avatar": getattr(row, "avatar", None),
            "name": getattr(row, "name", None),
        }
        for row in rows
    }


async def _load_provider_maps(
    db,
    provider_ids: set[int],
) -> tuple[dict[int, str], dict[int, str | None]]:
    if not provider_ids:
        return {}, {}
    rows = (
        await db.execute(
            select(AIProvider.id, AIProvider.name, AIProvider.icon).where(
                AIProvider.id.in_(provider_ids)
            )
        )
    ).all()
    provider_map = {
        int(row_id): str(row_name)
        for row in rows
        if (row_id := getattr(row, "id", None)) is not None
        and (row_name := getattr(row, "name", None)) is not None
    }
    provider_icon_map = {
        int(row_id): getattr(row, "icon", None)
        for row in rows
        if (row_id := getattr(row, "id", None)) is not None
    }
    return provider_map, provider_icon_map


async def _load_tenant_map(db, tenant_ids: set[int]) -> dict[int, str]:
    if not tenant_ids:
        return {}
    rows = (
        await db.execute(
            select(Tenant.id, Tenant.name).where(Tenant.id.in_(tenant_ids))
        )
    ).all()
    return {
        int(row_id): str(row_name)
        for row in rows
        if (row_id := getattr(row, "id", None)) is not None
        and (row_name := getattr(row, "name", None)) is not None
    }


async def _load_tenant_admin_identity_map(
    db,
    tenant_admin_ids: set[int],
) -> dict[tuple[str, int], dict[str, object]]:
    if not tenant_admin_ids:
        return {}
    rows = (
        await db.execute(
            select(
                TenantAdmin.id,
                TenantAdmin.username,
                TenantAdmin.nickname,
                TenantAdmin.avatar,
                TenantAdmin.org_node_id,
                TenantAdmin.is_active,
                TenantAdmin.is_owner,
                TenantAdminRole.name.label("role_name"),
                TenantOrgNode.name.label("org_node_name"),
                TenantOrgNode.leader_id.label("org_leader_id"),
            )
            .select_from(TenantAdmin)
            .join(
                TenantAdminRole,
                TenantAdminRole.id == TenantAdmin.role_id,
                isouter=True,
            )
            .join(
                TenantOrgNode,
                TenantOrgNode.id == TenantAdmin.org_node_id,
                isouter=True,
            )
            .where(
                TenantAdmin.id.in_(tenant_admin_ids),
                TenantAdmin.is_deleted.is_(False),
            )
        )
    ).all()

    identity_map: dict[tuple[str, int], dict[str, object]] = {}
    for row in rows:
        identity_map[("tenant_admin", int(row.id))] = {
            "display_name": display_name(row.nickname, row.username, f"#{row.id}"),
            "username": row.username,
            "nickname": row.nickname,
            "avatar": row.avatar,
            "org_node_id": row.org_node_id,
            "org_node_name": row.org_node_name,
            "role_name": row.role_name,
            "display_role_name": resolve_identity_display_role_name(
                row.role_name,
                row.org_node_name,
            ),
            "is_active": row.is_active,
            "is_owner": bool(row.is_owner),
            "is_leader": bool(row.org_leader_id and row.org_leader_id == row.id),
        }
    return identity_map


async def _load_tenant_user_identity_map(
    db,
    tenant_user_ids: set[int],
) -> dict[tuple[str, int], dict[str, object]]:
    if not tenant_user_ids:
        return {}
    rows = (
        await db.execute(
            select(
                TenantUser.id,
                TenantUser.username,
                TenantUser.nickname,
                TenantUser.email,
                TenantUser.avatar,
                TenantUser.org_node_id,
                TenantUser.is_active,
                TenantUserRole.name.label("role_name"),
                TenantOrgNode.name.label("org_node_name"),
            )
            .select_from(TenantUser)
            .join(
                TenantUserRole,
                TenantUserRole.id == TenantUser.role_id,
                isouter=True,
            )
            .join(
                TenantOrgNode,
                TenantOrgNode.id == TenantUser.org_node_id,
                isouter=True,
            )
            .where(
                TenantUser.id.in_(tenant_user_ids),
                TenantUser.is_deleted.is_(False),
            )
        )
    ).all()

    identity_map: dict[tuple[str, int], dict[str, object]] = {}
    for row in rows:
        identity_map[("tenant_user", int(row.id))] = {
            "display_name": display_name(
                row.nickname,
                row.username,
                row.email or f"#{row.id}",
            ),
            "username": row.username,
            "nickname": row.nickname,
            "avatar": row.avatar,
            "org_node_id": row.org_node_id,
            "org_node_name": row.org_node_name,
            "role_name": row.role_name,
            "display_role_name": resolve_identity_display_role_name(
                row.role_name,
                row.org_node_name,
            ),
            "is_active": row.is_active,
            "is_owner": False,
            "is_leader": False,
        }
    return identity_map


async def _load_platform_admin_identity_map(
    db,
    platform_admin_ids: set[int],
) -> dict[tuple[str, int], dict[str, object]]:
    if not platform_admin_ids:
        return {}
    rows = (
        await db.execute(
            select(
                Admin.id,
                Admin.username,
                Admin.nickname,
                Admin.avatar,
                Admin.org_node_id,
                Admin.is_active,
                Admin.is_super,
                AdminRole.name.label("role_name"),
                AdminOrgNode.name.label("org_node_name"),
                AdminOrgNode.leader_id.label("org_leader_id"),
            )
            .select_from(Admin)
            .join(AdminRole, AdminRole.id == Admin.role_id, isouter=True)
            .join(
                AdminOrgNode,
                AdminOrgNode.id == Admin.org_node_id,
                isouter=True,
            )
            .where(
                Admin.id.in_(platform_admin_ids),
                Admin.is_deleted.is_(False),
            )
        )
    ).all()

    identity_map: dict[tuple[str, int], dict[str, object]] = {}
    for row in rows:
        identity_map[("platform_admin", int(row.id))] = {
            "display_name": display_name(row.nickname, row.username, f"#{row.id}"),
            "username": row.username,
            "nickname": row.nickname,
            "avatar": row.avatar,
            "org_node_id": row.org_node_id,
            "org_node_name": row.org_node_name,
            "role_name": row.role_name,
            "display_role_name": resolve_identity_display_role_name(
                row.role_name,
                row.org_node_name,
            ),
            "is_active": row.is_active,
            "is_owner": bool(row.is_super),
            "is_leader": bool(row.org_leader_id and row.org_leader_id == row.id),
        }
    return identity_map


async def _load_caller_identity_map(
    db,
    *,
    tenant_admin_ids: set[int],
    tenant_user_ids: set[int],
    platform_admin_ids: set[int],
) -> dict[tuple[str, int], dict[str, object]]:
    identity_map: dict[tuple[str, int], dict[str, object]] = {}
    identity_map.update(await _load_tenant_admin_identity_map(db, tenant_admin_ids))
    identity_map.update(await _load_tenant_user_identity_map(db, tenant_user_ids))
    identity_map.update(await _load_platform_admin_identity_map(db, platform_admin_ids))
    return identity_map


async def enrich_logs_to_dicts(
    db,
    items: list[AICallLog],
    *,
    include_tenant_names: bool = True,
    include_caller_names: bool = False,
    include_payload: bool = False,
    platform_tenant_id: int,
    platform_usage_tenant_name: str,
) -> list[dict]:
    """
    将 ORM 列表转为 dict，并批量填充 model/provider/tenant/caller 展示字段。
    """
    if not items:
        return []

    (
        model_ids,
        agent_ids,
        provider_ids,
        tenant_ids,
        tenant_admin_ids,
        tenant_user_ids,
        platform_admin_ids,
    ) = _collect_enrichment_ids(
        items,
        include_tenant_names=include_tenant_names,
        include_caller_names=include_caller_names,
    )

    model_map = await _load_model_map(db, model_ids)
    agent_meta_map = await _load_agent_meta_map(db, agent_ids)
    provider_map, provider_icon_map = await _load_provider_maps(db, provider_ids)
    tenant_map = await _load_tenant_map(db, tenant_ids)
    caller_identity_map = await _load_caller_identity_map(
        db,
        tenant_admin_ids=tenant_admin_ids,
        tenant_user_ids=tenant_user_ids,
        platform_admin_ids=platform_admin_ids,
    )

    result: list[dict] = []
    for item in items:
        payload = _serialize_log(item)
        snap_model = getattr(item, "model_name_snapshot", None)
        snap_provider = getattr(item, "provider_name_snapshot", None)
        snap_agent = getattr(item, "agent_name_snapshot", None)
        resolved_agent_id = int(
            item.agent_id or getattr(item, "agent_id_snapshot", None) or 0
        )
        agent_meta = agent_meta_map.get(resolved_agent_id, {})

        payload["model_name"] = snap_model or model_map.get(item.model_id, "-")
        payload["provider_name"] = snap_provider or provider_map.get(
            item.provider_id, "-"
        )
        payload["provider_icon"] = provider_icon_map.get(item.provider_id)
        payload["routed_model_name"] = model_map.get(item.routed_model_id, "-")
        payload["agent_name"] = snap_agent or agent_meta.get("name") or "-"
        payload["agent_avatar"] = agent_meta.get("avatar")
        payload["agent_id_snapshot"] = getattr(item, "agent_id_snapshot", None)
        payload["billing_tenant_name_snapshot"] = getattr(
            item,
            "billing_tenant_name_snapshot",
            None,
        )
        metadata = (
            item.request_metadata if isinstance(item.request_metadata, dict) else {}
        )

        if include_tenant_names:
            effective_tenant_id = item.billing_tenant_id
            if effective_tenant_id is None and item.tenant_id is not None:
                effective_tenant_id = item.tenant_id
            if getattr(item, "billing_tenant_name_snapshot", None):
                payload["tenant_name"] = item.billing_tenant_name_snapshot
            elif effective_tenant_id == platform_tenant_id:
                payload["tenant_name"] = platform_usage_tenant_name
            else:
                payload["tenant_name"] = tenant_map.get(effective_tenant_id, "-")

        actor_id = item.actor_user_id or item.user_id
        actor_type = normalize_actor_type(item.actor_user_type, item.user_type)
        caller_identity: dict[str, object] | None = None
        caller = "-"
        if include_caller_names:
            caller_snapshot = normalize_caller_snapshot(metadata)
            if caller_snapshot:
                caller_identity = caller_snapshot
                caller = str(
                    caller_snapshot.get("display_name")
                    or caller_snapshot.get("username")
                    or caller_snapshot.get("nickname")
                    or "-"
                )
                actor_id = (
                    normalize_optional_int(
                        caller_snapshot.get("user_id"),
                        allow_zero=True,
                    )
                    or actor_id
                )
                actor_type = (
                    str(caller_snapshot.get("user_type") or "").strip() or actor_type
                )
            elif actor_id and actor_type:
                caller_identity = caller_identity_map.get((actor_type, int(actor_id)))
                if caller_identity:
                    caller = str(caller_identity.get("display_name") or "-")
                elif actor_type in {"tenant_admin", "tenant_user", "platform_admin"}:
                    caller = f"ID:{actor_id}"
                else:
                    caller = actor_type_fallback_name(actor_type)
            elif actor_type:
                caller = actor_type_fallback_name(actor_type)

        payload["caller_name"] = caller
        payload["caller_id"] = actor_id
        payload["caller_type"] = actor_type
        payload["caller_display_name"] = (
            caller_identity.get("display_name") if caller_identity else None
        )
        payload["caller_username"] = (
            caller_identity.get("username") if caller_identity else None
        )
        payload["caller_nickname"] = (
            caller_identity.get("nickname") if caller_identity else None
        )
        payload["caller_avatar"] = (
            caller_identity.get("avatar") if caller_identity else None
        )
        payload["caller_org_node_id"] = (
            caller_identity.get("org_node_id") if caller_identity else None
        )
        payload["caller_org_node_name"] = (
            caller_identity.get("org_node_name") if caller_identity else None
        )
        payload["caller_role_name"] = (
            caller_identity.get("display_role_name")
            if caller_identity
            and isinstance(caller_identity, dict)
            and "display_role_name" in caller_identity
            else caller_identity.get("role_name")
            if caller_identity
            else None
        )
        payload["caller_display_role_name"] = (
            caller_identity.get("display_role_name") if caller_identity else None
        )
        payload["caller_is_active"] = (
            caller_identity.get("is_active") if caller_identity else None
        )
        payload["caller_is_leader"] = (
            caller_identity.get("is_leader") if caller_identity else None
        )
        payload["caller_is_owner"] = (
            caller_identity.get("is_owner") if caller_identity else None
        )

        payload.pop("request_metadata", None)
        if not payload.get("routed_model_id"):
            payload["routed_model_id"] = metadata.get("routed_model_id")
        if not payload.get("route_reason"):
            payload["route_reason"] = metadata.get("route_reason")
        if include_payload:
            payload["request_data"] = metadata.get("request")
            payload["response_data"] = metadata.get("response")

        normalize_call_log_dict_datetimes(payload)
        result.append(payload)

    return result


__all__ = ["enrich_logs_to_dicts"]
