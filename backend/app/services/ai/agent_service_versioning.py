"""
Agent versioning parts / 智能体版本管理拆分模块。
"""

from __future__ import annotations

import inspect
from typing import Any

from app.configs.service import PLATFORM_TENANT_ID
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import AgentStatusEnum
from app.exceptions import NotFoundException
from app.repositories.ai.agent_version_repository import AgentVersionRepository
from app.services.ai.agent_service_support import VERSION_SNAPSHOT_FIELDS

logger = LogManager.get_logger("ai.agent_service")


def resolve_version_tenant_id(tenant_id: int | None) -> int:
    """Resolve version snapshot tenant scope / 解析版本快照使用的租户范围。"""
    return tenant_id if tenant_id is not None else PLATFORM_TENANT_ID


def get_version_repo(
    db: Any,
    tenant_id: int | None,
) -> AgentVersionRepository:
    """获取版本 Repository / Get version repository."""
    return AgentVersionRepository(db, resolve_version_tenant_id(tenant_id))


async def _await_if_needed(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def snapshot_skill_grants(svc: Any, agent_id: int) -> list[dict[str, Any]]:
    """快照当前 Agent 的技能授权列表（用于版本发布） / Snapshot agent skill grants (for version publish)."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.ai.agent_skill_grant import AgentSkillGrant
    from app.models.ai.skill import Skill

    result = await svc.db.execute(
        select(AgentSkillGrant)
        .options(selectinload(AgentSkillGrant.skill).selectinload(Skill.package))
        .where(
            AgentSkillGrant.agent_id == agent_id,
            AgentSkillGrant.is_deleted.is_(False),
        )
        .order_by(AgentSkillGrant.sort_order),
    )
    grants = result.scalars().all()

    return [
        {
            "skill_id": grant.skill_id,
            "skill_name": grant.skill.name if grant.skill else None,
            "package_id": grant.skill.package_id if grant.skill else None,
            "package_name": (
                grant.skill.package.name if grant.skill and grant.skill.package else None
            ),
            "enabled": grant.enabled,
            "default_consent_mode": grant.default_consent_mode,
            "capability_consent_overrides": grant.capability_consent_overrides,
            "sort_order": grant.sort_order,
            "config_override": grant.config_override,
        }
        for grant in grants
    ]


async def restore_skill_grants(
    svc: Any,
    agent_id: int,
    grants_snapshot: list[dict[str, Any]] | None,
) -> None:
    """从版本快照恢复技能授权（用于版本回滚） / Restore skill grants from snapshot (for rollback)."""
    if grants_snapshot is None:
        return

    from app.services.ai.agent_skill_grant_service import AgentSkillGrantService

    grant_svc = AgentSkillGrantService(svc.db, svc.tenant_id)

    from app.models.ai.skill import Skill

    valid_items: list[dict[str, Any]] = []
    default_consent_modes: dict[str, str] = {}

    for item in grants_snapshot:
        skill_id = item.get("skill_id")
        if not skill_id:
            continue
        skill = await svc.db.get(Skill, skill_id)
        if not skill or skill.is_deleted:
            logger.warning(
                "Skipping deleted skill {} during rollback for agent {}",
                skill_id,
                agent_id,
            )
            continue

        valid_items.append(item)
        default_consent_modes[str(skill_id)] = item.get("default_consent_mode", "auto")

    if not valid_items:
        await grant_svc.delete_all_for_agent(agent_id)
        return

    grants = await grant_svc.batch_bind(
        agent_id=agent_id,
        skill_ids=[int(item["skill_id"]) for item in valid_items],
        default_consent_modes=default_consent_modes,
    )
    grant_map = {grant.skill_id: grant for grant in grants}

    for item in valid_items:
        skill_id = int(item["skill_id"])
        grant = grant_map.get(skill_id)
        if not grant:
            continue

        await grant_svc.update_grant(
            grant.id,
            {
                "enabled": item.get("enabled", True),
                "default_consent_mode": item.get("default_consent_mode", "auto"),
                "capability_consent_overrides": item.get(
                    "capability_consent_overrides"
                ),
                "sort_order": item.get("sort_order", 0),
                "config_override": item.get("config_override"),
            },
        )


async def publish_agent(
    svc: Any,
    agent_id: int,
    change_log: str | None = None,
    created_by: int | None = None,
) -> Any:
    """发布智能体 / Publish agent."""
    agent = await svc.repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    version_repo = svc._get_version_repo()
    latest_version = await version_repo.get_latest_version_number(agent_id)
    latest_version = await _await_if_needed(latest_version)
    new_version = (latest_version or 0) + 1

    version_tenant_id = resolve_version_tenant_id(svc.tenant_id)
    version_data: dict[str, Any] = {
        "agent_id": agent_id,
        "version": new_version,
        "tenant_id": version_tenant_id,
        "change_log": change_log,
        "created_by": created_by,
    }
    for field_name in VERSION_SNAPSHOT_FIELDS:
        version_data[field_name] = getattr(agent, field_name)

    version_data["skill_grant_snapshot"] = await svc._snapshot_skill_grants(agent_id)

    await version_repo.create(version_data)

    updated = await svc.repo.update(
        agent_id,
        {
            "status": AgentStatusEnum.PUBLISHED.value,
            "published_version": new_version,
        },
    )

    logger.info(
        "Agent published: agent_id={} tenant_id={} version={}",
        agent_id,
        version_tenant_id,
        new_version,
    )

    return updated


async def rollback_agent(
    svc: Any,
    agent_id: int,
    version: int,
) -> Any:
    """回滚智能体到指定版本 / Rollback agent to given version."""
    agent = await svc.repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    version_repo = svc._get_version_repo()
    version_record = await version_repo.get_by_agent_and_version(agent_id, version)
    version_record = await _await_if_needed(version_record)
    if not version_record:
        raise NotFoundException(message=_("agent.version.error.not_found"))

    rollback_data: dict[str, Any] = {
        "status": AgentStatusEnum.DRAFT.value,
    }
    for field_name in VERSION_SNAPSHOT_FIELDS:
        rollback_data[field_name] = await _await_if_needed(
            getattr(version_record, field_name)
        )

    updated = await svc.repo.update(agent_id, rollback_data)

    await svc._restore_skill_grants(
        agent_id,
        await _await_if_needed(version_record.skill_grant_snapshot),
    )

    logger.info(
        "Agent rolled back: agent_id={} tenant_id={} version={}",
        agent_id,
        svc.tenant_id,
        version,
    )

    return updated


async def get_versions(svc: Any, agent_id: int) -> list[dict[str, Any]]:
    """获取智能体版本历史列表 / Get agent version history list."""
    agent = await svc.repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(message=_("agent.error.not_found"))

    version_repo = svc._get_version_repo()
    versions = await version_repo.get_versions_by_agent(agent_id)
    versions = await _await_if_needed(versions)
    return [v.to_dict() for v in versions]


async def get_version_detail(
    svc: Any,
    agent_id: int,
    version: int,
) -> dict[str, Any]:
    """获取智能体版本详情 / Get agent version detail."""
    version_repo = svc._get_version_repo()
    version_record = await version_repo.get_by_agent_and_version(agent_id, version)
    version_record = await _await_if_needed(version_record)
    if not version_record:
        raise NotFoundException(message=_("agent.version.error.not_found"))
    return version_record.to_dict()


async def diff_versions(
    svc: Any,
    agent_id: int,
    v1: int,
    v2: int,
) -> dict[str, Any]:
    """对比两个版本的字段差异 / Diff two versions by fields."""
    version_repo = svc._get_version_repo()

    record_v1 = await version_repo.get_by_agent_and_version(agent_id, v1)
    record_v1 = await _await_if_needed(record_v1)
    if not record_v1:
        raise NotFoundException(
            message=_("agent.version.error.version_not_found_n", version=v1)
        )

    record_v2 = await version_repo.get_by_agent_and_version(agent_id, v2)
    record_v2 = await _await_if_needed(record_v2)
    if not record_v2:
        raise NotFoundException(
            message=_("agent.version.error.version_not_found_n", version=v2)
        )

    diff: dict[str, Any] = {}
    for field_name in VERSION_SNAPSHOT_FIELDS:
        val1 = await _await_if_needed(getattr(record_v1, field_name))
        val2 = await _await_if_needed(getattr(record_v2, field_name))
        if val1 != val2:
            diff[field_name] = {"v1": val1, "v2": val2}

    return {
        "agent_id": agent_id,
        "v1": v1,
        "v2": v2,
        "changes": diff,
    }
