"""
技能包 Service / Skill Package Service
"""

from typing import Any

from app.core.base_service import GlobalService, TenantService
from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.skill_package import SkillPackage
from app.repositories.ai.skill_package_repository import (
    AdminSkillPackageRepository,
    SkillPackageRepository,
)
from app.schemas.common.select import SelectResponse

logger = LogManager.get_logger("ai")


class SkillPackageService(TenantService[SkillPackage, SkillPackageRepository]):
    """
    企业端技能包 Service / Tenant skill package service.

    提供技能包的创建、更新、删除等业务逻辑
    """

    model = SkillPackage
    repository_class = SkillPackageRepository

    async def _before_create(self, data: dict[str, Any]) -> None:
        """创建前校验：名称唯一性 / Before create: name uniqueness."""
        await super()._before_create(data)

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name(name)
            if existing:
                raise BusinessException(message=_("skill_package.error.name_exists"))

        from app.enums.common import SkillBindModeEnum
        data["bind_mode"] = SkillBindModeEnum.MANUAL.value

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """更新前校验：名称唯一性、系统技能包保护 / Before update: name uniqueness, system package protection."""
        await super()._before_update(id, data)

        pkg = await self.repo.get_by_id(id)
        if not pkg:
            raise NotFoundException(message=_("skill_package.error.not_found"))

        if pkg.tenant_id != self.tenant_id:
            raise BusinessException(message=_("skill_package.error.system_protected"))

        if pkg.is_system:
            protected = {"is_system", "is_active", "bind_mode"}
            if protected & set(data.keys()):
                raise BusinessException(message=_("skill_package.error.system_protected"))

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name(name, exclude_id=id)
            if existing:
                raise BusinessException(message=_("skill_package.error.name_exists"))

    async def _before_delete(self, id: int) -> None:
        """删除前校验：系统技能包不可删除、企业自有包保护 / Before delete: system package protected, tenant-owned only."""
        await super()._before_delete(id)

        pkg = await self.repo.get_by_id(id)
        if not pkg:
            raise NotFoundException(message=_("skill_package.error.not_found"))

        # 企业端只能删除自有包（tenant_id 与当前企业匹配）
        if pkg.tenant_id != self.tenant_id:
            raise BusinessException(message=_("skill_package.error.system_protected"))

        if pkg.is_system:
            raise BusinessException(message=_("skill_package.error.system_protected"))

        # 级联软删除技能包下的技能
        await self.repo.cascade_soft_delete_skills(id, self._default_delete_level)

    async def promote_to_global(self, id: int) -> SkillPackage | None:
        """推进到总回收站，级联推进技能 / Promote to global recycle bin and cascade skills."""
        instance = await self.repo.promote_to_global_by_id(
            id,
            delete_level=self._default_delete_level,
        )
        if instance is None:
            return None

        await self.repo.cascade_promote_skills(id)
        return instance

    async def escalate_delete(self, id: int) -> SkillPackage | None:
        """兼容旧接口：升级删除 → 推进总回收站 / Backward-compatible alias for promote_to_global."""
        return await self.promote_to_global(id)

    async def _after_restore(self, instance: SkillPackage) -> None:
        """恢复后：级联恢复技能包下的技能 / After restore: cascade restore skills."""
        await self.repo.cascade_restore_skills(instance.id)

    async def _before_permanent_delete(self, id: int) -> None:
        """永久删除前：清理磁盘存储文件 + 残留绑定 / Before permanent delete: cleanup storage and bindings."""
        await super()._before_permanent_delete(id)
        from app.ai.skills.packaging import cleanup_skill_storage
        cleanup_skill_storage(id)

    async def get_with_skill_count(self, package_id: int) -> dict | None:
        """获取技能包详情及其技能数量 / Get package detail with skill count."""
        return await self.repo.get_with_skill_count(package_id)

    async def get_skill_counts_batch(self, package_ids: list[int]) -> dict[int, int]:
        """批量获取技能包的技能数量 / Batch get skill counts per package."""
        return await self.repo.get_skill_counts_batch(package_ids)

    async def get_active_packages(self) -> list[SkillPackage]:
        """获取当前企业所有已激活的技能包 / Get all active packages for current tenant."""
        return await self.repo.get_active_packages()


class AdminSkillPackageService(GlobalService[SkillPackage, AdminSkillPackageRepository]):
    """
    管理端技能包 Service / Admin skill package service.
    无企业隔离，供平台管理端全局查询和 CRUD 使用 / No tenant isolation, for admin CRUD.
    """

    model = SkillPackage
    repository_class = AdminSkillPackageRepository

    async def _before_create(self, data: dict[str, Any]) -> None:
        """创建前校验：名称唯一性 / Before create: name uniqueness."""
        await super()._before_create(data)

        data["tenant_id"] = None

        from app.enums.common import SkillBindModeEnum
        bind_mode = data.get("bind_mode", SkillBindModeEnum.MANUAL.value)
        if bind_mode not in SkillBindModeEnum.values():
            raise BusinessException(message=_("skill_package.error.invalid_bind_mode"))

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name_global(name=name)
            if existing:
                raise BusinessException(message=_("skill_package.error.name_exists"))

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """更新前校验：系统技能包关键属性保护 / Before update: system package key fields protected."""
        await super()._before_update(id, data)

        pkg = await self.repo.get_by_id(id)
        if not pkg:
            raise NotFoundException(message=_("skill_package.error.not_found"))

        if pkg.is_system:
            protected = {"is_system", "is_active", "bind_mode"}
            if protected & set(data.keys()):
                raise BusinessException(message=_("skill_package.error.system_protected"))

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name_global(
                name=name,
                exclude_id=id,
            )
            if existing:
                raise BusinessException(message=_("skill_package.error.name_exists"))

        new_tenant_id = data.get("tenant_id")
        if new_tenant_id is not None and new_tenant_id != pkg.tenant_id:
            await self.repo.cascade_update_skill_tenant_id(id, new_tenant_id)
            logger.info(
                "Cascade synced Skill.tenant_id to {} for package {}",
                new_tenant_id, id,
            )

    async def _before_delete(self, id: int) -> None:
        """删除前校验：系统技能包不可删除，级联软删除技能 / Before delete: system protected, cascade soft-delete skills."""
        await super()._before_delete(id)

        pkg = await self.repo.get_by_id(id)
        if not pkg:
            raise NotFoundException(message=_("skill_package.error.not_found"))

        if pkg.is_system:
            raise BusinessException(message=_("skill_package.error.system_protected"))

        await self.repo.cascade_soft_delete_skills(id, self._default_delete_level)

    async def promote_to_global(self, id: int) -> SkillPackage | None:
        """推进到总回收站，级联推进技能 / Promote to global recycle bin and cascade skills."""
        instance = await self.repo.promote_to_global_by_id(
            id,
            delete_level=self._default_delete_level,
        )
        if instance is None:
            return None

        await self.repo.cascade_promote_skills(id)
        return instance

    async def escalate_delete(self, id: int) -> SkillPackage | None:
        """兼容旧接口：升级删除 → 推进总回收站 / Backward-compatible alias for promote_to_global."""
        return await self.promote_to_global(id)

    async def _after_restore(self, instance: SkillPackage) -> None:
        """恢复后：级联恢复技能包下的技能 / After restore: cascade restore skills."""
        await self.repo.cascade_restore_skills(instance.id)

    async def _before_permanent_delete(self, id: int) -> None:
        """永久删除前：清理磁盘存储文件 + 残留绑定 / Before permanent delete: cleanup storage and bindings."""
        await super()._before_permanent_delete(id)
        from app.ai.skills.packaging import cleanup_skill_storage
        cleanup_skill_storage(id)

    async def get_with_skill_count(self, package_id: int) -> dict | None:
        """获取技能包详情及其技能数量 / Get package detail with skill count."""
        return await self.repo.get_with_skill_count(package_id)

    async def get_skill_counts_batch(self, package_ids: list[int]) -> dict[int, int]:
        """批量获取技能包的技能数量 / Batch get skill counts per package."""
        return await self.repo.get_skill_counts_batch(package_ids)

    async def get_resolved_tools(self, package_id: int) -> dict[str, Any]:
        """
        获取技能包解析后的工具列表 / Get resolved tools for a skill package.

        统一复用 SkillResolver，覆盖 toolkit 与插件注册技能，避免控制器层手工解析。
        Reuse SkillResolver for both toolkit and plugin-backed skills instead of
        performing ad-hoc parsing in controller.
        """
        pkg = await self.repo.get_by_id(package_id)
        if not pkg:
            raise NotFoundException(message=_("skill_package.error.not_found"))

        from app.ai.skills.resolver import SkillResolver
        from app.services.ai.skill_service import AdminSkillService

        skill_service = AdminSkillService(self.db)
        skills = await skill_service.get_by_package_id(package_id)

        resolver = SkillResolver(db=self.db)
        resolve_result = await resolver.resolve(skills)

        if resolve_result.warnings:
            logger.warning(
                "Resolved tools for package {} with {} warnings: {}",
                package_id,
                len(resolve_result.warnings),
                "; ".join(resolve_result.warnings),
            )

        tools = [
            {
                "name": td.name,
                "description": td.description,
                "tool_type": td.tool_type,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description,
                        "required": p.required,
                    }
                    for p in (td.parameters or [])
                ],
                "source_skill_id": td.source_skill_id,
                "source_skill_name": td.source_skill_name,
                "source_plugin": td.source_plugin or pkg.source_plugin,
            }
            for td in resolve_result.tools
        ]

        return {
            "package_id": package_id,
            "package_name": pkg.name,
            "source_plugin": pkg.source_plugin,
            "tool_count": len(tools),
            "tools": tools,
        }


    async def get_select_options(
        self,
        search: str = "",
        limit: int = 50,
        tree: bool = False,
        parent_id: int | None = None,
        page: int = 0,
        page_size: int = 20,
        **filters: Any,
    ) -> SelectResponse:
        """管理端下拉选项，自动排除系统内部技能包 / Admin select options, exclude internal system packages."""
        filters.setdefault("is_system", False)
        return await super().get_select_options(
            search=search, limit=limit, tree=tree,
            parent_id=parent_id, page=page, page_size=page_size,
            **filters,
        )



__all__ = ["SkillPackageService", "AdminSkillPackageService"]
