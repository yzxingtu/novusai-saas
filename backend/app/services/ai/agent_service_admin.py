"""
Admin agent service parts / 平台管理端智能体拆分模块。
"""

from __future__ import annotations

from typing import Any

from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import AgentStatusEnum
from app.enums.ai import CallAccessChannelEnum
from app.enums.common import ResourceScopeEnum
from app.exceptions import BusinessException, NotFoundException
from app.services.ai.agent_service_support import (
    clear_cascaded_conversation_memories,
    normalize_agent_rag_config,
    validate_agent_model_ready,
    validate_agent_max_tokens_against_model,
)

logger = LogManager.get_logger("ai.agent_service")


def validate_resource_scope(scope: str | None) -> str:
    allowed = {e.value for e in ResourceScopeEnum}
    val = scope or ResourceScopeEnum.GLOBAL_SHARED.value
    if val not in allowed:
        raise BusinessException(message=_("agent.error.invalid_scope"))
    return val


async def before_create(svc: Any, data: dict[str, Any]) -> None:
    """创建前校验：平台级资源 + 资源作用域 + 名称唯一性 / Before create: platform resource, scope, name uniqueness."""
    data["owner_tenant_id"] = None
    for rejected in ("owner_type", "distribution_mode"):
        if rejected in data:
            raise BusinessException(
                message=_("agent.error.rejected_legacy_field").format(field=rejected)
            )
    data.pop("tenant_id", None)
    data["scope"] = validate_resource_scope(data.get("scope"))
    data.pop("tenant_ids", None)
    if "rag_config" in data:
        data["rag_config"] = normalize_agent_rag_config(data.get("rag_config"))

    name = data.get("name")
    if name:
        existing = await svc.repo.exists_by_name(
            name,
            owner_tenant_id=None,
        )
        if existing:
            raise BusinessException(message=_("agent.error.name_exists"))

    await validate_agent_model_ready(svc.db, model_id=data.get("model_id"))
    await validate_agent_max_tokens_against_model(
        svc.db,
        model_id=data.get("model_id"),
        max_tokens=data.get("max_tokens"),
    )


async def before_update(svc: Any, id: int, data: dict[str, Any]) -> None:
    """更新前校验：平台级资源 + 作用域 + 名称唯一性 + 系统保护 / Before update: platform resource, scope, name uniqueness, system protection."""
    agent = await svc.repo.get_by_id(id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    if agent.owner_tenant_id is not None:
        raise BusinessException(message=_("agent.error.system_protected"))

    if agent.is_system:
        protected = {
            "is_system",
            "status",
            "execution_mode",
            "owner_type",
            "tenant_id",
            "owner_tenant_id",
        }
        if protected & set(data.keys()):
            raise BusinessException(message=_("agent.error.system_protected"))

    for rejected in ("owner_type", "distribution_mode"):
        if rejected in data:
            raise BusinessException(
                message=_("agent.error.rejected_legacy_field").format(field=rejected)
            )
    data.pop("tenant_id", None)
    data.pop("owner_tenant_id", None)
    if "scope" in data and data["scope"] is not None:
        data["scope"] = validate_resource_scope(data["scope"])
    data.pop("tenant_ids", None)
    if "rag_config" in data:
        data["rag_config"] = normalize_agent_rag_config(data.get("rag_config"))

    name = data.get("name")
    if name:
        existing = await svc.repo.exists_by_name(
            name,
            owner_tenant_id=None,
            exclude_id=id,
        )
        if existing:
            raise BusinessException(message=_("agent.error.name_exists"))

    if "model_id" in data and data.get("model_id") is None:
        raise BusinessException(message=_("agent.error.invalid_chat_model"))
    if "model_id" in data:
        await validate_agent_model_ready(svc.db, model_id=data.get("model_id"))

    await validate_agent_max_tokens_against_model(
        svc.db,
        model_id=data.get("model_id", agent.model_id),
        max_tokens=data.get("max_tokens", agent.max_tokens),
    )


async def query_list(svc: Any, query: Any) -> tuple[list[Any], int]:
    """全企业智能体列表查询 / Query agent list (all tenants)."""
    return await svc.repo.query_list(query)


async def before_delete(svc: Any, id: int) -> None:
    """删除前校验：系统智能体不可删除，级联软删除对话，清理企业分配 / Before delete: system protected, cascade conversations, clear assignments."""
    agent = await svc.repo.get_by_id(id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))
    if agent.is_system:
        raise BusinessException(message=_("agent.error.system_protected"))

    conversation_targets = await svc.repo.list_conversation_memory_cleanup_targets(id)
    await svc.repo.cascade_soft_delete_conversations(id, svc._default_delete_level)
    deleted_keys = await clear_cascaded_conversation_memories(conversation_targets)
    if conversation_targets:
        logger.info(
            "Admin cascade conversation cleanup finished: agent_id={} conversations={} deleted_keys={}",
            id,
            len(conversation_targets),
            deleted_keys,
        )

    from app.repositories.system.resource_tenant_assignment_repository import (
        ResourceTenantAssignmentRepository,
    )

    rta_repo = ResourceTenantAssignmentRepository(svc.db)
    await rta_repo.delete_all_for_resource("agent", id)


async def get_access_config(svc: Any, agent_id: int) -> dict[str, Any]:
    """获取平台侧访问配置（仅 admin 角色）/ Get platform-side access config (admin roles only)."""
    agent = await svc.repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    access = await svc._get_platform_access_repo().get_by_agent_id(agent_id)
    return {
        "agent_id": agent_id,
        "admin_role_ids": getattr(access, "admin_role_ids", None) if access else None,
        "tenant_role_ids": None,
    }


async def update_access_config(
    svc: Any,
    agent_id: int,
    patch: dict[str, Any],
) -> dict[str, Any]:
    """更新平台侧访问配置（仅 admin 角色）/ Update platform-side access config (admin roles only)."""
    agent = await svc.repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    if agent.owner_tenant_id is not None:
        raise BusinessException(message=_("agent.error.system_protected"))

    allowed = frozenset({"admin_role_ids", "tenant_role_ids"})
    body = {
        "tenant_role_ids": None,
        **{k: v for k, v in patch.items() if k in allowed},
    }
    access = await svc._get_platform_access_repo().upsert(agent_id, body)
    return {
        "agent_id": agent_id,
        "admin_role_ids": getattr(access, "admin_role_ids", None),
        "tenant_role_ids": None,
    }


async def build_usage_attribution_context(
    svc: Any,
    *,
    agent: Any,
    user_id: int | None,
    user_role: str,
    user_role_id: int | None = None,
) -> dict[str, Any]:
    """构建平台管理端调用的计费归属上下文 / Build billing attribution context for platform-admin calls."""
    _ = user_role_id
    _own_tid = getattr(agent, "owner_tenant_id", None)
    return {
        "billing_tenant_id": None,
        "actor_user_id": user_id,
        "actor_user_type": user_role,
        "access_channel": CallAccessChannelEnum.ADMIN_INTERNAL.value,
        "agent_owner_type": ("platform" if _own_tid is None else "tenant"),
        "agent_owner_tenant_id": _own_tid,
        "agent_resource_scope": getattr(agent, "scope", None),
        "tenant_publication_id": None,
        "publication_enabled_snapshot": None,
        "publication_access_type_snapshot": None,
        "agent_id_snapshot": agent.id,
        "agent_name_snapshot": getattr(agent, "name", None),
        "billing_tenant_name_snapshot": None,
    }


async def update_status(svc: Any, agent_id: int, status: str) -> Any:
    """更新智能体状态（含状态机校验）/ Update agent status (with state machine check)."""
    valid_statuses = {e.value for e in AgentStatusEnum}
    if status not in valid_statuses:
        raise BusinessException(message=_("agent.error.invalid_status"))

    agent = await svc.repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    if agent.is_system:
        raise BusinessException(message=_("agent.error.system_protected"))

    if status == AgentStatusEnum.DISABLED.value and agent.status not in (
        AgentStatusEnum.PUBLISHED.value,
        AgentStatusEnum.DISABLED.value,
    ):
        raise BusinessException(message=_("agent.error.invalid_status_transition"))

    updated = await svc.repo.update(agent_id, {"status": status})

    logger.info(
        "Agent admin status updated: agent_id={} status={}",
        agent_id,
        status,
    )

    return updated
