"""
技能包 Repository / Skill Package Repository
"""


from sqlalchemy import and_, func, or_, select, update
from sqlalchemy import delete as sa_delete

from app.core.base_model import utc_now
from app.core.base_repository import BaseRepository, TenantRepository
from app.enums.common import DeleteLevelEnum
from app.models.ai.agent_skill_binding import AgentSkillBinding
from app.models.ai.skill import Skill
from app.models.ai.skill_package import SkillPackage
from app.schemas.common.query import FilterRule, QuerySpec


class _SkillPackageCascadeMixin:
    """技能包级联操作 Mixin（admin/tenant 共用）"""

    async def cascade_soft_delete_skills(
        self, package_id: int, delete_level: str,
    ) -> None:
        """级联软删除技能包下的技能"""
        now = utc_now()
        await self.db.execute(
            update(Skill)
            .where(
                Skill.package_id == package_id,
                Skill.is_deleted.is_(False),
            )
            .values(is_deleted=True, deleted_at=now, delete_level=delete_level, updated_at=now)
        )

    async def cascade_escalate_skills(self, package_id: int) -> None:
        """级联升级技能的删除层级"""
        now = utc_now()
        await self.db.execute(
            update(Skill)
            .where(
                Skill.package_id == package_id,
                Skill.is_deleted.is_(True),
            )
            .values(delete_level=DeleteLevelEnum.ADMIN.value, deleted_at=now, updated_at=now)
        )

    async def cascade_restore_skills(self, package_id: int) -> None:
        """级联恢复技能"""
        now = utc_now()
        await self.db.execute(
            update(Skill)
            .where(
                Skill.package_id == package_id,
                Skill.is_deleted.is_(True),
            )
            .values(is_deleted=False, deleted_at=None, delete_level=None, updated_at=now)
        )

    async def delete_skill_bindings(self, package_id: int) -> None:
        """物理删除技能包的 AgentSkillBinding 记录"""
        await self.db.execute(
            sa_delete(AgentSkillBinding).where(
                AgentSkillBinding.package_id == package_id,
            )
        )

    async def get_with_skill_count(
        self,
        package_id: int,
    ) -> dict | None:
        """获取技能包详情及其包含的技能数量"""
        pkg = await self.get_by_id(package_id)
        if not pkg:
            return None

        count_stmt = select(func.count()).where(
            Skill.package_id == package_id,
            Skill.is_deleted.is_(False),
        )
        count_result = await self.db.execute(count_stmt)
        skill_count = count_result.scalar() or 0

        data = pkg.to_dict()
        data["skill_count"] = skill_count
        return data

    async def get_skill_counts_batch(
        self,
        package_ids: list[int],
    ) -> dict[int, int]:
        """
        批量获取技能包的技能数量

        Args:
            package_ids: 技能包 ID 列表

        Returns:
            {package_id: skill_count} 映射
        """
        if not package_ids:
            return {}

        stmt = (
            select(Skill.package_id, func.count().label("cnt"))
            .where(
                Skill.package_id.in_(package_ids),
                Skill.is_deleted.is_(False),
            )
            .group_by(Skill.package_id)
        )
        result = await self.db.execute(stmt)
        return {row.package_id: row.cnt for row in result.all()}


class SkillPackageRepository(_SkillPackageCascadeMixin, TenantRepository[SkillPackage]):
    """
    租户级技能包 Repository
    Tenant-level Skill Package Repository

    提供基于租户隔离的技能包数据访问，自动包含平台级包（tenant_id=NULL）。
    Provides tenant-isolated data access, automatically includes platform-level packages (tenant_id=NULL).
    """

    model = SkillPackage

    async def get_by_id(
        self, id: int, include_deleted: bool = False
    ) -> SkillPackage | None:
        """根据 ID 获取技能包（同租户包 + 平台级包均可访问）
        Get skill package by ID (same-tenant + platform-level packages are accessible)"""
        instance = await BaseRepository.get_by_id(self, id, include_deleted)
        if instance and hasattr(instance, "tenant_id"):
            if instance.tenant_id == self.tenant_id:
                return instance
            if instance.tenant_id is None:
                return instance
            return None
        return instance

    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[SkillPackage], int]:
        """
        租户级技能包列表查询
        Tenant-level skill package list query

        自动注入条件：(tenant_id = X) OR (平台级包 tenant_id=NULL)
        Auto-inject: (tenant_id = X) OR (platform-level tenant_id=NULL)
        """
        from app.enums.common import AudienceEnum

        allowed_fields = self.get_allowed_fields(scope)
        all_fields = self.get_allowed_fields(None)

        query = select(self.model)

        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        query = query.where(
            or_(
                self.model.tenant_id == self.tenant_id,
                and_(
                    self.model.tenant_id.is_(None),
                    self.model.target_audience != AudienceEnum.ADMIN_ONLY.value,
                ),
            )
        )

        query = query.where(self.model.is_system.is_(False))

        if forced_filters:
            query = self._apply_filters(query, forced_filters, all_fields)

        if spec.filters:
            query = self._apply_filters(query, spec.filters, allowed_fields)

        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        sortable_fields = self.get_sortable_fields()
        query = self._apply_sort(query, spec.sort, sortable_fields)

        query = query.offset(spec.offset).limit(spec.limit)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_by_name(
        self,
        name: str,
        exclude_id: int | None = None,
    ) -> SkillPackage | None:
        """
        按名称查找技能包（同租户内唯一性检查）
        """
        conditions = [
            SkillPackage.tenant_id == self.tenant_id,
            SkillPackage.name == name,
            SkillPackage.is_deleted.is_(False),
        ]
        if exclude_id is not None:
            conditions.append(SkillPackage.id != exclude_id)

        stmt = select(SkillPackage).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_packages(self) -> list[SkillPackage]:
        """
        获取当前租户所有已激活的技能包（含平台级包）
        Get all active skill packages for the current tenant (including platform-level packages)
        """
        from app.enums.common import AudienceEnum

        stmt = (
            select(SkillPackage)
            .where(
                and_(
                    SkillPackage.is_active.is_(True),
                    SkillPackage.is_deleted.is_(False),
                    SkillPackage.is_system.is_(False),
                    or_(
                        SkillPackage.tenant_id == self.tenant_id,
                        and_(
                            SkillPackage.tenant_id.is_(None),
                            SkillPackage.target_audience != AudienceEnum.ADMIN_ONLY.value,
                        ),
                    ),
                )
            )
            .order_by(SkillPackage.sort_order, SkillPackage.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_available_for_binding(self) -> list[SkillPackage]:
        """
        获取租户可绑定的所有技能包（用于智能体技能绑定下拉）
        Get all skill packages available for tenant binding (for agent skill binding dropdown)

        包括 / Includes:
          - 同租户自有包 / Same tenant's own packages
          - 平台级包（tenant_id=NULL）且 target_audience != admin_only / Platform packages visible to tenants

        不包括 / Excludes:
          - target_audience=admin_only 的包（仅管理端可见）/ Admin-only audience packages
        """
        from app.enums.common import AudienceEnum

        stmt = (
            select(SkillPackage)
            .where(
                and_(
                    SkillPackage.is_active.is_(True),
                    SkillPackage.is_deleted.is_(False),
                    SkillPackage.is_system.is_(False),
                    SkillPackage.target_audience != AudienceEnum.ADMIN_ONLY.value,
                    or_(
                        SkillPackage.tenant_id == self.tenant_id,
                        SkillPackage.tenant_id.is_(None),
                    ),
                )
            )
            .order_by(SkillPackage.sort_order, SkillPackage.name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class AdminSkillPackageRepository(_SkillPackageCascadeMixin, BaseRepository[SkillPackage]):
    """
    管理端技能包 Repository

    无租户隔离，供平台管理端全局查询使用
    """

    model = SkillPackage

    async def cascade_update_skill_tenant_id(
        self, package_id: int, new_tenant_id: int | None,
    ) -> None:
        """级联更新技能包下所有技能的 tenant_id"""
        now = utc_now()
        await self.db.execute(
            update(Skill)
            .where(Skill.package_id == package_id)
            .values(tenant_id=new_tenant_id, updated_at=now)
        )

    async def get_by_source_plugin(
        self,
        plugin_name: str,
    ) -> SkillPackage | None:
        """
        按来源插件名查找技能包（含已软删除的）

        用于插件启用时幂等检查和禁用/卸载时定位记录。
        不过滤 scope，因为 source_plugin 已唯一标识插件创建的技能包。
        """
        stmt = select(SkillPackage).where(
            SkillPackage.source_plugin == plugin_name,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name_global(
        self,
        name: str,
        exclude_id: int | None = None,
    ) -> SkillPackage | None:
        """
        在平台级包（tenant_id=NULL）中按名称查找技能包
        Find a platform-level package (tenant_id=NULL) by name
        """
        conditions = [
            SkillPackage.name == name,
            SkillPackage.tenant_id.is_(None),
            SkillPackage.is_deleted.is_(False),
        ]

        if exclude_id is not None:
            conditions.append(SkillPackage.id != exclude_id)

        stmt = select(SkillPackage).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


__all__ = [
    "SkillPackageRepository",
    "AdminSkillPackageRepository",
]
