"""
技能包 Repository / Skill Package Repository
"""

from sqlalchemy import and_, func, or_, select, update

from app.core.base_model import utc_now
from app.core.base_repository import BaseRepository, TenantRepository
from app.enums.common import RecycleStageEnum
from app.models.ai.skill import Skill
from app.models.ai.skill_package import SkillPackage
from app.schemas.common.query import FilterRule, QuerySpec


class _SkillPackageCascadeMixin:
    """技能包级联操作 Mixin（admin/tenant 共用） / Skill package cascade mixin (admin/tenant)."""

    async def cascade_soft_delete_skills(
        self, package_id: int, delete_level: str,
    ) -> None:
        """级联软删除技能包下的技能 / Cascade soft-delete skills in package."""
        now = utc_now()
        await self.db.execute(
            update(Skill)
            .where(
                Skill.package_id == package_id,
                Skill.is_deleted.is_(False),
            )
            .values(
                is_deleted=True,
                deleted_at=now,
                delete_level=delete_level,
                recycle_stage=RecycleStageEnum.MODULE.value,
                promoted_to_global_at=None,
                updated_at=now,
            )
        )

    async def cascade_promote_skills(self, package_id: int) -> None:
        """级联推进技能到总回收站 / Cascade promote skills to global recycle bin."""
        now = utc_now()
        await self.db.execute(
            update(Skill)
            .where(
                Skill.package_id == package_id,
                Skill.is_deleted.is_(True),
            )
            .values(
                recycle_stage=RecycleStageEnum.GLOBAL.value,
                promoted_to_global_at=now,
                updated_at=now,
            )
        )

    async def cascade_restore_skills(self, package_id: int) -> None:
        """级联恢复技能 / Cascade restore skills."""
        now = utc_now()
        await self.db.execute(
            update(Skill)
            .where(
                Skill.package_id == package_id,
                Skill.is_deleted.is_(True),
            )
            .values(
                is_deleted=False,
                deleted_at=None,
                delete_level=None,
                recycle_stage=None,
                promoted_to_global_at=None,
                updated_at=now,
            )
        )

    async def get_with_skill_count(
        self,
        package_id: int,
    ) -> dict | None:
        """获取技能包详情及其包含的技能数量 / Get package detail with skill count."""
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
        批量获取技能包的技能数量 / Batch get skill counts per package.

        Args:
            package_ids: 技能包 ID 列表 / Package ID list.

        Returns:
            {package_id: skill_count} 映射 / Map package_id -> skill_count.
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
    企业级技能包 Repository / Tenant-level Skill Package Repository.

    提供基于企业隔离的技能包数据访问，自动包含平台级包（tenant_id=NULL）。
    Provides tenant-isolated data access, automatically includes platform-level packages (tenant_id=NULL).
    """

    model = SkillPackage

    @staticmethod
    def _is_tenant_accessible(instance: SkillPackage, tenant_id: int | None) -> bool:
        """Tenant can access own packages and shared platform packages."""
        if instance.tenant_id == tenant_id:
            return True
        if instance.tenant_id is None:
            return True
        return False

    async def get_by_id(
        self, id: int, include_deleted: bool = False
    ) -> SkillPackage | None:
        """根据 ID 获取技能包（同企业包 + 平台级包均可访问）/ Get skill package by ID (same-tenant + platform-level packages are accessible)."""
        instance = await BaseRepository.get_by_id(self, id, include_deleted)
        if instance and hasattr(instance, "tenant_id"):
            if self._is_tenant_accessible(instance, self.tenant_id):
                return instance
            return None
        return instance

    async def get_by_ids(
        self,
        ids: list[int],
        include_deleted: bool = False,
    ) -> list[SkillPackage]:
        """根据 ID 列表获取技能包，并按企业归属过滤可见性。"""
        instances = await BaseRepository.get_by_ids(self, ids, include_deleted)
        return [
            instance
            for instance in instances
            if self._is_tenant_accessible(instance, self.tenant_id)
        ]

    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
        include_deleted: bool = False,
        include_system: bool = False,
    ) -> tuple[list[SkillPackage], int]:
        """
        企业级技能包列表查询 / Tenant-level skill package list query.

        自动注入条件：(tenant_id = X) OR (平台级包 tenant_id=NULL)
        Auto-inject: (tenant_id = X) OR (platform-level tenant_id=NULL)
        """
        allowed_fields = self.get_allowed_fields(scope)
        all_fields = self.get_allowed_fields(None)

        query = select(self.model)

        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        query = query.where(
            or_(
                self.model.tenant_id == self.tenant_id,
                self.model.tenant_id.is_(None),
            )
        )

        if not include_system:
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
        按名称查找技能包（同企业内唯一性检查） / Get package by name (uniqueness check).
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
        获取当前企业所有已激活的技能包（含平台级包）/ Get all active skill packages for current tenant (including platform-level).
        """
        stmt = (
            select(SkillPackage)
            .where(
                and_(
                    SkillPackage.is_active.is_(True),
                    SkillPackage.is_deleted.is_(False),
                    SkillPackage.is_system.is_(False),
                    or_(
                        SkillPackage.tenant_id == self.tenant_id,
                        SkillPackage.tenant_id.is_(None),
                    ),
                )
            )
            .order_by(SkillPackage.sort_order, SkillPackage.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_available_for_binding(self) -> list[SkillPackage]:
        """
        获取企业可绑定的所有技能包（用于智能体技能绑定下拉）
        Get all skill packages available for tenant binding (for agent skill binding dropdown)

        包括 / Includes:
          - 同企业自有包 / Same tenant's own packages
          - 平台级包（tenant_id=NULL）/ Platform packages
        """
        stmt = (
            select(SkillPackage)
            .where(
                and_(
                    SkillPackage.is_active.is_(True),
                    SkillPackage.is_deleted.is_(False),
                    SkillPackage.is_system.is_(False),
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
    管理端技能包 Repository / Admin skill package repository.

    无企业隔离，供平台管理端全局查询使用。No tenant filter; for platform admin global query.
    """

    model = SkillPackage

    async def cascade_update_skill_tenant_id(
        self, package_id: int, new_tenant_id: int | None,
    ) -> None:
        """级联更新技能包下所有技能的 tenant_id / Cascade update skills' tenant_id."""
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
        按来源插件名查找技能包（含已软删除的） / Get package by source_plugin (incl. deleted).

        用于插件启用时幂等检查和禁用/卸载时定位记录。
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
        在平台级包（tenant_id=NULL）中按名称查找技能包 / Find platform-level package (tenant_id=NULL) by name.
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
