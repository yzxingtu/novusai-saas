"""
企业网盘插件 — PluginBase 生命周期

关键约束（来自 plugin-spec.md）：
- ctx.get_db() 返回 PluginDbProxy，仅允许操作 px_netdisk_* 表
- 系统表（tenants / SkillPackage / PeriodicTask）访问会触发 PluginSecurityError
- SkillPackage + Skill DB 记录由平台 lifecycle enable 阶段自动创建
- 定时任务由 plugin.yaml extensions.tasks 声明，ExtensionRegistry 负责注册
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

from app.plugins.base import PluginBase


def _ensure_legacy_backend_package() -> None:
    """Register a legacy `backend` package alias for this plugin. / 插件

    Netdisk historically uses absolute imports like `backend.services.*`.
    When plugin modules are loaded directly, package `backend` may not exist."""
    backend_pkg = sys.modules.get("backend")
    backend_path = str(Path(__file__).resolve().parent)

    if backend_pkg is None:
        backend_pkg = types.ModuleType("backend")
        backend_pkg.__path__ = [backend_path]  # type: ignore[attr-defined]
        sys.modules["backend"] = backend_pkg
        return

    pkg_path = list(getattr(backend_pkg, "__path__", []))
    if backend_path not in pkg_path:
        pkg_path.append(backend_path)
        backend_pkg.__path__ = pkg_path  # type: ignore[attr-defined]


_ensure_legacy_backend_package()


class NetDiskPlugin(PluginBase):
    """企业网盘插件 / Tenant netdisk plugin."""

    async def on_install(self, ctx) -> None:
        """安装回调 — Alembic 迁移已由平台执行完毕，配额懒加载 / On install: migrations done by platform, quota lazy."""
        log = ctx.get_logger()
        log.info("netdisk: on_install complete")

    async def on_enable(self, ctx) -> None:
        """启用回调 — 定时任务由 extensions.tasks 声明，ExtensionRegistry 自动注册 / On enable: tasks auto-registered."""
        log = ctx.get_logger()
        log.info("netdisk: on_enable complete")

    async def on_disable(self, ctx) -> None:
        """禁用回调 — ExtensionRegistry 自动反注册定时任务 / On disable: tasks auto-unregistered."""
        log = ctx.get_logger()
        log.info("netdisk: on_disable complete")

    async def on_uninstall(self, ctx) -> None:
        """卸载回调 — 清理 px_netdisk_* 业务数据（Alembic downgrade 由平台执行） / On uninstall: clear px_netdisk_* data."""
        log = ctx.get_logger()
        log.info("netdisk: on_uninstall start")

        db = ctx.get_db()  # PluginDbProxy — 仅 px_netdisk_* 表
        from sqlalchemy import text

        # 清理顺序遵从 FK 依赖：shares → nodes → quotas
        await db.execute(text("DELETE FROM px_netdisk_shares"))
        await db.execute(text("DELETE FROM px_netdisk_nodes"))
        await db.execute(text("DELETE FROM px_netdisk_quotas"))
        await db.commit()

        log.info("netdisk: on_uninstall complete")

    async def on_upgrade(self, ctx, old_version: str) -> None:
        log = ctx.get_logger()
        log.info("netdisk: upgraded from %s to current", old_version)
