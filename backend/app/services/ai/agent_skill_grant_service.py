"""
Agent skill grant service.
"""

from typing import Any

from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent_skill_grant import AgentSkillGrant
from app.repositories.ai.agent_repository import AgentRepository
from app.repositories.ai.agent_skill_grant_repository import (
    AgentSkillGrantRepository,
)
from app.repositories.ai.skill_repository import AdminSkillRepository, SkillRepository

logger = LogManager.get_logger("ai")


class AgentSkillGrantService:
    """Manage direct Agent -> Skill grants."""

    def __init__(self, db, tenant_id: int | None):
        self.db = db
        self.tenant_id = tenant_id
        if tenant_id is not None:
            self.grant_repo = AgentSkillGrantRepository(db, tenant_id)
            self.skill_repo = SkillRepository(db, tenant_id)
            self.agent_repo = AgentRepository(db, tenant_id)
        else:
            from app.repositories.ai.agent_repository import AdminAgentRepository
            from app.repositories.ai.skill_repository import AdminSkillRepository

            self.grant_repo = AgentSkillGrantRepository(db, None)
            self.skill_repo = AdminSkillRepository(db)  # type: ignore[assignment]  # 类型存根 / typing stub
            self.agent_repo = AdminAgentRepository(db)  # type: ignore[assignment]  # 类型存根 / typing stub

    @staticmethod
    def _skill_runtime_available(skill: Any) -> bool:
        if not skill:
            return False
        if not getattr(skill, "is_active", True) or getattr(skill, "is_deleted", False):
            return False
        package = getattr(skill, "package", None)
        if package is None:
            return False
        return bool(
            getattr(package, "is_active", True)
            and not getattr(package, "is_deleted", False)
        )

    def _grant_to_item(self, grant: AgentSkillGrant) -> dict[str, Any]:
        """Serialize a grant row with joined skill/package metadata."""
        item: dict[str, Any] = {
            "id": grant.id,
            "agent_id": grant.agent_id,
            "skill_id": grant.skill_id,
            "enabled": grant.enabled,
            "config_override": grant.config_override,
            "sort_order": grant.sort_order,
            "default_consent_mode": grant.default_consent_mode,
            "capability_consent_overrides": grant.capability_consent_overrides,
            "skill_name": None,
            "skill_key": None,
            "skill_description": None,
            "skill_type": None,
            "skill_source_type": None,
            "skill_status": None,
            "package_id": None,
            "package_name": None,
            "package_description": None,
            "package_is_system": False,
        }

        skill = grant.skill
        if not skill:
            return item

        item["skill_name"] = skill.name
        item["skill_key"] = getattr(skill, "key", None)
        item["skill_description"] = skill.description
        item["skill_type"] = skill.type
        item["skill_source_type"] = getattr(skill, "source_type", None)
        item["skill_status"] = getattr(skill, "status", None)
        item["package_id"] = skill.package_id

        package = getattr(skill, "package", None)
        if package is not None:
            item["package_name"] = package.name
            item["package_description"] = package.description
            item["package_is_system"] = bool(getattr(package, "is_system", False))

        return item

    def serialize_grant_public(self, grant: AgentSkillGrant) -> dict[str, Any]:
        """Single grant response payload."""
        return self._grant_to_item(grant)

    async def _validate_skill_accessible(self, skill_id: int):
        """Validate skill exists and is visible in the current scope."""
        skill = await self.skill_repo.get_by_id(skill_id)
        if not self._skill_runtime_available(skill):
            raise NotFoundException(
                message=_("agent_skill_grant.error.skill_not_found"),
            )
        return skill

    async def get_agent_skills(self, agent_id: int) -> list[dict[str, Any]]:
        """Get all skill grants for an agent."""
        agent = await self.agent_repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(
                message=_("agent_skill_grant.error.agent_not_found"),
            )

        owner_tenant_id = getattr(agent, "owner_tenant_id", self.tenant_id)
        effective_repo = AgentSkillGrantRepository(self.db, owner_tenant_id)
        grants = await effective_repo.get_by_agent_id(agent_id)
        visible_skill_repo = getattr(self, "skill_repo", None)
        if owner_tenant_id != self.tenant_id or visible_skill_repo is None:
            visible_skill_repo = (
                SkillRepository(self.db, owner_tenant_id)
                if owner_tenant_id is not None
                else AdminSkillRepository(self.db)
            )
        visible_skills = await visible_skill_repo.get_by_ids(
            [grant.skill_id for grant in grants]
        )
        visible_skill_ids = {
            skill.id for skill in visible_skills if self._skill_runtime_available(skill)
        }
        return [
            self._grant_to_item(grant)
            for grant in grants
            if grant.skill_id in visible_skill_ids
            and self._skill_runtime_available(getattr(grant, "skill", None))
        ]

    async def bind_skill(
        self,
        agent_id: int,
        skill_id: int,
        config_override: dict[str, Any] | None = None,
        sort_order: int = 0,
        default_consent_mode: str = "auto",
        capability_consent_overrides: dict[str, str] | None = None,
    ) -> AgentSkillGrant:
        """Bind a single skill to an agent."""
        agent = await self.agent_repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(
                message=_("agent_skill_grant.error.agent_not_found"),
            )

        await self._validate_skill_accessible(skill_id)

        existing = await self.grant_repo.get_grant(agent_id, skill_id)
        if existing:
            raise BusinessException(
                message=_("agent_skill_grant.error.already_bound"),
            )

        grant = await self.grant_repo.create(
            {
                "agent_id": agent_id,
                "skill_id": skill_id,
                "tenant_id": getattr(agent, "owner_tenant_id", None),
                "enabled": True,
                "config_override": config_override,
                "sort_order": sort_order,
                "default_consent_mode": default_consent_mode,
                "capability_consent_overrides": capability_consent_overrides,
            }
        )

        logger.info(
            "Skill {} granted to agent {} (tenant={})",
            skill_id,
            agent_id,
            getattr(agent, "owner_tenant_id", None),
        )

        return grant

    async def unbind_skill(self, agent_id: int, skill_id: int) -> None:
        """Unbind a skill from an agent."""
        grant = await self.grant_repo.get_grant(agent_id, skill_id)
        if not grant:
            raise NotFoundException(
                message=_("agent_skill_grant.error.binding_not_found"),
            )

        deleted = await self.grant_repo.delete(grant.id, soft=False)
        if not deleted:
            raise BusinessException(message=_("common.failed"))

        logger.info(
            "Skill {} unbound from agent {} (tenant={})",
            skill_id,
            agent_id,
            self.tenant_id,
        )

    async def batch_bind(
        self,
        agent_id: int,
        skill_ids: list[int],
        default_consent_modes: dict[str, str] | None = None,
    ) -> list[AgentSkillGrant]:
        """Replace all grants on an agent with the provided ordered skill list."""
        agent = await self.agent_repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(
                message=_("agent_skill_grant.error.agent_not_found"),
            )

        deduped_skill_ids = list(dict.fromkeys(skill_ids))
        skills = await self.skill_repo.get_by_ids(deduped_skill_ids)
        skill_map = {
            skill.id: skill for skill in skills if self._skill_runtime_available(skill)
        }

        for skill_id in deduped_skill_ids:
            if skill_map.get(skill_id) is None:
                raise NotFoundException(
                    message=_("agent_skill_grant.error.skill_not_found"),
                )

        async with self.db.begin_nested():
            await self.grant_repo.delete_by_agent_id(agent_id)

            grants: list[AgentSkillGrant] = []
            modes = default_consent_modes or {}
            owner_tenant_id = getattr(agent, "owner_tenant_id", None)
            for idx, skill_id in enumerate(deduped_skill_ids):
                row: dict[str, Any] = {
                    "agent_id": agent_id,
                    "skill_id": skill_id,
                    "tenant_id": owner_tenant_id,
                    "enabled": True,
                    "sort_order": idx,
                }
                consent_mode = modes.get(str(skill_id))
                if consent_mode and consent_mode in ("auto", "ask", "reject"):
                    row["default_consent_mode"] = consent_mode
                grant = await self.grant_repo.create(row)
                grants.append(grant)

        logger.info(
            "Batch granted {} skills to agent {} (tenant={})",
            len(deduped_skill_ids),
            agent_id,
            getattr(agent, "owner_tenant_id", None),
        )

        return grants

    async def update_grant(
        self,
        grant_id: int,
        data: dict[str, Any],
    ) -> AgentSkillGrant:
        """Update grant config."""
        grant = await self.grant_repo.get_by_id(grant_id)
        if not grant:
            raise NotFoundException(
                message=_("agent_skill_grant.error.binding_not_found"),
            )

        updated = await self.grant_repo.update(grant_id, data)
        return updated

    async def get_by_id(self, grant_id: int) -> AgentSkillGrant | None:
        """Get grant detail."""
        return await self.grant_repo.get_by_id(grant_id)

    async def delete_all_for_agent(self, agent_id: int) -> int:
        """Delete all grants for an agent."""
        return await self.grant_repo.delete_by_agent_id(agent_id)


__all__ = ["AgentSkillGrantService"]
