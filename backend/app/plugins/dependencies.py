"""
插件依赖管理

提供：
1. 安装时依赖检查（dependencies 中声明的插件是否已安装且版本满足）
2. 卸载时反向依赖检查（是否有其他插件依赖当前插件）
3. 禁用时依赖链检查
4. 冲突插件检测（conflicts 字段）
5. 平台版本要求校验（platform_version 字段）
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException

logger = LogManager.get_logger("app")

# semver 比较用的正则
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")

# 版本约束正则：>=1.0.0, ==2.1.0, ~=1.2.0 等
_CONSTRAINT_RE = re.compile(r"^(>=|<=|==|!=|>|<|~=)\s*(.+)$")


def _parse_version(version: str) -> tuple[int, ...]:
    """
    解析 semver 版本号为元组

    Args:
        version: 版本号字符串（如 "1.2.3"）

    Returns:
        版本元组 (major, minor, patch)
    """
    m = _VERSION_RE.match(version)
    if not m:
        return (0, 0, 0)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _check_version_constraint(version: str, constraint: str) -> bool:
    """
    检查版本是否满足约束

    Args:
        version: 实际版本号
        constraint: 版本约束（如 ">=1.0.0"）

    Returns:
        是否满足
    """
    m = _CONSTRAINT_RE.match(constraint.strip())
    if not m:
        return version == constraint

    op, required = m.group(1), m.group(2)
    v = _parse_version(version)
    r = _parse_version(required)

    if op == ">=":
        return v >= r
    elif op == "<=":
        return v <= r
    elif op == "==":
        return v == r
    elif op == "!=":
        return v != r
    elif op == ">":
        return v > r
    elif op == "<":
        return v < r
    elif op == "~=":
        return v >= r and v[:2] == r[:2]
    return False


async def check_dependencies(
    db: AsyncSession,
    dependencies: dict[str, str] | None,
) -> list[str]:
    """
    检查插件依赖是否满足

    遍历 dependencies 声明，检查每个依赖插件是否已安装且版本满足要求。

    Args:
        db: 数据库会话
        dependencies: 依赖声明（如 {"novusai-core": ">=1.0.0"}）

    Returns:
        未满足的依赖列表（每项为描述信息）
    """
    if not dependencies:
        return []

    from app.repositories.system.plugin_repository import PluginRepository

    repo = PluginRepository(db)
    missing: list[str] = []

    for dep_name, version_constraint in dependencies.items():
        dep_plugin = await repo.get_by_name(dep_name)
        if not dep_plugin:
            missing.append(
                f"{dep_name} ({version_constraint}) — "
                + _("plugin.dependency_not_installed")
            )
        elif not _check_version_constraint(dep_plugin.version, version_constraint):
            missing.append(
                f"{dep_name} ({version_constraint}) — "
                + _("plugin.dependency_version_mismatch",
                    version=dep_plugin.version)
            )

    return missing


async def check_dependencies_or_raise(
    db: AsyncSession,
    dependencies: dict[str, str] | None,
) -> None:
    """
    检查依赖，不满足时抛出 BusinessException

    Args:
        db: 数据库会话
        dependencies: 依赖声明
    """
    missing = await check_dependencies(db, dependencies)
    if missing:
        detail = "; ".join(missing)
        raise BusinessException(
            _("plugin.unmet_dependencies") + ": " + detail
        )


async def check_reverse_dependencies(
    db: AsyncSession,
    plugin_name: str,
) -> list[str]:
    """
    检查反向依赖：是否有其他插件依赖当前插件

    Args:
        db: 数据库会话
        plugin_name: 要卸载/禁用的插件名称

    Returns:
        依赖当前插件的其他插件名称列表
    """
    from app.repositories.system.plugin_repository import PluginRepository

    repo = PluginRepository(db)
    all_plugins = await repo.get_all_active()

    dependents: list[str] = []
    for p in all_plugins:
        deps = p.dependencies or {}
        if plugin_name in deps:
            dependents.append(p.name)

    return dependents


async def check_reverse_dependencies_or_raise(
    db: AsyncSession,
    plugin_name: str,
    action: str = "uninstall",
) -> None:
    """
    检查反向依赖，有依赖者时阻止操作

    Args:
        db: 数据库会话
        plugin_name: 插件名称
        action: 操作类型（用于错误消息）
    """
    dependents = await check_reverse_dependencies(db, plugin_name)
    if dependents:
        names = ", ".join(dependents)
        raise BusinessException(
            _("plugin.has_dependents") + f": {names}"
        )


async def check_conflicts(
    db: AsyncSession,
    conflicts: list[str] | None,
    plugin_name: str,
) -> list[str]:
    """
    检查冲突插件：是否有互斥插件已安装/已启用

    同时也检查反向冲突：已安装的插件是否在其 conflicts 中声明了当前插件。

    Args:
        db: 数据库会话
        conflicts: 当前插件声明的冲突列表
        plugin_name: 当前插件名称

    Returns:
        冲突的插件名称列表
    """
    from app.repositories.system.plugin_repository import PluginRepository

    repo = PluginRepository(db)
    conflicting: list[str] = []

    # 正向冲突：当前插件声明的冲突
    if conflicts:
        for conflict_name in conflicts:
            existing = await repo.get_by_name(conflict_name)
            if existing:
                conflicting.append(conflict_name)

    # 反向冲突：已安装插件声明与当前插件冲突
    all_plugins = await repo.get_all_active()
    for p in all_plugins:
        p_conflicts = p.conflicts or []
        if plugin_name in p_conflicts:
            if p.name not in conflicting:
                conflicting.append(p.name)

    return conflicting


async def check_conflicts_or_raise(
    db: AsyncSession,
    conflicts: list[str] | None,
    plugin_name: str,
) -> None:
    """
    检查冲突，有冲突时抛出 BusinessException

    Args:
        db: 数据库会话
        conflicts: 冲突声明
        plugin_name: 当前插件名称
    """
    conflicting = await check_conflicts(db, conflicts, plugin_name)
    if conflicting:
        names = ", ".join(conflicting)
        raise BusinessException(
            _("plugin.has_conflicts") + f": {names}"
        )


def check_platform_version(
    required: str | None,
    current_version: str | None = None,
) -> bool:
    """
    检查平台版本是否满足要求

    Args:
        required: 版本约束（如 ">=2.0.0"）
        current_version: 当前平台版本

    Returns:
        是否满足
    """
    if not required:
        return True

    if not current_version:
        from app.core.config import settings
        current_version = getattr(settings, "PLATFORM_VERSION", "1.0.0")

    return _check_version_constraint(current_version, required)


def check_platform_version_or_raise(
    required: str | None,
    current_version: str | None = None,
) -> None:
    """
    检查平台版本，不满足时抛出 BusinessException
    """
    if not check_platform_version(required, current_version):
        raise BusinessException(
            _("plugin.platform_version_mismatch") + f": {required}"
        )


async def check_dependencies_detailed(
    db: AsyncSession,
    dependencies: dict[str, str] | None,
) -> list[dict[str, Any]]:
    """
    返回结构化的依赖检查结果（供前端展示）

    Args:
        db: 数据库会话
        dependencies: 依赖声明

    Returns:
        [{"name": "...", "required": ">=1.0.0", "status": "ok|missing|version_mismatch",
          "installed_version": "1.0.0"|null}, ...]
    """
    if not dependencies:
        return []

    from app.repositories.system.plugin_repository import PluginRepository

    repo = PluginRepository(db)
    results: list[dict[str, Any]] = []

    for dep_name, version_constraint in dependencies.items():
        dep_plugin = await repo.get_by_name(dep_name)
        if not dep_plugin:
            results.append({
                "name": dep_name,
                "required": version_constraint,
                "status": "missing",
                "installed_version": None,
            })
        elif not _check_version_constraint(dep_plugin.version, version_constraint):
            results.append({
                "name": dep_name,
                "required": version_constraint,
                "status": "version_mismatch",
                "installed_version": dep_plugin.version,
            })
        else:
            results.append({
                "name": dep_name,
                "required": version_constraint,
                "status": "ok",
                "installed_version": dep_plugin.version,
            })

    return results


__all__ = [
    "check_dependencies",
    "check_dependencies_detailed",
    "check_dependencies_or_raise",
    "check_reverse_dependencies",
    "check_reverse_dependencies_or_raise",
    "check_conflicts",
    "check_conflicts_or_raise",
    "check_platform_version",
    "check_platform_version_or_raise",
]
