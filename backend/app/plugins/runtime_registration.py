"""Cold-path plugin runtime registration helpers.

These helpers keep runtime entrypoints that do not pass through FastAPI startup
from seeing an empty process-local ExtensionRegistry.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_REGISTER_LOCK: asyncio.Lock | None = None


def _get_register_lock() -> asyncio.Lock:
    global _REGISTER_LOCK
    if _REGISTER_LOCK is None:
        _REGISTER_LOCK = asyncio.Lock()
    return _REGISTER_LOCK


def _stable_plugin_names(source_plugins: Iterable[Any] | None) -> list[str]:
    return [
        name
        for name in dict.fromkeys(
            str(item or "").strip() for item in list(source_plugins or [])
        )
        if name
    ]


def _manifest_skill_names(manifest: Any) -> list[str]:
    if not isinstance(manifest, dict):
        return []
    extensions = manifest.get("extensions")
    if not isinstance(extensions, dict):
        return []
    skills = extensions.get("skills")
    if not isinstance(skills, list):
        return []

    names: list[str] = []
    for item in skills:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


async def _plugin_names_missing_skill_runtime(
    db: Any,
    *,
    source_plugins: list[str],
) -> list[str]:
    if not db or not source_plugins:
        return []

    from sqlalchemy import select

    from app.enums.plugin import PluginStatusEnum
    from app.models.system.plugin import Plugin
    from app.plugins.registry import ExtensionRegistry

    result = await db.execute(
        select(Plugin.name, Plugin.manifest).where(
            Plugin.name.in_(source_plugins),
            Plugin.status == PluginStatusEnum.ENABLED.value,
            Plugin.is_deleted.is_(False),
        )
    )
    registry = ExtensionRegistry.get_instance()
    missing: list[str] = []

    for plugin_name, manifest in result.all():
        normalized_plugin_name = str(plugin_name or "").strip()
        if not normalized_plugin_name:
            continue

        skill_names = _manifest_skill_names(manifest)
        if not skill_names:
            if registry.get_registered_count(normalized_plugin_name) <= 0:
                missing.append(normalized_plugin_name)
            continue

        if any(
            registry.get_plugin_skill_resolver(normalized_plugin_name, skill_name)
            is None
            for skill_name in skill_names
        ):
            missing.append(normalized_plugin_name)

    return missing


async def ensure_enabled_plugin_skill_runtime_registered(
    db: Any,
    *,
    source_plugins: Iterable[Any] | None,
) -> dict[str, Any]:
    """Ensure enabled plugin-owned skill resolvers are registered in this process.

    中文: AI runtime/CLI 等冷入口可能没有经过 FastAPI startup。这里仅在
    已授权插件 skill 的 resolver 缺失时触发 register-only restore，不写插件
    DB 状态，后续仍由技能解析器按统一 `plugin_resolver_missing` 语义降级。
    """
    plugin_names = _stable_plugin_names(source_plugins)
    if not plugin_names:
        return {"checked": [], "restored": 0, "failed": 0, "total": 0}

    try:
        missing = await _plugin_names_missing_skill_runtime(
            db,
            source_plugins=plugin_names,
        )
    except Exception as exc:  # noqa: BLE001 - runtime restore must degrade to resolver diagnostics
        logger.warning(
            "Plugin runtime registration precheck degraded: plugins={} err={}",
            plugin_names,
            str(exc),
        )
        return {
            "checked": plugin_names,
            "restored": 0,
            "failed": 0,
            "total": 0,
            "error": str(exc),
        }

    if not missing:
        return {"checked": plugin_names, "restored": 0, "failed": 0, "total": 0}

    async with _get_register_lock():
        try:
            missing = await _plugin_names_missing_skill_runtime(
                db,
                source_plugins=missing,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Plugin runtime registration recheck degraded: plugins={} err={}",
                plugin_names,
                str(exc),
            )
            return {
                "checked": plugin_names,
                "restored": 0,
                "failed": 0,
                "total": 0,
                "error": str(exc),
            }
        if not missing:
            return {
                "checked": plugin_names,
                "restored": 0,
                "failed": 0,
                "total": 0,
            }

        from app.plugins.startup import restore_enabled_plugins

        try:
            return await restore_enabled_plugins(
                db,
                run_heavy=False,
                mutate_db_status=False,
                plugin_names=missing,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Plugin runtime registration degraded: plugins={} err={}",
                missing,
                str(exc),
            )
            return {
                "checked": plugin_names,
                "restored": 0,
                "failed": len(missing),
                "total": len(missing),
                "error": str(exc),
            }


__all__ = ["ensure_enabled_plugin_skill_runtime_registered"]
