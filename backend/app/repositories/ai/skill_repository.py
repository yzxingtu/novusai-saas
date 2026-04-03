"""
技能 Repository / Skill Repository
"""

from sqlalchemy import and_, func, or_, select

from app.core.base_repository import BaseRepository, TenantRepository
from app.models.ai.skill import Skill
from app.models.ai.skill_package import SkillPackage
from app.schemas.common.query import FilterRule, QuerySpec


class SkillRepository(TenantRepository[Skill]):
    """
    企业级技能 Repository / Tenant-level skill repository.

    提供基于企业隔离的技能数据访问。
    查询时自动包含平台技能包下的共享技能。
    """

    model = Skill

    async def get_by_id(self, id: int, include_deleted: bool = False) -> Skill | None:
        """根据 ID 获取技能，允许访问全局 + 已分配技能包下的技能 / Get skill by ID (global + assigned package)."""
        instance = await BaseRepository.get_by_id(self, id, include_deleted)
        if instance and hasattr(instance, "tenant_id"):
            if instance.tenant_id == self.tenant_id:
                return instance
            if instance.tenant_id is None:
                pkg = await self.db.get(SkillPackage, instance.package_id)
                if pkg and pkg.tenant_id is None:
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
        企业级技能列表查询 / Tenant-level skill list query.

        自动注入条件：(tenant_id = X) OR (所属技能包为平台级包 tenant_id=NULL)
        Auto-inject: (tenant_id = X) OR (package is platform-level, tenant_id=NULL)
        """
        allowed_fields = self.get_allowed_fields(scope)
        all_fields = self.get_allowed_fields(None)

        platform_pkg_stmt = select(SkillPackage.id).where(
            SkillPackage.is_deleted.is_(False),
            SkillPackage.tenant_id.is_(None),
        )
        platform_pkg_result = await self.db.execute(platform_pkg_stmt)
        platform_pkg_ids = [row[0] for row in platform_pkg_result.all()]

        query = select(self.model)

        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        if platform_pkg_ids:
            query = query.where(
                or_(
                    self.model.tenant_id == self.tenant_id,
                    self.model.package_id.in_(platform_pkg_ids),
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

    async def get_by_ids(
        self,
        ids: list[int],
        include_deleted: bool = False,
    ) -> list[Skill]:
        """Get skills by IDs with tenant-visible package fallback."""
        instances = await BaseRepository.get_by_ids(self, ids, include_deleted)
        visible: list[Skill] = []
        for instance in instances:
            if instance.tenant_id == self.tenant_id:
                visible.append(instance)
                continue
            if instance.tenant_id is None:
                pkg = await self.db.get(SkillPackage, instance.package_id)
                if pkg and pkg.tenant_id is None:
                    visible.append(instance)
        return visible

    async def get_by_package_id(
        self,
        package_id: int,
        include_deleted: bool = False,
    ) -> list[Skill]:
        """
        获取企业可见技能包下的全部技能 / Get all skills under a tenant-visible package.

        只要技能包本身对当前企业可见，就允许读取该包下的技能定义。
        If the package itself is visible to the current tenant, the tenant may
        read all skills grouped under that package.
        """
        pkg = await self.db.get(SkillPackage, package_id)
        if not pkg:
            return []
        if pkg.tenant_id not in {None, self.tenant_id}:
            return []

        stmt = select(Skill).where(Skill.package_id == package_id)

        if not include_deleted:
            stmt = stmt.where(Skill.is_deleted.is_(False))

        stmt = stmt.order_by(Skill.sort_order.asc(), Skill.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_name(
        self,
        name: str,
        exclude_id: int | None = None,
    ) -> Skill | None:
        """
        按名称查找技能（同企业内唯一性检查）/ Find skill by name (uniqueness within tenant).

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
        获取当前企业所有已激活的技能 / Get all active skills for current tenant.

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
        按类型获取当前企业的技能 / Get skills by type for current tenant.

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
    管理端技能 Repository / Admin skill repository.

    无企业隔离，供平台管理端全局查询使用
    """

    model = Skill

    async def get_by_package_id(
        self,
        package_id: int,
        include_deleted: bool = False,
    ) -> list[Skill]:
        """
        获取技能包下的全部技能 / Get all skills under a skill package.

        用于非分页场景（如工具解析），避免 query_list 默认分页截断。
        Used by non-paginated flows (for example tool resolution) to avoid
        truncation caused by query_list default pagination.
        """
        stmt = select(Skill).where(Skill.package_id == package_id)

        if not include_deleted:
            stmt = stmt.where(Skill.is_deleted.is_(False))

        stmt = stmt.order_by(Skill.sort_order.asc(), Skill.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_name_in_package(
        self,
        name: str,
        package_id: int,
        exclude_id: int | None = None,
    ) -> Skill | None:
        """
        在指定技能包内按名称查找技能 / Find skill by name within package.

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

    async def query_admin_binding_select(
        self,
        *,
        search: str | None,
        package_id: int | None,
        page: int,
        page_size: int,
        include_system: bool,
        only_active: bool,
    ) -> tuple[list[tuple[Skill, SkillPackage]], int]:
        """
        Paginated skill rows with package join for admin agent binding picker.
        管理端智能体技能绑定选择器：分页 + 技能包联表。
        """
        page = max(1, page)
        page_size = max(1, min(100, page_size))

        pkg = SkillPackage
        sk = Skill
        join_on = sk.package_id == pkg.id

        conditions = [
            sk.is_deleted.is_(False),
            pkg.is_deleted.is_(False),
        ]
        if only_active:
            conditions.append(sk.is_active.is_(True))
        if not include_system:
            conditions.append(sk.is_system.is_(False))
        if package_id is not None:
            conditions.append(sk.package_id == package_id)

        raw = (search or "").strip()
        if raw:
            term = f"%{raw}%"
            conditions.append(
                or_(
                    sk.name.ilike(term),
                    sk.key.ilike(term),
                    sk.description.ilike(term),
                    pkg.name.ilike(term),
                )
            )

        base_joined = (
            select(sk, pkg).select_from(sk).join(pkg, join_on).where(and_(*conditions))
        )

        count_stmt = (
            select(func.count(sk.id))
            .select_from(sk)
            .join(pkg, join_on)
            .where(and_(*conditions))
        )
        total = (await self.db.execute(count_stmt)).scalar() or 0

        ordered = (
            base_joined.order_by(
                pkg.sort_order.asc(),
                pkg.created_at.desc(),
                sk.sort_order.asc(),
                sk.created_at.desc(),
                sk.id.asc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.db.execute(ordered)
        rows = list(result.all())
        return rows, total


__all__ = [
    "SkillRepository",
    "AdminSkillRepository",
]
