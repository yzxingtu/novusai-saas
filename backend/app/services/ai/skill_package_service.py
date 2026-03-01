"""
技能包 Service
"""

from typing import Any

from app.core.base_service import TenantService, GlobalService
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.common import ResourceScopeEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.skill_package import SkillPackage
from app.repositories.ai.skill_package_repository import (
    SkillPackageRepository,
    AdminSkillPackageRepository,
)
from app.schemas.common.select import SelectResponse

logger = LogManager.get_logger("ai")


class SkillPackageService(TenantService[SkillPackage, SkillPackageRepository]):
    """
    租户端技能包 Service

    提供技能包的创建、更新、删除等业务逻辑
    """

    model = SkillPackage
    repository_class = SkillPackageRepository

    async def _before_create(self, data: dict[str, Any]) -> None:
        """创建前校验：名称唯一性、作用域合法性"""
        await super()._before_create(data)

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name(name)
            if existing:
                raise BusinessException(message=_("skill_package.error.name_exists"))

        scope = data.get("scope", ResourceScopeEnum.ALL_TENANTS.value)
        if scope not in ResourceScopeEnum.values():
            raise BusinessException(message=_("skill_package.error.invalid_scope"))

        # 租户端只能创建 all_tenants scope 技能包
        if scope != ResourceScopeEnum.ALL_TENANTS.value:
            raise BusinessException(message=_("skill_package.error.invalid_scope"))

        # 租户端只能创建 manual 绑定模式
        from app.enums.common import SkillBindModeEnum
        data["bind_mode"] = SkillBindModeEnum.MANUAL.value

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """更新前校验：名称唯一性、系统技能包保护、scope 保护"""
        await super()._before_update(id, data)

        pkg = await self.repo.get_by_id(id)
        if not pkg:
            raise NotFoundException(message=_("skill_package.error.not_found"))

        # 租户端只能修改自有包（tenant_id 与当前租户匹配）
        if pkg.tenant_id != self.tenant_id:
            raise BusinessException(message=_("skill_package.error.system_protected"))

        if pkg.is_system:
            protected = {"scope", "is_system", "is_active", "bind_mode"}
            if protected & set(data.keys()):
                raise BusinessException(message=_("skill_package.error.system_protected"))

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name(name, exclude_id=id)
            if existing:
                raise BusinessException(message=_("skill_package.error.name_exists"))

        # 不允许修改 scope
        if "scope" in data and data["scope"] != pkg.scope:
            raise BusinessException(message=_("skill_package.error.invalid_scope"))

    async def _before_delete(self, id: int) -> None:
        """删除前校验：系统技能包不可删除、scope 保护"""
        await super()._before_delete(id)

        pkg = await self.repo.get_by_id(id)
        if not pkg:
            raise NotFoundException(message=_("skill_package.error.not_found"))

        # 租户端只能删除自有包（tenant_id 与当前租户匹配）
        if pkg.tenant_id != self.tenant_id:
            raise BusinessException(message=_("skill_package.error.system_protected"))

        if pkg.is_system:
            raise BusinessException(message=_("skill_package.error.system_protected"))

        # 级联软删除技能包下的技能
        await self.repo.cascade_soft_delete_skills(id, self._default_delete_level)

        # 级联物理删除关联的 AgentSkillBinding（绑定关系无需回收站）
        await self.repo.delete_skill_bindings(id)
        logger.info("Cascade deleted AgentSkillBindings for package %d", id)

    async def escalate_delete(self, id: int) -> SkillPackage | None:
        """升级删除层级，级联升级技能"""
        instance = await self.repo.escalate_delete_by_id(id)
        if instance is None:
            return None

        await self.repo.cascade_escalate_skills(id)
        return instance

    async def _after_restore(self, instance: SkillPackage) -> None:
        """恢复后：级联恢复技能包下的技能"""
        await self.repo.cascade_restore_skills(instance.id)

    async def _before_permanent_delete(self, id: int) -> None:
        """永久删除前：清理磁盘存储文件 + 残留绑定"""
        await super()._before_permanent_delete(id)
        from app.ai.skills.packaging import cleanup_skill_storage
        cleanup_skill_storage(id)

        # 清理可能残留的绑定记录
        await self.repo.delete_skill_bindings(id)

    async def get_with_skill_count(self, package_id: int) -> dict | None:
        """获取技能包详情及其技能数量"""
        return await self.repo.get_with_skill_count(package_id)

    async def get_skill_counts_batch(self, package_ids: list[int]) -> dict[int, int]:
        """批量获取技能包的技能数量"""
        return await self.repo.get_skill_counts_batch(package_ids)

    async def get_active_packages(self) -> list[SkillPackage]:
        """获取当前租户所有已激活的技能包"""
        return await self.repo.get_active_packages()


class AdminSkillPackageService(GlobalService[SkillPackage, AdminSkillPackageRepository]):
    """
    管理端技能包 Service

    无租户隔离，供平台管理端全局查询和 CRUD 使用
    """

    model = SkillPackage
    repository_class = AdminSkillPackageRepository

    async def _before_create(self, data: dict[str, Any]) -> None:
        """创建前校验：作用域合法性、名称唯一性"""
        await super()._before_create(data)

        scope = data.get("scope", ResourceScopeEnum.ADMIN_AND_ALL.value)
        if scope not in ResourceScopeEnum.values():
            raise BusinessException(message=_("skill_package.error.invalid_scope"))

        # all_tenants 现在表示平台全局资源（tenant_id=null），其他 scope 同样不需要 tenant_id
        data["tenant_id"] = None

        # tenant_ids 不是模型字段，由 Controller 通过 resource_tenant_assignments 处理
        data.pop("tenant_ids", None)

        # bind_mode 校验（管理端允许 auto/manual）
        from app.enums.common import SkillBindModeEnum
        bind_mode = data.get("bind_mode", SkillBindModeEnum.MANUAL.value)
        if bind_mode not in SkillBindModeEnum.values():
            raise BusinessException(message=_("skill_package.error.invalid_bind_mode"))

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name_in_scope(
                name=name,
                scope=scope,
                tenant_id=data.get("tenant_id"),
            )
            if existing:
                raise BusinessException(message=_("skill_package.error.name_exists"))

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """更新前校验：系统技能包关键属性保护、scope 不可变"""
        await super()._before_update(id, data)

        pkg = await self.repo.get_by_id(id)
        if not pkg:
            raise NotFoundException(message=_("skill_package.error.not_found"))

        if pkg.is_system:
            protected = {"scope", "is_system", "is_active", "bind_mode"}
            if protected & set(data.keys()):
                raise BusinessException(message=_("skill_package.error.system_protected"))

        # 不允许修改 scope
        if "scope" in data and data["scope"] != pkg.scope:
            raise BusinessException(message=_("skill_package.error.invalid_scope"))

        # tenant_ids 不是模型字段，由 Controller 通过 resource_tenant_assignments 处理
        data.pop("tenant_ids", None)

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name_in_scope(
                name=name,
                scope=pkg.scope,
                tenant_id=pkg.tenant_id,
                exclude_id=id,
            )
            if existing:
                raise BusinessException(message=_("skill_package.error.name_exists"))

        # 如果 tenant_id 发生变化，级联同步子技能的 tenant_id
        new_tenant_id = data.get("tenant_id")
        if new_tenant_id is not None and new_tenant_id != pkg.tenant_id:
            await self.repo.cascade_update_skill_tenant_id(id, new_tenant_id)
            logger.info(
                "Cascade synced Skill.tenant_id to %s for package %d",
                new_tenant_id, id,
            )

    async def _before_delete(self, id: int) -> None:
        """删除前校验：系统技能包不可删除，级联软删除技能"""
        await super()._before_delete(id)

        pkg = await self.repo.get_by_id(id)
        if not pkg:
            raise NotFoundException(message=_("skill_package.error.not_found"))

        if pkg.is_system:
            raise BusinessException(message=_("skill_package.error.system_protected"))

        await self.repo.cascade_soft_delete_skills(id, self._default_delete_level)

        # 级联物理删除关联的 AgentSkillBinding
        await self.repo.delete_skill_bindings(id)
        logger.info("Cascade deleted AgentSkillBindings for package %d", id)

        # 清理 resource_tenant_assignments 残留记录
        if pkg.scope in (
            ResourceScopeEnum.ASSIGNED_TENANTS.value,
            ResourceScopeEnum.ADMIN_AND_ASSIGNED.value,
        ):
            from app.repositories.system.resource_tenant_assignment_repository import ResourceTenantAssignmentRepository
            rta_repo = ResourceTenantAssignmentRepository(self.db)
            await rta_repo.delete_all_for_resource("skill_package", id)

    async def escalate_delete(self, id: int) -> SkillPackage | None:
        """升级删除层级，级联升级技能"""
        instance = await self.repo.escalate_delete_by_id(id)
        if instance is None:
            return None

        await self.repo.cascade_escalate_skills(id)
        return instance

    async def _after_restore(self, instance: SkillPackage) -> None:
        """恢复后：级联恢复技能包下的技能"""
        await self.repo.cascade_restore_skills(instance.id)

    async def _before_permanent_delete(self, id: int) -> None:
        """永久删除前：清理磁盘存储文件 + 残留绑定"""
        await super()._before_permanent_delete(id)
        from app.ai.skills.packaging import cleanup_skill_storage
        cleanup_skill_storage(id)

        await self.repo.delete_skill_bindings(id)

    async def get_with_skill_count(self, package_id: int) -> dict | None:
        """获取技能包详情及其技能数量"""
        return await self.repo.get_with_skill_count(package_id)

    async def get_skill_counts_batch(self, package_ids: list[int]) -> dict[int, int]:
        """批量获取技能包的技能数量"""
        return await self.repo.get_skill_counts_batch(package_ids)


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
        """管理端下拉选项，自动排除系统内部技能包"""
        filters.setdefault("is_system", False)
        return await super().get_select_options(
            search=search, limit=limit, tree=tree,
            parent_id=parent_id, page=page, page_size=page_size,
            **filters,
        )

    async def get_by_name_in_scope(
        self,
        name: str,
        scope: str,
        tenant_id: int | None = None,
        exclude_id: int | None = None,
    ) -> SkillPackage | None:
        """在指定作用域内按名称查找技能包"""
        return await self.repo.get_by_name_in_scope(
            name=name, scope=scope, tenant_id=tenant_id, exclude_id=exclude_id,
        )


__all__ = ["SkillPackageService", "AdminSkillPackageService"]
