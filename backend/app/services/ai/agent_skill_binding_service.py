"""
智能体技能绑定 Service
"""

from typing import Any

from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent_skill_binding import AgentSkillBinding
from app.repositories.ai.agent_skill_binding_repository import AgentSkillBindingRepository
from app.repositories.ai.skill_package_repository import SkillPackageRepository
from app.repositories.ai.agent_repository import AgentRepository
from app.enums.common import ResourceScopeEnum

logger = LogManager.get_logger("ai")


class AgentSkillBindingService:
    """
    智能体技能包绑定 Service

    管理 Agent 与 SkillPackage 的 M:N 关系
    """

    def __init__(self, db, tenant_id: int | None):
        self.db = db
        self.tenant_id = tenant_id
        if tenant_id is not None:
            self.binding_repo = AgentSkillBindingRepository(db, tenant_id)
            self.package_repo = SkillPackageRepository(db, tenant_id)
            self.agent_repo = AgentRepository(db, tenant_id)
        else:
            from app.repositories.ai.skill_package_repository import AdminSkillPackageRepository
            from app.repositories.ai.agent_repository import AdminAgentRepository
            self.binding_repo = AgentSkillBindingRepository(db, 0)
            self.package_repo = AdminSkillPackageRepository(db)  # type: ignore[assignment]
            self.agent_repo = AdminAgentRepository(db)  # type: ignore[assignment]

    async def get_agent_packages(self, agent_id: int) -> list[dict[str, Any]]:
        """
        获取智能体的所有技能包绑定

        Args:
            agent_id: 智能体 ID

        Returns:
            绑定列表（含 SkillPackage 详情）
        """
        bindings = await self.binding_repo.get_by_agent_id(agent_id)
        result = []
        for binding in bindings:
            item = {
                "id": binding.id,
                "agent_id": binding.agent_id,
                "package_id": binding.package_id,
                "enabled": binding.enabled,
                "config_override": binding.config_override,
                "sort_order": binding.sort_order,
                "consent_mode": binding.consent_mode,
            }
            if binding.package:
                item["package"] = {
                    "id": binding.package.id,
                    "name": binding.package.name,
                    "description": binding.package.description,
                    "avatar": binding.package.avatar,
                    "scope": binding.package.scope,
                    "is_active": binding.package.is_active,
                }
            result.append(item)
        return result

    @staticmethod
    def _validate_scope(
        agent_scope: str,
        pkg_scope: str,
        agent_tenant_id: int | None,
        pkg_tenant_id: int | None,
    ) -> None:
        """
        校验 Agent scope 与 SkillPackage scope 的兼容性。

        Rules:
          - tenant agent → 同租户 tenant 包 + global 包 + admin 包
          - admin agent  → admin 包 + global 包
          - global agent → global 包 + admin 包 + 任意 tenant 包
        """
        a = agent_scope
        p = pkg_scope

        if a == ResourceScopeEnum.TENANT.value:
            if p == ResourceScopeEnum.TENANT.value:
                if agent_tenant_id != pkg_tenant_id:
                    raise BusinessException(
                        message=_("agent_skill_binding.error.scope_mismatch")
                    )
            elif p not in (
                ResourceScopeEnum.ADMIN.value,
                ResourceScopeEnum.GLOBAL.value,
            ):
                raise BusinessException(
                    message=_("agent_skill_binding.error.scope_mismatch")
                )
        elif a == ResourceScopeEnum.ADMIN.value:
            if p not in (
                ResourceScopeEnum.ADMIN.value,
                ResourceScopeEnum.GLOBAL.value,
            ):
                raise BusinessException(
                    message=_("agent_skill_binding.error.scope_mismatch")
                )
        elif a == ResourceScopeEnum.GLOBAL.value:
            if p not in (
                ResourceScopeEnum.GLOBAL.value,
                ResourceScopeEnum.ADMIN.value,
                ResourceScopeEnum.TENANT.value,
            ):
                raise BusinessException(
                    message=_("agent_skill_binding.error.scope_mismatch")
                )

    async def bind_package(
        self,
        agent_id: int,
        package_id: int,
        config_override: dict[str, Any] | None = None,
        sort_order: int = 0,
        consent_mode: str = "auto",
    ) -> AgentSkillBinding:
        """
        绑定技能包到智能体

        Args:
            agent_id: 智能体 ID
            package_id: 技能包 ID
            config_override: 配置覆盖
            sort_order: 排序
            consent_mode: 工具执行授权模式 (auto/ask/reject)

        Returns:
            AgentSkillBinding 实例
        """
        agent = await self.agent_repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent_skill_binding.error.agent_not_found"))

        package = await self.package_repo.get_by_id(package_id)
        if not package:
            raise NotFoundException(message=_("agent_skill_binding.error.package_not_found"))

        self._validate_scope(
            agent.scope, package.scope, agent.tenant_id, package.tenant_id,
        )

        existing = await self.binding_repo.get_binding(agent_id, package_id)
        if existing:
            raise BusinessException(message=_("agent_skill_binding.error.already_bound"))

        binding = await self.binding_repo.create({
            "agent_id": agent_id,
            "package_id": package_id,
            "tenant_id": self.tenant_id,
            "enabled": True,
            "config_override": config_override,
            "sort_order": sort_order,
            "consent_mode": consent_mode,
        })

        logger.info(
            "SkillPackage %d bound to agent %d (tenant=%s)",
            package_id, agent_id, self.tenant_id,
        )

        return binding

    async def unbind_package(self, agent_id: int, package_id: int) -> None:
        """
        解绑技能包

        Args:
            agent_id: 智能体 ID
            package_id: 技能包 ID
        """
        binding = await self.binding_repo.get_binding(agent_id, package_id)
        if not binding:
            raise NotFoundException(message=_("agent_skill_binding.error.binding_not_found"))

        await self.binding_repo.permanent_delete(binding.id)

        logger.info(
            "SkillPackage %d unbound from agent %d (tenant=%s)",
            package_id, agent_id, self.tenant_id,
        )

    async def batch_bind(
        self,
        agent_id: int,
        package_ids: list[int],
        consent_modes: dict[str, str] | None = None,
    ) -> list[AgentSkillBinding]:
        """
        批量绑定技能包（替换模式：先清空再批量插入）

        Args:
            agent_id: 智能体 ID
            package_ids: 技能包 ID 列表（有序）

        Returns:
            新绑定列表
        """
        agent = await self.agent_repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent_skill_binding.error.agent_not_found"))

        # 批量查询所有 package_id（避免 N+1）
        packages = await self.package_repo.get_by_ids(package_ids)
        pkg_map = {pkg.id: pkg for pkg in packages}

        # 校验所有 package_id 存在且 scope 兼容
        for pid in package_ids:
            package = pkg_map.get(pid)
            if not package:
                raise NotFoundException(
                    message=_("agent_skill_binding.error.package_not_found")
                )
            self._validate_scope(
                agent.scope, package.scope, agent.tenant_id, package.tenant_id,
            )

        # 使用 savepoint 保护 delete + create 的原子性
        # 如果批量插入中途失败，回滚到 savepoint，保留原有绑定
        async with self.db.begin_nested():
            # 清空已有绑定
            await self.binding_repo.delete_by_agent_id(agent_id)

            # 批量插入
            _modes = consent_modes or {}
            bindings = []
            for idx, pid in enumerate(package_ids):
                row: dict[str, Any] = {
                    "agent_id": agent_id,
                    "package_id": pid,
                    "tenant_id": self.tenant_id,
                    "enabled": True,
                    "sort_order": idx,
                }
                _cm = _modes.get(str(pid))
                if _cm and _cm in ("auto", "ask", "reject"):
                    row["consent_mode"] = _cm
                binding = await self.binding_repo.create(row)
                bindings.append(binding)

        logger.info(
            "Batch bound %d skill packages to agent %d (tenant=%s)",
            len(package_ids), agent_id, self.tenant_id,
        )

        return bindings

    async def update_binding(
        self,
        binding_id: int,
        data: dict[str, Any],
    ) -> AgentSkillBinding:
        """
        更新绑定配置

        Args:
            binding_id: 绑定 ID
            data: 更新数据（enabled / config_override / sort_order）

        Returns:
            更新后的 AgentSkillBinding
        """
        binding = await self.binding_repo.get_by_id(binding_id)
        if not binding:
            raise NotFoundException(message=_("agent_skill_binding.error.binding_not_found"))

        updated = await self.binding_repo.update(binding_id, data)
        return updated

    async def delete_all_for_agent(self, agent_id: int) -> int:
        """
        删除智能体的所有技能绑定（用于版本回滚前清空）

        Args:
            agent_id: 智能体 ID

        Returns:
            删除的绑定数量
        """
        return await self.binding_repo.delete_by_agent_id(agent_id)


__all__ = ["AgentSkillBindingService"]
