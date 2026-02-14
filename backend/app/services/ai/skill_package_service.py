"""
技能包 Service
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select, update

from app.core.base_service import TenantService, GlobalService
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.common import ResourceScopeEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent_skill_binding import AgentSkillBinding
from app.models.ai.skill import Skill
from app.models.ai.skill_package import SkillPackage
from app.repositories.ai.skill_package_repository import (
    SkillPackageRepository,
    AdminSkillPackageRepository,
)

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

        scope = data.get("scope", ResourceScopeEnum.TENANT.value)
        if scope not in ResourceScopeEnum.values():
            raise BusinessException(message=_("skill_package.error.invalid_scope"))

        # 租户端只能创建 tenant scope 技能包
        if scope != ResourceScopeEnum.TENANT.value:
            raise BusinessException(message=_("skill_package.error.invalid_scope"))

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """更新前校验：名称唯一性、系统技能包保护"""
        await super()._before_update(id, data)

        pkg = await self.repo.get_by_id(id)
        if not pkg:
            raise NotFoundException(message=_("skill_package.error.not_found"))

        if pkg.is_system:
            protected = {"scope", "is_system", "is_active"}
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
        """删除前校验：系统技能包不可删除"""
        await super()._before_delete(id)

        pkg = await self.repo.get_by_id(id)
        if not pkg:
            raise NotFoundException(message=_("skill_package.error.not_found"))

        if pkg.is_system:
            raise BusinessException(message=_("skill_package.error.system_protected"))

        # 级联软删除技能包下的技能
        level = self._default_delete_level
        now = datetime.utcnow()
        await self.repo.db.execute(
            update(Skill)
            .where(
                Skill.package_id == id,
                Skill.is_deleted.is_(False),
            )
            .values(is_deleted=True, deleted_at=now, delete_level=level, updated_at=now)
        )

        # 级联物理删除关联的 AgentSkillBinding（绑定关系无需回收站）
        from sqlalchemy import delete as sa_delete
        await self.repo.db.execute(
            sa_delete(AgentSkillBinding).where(
                AgentSkillBinding.package_id == id,
            )
        )
        logger.info("Cascade deleted AgentSkillBindings for package %d", id)

    async def escalate_delete(self, id: int) -> SkillPackage | None:
        """升级删除层级，级联升级技能"""
        instance = await self.repo.escalate_delete_by_id(id)
        if instance is None:
            return None

        now = datetime.utcnow()
        await self.repo.db.execute(
            update(Skill)
            .where(
                Skill.package_id == id,
                Skill.is_deleted.is_(True),
            )
            .values(delete_level="admin", deleted_at=now, updated_at=now)
        )
        return instance

    async def _after_restore(self, instance: SkillPackage) -> None:
        """恢复后：级联恢复技能包下的技能"""
        now = datetime.utcnow()
        await self.repo.db.execute(
            update(Skill)
            .where(
                Skill.package_id == instance.id,
                Skill.is_deleted.is_(True),
            )
            .values(is_deleted=False, deleted_at=None, delete_level=None, updated_at=now)
        )

    async def _before_permanent_delete(self, id: int) -> None:
        """永久删除前：清理磁盘存储文件 + 残留绑定"""
        await super()._before_permanent_delete(id)
        from app.ai.skills.packaging import cleanup_skill_storage
        cleanup_skill_storage(id)

        # 清理可能残留的绑定记录
        from sqlalchemy import delete as sa_delete
        await self.repo.db.execute(
            sa_delete(AgentSkillBinding).where(
                AgentSkillBinding.package_id == id,
            )
        )

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

        scope = data.get("scope", ResourceScopeEnum.TENANT.value)
        if scope not in ResourceScopeEnum.values():
            raise BusinessException(message=_("skill_package.error.invalid_scope"))

        if scope in (ResourceScopeEnum.ADMIN.value, ResourceScopeEnum.GLOBAL.value):
            data["tenant_id"] = None

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
        """更新前校验：系统技能包关键属性保护"""
        await super()._before_update(id, data)

        pkg = await self.repo.get_by_id(id)
        if not pkg:
            raise NotFoundException(message=_("skill_package.error.not_found"))

        if pkg.is_system:
            protected = {"scope", "is_system", "is_active"}
            if protected & set(data.keys()):
                raise BusinessException(message=_("skill_package.error.system_protected"))

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

    async def _before_delete(self, id: int) -> None:
        """删除前校验：系统技能包不可删除，级联软删除技能"""
        await super()._before_delete(id)

        pkg = await self.repo.get_by_id(id)
        if not pkg:
            raise NotFoundException(message=_("skill_package.error.not_found"))

        if pkg.is_system:
            raise BusinessException(message=_("skill_package.error.system_protected"))

        level = self._default_delete_level
        now = datetime.utcnow()
        await self.repo.db.execute(
            update(Skill)
            .where(
                Skill.package_id == id,
                Skill.is_deleted.is_(False),
            )
            .values(is_deleted=True, deleted_at=now, delete_level=level, updated_at=now)
        )

        # 级联物理删除关联的 AgentSkillBinding
        from sqlalchemy import delete as sa_delete
        await self.repo.db.execute(
            sa_delete(AgentSkillBinding).where(
                AgentSkillBinding.package_id == id,
            )
        )
        logger.info("Cascade deleted AgentSkillBindings for package %d", id)

    async def escalate_delete(self, id: int) -> SkillPackage | None:
        """升级删除层级，级联升级技能"""
        instance = await self.repo.escalate_delete_by_id(id)
        if instance is None:
            return None

        now = datetime.utcnow()
        await self.repo.db.execute(
            update(Skill)
            .where(
                Skill.package_id == id,
                Skill.is_deleted.is_(True),
            )
            .values(delete_level="admin", deleted_at=now, updated_at=now)
        )
        return instance

    async def _after_restore(self, instance: SkillPackage) -> None:
        """恢复后：级联恢复技能包下的技能"""
        now = datetime.utcnow()
        await self.repo.db.execute(
            update(Skill)
            .where(
                Skill.package_id == instance.id,
                Skill.is_deleted.is_(True),
            )
            .values(is_deleted=False, deleted_at=None, delete_level=None, updated_at=now)
        )

    async def _before_permanent_delete(self, id: int) -> None:
        """永久删除前：清理磁盘存储文件 + 残留绑定"""
        await super()._before_permanent_delete(id)
        from app.ai.skills.packaging import cleanup_skill_storage
        cleanup_skill_storage(id)

        from sqlalchemy import delete as sa_delete
        await self.repo.db.execute(
            sa_delete(AgentSkillBinding).where(
                AgentSkillBinding.package_id == id,
            )
        )

    async def get_with_skill_count(self, package_id: int) -> dict | None:
        """获取技能包详情及其技能数量"""
        return await self.repo.get_with_skill_count(package_id)

    async def get_skill_counts_batch(self, package_ids: list[int]) -> dict[int, int]:
        """批量获取技能包的技能数量"""
        return await self.repo.get_skill_counts_batch(package_ids)

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
