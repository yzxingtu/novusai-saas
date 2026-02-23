"""
技能 Service
"""

from typing import Any

from app.core.base_service import TenantService, GlobalService
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import SkillTypeEnum, get_all_skill_types
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.skill import Skill
from app.repositories.ai.skill_repository import SkillRepository, AdminSkillRepository

logger = LogManager.get_logger("ai")


class SkillService(TenantService[Skill, SkillRepository]):
    """
    租户端技能 Service

    提供技能的创建、更新、删除等业务逻辑
    """

    model = Skill
    repository_class = SkillRepository

    async def _get_toolkit_security_level(self) -> str | None:
        """读取平台 Toolkit 安全等级配置（扫描开启时返回等级，否则 None）"""
        from app.configs.service import ConfigService
        cfg = ConfigService(self.repo.db)
        scan_enabled = await cfg.get_platform_config(
            "toolkit_scan_on_upload", default=True,
        )
        if not scan_enabled:
            return None
        level = await cfg.get_platform_config(
            "toolkit_security_level", default="normal",
        )
        return str(level)

    async def _before_create(self, data: dict[str, Any]) -> None:
        """创建前校验：名称唯一性、类型合法性 + 插件钩子"""
        await super()._before_create(data)

        from app.ai.events.hooks import HookPoint, get_hook_registry
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.BEFORE_SKILL_CREATE):
            ctx = await hook_registry.trigger(
                HookPoint.BEFORE_SKILL_CREATE,
                tenant_id=self.repo.tenant_id,
                skill_data=data,
            )
            if ctx.get("blocked"):
                raise BusinessException(message=ctx.get("block_reason", _("skill.error.blocked_by_hook")))
            data.update(ctx.get("skill_data", data))

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name(name)
            if existing:
                raise BusinessException(message=_("skill.error.name_exists"))

        skill_type = data.get("type", SkillTypeEnum.TOOLKIT.value)
        valid_types = get_all_skill_types()
        if skill_type not in valid_types:
            raise BusinessException(message=_("skill.error.invalid_type"))

        security_level = await self._get_toolkit_security_level()
        self._parse_toolkit_meta(data, skill_type, security_level)

    async def _after_create(self, instance: Skill) -> None:
        """创建后：触发插件钩子"""
        await super()._after_create(instance)
        from app.ai.events.hooks import HookPoint, get_hook_registry
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.AFTER_SKILL_CREATE):
            await hook_registry.trigger(
                HookPoint.AFTER_SKILL_CREATE,
                tenant_id=self.repo.tenant_id,
                skill_id=instance.id,
                skill_data=instance.to_dict() if hasattr(instance, "to_dict") else {},
            )

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """更新前校验：名称唯一性、系统技能保护 + 插件钩子"""
        await super()._before_update(id, data)

        from app.ai.events.hooks import HookPoint, get_hook_registry
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.BEFORE_SKILL_UPDATE):
            ctx = await hook_registry.trigger(
                HookPoint.BEFORE_SKILL_UPDATE,
                tenant_id=self.repo.tenant_id,
                skill_id=id,
                updates=data,
            )
            if ctx.get("blocked"):
                raise BusinessException(message=ctx.get("block_reason", _("skill.error.blocked_by_hook")))
            data.update(ctx.get("updates", data))

        skill = await self.repo.get_by_id(id)
        if not skill:
            raise NotFoundException(message=_("skill.error.not_found"))

        # 系统技能不允许修改关键字段
        if skill.is_system:
            protected = {"type", "is_system", "is_active"}
            if protected & set(data.keys()):
                raise BusinessException(message=_("skill.error.system_protected"))

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name(name, exclude_id=id)
            if existing:
                raise BusinessException(message=_("skill.error.name_exists"))

        skill_type = data.get("type", skill.type)
        security_level = await self._get_toolkit_security_level()
        self._parse_toolkit_meta(data, skill_type, security_level)

    async def _after_update(self, instance: Skill) -> None:
        """更新后：触发插件钩子"""
        await super()._after_update(instance)
        from app.ai.events.hooks import HookPoint, get_hook_registry
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.AFTER_SKILL_UPDATE):
            await hook_registry.trigger(
                HookPoint.AFTER_SKILL_UPDATE,
                tenant_id=self.repo.tenant_id,
                skill_id=instance.id,
                updates=instance.to_dict() if hasattr(instance, "to_dict") else {},
            )

    async def _before_delete(self, id: int) -> None:
        """删除前校验：系统技能不可删除 + 插件钩子"""
        await super()._before_delete(id)

        from app.ai.events.hooks import HookPoint, get_hook_registry
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.BEFORE_SKILL_DELETE):
            ctx = await hook_registry.trigger(
                HookPoint.BEFORE_SKILL_DELETE,
                tenant_id=self.repo.tenant_id,
                skill_id=id,
            )
            if ctx.get("blocked"):
                raise BusinessException(message=ctx.get("block_reason", _("skill.error.blocked_by_hook")))

        skill = await self.repo.get_by_id(id)
        if not skill:
            raise NotFoundException(message=_("skill.error.not_found"))

        if skill.is_system:
            raise BusinessException(message=_("skill.error.system_protected"))

    async def _after_delete(self, instance: Skill) -> None:
        """删除后：触发插件钩子"""
        await super()._after_delete(instance)
        from app.ai.events.hooks import HookPoint, get_hook_registry
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.AFTER_SKILL_DELETE):
            await hook_registry.trigger(
                HookPoint.AFTER_SKILL_DELETE,
                tenant_id=self.repo.tenant_id,
                skill_id=instance.id,
            )

    @staticmethod
    def _parse_toolkit_meta(
        data: dict[str, Any],
        skill_type: str,
        security_level: str | None = None,
    ) -> None:
        """If toolkit_content is provided, parse and cache toolkit_meta.

        Also performs security scan for non-system toolkits when
        toolkit_scan_on_upload is enabled (default).
        """
        if skill_type != SkillTypeEnum.TOOLKIT.value:
            return
        toolkit_content = data.get("toolkit_content")
        if toolkit_content is None:
            return
        if not toolkit_content.strip():
            data["toolkit_meta"] = None
            return

        # 安全扫描（非系统技能）
        is_system = data.get("is_system", False)
        if not is_system and security_level:
            from app.ai.tools.executors.toolkit_executor import (
                _scan_toolkit_security,
            )
            violations = _scan_toolkit_security(toolkit_content, security_level)
            if violations:
                detail = "; ".join(violations[:5])
                raise BusinessException(
                    message=_("skill.error.toolkit_security_violation", detail=detail),
                )

        try:
            from app.ai.skills.toolkit_parser import parse_toolkit
            meta = parse_toolkit(toolkit_content)
            data["toolkit_meta"] = meta.to_dict()
        except Exception as exc:
            raise BusinessException(
                message=_("skill.error.toolkit_parse_failed", error=str(exc)),
            )

    async def get_active_skills(self) -> list[Skill]:
        """获取当前租户所有已激活的技能"""
        return await self.repo.get_active_skills()

    async def get_by_type(self, skill_type: str) -> list[Skill]:
        """按类型获取技能"""
        return await self.repo.get_by_type(skill_type)


class AdminSkillService(GlobalService[Skill, AdminSkillRepository]):
    """
    管理端技能 Service

    无租户隔离，供平台管理端全局 CRUD 使用
    """

    model = Skill
    repository_class = AdminSkillRepository

    async def _get_toolkit_security_level(self) -> str | None:
        """读取平台 Toolkit 安全等级配置"""
        from app.configs.service import ConfigService
        cfg = ConfigService(self.repo.db)
        scan_enabled = await cfg.get_platform_config(
            "toolkit_scan_on_upload", default=True,
        )
        if not scan_enabled:
            return None
        level = await cfg.get_platform_config(
            "toolkit_security_level", default="normal",
        )
        return str(level)

    async def _before_create(self, data: dict[str, Any]) -> None:
        """创建前校验：类型合法性、toolkit_meta 解析"""
        await super()._before_create(data)

        skill_type = data.get("type", SkillTypeEnum.TOOLKIT.value)
        valid_types = get_all_skill_types()
        if skill_type not in valid_types:
            raise BusinessException(message=_("skill.error.invalid_type"))

        security_level = await self._get_toolkit_security_level()
        SkillService._parse_toolkit_meta(data, skill_type, security_level)

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """更新前校验：系统技能保护"""
        await super()._before_update(id, data)

        skill = await self.repo.get_by_id(id)
        if not skill:
            raise NotFoundException(message=_("skill.error.not_found"))

        if skill.is_system:
            protected = {"type", "is_system", "is_active"}
            if protected & set(data.keys()):
                raise BusinessException(message=_("skill.error.system_protected"))

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name_in_package(
                name=name,
                package_id=skill.package_id,
                exclude_id=id,
            )
            if existing:
                raise BusinessException(message=_("skill.error.name_exists"))

        skill_type = data.get("type", skill.type)
        security_level = await self._get_toolkit_security_level()
        SkillService._parse_toolkit_meta(data, skill_type, security_level)

    async def _before_delete(self, id: int) -> None:
        """删除前校验：系统技能不可删除"""
        await super()._before_delete(id)

        skill = await self.repo.get_by_id(id)
        if not skill:
            raise NotFoundException(message=_("skill.error.not_found"))

        if skill.is_system:
            raise BusinessException(message=_("skill.error.system_protected"))

    async def update_status(self, id: int, is_active: bool) -> Skill:
        """切换技能状态，系统技能不可禁用"""
        skill = await self.repo.get_by_id(id)
        if not skill:
            raise NotFoundException(message=_("skill.error.not_found"))

        if skill.is_system and not is_active:
            raise BusinessException(message=_("skill.error.system_protected"))

        updated = await self.repo.update(id, {"is_active": is_active})
        return updated


__all__ = ["SkillService", "AdminSkillService"]
