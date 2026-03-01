"""
技能 Repository
"""

from sqlalchemy import or_, select, and_

from app.models.ai.skill import Skill
from app.models.ai.skill_package import SkillPackage
from app.core.base_repository import TenantRepository, BaseRepository
from app.enums.common import ResourceScopeEnum
from app.repositories.system.resource_tenant_assignment_repository import assigned_resource_ids_subquery
from app.schemas.common.query import QuerySpec, FilterRule

_ASSIGNED_SCOPES = (
    ResourceScopeEnum.ASSIGNED_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_ASSIGNED.value,
)


class SkillRepository(TenantRepository[Skill]):
    """
    租户级技能 Repository

    提供基于租户隔离的技能数据访问。
    查询时自动包含 scope=global 的全局技能。
    """

    model = Skill

    async def get_by_id(
        self, id: int, include_deleted: bool = False
    ) -> Skill | None:
        """根据 ID 获取技能，允许访问全局 + 已分配技能包下的技能"""
        instance = await BaseRepository.get_by_id(self, id, include_deleted)
        if instance and hasattr(instance, "tenant_id"):
            # 同租户的技能
            if instance.tenant_id == self.tenant_id:
                return instance
            # 检查所属包的 scope（技能本身没有独立 scope，继承自包）
            if instance.tenant_id is None:
                pkg = await self.db.get(SkillPackage, instance.package_id)
                if not pkg:
                    return None
                if pkg.scope == ResourceScopeEnum.ADMIN_AND_ALL.value:
                    return instance
                # 平台创建的全局包（all_tenants, tenant_id=null）
                if pkg.scope == ResourceScopeEnum.ALL_TENANTS.value and pkg.tenant_id is None:
                    return instance
                if pkg.scope in _ASSIGNED_SCOPES:
                    from app.repositories.system.resource_tenant_assignment_repository import ResourceTenantAssignmentRepository
                    repo = ResourceTenantAssignmentRepository(self.db)
                    if await repo.check_assignment("skill_package", pkg.id, self.tenant_id):
                        return instance
                return None
            if instance.tenant_id != self.tenant_id:
                return None
        return instance

    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[Skill], int]:
        """
        租户级技能列表查询

        自动注入条件：(tenant_id = X) OR (所属技能包 scope = 'admin_and_all')
        """
        allowed_fields = self.get_allowed_fields(scope)
        all_fields = self.get_allowed_fields(None)

        # 查找 global scope 的技能包 ID（admin_and_all + 平台创建的 all_tenants）
        from sqlalchemy import and_ as sa_and_
        global_pkg_stmt = select(SkillPackage.id).where(
            SkillPackage.is_deleted.is_(False),
            or_(
                SkillPackage.scope == ResourceScopeEnum.ADMIN_AND_ALL.value,
                sa_and_(
                    SkillPackage.scope == ResourceScopeEnum.ALL_TENANTS.value,
                    SkillPackage.tenant_id.is_(None),
                ),
            ),
        )
        global_pkg_result = await self.db.execute(global_pkg_stmt)
        global_pkg_ids = [row[0] for row in global_pkg_result.all()]

        # 查找已分配给当前租户的技能包 ID
        assigned_pkg_subq = assigned_resource_ids_subquery("skill_package", self.tenant_id)
        assigned_pkg_stmt = select(SkillPackage.id).where(
            SkillPackage.scope.in_(_ASSIGNED_SCOPES),
            SkillPackage.is_deleted.is_(False),
            SkillPackage.id.in_(assigned_pkg_subq),
        )
        assigned_pkg_result = await self.db.execute(assigned_pkg_stmt)
        assigned_pkg_ids = [row[0] for row in assigned_pkg_result.all()]

        visible_pkg_ids = set(global_pkg_ids + assigned_pkg_ids)

        query = select(self.model)

        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        if visible_pkg_ids:
            query = query.where(
                or_(
                    self.model.tenant_id == self.tenant_id,
                    self.model.package_id.in_(visible_pkg_ids),
                )
            )
        else:
            query = query.where(self.model.tenant_id == self.tenant_id)

        if forced_filters:
            query = self._apply_filters(query, forced_filters, all_fields)

        if spec.filters:
            query = self._apply_filters(query, spec.filters, allowed_fields)

        from sqlalchemy import func
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
    ) -> Skill | None:
        """
        按名称查找技能（同租户内唯一性检查）

        Args:
            name: 技能名称
            exclude_id: 排除的 ID（用于更新时排除自身）

        Returns:
            Skill 实例或 None
        """
        conditions = [
            Skill.tenant_id == self.tenant_id,
            Skill.name == name,
            Skill.is_deleted.is_(False),
        ]
        if exclude_id is not None:
            conditions.append(Skill.id != exclude_id)

        stmt = select(Skill).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_skills(self) -> list[Skill]:
        """
        获取当前租户所有已激活的技能

        Returns:
            已激活的 Skill 列表
        """
        stmt = (
            select(Skill)
            .where(
                and_(
                    Skill.tenant_id == self.tenant_id,
                    Skill.is_active.is_(True),
                    Skill.is_deleted.is_(False),
                )
            )
            .order_by(Skill.sort_order, Skill.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_type(self, skill_type: str) -> list[Skill]:
        """
        按类型获取当前租户的技能

        Args:
            skill_type: 技能类型

        Returns:
            Skill 列表
        """
        stmt = (
            select(Skill)
            .where(
                and_(
                    Skill.tenant_id == self.tenant_id,
                    Skill.type == skill_type,
                    Skill.is_active.is_(True),
                    Skill.is_deleted.is_(False),
                )
            )
            .order_by(Skill.sort_order)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class AdminSkillRepository(BaseRepository[Skill]):
    """
    管理端技能 Repository

    无租户隔离，供平台管理端全局查询使用
    """

    model = Skill

    async def get_by_name_in_package(
        self,
        name: str,
        package_id: int,
        exclude_id: int | None = None,
    ) -> Skill | None:
        """
        在指定技能包内按名称查找技能

        Args:
            name: 技能名称
            package_id: 技能包 ID
            exclude_id: 排除的 ID

        Returns:
            Skill 实例或 None
        """
        conditions = [
            Skill.name == name,
            Skill.package_id == package_id,
            Skill.is_deleted.is_(False),
        ]

        if exclude_id is not None:
            conditions.append(Skill.id != exclude_id)

        stmt = select(Skill).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


__all__ = [
    "SkillRepository",
    "AdminSkillRepository",
]
