"""
Agent memory config parts / 智能体记忆配置拆分模块。
"""

from __future__ import annotations

import inspect
from typing import Any

from app.configs.service import ConfigService
from app.core.i18n import _
from app.exceptions import BusinessException, NotFoundException
from app.repositories.ai.agent_memory_override_repository import (
    AgentMemoryOverrideRepository,
)


async def get_platform_default_memory_enabled(db: Any) -> bool:
    """获取平台默认记忆开关（默认 True） / Get platform default memory enabled (default True)."""
    config_service = ConfigService(db)
    value = await config_service.get_platform_config(
        "platform_default_memory_enabled",
        default=True,
    )
    if inspect.isawaitable(value):
        value = await value
    return bool(value)


async def resolve_memory_effective_config(
    svc: Any,
    agent_id: int,
) -> dict[str, bool]:
    """
    计算智能体记忆最终生效状态（企业侧） / Resolve effective memory config (tenant side).
    规则：effective = platform AND admin_agent AND (NOT tenant_disabled).
    """
    agent = await svc.repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    if hasattr(svc, "_get_platform_default_memory_enabled"):
        platform_enabled = await svc._get_platform_default_memory_enabled()
    else:
        platform_enabled = await get_platform_default_memory_enabled(svc.db)
    admin_agent_enabled = bool(getattr(agent, "memory_enabled", True))

    if hasattr(svc, "_get_memory_override_repo"):
        override_repo = svc._get_memory_override_repo()
    else:
        override_repo = AgentMemoryOverrideRepository(svc.db, svc.tenant_id)
    override = await override_repo.get_by_agent_id(agent_id)
    tenant_disabled = bool(override and override.disabled)

    effective = platform_enabled and admin_agent_enabled and (not tenant_disabled)

    return {
        "platform_default_memory_enabled": platform_enabled,
        "admin_agent_memory_enabled": admin_agent_enabled,
        "tenant_agent_memory_disabled": tenant_disabled,
        "effective_memory_enabled": effective,
    }


async def get_memory_config(
    svc: Any,
    agent_id: int,
) -> dict[str, Any]:
    """获取企业侧智能体记忆配置状态 / Get tenant-side agent memory config."""
    await svc.get_agent_detail(agent_id)
    resolved = await resolve_memory_effective_config(svc, agent_id)
    return {
        "agent_id": agent_id,
        **resolved,
    }


async def set_memory_disabled(
    svc: Any,
    agent_id: int,
    disabled: bool,
) -> dict[str, Any]:
    """设置企业侧“关闭记忆”覆盖（仅支持关闭/恢复默认） / Set tenant memory-disabled override (disable or restore default)."""
    agent = await svc.repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    if agent.owner_tenant_id != svc.tenant_id:
        raise BusinessException(message=_("agent.error.system_protected"))

    if hasattr(svc, "_get_memory_override_repo"):
        override_repo = svc._get_memory_override_repo()
    else:
        override_repo = AgentMemoryOverrideRepository(svc.db, svc.tenant_id)
    existing = await override_repo.get_by_agent_id(agent_id)

    if disabled:
        if existing:
            await override_repo.update(existing.id, {"disabled": True})
        else:
            await override_repo.create(
                {
                    "tenant_id": svc.tenant_id,
                    "agent_id": agent_id,
                    "disabled": True,
                }
            )
    else:
        if existing:
            await override_repo.delete(existing.id, soft=False)

    if hasattr(svc, "get_memory_config"):
        return await svc.get_memory_config(agent_id)
    return await get_memory_config(svc, agent_id)


async def get_admin_memory_config(
    svc: Any,
    agent_id: int,
) -> dict[str, Any]:
    """获取管理端智能体记忆配置状态 / Get admin-side agent memory config."""
    agent = await svc.repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    if hasattr(svc, "_get_platform_default_memory_enabled"):
        platform_enabled = await svc._get_platform_default_memory_enabled()
    else:
        platform_enabled = await get_platform_default_memory_enabled(svc.db)
    admin_agent_enabled = bool(getattr(agent, "memory_enabled", True))
    effective = platform_enabled and admin_agent_enabled

    return {
        "agent_id": agent_id,
        "platform_default_memory_enabled": platform_enabled,
        "admin_agent_memory_enabled": admin_agent_enabled,
        "tenant_agent_memory_disabled": False,
        "effective_memory_enabled": effective,
    }


async def set_memory_enabled(
    svc: Any,
    agent_id: int,
    enabled: bool,
) -> dict[str, Any]:
    """设置管理端 Agent 级记忆开关 / Set admin-side agent-level memory toggle."""
    agent = await svc.repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    await svc.repo.update(agent_id, {"memory_enabled": bool(enabled)})
    if hasattr(svc, "get_memory_config"):
        return await svc.get_memory_config(agent_id)
    return await get_admin_memory_config(svc, agent_id)
