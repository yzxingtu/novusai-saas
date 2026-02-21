"""
SkillPlugin 自动装配器

负责 SkillPlugin 启用/禁用/卸载时的 SkillPackage + Skill 记录管理。
从 PluginManager 提取，降低 God Object 复杂度。
"""

from __future__ import annotations

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import LogManager
from app.models.ai.skill import Skill
from app.plugins.config_manager import PluginConfigManager
from app.plugins.extensions.skill_plugin import SkillPlugin
from app.core.base_model import utc_now

logger = LogManager.get_logger("app")


class SkillPluginProvisioner:
    """
    SkillPlugin 自动装配器

    职责：
    - 启用 SkillPlugin 时自动创建 SkillPackage + Skill 记录
    - 禁用时停用记录
    - 卸载时软删除记录
    - 幂等操作：已有记录时恢复激活
    """

    @staticmethod
    async def provision(
        db: AsyncSession,
        instance: SkillPlugin,
    ) -> None:
        """
        SkillPlugin 启用时自动创建 SkillPackage + Skill 记录

        幂等：若已存在同名 source_plugin 记录则恢复激活，不重复创建。
        """
        from app.repositories.ai.skill_package_repository import (
            AdminSkillPackageRepository,
        )
        from app.repositories.ai.skill_repository import AdminSkillRepository

        pkg_repo = AdminSkillPackageRepository(db)
        skill_repo = AdminSkillRepository(db)

        plugin_name = instance.name
        skill_type = instance.get_skill_type()
        display_name = instance.get_skill_display_name()

        # 幂等：检查是否已有该插件创建的技能包
        existing_pkg = await pkg_repo.get_by_source_plugin(plugin_name)
        if existing_pkg:
            # 已存在 → 恢复激活
            if existing_pkg.is_deleted or not existing_pkg.is_active:
                await pkg_repo.update(existing_pkg.id, {
                    "is_active": True,
                    "is_deleted": False,
                    "deleted_at": None,
                    "delete_level": None,
                    "name": display_name,
                    "avatar": instance.get_skill_icon(),
                })
            # 恢复技能包下的技能
            stmt = select(Skill).where(
                and_(
                    Skill.package_id == existing_pkg.id,
                    Skill.type == skill_type,
                )
            )
            result = await db.execute(stmt)
            existing_skills = list(result.scalars().all())
            for s in existing_skills:
                if s.is_deleted or not s.is_active:
                    await skill_repo.update(s.id, {
                        "is_active": True,
                        "is_deleted": False,
                        "deleted_at": None,
                        "delete_level": None,
                    })
            logger.info(
                "Skill plugin re-activated: plugin=%s package_id=%d",
                plugin_name, existing_pkg.id,
            )
            return

        # 新建 SkillPackage
        config_schema = instance.get_skill_config_schema()
        default_config = PluginConfigManager.extract_schema_defaults(config_schema)

        # scope 根据插件作用域动态设置
        from app.enums.plugin import PluginScopeEnum
        plugin_scope = instance.scope
        if plugin_scope == PluginScopeEnum.PLATFORM_ONLY.value:
            pkg_scope = "admin"
        elif plugin_scope in (PluginScopeEnum.ALL_TENANTS.value, PluginScopeEnum.GLOBAL.value):
            pkg_scope = "system"
        else:
            pkg_scope = "admin"

        pkg = await pkg_repo.create({
            "name": display_name,
            "description": instance.description,
            "avatar": instance.get_skill_icon(),
            "scope": pkg_scope,
            "source_plugin": plugin_name,
            "is_system": True,
            "is_active": True,
            "tenant_id": None,
        })
        await db.flush()

        # 新建 Skill
        await skill_repo.create({
            "package_id": pkg.id,
            "name": display_name,
            "description": instance.description,
            "avatar": instance.get_skill_icon(),
            "type": skill_type,
            "scope": pkg_scope,
            "is_system": True,
            "is_active": True,
            "config": default_config,
            "input_schema": config_schema,
            "tenant_id": None,
        })
        await db.flush()

        logger.info(
            "Skill plugin provisioned: plugin=%s type=%s package_id=%d",
            plugin_name, skill_type, pkg.id,
        )

    @staticmethod
    async def deprovision(
        db: AsyncSession,
        instance: SkillPlugin,
        *,
        soft_delete: bool = False,
    ) -> None:
        """
        SkillPlugin 禁用/卸载时停用或软删除 SkillPackage + Skill

        Args:
            db: 数据库会话
            instance: SkillPlugin 实例
            soft_delete: True=软删除（卸载时），False=仅停用（禁用时）
        """
        from app.repositories.ai.skill_package_repository import (
            AdminSkillPackageRepository,
        )
        from app.repositories.ai.skill_repository import AdminSkillRepository

        pkg_repo = AdminSkillPackageRepository(db)
        skill_repo = AdminSkillRepository(db)
        plugin_name = instance.name

        existing_pkg = await pkg_repo.get_by_source_plugin(plugin_name)
        if not existing_pkg:
            return

        # 处理技能包下的所有技能
        stmt = select(Skill).where(Skill.package_id == existing_pkg.id)
        result = await db.execute(stmt)
        skills = list(result.scalars().all())

        if soft_delete:
            now = utc_now()
            for s in skills:
                await skill_repo.update(s.id, {
                    "is_active": False,
                    "is_deleted": True,
                    "deleted_at": now,
                    "delete_level": "admin",
                })
            await pkg_repo.update(existing_pkg.id, {
                "is_active": False,
                "is_deleted": True,
                "deleted_at": now,
                "delete_level": "admin",
            })
            logger.info(
                "Skill plugin soft-deleted: plugin=%s package_id=%d",
                plugin_name, existing_pkg.id,
            )
        else:
            for s in skills:
                await skill_repo.update(s.id, {"is_active": False})
            await pkg_repo.update(existing_pkg.id, {"is_active": False})
            logger.info(
                "Skill plugin deactivated: plugin=%s package_id=%d",
                plugin_name, existing_pkg.id,
            )


__all__ = ["SkillPluginProvisioner"]
