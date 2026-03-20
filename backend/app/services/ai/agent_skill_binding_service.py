"""
智能体技能绑定 Service / Agent Skill Binding Service
"""

from typing import Any

from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent_skill_binding import AgentSkillBinding
from app.repositories.ai.agent_repository import AgentRepository
from app.repositories.ai.agent_skill_binding_repository import (
    AgentSkillBindingRepository,
)
from app.repositories.ai.skill_package_repository import SkillPackageRepository

logger = LogManager.get_logger("ai")


class AgentSkillBindingService:
    """
    智能体技能包绑定 Service / Agent skill binding service.

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
            from app.repositories.ai.agent_repository import AdminAgentRepository
            from app.repositories.ai.skill_package_repository import (
                AdminSkillPackageRepository,
            )
            # admin/global agent 的绑定记录 tenant_id 存储为 NULL
            self.binding_repo = AgentSkillBindingRepository(db, None)
            self.package_repo = AdminSkillPackageRepository(db)  # type: ignore[assignment]
            self.agent_repo = AdminAgentRepository(db)  # type: ignore[assignment]

    async def get_agent_packages(self, agent_id: int) -> list[dict[str, Any]]:
        """
        获取智能体的所有技能包绑定（含自动绑定包）/ Get agent skill package bindings (incl. auto-bound).

        返回两类包：
        1. 自动绑定包（is_auto_bound=True）— 来自 bind_mode=auto 的 SkillPackage
        2. 显式绑定包（is_auto_bound=False）— 来自 AgentSkillBinding

        Args:
            agent_id: 智能体 ID

        Returns:
            绑定列表（含 SkillPackage 详情 + is_auto_bound 标记）
        """
        agent = await self.agent_repo.get_by_id(agent_id)

        # 绑定记录的 tenant_id 跟随 agent.tenant_id，而非调用方的 tenant_id
        # Binding tenant_id follows agent.tenant_id, not the caller's tenant_id
        agent_owner_tid = agent.tenant_id if agent else self.tenant_id
        effective_binding_repo = AgentSkillBindingRepository(self.db, agent_owner_tid)

        auto_items: list[dict[str, Any]] = []
        if agent:
            from app.ai.skills.resolver import _load_auto_bind_packages
            try:
                dm = getattr(agent, "distribution_mode", None)
                from app.enums.agent import AgentDistributionModeEnum
                from app.enums.common import ResourceScopeEnum
                if dm == AgentDistributionModeEnum.INTERNAL.value:
                    _scope = ResourceScopeEnum.ADMIN_ONLY.value
                elif dm == AgentDistributionModeEnum.ALL_TENANTS.value:
                    _scope = ResourceScopeEnum.ALL_TENANTS.value
                elif dm in (
                    AgentDistributionModeEnum.ASSIGNED_TENANTS.value,
                    getattr(AgentDistributionModeEnum, "OWNER_ONLY", object()).value
                    if hasattr(AgentDistributionModeEnum, "OWNER_ONLY") else "__none__",
                ):
                    _scope = ResourceScopeEnum.ASSIGNED_TENANTS.value
                else:
                    _scope = getattr(agent, "scope", ResourceScopeEnum.ALL_TENANTS.value)
                auto_packages = await _load_auto_bind_packages(
                    self.db,
                    agent_scope=_scope,
                    tenant_id=self.tenant_id,
                )
                for pkg in auto_packages:
                    auto_items.append({
                        "id": None,
                        "agent_id": agent_id,
                        "package_id": pkg.id,
                        "enabled": True,
                        "config_override": None,
                        "sort_order": -1,
                        "consent_mode": "auto",
                        "is_auto_bound": True,
                        "package_name": pkg.name,
                        "package_description": pkg.description,
                        "package_target_audience": pkg.target_audience,
                        "package_bind_mode": getattr(pkg, "bind_mode", "auto"),
                        "package_is_system": getattr(pkg, "is_system", False),
                    })
            except Exception as exc:
                logger.warning("Failed to load auto-bind packages for agent {}: {}", agent_id, exc)

        bindings = await effective_binding_repo.get_by_agent_id(agent_id)
        explicit_pkg_ids = set()
        explicit_items: list[dict[str, Any]] = []
        for binding in bindings:
            item: dict[str, Any] = {
                "id": binding.id,
                "agent_id": binding.agent_id,
                "package_id": binding.package_id,
                "enabled": binding.enabled,
                "config_override": binding.config_override,
                "sort_order": binding.sort_order,
                "consent_mode": binding.consent_mode,
                "is_auto_bound": False,
                "package_name": None,
                "package_description": None,
                "package_target_audience": None,
                "package_bind_mode": "manual",
                "package_is_system": False,
            }
            if binding.package:
                explicit_pkg_ids.add(binding.package.id)
                item["package_name"] = binding.package.name
                item["package_description"] = binding.package.description
                item["package_target_audience"] = binding.package.target_audience
                item["package_bind_mode"] = getattr(binding.package, "bind_mode", "manual")
                item["package_is_system"] = getattr(binding.package, "is_system", False)
            explicit_items.append(item)

        # 合并：auto 包（排除已有 explicit binding 的）+ explicit 包
        result = [item for item in auto_items if item["package_id"] not in explicit_pkg_ids]
        result.extend(explicit_items)
        return result

    async def bind_package(
        self,
        agent_id: int,
        package_id: int,
        config_override: dict[str, Any] | None = None,
        sort_order: int = 0,
        consent_mode: str = "auto",
    ) -> AgentSkillBinding:
        """
        绑定技能包到智能体 / Bind skill package to agent.

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
            "SkillPackage {} bound to agent {} (tenant={})",
            package_id, agent_id, self.tenant_id,
        )

        return binding

    async def unbind_package(self, agent_id: int, package_id: int) -> None:
        """
        解绑技能包 / Unbind skill package from agent.

        Args:
            agent_id: 智能体 ID
            package_id: 技能包 ID
        """
        binding = await self.binding_repo.get_binding(agent_id, package_id)
        if not binding:
            raise NotFoundException(message=_("agent_skill_binding.error.binding_not_found"))

        await self.binding_repo.permanent_delete(binding.id)

        logger.info(
            "SkillPackage {} unbound from agent {} (tenant={})",
            package_id, agent_id, self.tenant_id,
        )

    async def batch_bind(
        self,
        agent_id: int,
        package_ids: list[int],
        consent_modes: dict[str, str] | None = None,
    ) -> list[AgentSkillBinding]:
        """
        批量绑定技能包（替换模式：先清空再批量插入）/ Batch bind packages (replace mode: clear then insert).

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

        for pid in package_ids:
            package = pkg_map.get(pid)
            if not package:
                raise NotFoundException(
                    message=_("agent_skill_binding.error.package_not_found")
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
            "Batch bound {} skill packages to agent {} (tenant={})",
            len(package_ids), agent_id, self.tenant_id,
        )

        return bindings

    async def update_binding(
        self,
        binding_id: int,
        data: dict[str, Any],
    ) -> AgentSkillBinding:
        """
        更新绑定配置 / Update binding config.

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
        删除智能体的所有技能绑定（用于版本回滚前清空）/ Delete all skill bindings for agent (e.g. before version rollback).

        Args:
            agent_id: 智能体 ID

        Returns:
            删除的绑定数量
        """
        return await self.binding_repo.delete_by_agent_id(agent_id)


__all__ = ["AgentSkillBindingService"]
