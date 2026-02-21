"""
删除依赖检查器

通用依赖检查器，读取 Model.__delete_deps__ 声明，
在删除前自动检查是否有活跃记录引用当前实例。

- BLOCK: 存在活跃依赖时阻止删除
- CASCADE_SOFT: 收集需要级联软删除的依赖
- CASCADE_DELETE: 收集需要级联物理删除的依赖
- NULLIFY: 收集需要置 NULL 的依赖
- IGNORE: 跳过
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy import exists, func, select, update

from app.core.base_model import Base, TenantModel, utc_now
from app.core.deletion import DeletionDep, DeletionStrategy
from app.core.logging import LogManager

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = LogManager.get_logger("db")

# ── Model 类名 → ORM 类的注册表缓存 ──
_MODEL_REGISTRY: dict[str, type] | None = None


def _get_model_registry() -> dict[str, type]:
    """
    构建 Model 类名 → ORM 类的映射表（惰性构建，首次调用后缓存）。

    通过遍历 SQLAlchemy Base 的所有已注册 mapper 获取。
    """
    global _MODEL_REGISTRY
    if _MODEL_REGISTRY is not None:
        return _MODEL_REGISTRY

    registry: dict[str, type] = {}
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        registry[cls.__name__] = cls

    _MODEL_REGISTRY = registry
    return registry


def resolve_model_class(class_name: str) -> type | None:
    """
    根据类名解析 ORM Model 类。

    Args:
        class_name: Model 类名（如 "AIModel"）

    Returns:
        ORM 类或 None
    """
    return _get_model_registry().get(class_name)


@dataclass
class DependencyInfo:
    """
    单个依赖的检查结果（用于前端展示）

    Attributes:
        model_name: 模型的 i18n key（如 "deletion.model.ai_model"）
        count: 依赖记录总数
        items: 前 N 条记录摘要 [{"id": 1, "label": "deepseek-chat"}, ...]
        strategy: 策略值
    """

    model_name: str
    count: int
    items: list[dict[str, Any]]
    strategy: str


@dataclass
class DependencyCheckResult:
    """
    依赖检查总结果

    Attributes:
        blocked: 是否被 BLOCK 策略阻止
        blockers: 阻止删除的依赖列表
        cascade_soft: 需要级联软删除的依赖
        cascade_delete: 需要级联物理删除的依赖
        nullify: 需要置 NULL 的依赖
    """

    blocked: bool = False
    blockers: list[DependencyInfo] = field(default_factory=list)
    cascade_soft: list[DependencyInfo] = field(default_factory=list)
    cascade_delete: list[DependencyInfo] = field(default_factory=list)
    nullify: list[DependencyInfo] = field(default_factory=list)


# 前端展示摘要的最大条目数
_MAX_ITEMS_PREVIEW = 5


async def check_deletion_deps(
    db: AsyncSession,
    instance: Any,
    tenant_id: int | None = None,
) -> DependencyCheckResult:
    """
    通用依赖检查器。

    读取 instance.__class__.__delete_deps__，逐条检查是否有活跃记录
    引用当前实例。

    Args:
        db: 异步数据库会话
        instance: 要删除的模型实例
        tenant_id: 租户 ID（TenantModel 子类自动添加过滤）

    Returns:
        DependencyCheckResult
    """
    model_cls = instance.__class__
    deps: list[DeletionDep] = getattr(model_cls, "__delete_deps__", [])
    if not deps:
        return DependencyCheckResult()

    result = DependencyCheckResult()
    instance_id = instance.id

    for dep in deps:
        if dep.strategy == DeletionStrategy.IGNORE:
            continue

        target_cls = resolve_model_class(dep.model)
        if target_cls is None:
            logger.warning(
                "DeletionDep references unknown model %r on %s",
                dep.model, model_cls.__name__,
            )
            continue

        fk_col = getattr(target_cls, dep.fk_field, None)
        if fk_col is None:
            logger.warning(
                "DeletionDep references unknown field %r on %s",
                dep.fk_field, dep.model,
            )
            continue

        # 基础过滤条件：FK 匹配 + 未软删除
        conditions = [fk_col == instance_id]
        if hasattr(target_cls, "is_deleted"):
            conditions.append(target_cls.is_deleted.is_(False))

        # 多租户隔离：如果目标模型是 TenantModel 且提供了 tenant_id
        if tenant_id is not None and issubclass(target_cls, TenantModel):
            conditions.append(target_cls.tenant_id == tenant_id)

        if dep.strategy == DeletionStrategy.BLOCK:
            info = await _check_block(db, target_cls, conditions, dep)
            if info is not None:
                result.blocked = True
                result.blockers.append(info)

        elif dep.strategy == DeletionStrategy.CASCADE_SOFT:
            info = await _count_deps(db, target_cls, conditions, dep)
            if info is not None:
                result.cascade_soft.append(info)

        elif dep.strategy == DeletionStrategy.CASCADE_DELETE:
            info = await _count_deps(db, target_cls, conditions, dep)
            if info is not None:
                result.cascade_delete.append(info)

        elif dep.strategy == DeletionStrategy.NULLIFY:
            info = await _count_deps(db, target_cls, conditions, dep)
            if info is not None:
                result.nullify.append(info)

    return result


async def _check_block(
    db: AsyncSession,
    target_cls: type,
    conditions: list[Any],
    dep: DeletionDep,
) -> DependencyInfo | None:
    """
    BLOCK 策略检查：使用 EXISTS 快速判断，存在依赖时获取数量和摘要。

    Returns:
        DependencyInfo if blocked, None otherwise
    """
    # 快速 EXISTS 检查
    stmt = select(exists().where(*conditions))
    has_deps = (await db.execute(stmt)).scalar()
    if not has_deps:
        return None

    # 获取数量
    count_stmt = select(func.count()).select_from(target_cls).where(*conditions)
    count = (await db.execute(count_stmt)).scalar() or 0

    # 获取前 N 条摘要
    items = await _fetch_preview_items(db, target_cls, conditions, dep.label_field)

    return DependencyInfo(
        model_name=dep.i18n_key or dep.model,
        count=count,
        items=items,
        strategy=dep.strategy.value,
    )


async def _count_deps(
    db: AsyncSession,
    target_cls: type,
    conditions: list[Any],
    dep: DeletionDep,
) -> DependencyInfo | None:
    """
    非 BLOCK 策略：统计数量（用于级联操作日志）。

    Returns:
        DependencyInfo if count > 0, None otherwise
    """
    count_stmt = select(func.count()).select_from(target_cls).where(*conditions)
    count = (await db.execute(count_stmt)).scalar() or 0
    if count == 0:
        return None

    return DependencyInfo(
        model_name=dep.i18n_key or dep.model,
        count=count,
        items=[],
        strategy=dep.strategy.value,
    )


async def _fetch_preview_items(
    db: AsyncSession,
    target_cls: type,
    conditions: list[Any],
    label_field: str,
) -> list[dict[str, Any]]:
    """
    获取前 N 条记录摘要用于前端展示。

    Returns:
        [{"id": 1, "label": "deepseek-chat"}, ...]
    """
    label_col = getattr(target_cls, label_field, None)
    if label_col is not None:
        stmt = (
            select(target_cls.id, label_col)
            .where(*conditions)
            .order_by(target_cls.id)
            .limit(_MAX_ITEMS_PREVIEW)
        )
    else:
        stmt = (
            select(target_cls.id)
            .where(*conditions)
            .order_by(target_cls.id)
            .limit(_MAX_ITEMS_PREVIEW)
        )

    rows = (await db.execute(stmt)).all()
    items: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {"id": row[0]}
        if label_col is not None and len(row) > 1:
            item["label"] = str(row[1]) if row[1] is not None else ""
        items.append(item)

    return items


async def execute_cascade_deps(
    db: AsyncSession,
    instance: Any,
    delete_level: str,
    tenant_id: int | None = None,
) -> dict[str, int]:
    """
    执行非 BLOCK 的级联操作（CASCADE_SOFT / CASCADE_DELETE / NULLIFY）。

    在主记录 soft_delete 之后调用。

    Args:
        db: 异步数据库会话
        instance: 已软删除的模型实例
        delete_level: 删除层级（tenant / admin）
        tenant_id: 租户 ID

    Returns:
        {"cascade_soft": N, "cascade_delete": N, "nullify": N}
    """
    model_cls = instance.__class__
    deps: list[DeletionDep] = getattr(model_cls, "__delete_deps__", [])
    if not deps:
        return {}

    instance_id = instance.id
    stats: dict[str, int] = {}
    now = utc_now()

    for dep in deps:
        if dep.strategy in (DeletionStrategy.BLOCK, DeletionStrategy.IGNORE):
            continue

        target_cls = resolve_model_class(dep.model)
        if target_cls is None:
            continue

        fk_col = getattr(target_cls, dep.fk_field, None)
        if fk_col is None:
            continue

        # 基础条件
        conditions = [fk_col == instance_id]

        # 多租户隔离
        if tenant_id is not None and issubclass(target_cls, TenantModel):
            conditions.append(target_cls.tenant_id == tenant_id)

        if dep.strategy == DeletionStrategy.CASCADE_SOFT:
            if not hasattr(target_cls, "is_deleted"):
                continue
            # 只对未删除的记录执行
            conditions.append(target_cls.is_deleted.is_(False))
            stmt = (
                update(target_cls)
                .where(*conditions)
                .values(
                    is_deleted=True,
                    deleted_at=now,
                    delete_level=delete_level,
                    updated_at=now,
                )
            )
            result = await db.execute(stmt)
            affected = result.rowcount
            if affected > 0:
                stats["cascade_soft"] = stats.get("cascade_soft", 0) + affected
                logger.info(
                    "CASCADE_SOFT %s.%s=%d → %s: %d rows",
                    model_cls.__name__, "id", instance_id,
                    dep.model, affected,
                )

        elif dep.strategy == DeletionStrategy.CASCADE_DELETE:
            from sqlalchemy import delete as sa_delete
            stmt = sa_delete(target_cls).where(*conditions)
            result = await db.execute(stmt)
            affected = result.rowcount
            if affected > 0:
                stats["cascade_delete"] = stats.get("cascade_delete", 0) + affected
                logger.info(
                    "CASCADE_DELETE %s.%s=%d → %s: %d rows",
                    model_cls.__name__, "id", instance_id,
                    dep.model, affected,
                )

        elif dep.strategy == DeletionStrategy.NULLIFY:
            stmt = (
                update(target_cls)
                .where(*conditions)
                .values(**{dep.fk_field: None, "updated_at": now})
            )
            result = await db.execute(stmt)
            affected = result.rowcount
            if affected > 0:
                stats["nullify"] = stats.get("nullify", 0) + affected
                logger.info(
                    "NULLIFY %s.%s=%d → %s.%s: %d rows",
                    model_cls.__name__, "id", instance_id,
                    dep.model, dep.fk_field, affected,
                )

    return stats


async def execute_cascade_escalate(
    db: AsyncSession,
    instance: Any,
    tenant_id: int | None = None,
) -> int:
    """
    级联升级子记录的删除层级（tenant → admin）。

    对 CASCADE_SOFT 声明的子模型中已软删除的记录执行升级。

    Returns:
        总影响行数
    """
    from app.enums.common import DeleteLevelEnum

    model_cls = instance.__class__
    deps: list[DeletionDep] = getattr(model_cls, "__delete_deps__", [])
    total = 0
    now = utc_now()

    for dep in deps:
        if dep.strategy != DeletionStrategy.CASCADE_SOFT:
            continue

        target_cls = resolve_model_class(dep.model)
        if target_cls is None or not hasattr(target_cls, "is_deleted"):
            continue

        fk_col = getattr(target_cls, dep.fk_field, None)
        if fk_col is None:
            continue

        conditions = [
            fk_col == instance.id,
            target_cls.is_deleted.is_(True),
        ]
        if tenant_id is not None and issubclass(target_cls, TenantModel):
            conditions.append(target_cls.tenant_id == tenant_id)

        stmt = (
            update(target_cls)
            .where(*conditions)
            .values(
                delete_level=DeleteLevelEnum.ADMIN.value,
                deleted_at=now,
                updated_at=now,
            )
        )
        result = await db.execute(stmt)
        total += result.rowcount

    return total


async def execute_cascade_restore(
    db: AsyncSession,
    instance: Any,
    tenant_id: int | None = None,
) -> int:
    """
    级联恢复子记录。

    对 CASCADE_SOFT 声明的子模型中已软删除的记录执行恢复。

    Returns:
        总影响行数
    """
    model_cls = instance.__class__
    deps: list[DeletionDep] = getattr(model_cls, "__delete_deps__", [])
    total = 0
    now = utc_now()

    for dep in deps:
        if dep.strategy != DeletionStrategy.CASCADE_SOFT:
            continue

        target_cls = resolve_model_class(dep.model)
        if target_cls is None or not hasattr(target_cls, "is_deleted"):
            continue

        fk_col = getattr(target_cls, dep.fk_field, None)
        if fk_col is None:
            continue

        conditions = [
            fk_col == instance.id,
            target_cls.is_deleted.is_(True),
        ]
        if tenant_id is not None and issubclass(target_cls, TenantModel):
            conditions.append(target_cls.tenant_id == tenant_id)

        stmt = (
            update(target_cls)
            .where(*conditions)
            .values(
                is_deleted=False,
                deleted_at=None,
                delete_level=None,
                updated_at=now,
            )
        )
        result = await db.execute(stmt)
        total += result.rowcount

    return total


__all__ = [
    "DependencyInfo",
    "DependencyCheckResult",
    "check_deletion_deps",
    "execute_cascade_deps",
    "execute_cascade_escalate",
    "execute_cascade_restore",
    "resolve_model_class",
]
