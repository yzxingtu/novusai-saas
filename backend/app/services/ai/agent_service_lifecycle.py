"""
Agent lifecycle parts / 智能体生命周期拆分模块。
"""

from __future__ import annotations

from typing import Any

from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.common import ResourceScopeEnum
from app.exceptions import BusinessException, NotFoundException
from app.services.ai.agent_service_memory import resolve_memory_effective_config
from app.services.ai.agent_service_support import (
    clear_cascaded_conversation_memories,
    normalize_agent_rag_config,
    validate_agent_model_ready,
    validate_agent_max_tokens_against_model,
)

logger = LogManager.get_logger("ai.agent_service")


def _reject_legacy_fields(data: dict[str, Any]) -> None:
    for rejected in (
        "tenant_id",
        "owner_tenant_id",
        "owner_type",
        "distribution_mode",
    ):
        if rejected in data:
            raise BusinessException(
                message=_("agent.error.rejected_legacy_field").format(field=rejected)
            )


async def tenant_before_create(svc: Any, data: dict[str, Any]) -> None:
    """创建前校验：名称唯一性 + 插件钩子 / Before create: name uniqueness + plugin hooks."""
    from app.ai.events.hooks import HookPoint, get_hook_registry

    hook_registry = get_hook_registry()
    if hook_registry.has_hooks(HookPoint.BEFORE_AGENT_CREATE):
        ctx = await hook_registry.trigger(
            HookPoint.BEFORE_AGENT_CREATE,
            tenant_id=svc.tenant_id,
            agent_data=data,
        )
        if ctx.get("blocked"):
            raise BusinessException(
                message=ctx.get("block_reason", _("agent.error.blocked_by_hook"))
            )
        data.update(ctx.get("agent_data", data))

    _reject_legacy_fields(data)
    data["owner_tenant_id"] = svc.tenant_id
    scope_val = data.get("scope") or ResourceScopeEnum.ALL_TENANTS.value
    if scope_val not in {e.value for e in ResourceScopeEnum}:
        raise BusinessException(message=_("agent.error.invalid_scope"))
    data["scope"] = scope_val
    if "rag_config" in data:
        data["rag_config"] = normalize_agent_rag_config(data.get("rag_config"))

    name = data.get("name")
    if name:
        existing = await svc.repo.get_by_name(name)
        if existing:
            raise BusinessException(message=_("agent.error.name_exists"))

    await validate_agent_model_ready(svc.db, model_id=data.get("model_id"))
    await validate_agent_max_tokens_against_model(
        svc.db,
        model_id=data.get("model_id"),
        max_tokens=data.get("max_tokens"),
    )


async def tenant_after_create(svc: Any, instance: Any) -> None:
    """创建后：触发插件钩子 / After create: trigger plugin hooks."""
    from app.ai.events.hooks import HookPoint, get_hook_registry

    hook_registry = get_hook_registry()
    if hook_registry.has_hooks(HookPoint.AFTER_AGENT_CREATE):
        await hook_registry.trigger(
            HookPoint.AFTER_AGENT_CREATE,
            tenant_id=svc.tenant_id,
            agent_id=instance.id,
            agent_data=instance.to_dict() if hasattr(instance, "to_dict") else {},
        )


async def tenant_before_update(
    svc: Any,
    id: int,
    data: dict[str, Any],
) -> None:
    """更新前校验：名称唯一性、系统智能体保护 + 插件钩子 / Before update: name uniqueness, system agent protection, plugin hooks."""
    from app.ai.events.hooks import HookPoint, get_hook_registry

    hook_registry = get_hook_registry()
    if hook_registry.has_hooks(HookPoint.BEFORE_AGENT_UPDATE):
        ctx = await hook_registry.trigger(
            HookPoint.BEFORE_AGENT_UPDATE,
            tenant_id=svc.tenant_id,
            agent_id=id,
            updates=data,
        )
        if ctx.get("blocked"):
            raise BusinessException(
                message=ctx.get("block_reason", _("agent.error.blocked_by_hook"))
            )
        data.update(ctx.get("updates", data))

    agent = await svc.repo.get_by_id(id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    if agent.owner_tenant_id != svc.tenant_id:
        raise BusinessException(message=_("agent.error.system_protected"))

    _reject_legacy_fields(data)
    if (
        "scope" in data
        and data["scope"] is not None
        and data["scope"] not in {e.value for e in ResourceScopeEnum}
    ):
        raise BusinessException(message=_("agent.error.invalid_scope"))
    if "rag_config" in data:
        data["rag_config"] = normalize_agent_rag_config(data.get("rag_config"))

    if agent.is_system:
        protected = {"is_system", "status", "execution_mode"}
        if protected & set(data.keys()):
            raise BusinessException(message=_("agent.error.system_protected"))

    name = data.get("name")
    if name:
        existing = await svc.repo.get_by_name(name, exclude_id=id)
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


async def tenant_after_update(svc: Any, instance: Any) -> None:
    """更新后：触发插件钩子 / After update: trigger plugin hooks."""
    from app.ai.events.hooks import HookPoint, get_hook_registry

    hook_registry = get_hook_registry()
    if hook_registry.has_hooks(HookPoint.AFTER_AGENT_UPDATE):
        await hook_registry.trigger(
            HookPoint.AFTER_AGENT_UPDATE,
            tenant_id=svc.tenant_id,
            agent_id=instance.id,
            updates=instance.to_dict() if hasattr(instance, "to_dict") else {},
        )


async def tenant_before_delete(svc: Any, id: int) -> None:
    """删除前校验：系统智能体不可删除，级联软删除对话 + 插件钩子 / Before delete: system protected, cascade soft-delete conversations, plugin hooks."""
    from app.ai.events.hooks import HookPoint, get_hook_registry

    hook_registry = get_hook_registry()
    if hook_registry.has_hooks(HookPoint.BEFORE_AGENT_DELETE):
        ctx = await hook_registry.trigger(
            HookPoint.BEFORE_AGENT_DELETE,
            tenant_id=svc.tenant_id,
            agent_id=id,
        )
        if ctx.get("blocked"):
            raise BusinessException(
                message=ctx.get("block_reason", _("agent.error.blocked_by_hook"))
            )

    agent = await svc.repo.get_by_id(id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    if agent.owner_tenant_id != svc.tenant_id:
        raise BusinessException(message=_("agent.error.system_protected"))

    if agent.is_system:
        raise BusinessException(message=_("agent.error.system_protected"))

    conversation_targets = await svc.repo.list_conversation_memory_cleanup_targets(id)
    await svc.repo.cascade_soft_delete_conversations(id, svc._default_delete_level)
    deleted_keys = await clear_cascaded_conversation_memories(conversation_targets)
    if conversation_targets:
        logger.info(
            "Cascade conversation cleanup finished: agent_id={} conversations={} deleted_keys={}",
            id,
            len(conversation_targets),
            deleted_keys,
        )


async def tenant_after_delete(svc: Any, instance: Any) -> None:
    """删除后：触发插件钩子 / After delete: trigger plugin hooks."""
    from app.ai.events.hooks import HookPoint, get_hook_registry

    hook_registry = get_hook_registry()
    if hook_registry.has_hooks(HookPoint.AFTER_AGENT_DELETE):
        await hook_registry.trigger(
            HookPoint.AFTER_AGENT_DELETE,
            tenant_id=svc.tenant_id,
            agent_id=instance.id,
        )


async def promote_to_global(svc: Any, id: int) -> Any | None:
    """推进到总回收站，级联推进对话记录 / Promote to global recycle bin and cascade conversations."""
    instance = await svc.repo.promote_to_global_by_id(
        id,
        delete_level=svc._default_delete_level,
    )
    if instance is None:
        return None

    await svc.repo.cascade_promote_conversations(id)
    return instance


async def after_restore(svc: Any, instance: Any) -> None:
    """恢复后：级联恢复对话记录 / After restore: cascade restore conversations."""
    await svc.repo.cascade_restore_conversations(instance.id)


async def get_agent_detail(svc: Any, agent_id: int) -> dict[str, Any]:
    """获取智能体详情（含关联模型信息） / Get agent detail (with model info)."""
    agent = await svc.repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    result = agent.to_dict()
    result["owner_tenant_id"] = agent.owner_tenant_id
    result["tenant_id"] = agent.owner_tenant_id
    result["owner_type"] = "tenant" if agent.owner_tenant_id is not None else "platform"
    result["scope"] = getattr(agent, "scope", None)
    result["model_name"] = None
    result["model_code"] = None

    try:
        model_obj = getattr(agent, "model", None)
        if model_obj is not None:
            result["model_name"] = model_obj.name
            result["model_code"] = model_obj.code
    except AttributeError:
        pass

    resolved = await resolve_memory_effective_config(svc, agent_id)
    result["memory_enabled"] = bool(getattr(agent, "memory_enabled", True))
    result["effective_memory_enabled"] = resolved["effective_memory_enabled"]
    result["memory_disabled_by_tenant"] = resolved["tenant_agent_memory_disabled"]

    return result
