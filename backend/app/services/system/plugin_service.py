"""
插件 Service / Plugin Service

封装插件安装/启停/卸载/配置/企业分配等业务逻辑。
Encapsulates plugin install/enable/disable/uninstall/config/tenant assignment business logic.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.base_service import BaseService
from app.core.logging import get_logger
from app.exceptions.base import BusinessException, NotFoundException, ValidationException
from app.models.system.plugin import Plugin
from app.repositories.system.plugin_repository import PluginRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class PluginService(BaseService[Plugin, PluginRepository]):
    """插件业务服务"""

    model = Plugin
    repository_class = PluginRepository

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        from app.plugins.lifecycle import PluginLifecycle
        from app.plugins.loader import PluginLoader

        self._lifecycle = PluginLifecycle(db)
        self._loader = PluginLoader()

    @staticmethod
    def _validate_config_against_schema(config: dict, schema: dict) -> None:
        """
        对插件配置执行轻量级 JSON-Schema 校验。

        说明：
        - 当前只覆盖项目实际会用到的常见约束（required/type/enum/min-max/pattern）。
        - 重点补齐 required 字段对空字符串的拦截（避免 `""` 绕过 required）。
        """
        if not isinstance(config, dict):
            raise ValidationException(message="Plugin config must be an object")
        if not isinstance(schema, dict):
            return

        properties = schema.get("properties") or {}
        required_fields = schema.get("required") or []

        # required: 同时拦截 key 缺失与空字符串
        missing_required: list[str] = []
        for field in required_fields:
            if field not in config:
                missing_required.append(field)
                continue
            value = config.get(field)
            if value is None:
                missing_required.append(field)
                continue
            if isinstance(value, str) and value.strip() == "":
                missing_required.append(field)
        if missing_required:
            raise ValidationException(
                message=f"Missing required plugin config fields: {', '.join(missing_required)}",
            )

        def _type_ok(value: object, expected_type: str) -> bool:
            if expected_type == "string":
                return isinstance(value, str)
            if expected_type == "integer":
                return isinstance(value, int) and not isinstance(value, bool)
            if expected_type == "number":
                return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
            if expected_type == "boolean":
                return isinstance(value, bool)
            if expected_type == "object":
                return isinstance(value, dict)
            if expected_type == "array":
                return isinstance(value, list)
            return True

        for key, value in config.items():
            if key not in properties:
                # 允许额外字段，保持向后兼容
                continue
            spec = properties.get(key) or {}
            expected_type = spec.get("type")
            if isinstance(expected_type, str) and not _type_ok(value, expected_type):
                raise ValidationException(
                    message=f"Invalid type for config '{key}', expected {expected_type}",
                )

            if "enum" in spec and value not in (spec.get("enum") or []):
                raise ValidationException(
                    message=f"Invalid value for config '{key}', allowed: {spec.get('enum')}",
                )

            if isinstance(value, str):
                min_len = spec.get("minLength")
                if isinstance(min_len, int) and len(value) < min_len:
                    raise ValidationException(
                        message=f"Config '{key}' must have at least {min_len} characters",
                    )
                max_len = spec.get("maxLength")
                if isinstance(max_len, int) and len(value) > max_len:
                    raise ValidationException(
                        message=f"Config '{key}' must have at most {max_len} characters",
                    )
                pattern = spec.get("pattern")
                if isinstance(pattern, str) and not re.search(pattern, value):
                    raise ValidationException(
                        message=f"Config '{key}' format is invalid",
                    )

            if isinstance(value, int) or isinstance(value, float):
                minimum = spec.get("minimum")
                if isinstance(minimum, int) or isinstance(minimum, float):
                    if value < minimum:
                        raise ValidationException(
                            message=f"Config '{key}' must be >= {minimum}",
                        )
                maximum = spec.get("maximum")
                if isinstance(maximum, int) or isinstance(maximum, float):
                    if value > maximum:
                        raise ValidationException(
                            message=f"Config '{key}' must be <= {maximum}",
                        )

    # ── 安装/启停/卸载 ──

    async def install_from_path(
        self,
        source_path: Path,
        config: dict | None = None,
        capabilities: list[str] | None = None,
        operator_id: int | None = None,
    ) -> Plugin:
        """
        安装插件

        Args:
            source_path: 插件源目录
            config: 初始配置
            capabilities: 授权能力列表
            operator_id: 操作者管理员 ID（用于进度推送）
        """
        plugin = await self._lifecycle.install(source_path, config, operator_id=operator_id)
        if capabilities:
            plugin.granted_capabilities = capabilities
            await self.db.flush()
        return plugin

    async def enable_plugin(self, plugin_id: int, operator_id: int | None = None) -> None:
        """启用插件"""
        await self._lifecycle.enable(plugin_id, operator_id=operator_id)

    async def disable_plugin(self, plugin_id: int, force: bool = False, operator_id: int | None = None) -> None:
        """禁用插件"""
        await self._lifecycle.disable(plugin_id, force=force, operator_id=operator_id)

    async def install_plugin_dependencies(
        self,
        plugin_id: int,
        *,
        install_python: bool = True,
        install_npm: bool = True,
    ) -> dict:
        """显式安装插件依赖（不改变插件状态）"""
        return await self._lifecycle.install_dependencies(
            plugin_id,
            install_python=install_python,
            install_npm=install_npm,
        )

    async def uninstall_plugin_dependencies(
        self,
        plugin_id: int,
        *,
        uninstall_python: bool = True,
        uninstall_npm: bool = True,
        force: bool = False,
    ) -> dict:
        """显式卸载插件依赖（不卸载插件本体）"""
        return await self._lifecycle.uninstall_dependencies(
            plugin_id,
            uninstall_python=uninstall_python,
            uninstall_npm=uninstall_npm,
            force=force,
        )

    async def uninstall_plugin(
        self,
        plugin_id: int,
        confirm_data_delete: bool = False,
        *,
        cleanup_dependencies: bool = False,
        operator_id: int | None = None,
    ) -> None:
        """卸载插件"""
        await self._lifecycle.uninstall(
            plugin_id,
            confirm_data_delete,
            cleanup_dependencies=cleanup_dependencies,
            operator_id=operator_id,
        )

    # ── 配置 ──

    async def update_plugin_config(
        self, plugin_id: int, config: dict
    ) -> Plugin:
        """更新插件全局配置（自动加密敏感字段）"""
        from app.plugins.crypto import encrypt_plugin_config

        plugin = await self.repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(message="plugin.error.not_found")

        # 优先读取磁盘最新 manifest（便于插件作者修正 schema 后立即生效）
        manifest_data = plugin.manifest or {}
        try:
            latest_manifest = self._loader.load_manifest(plugin.name)
            manifest_data = latest_manifest.model_dump(exclude_none=True)
            plugin.manifest = manifest_data
        except Exception as exc:
            logger.warning(
                "Failed to load latest manifest for plugin %s, fallback to DB manifest: %s",
                plugin.name,
                exc,
            )

        config_schema = manifest_data.get("config_schema")
        if config_schema:
            self._validate_config_against_schema(config, config_schema)
            config = encrypt_plugin_config(config, config_schema)

        plugin.config = config
        await self.db.flush()
        return plugin

    async def update_capabilities(
        self, plugin_id: int, capabilities: list[str]
    ) -> Plugin:
        """更新插件授权能力列表"""
        plugin = await self.repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(message="plugin.error.not_found")

        plugin.granted_capabilities = capabilities
        await self.db.flush()
        return plugin

    # ── 企业分配 ──

    async def assign_tenants(
        self, plugin_id: int, tenant_ids: list[int]
    ) -> int:
        """
        批量分配企业

        Returns:
            实际新增的分配数量
        """
        from sqlalchemy import select

        from app.models.system.resource_tenant_assignment import (
            ResourceTenantAssignment,
        )

        plugin = await self.repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(message="plugin.error.not_found")

        # 查询已有分配（仅非软删除记录；已删除的分配不阻止重新分配）
        result = await self.db.execute(
            select(ResourceTenantAssignment.tenant_id).where(
                ResourceTenantAssignment.resource_type == "plugin",
                ResourceTenantAssignment.resource_id == plugin_id,
                ResourceTenantAssignment.is_deleted.is_(False),
            )
        )
        existing = set(result.scalars())

        count = 0
        for tid in tenant_ids:
            if tid not in existing:
                self.db.add(ResourceTenantAssignment(
                    resource_type="plugin",
                    resource_id=plugin_id,
                    tenant_id=tid,
                    is_active=True,
                    config={},
                ))
                count += 1

        if count:
            await self.db.flush()
        return count

    async def unassign_tenant(self, plugin_id: int, tenant_id: int) -> None:
        """取消企业分配"""
        from sqlalchemy import delete

        from app.models.system.resource_tenant_assignment import (
            ResourceTenantAssignment,
        )

        await self.db.execute(
            delete(ResourceTenantAssignment).where(
                ResourceTenantAssignment.resource_type == "plugin",
                ResourceTenantAssignment.resource_id == plugin_id,
                ResourceTenantAssignment.tenant_id == tenant_id,
            )
        )
        await self.db.flush()

    async def toggle_tenant_assignment(
        self, plugin_id: int, tenant_id: int, is_active: bool
    ) -> None:
        """切换企业分配启用状态"""
        from sqlalchemy import update

        from app.models.system.resource_tenant_assignment import (
            ResourceTenantAssignment,
        )

        await self.db.execute(
            update(ResourceTenantAssignment).where(
                ResourceTenantAssignment.resource_type == "plugin",
                ResourceTenantAssignment.resource_id == plugin_id,
                ResourceTenantAssignment.tenant_id == tenant_id,
            ).values(is_active=is_active)
        )
        await self.db.flush()

    # ── License ──

    async def activate_license(
        self, plugin_id: int, license_key: str
    ) -> None:
        """激活插件 License"""
        from app.plugins.license import activate_license as activate_plugin_license

        result = await activate_plugin_license(plugin_id, license_key, self.db)
        if not result.get("success"):
            raise BusinessException(
                message=result.get("message") or "plugin.error.license_invalid",
            )

    # ── 查询辅助 ──

    async def get_readme(
        self, plugin_id: int, locale: str = "zh-CN"
    ) -> str | None:
        """获取插件 README"""
        plugin = await self.repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(message="plugin.error.not_found")
        return self._loader.load_readme(plugin.name, locale)

    async def get_by_name(self, name: str) -> Plugin | None:
        """根据名称查询插件"""
        return await self.repo.get_by_name(name)

    async def list_enabled(self) -> list[Plugin]:
        """查询所有已启用的插件"""
        return await self.repo.list_enabled()

    async def get_tenant_visible_plugin_names(self, tenant_id: int) -> set[str]:
        """
        获取当前企业可见的已启用插件名称集合。

        过滤规则（基于 ResourceScopeEnum）：
        - ADMIN_ONLY        → 企业端不可见
        - ALL_TENANTS       → 所有企业可见
        - ADMIN_AND_ALL     → 所有企业可见
        - ASSIGNED_TENANTS  → 仅分配了当前企业的插件
        - ADMIN_AND_ASSIGNED→ 仅分配了当前企业的插件
        """
        from sqlalchemy import select

        from app.enums.common import ResourceScopeEnum
        from app.enums.plugin import PluginStatusEnum
        from app.models.system.resource_tenant_assignment import (
            ResourceTenantAssignment,
        )

        # 查询当前企业被分配的插件 ID
        assignment_result = await self.db.execute(
            select(ResourceTenantAssignment.resource_id).where(
                ResourceTenantAssignment.resource_type == "plugin",
                ResourceTenantAssignment.tenant_id == tenant_id,
                ResourceTenantAssignment.is_active.is_(True),
            )
        )
        assigned_plugin_ids = set(assignment_result.scalars().all())

        # 查询所有已启用插件的名称+scope+id
        plugin_result = await self.db.execute(
            select(Plugin.name, Plugin.scope, Plugin.id).where(
                Plugin.status == PluginStatusEnum.ENABLED.value,
                Plugin.is_deleted.is_(False),
            )
        )
        plugin_rows = plugin_result.all()

        _TENANT_ALL_SCOPES = {
            ResourceScopeEnum.ALL_TENANTS.value,
            ResourceScopeEnum.ADMIN_AND_ALL.value,
        }
        _TENANT_ASSIGNED_SCOPES = {
            ResourceScopeEnum.ASSIGNED_TENANTS.value,
            ResourceScopeEnum.ADMIN_AND_ASSIGNED.value,
        }

        visible: set[str] = set()
        for row in plugin_rows:
            pname, pscope, pid = row[0], row[1], row[2]
            if pscope in _TENANT_ALL_SCOPES or pscope in _TENANT_ASSIGNED_SCOPES and pid in assigned_plugin_ids:
                visible.add(pname)
        return visible

    # ── 依赖状态（用于前端卡片展示） ──

    @staticmethod
    def _normalize_python_package_name(raw: str) -> str:
        """将 requirement 字符串归一化为可用于 metadata 查询的包名。"""
        name = re.split(r"[><=!~;@\[]", raw, maxsplit=1)[0].strip()
        return re.sub(r"[-_.]+", "-", name).lower()

    @staticmethod
    def _is_python_distribution_installed(package_name: str) -> bool:
        """判断 Python 包是否已安装（兼容 -/_ 命名差异）。"""
        from importlib import metadata as importlib_metadata

        normalized = package_name.strip()
        if not normalized:
            return False

        candidates = {
            normalized,
            normalized.replace("-", "_"),
            normalized.replace("_", "-"),
        }
        for candidate in candidates:
            try:
                importlib_metadata.version(candidate)
                return True
            except importlib_metadata.PackageNotFoundError:
                continue
        return False

    @staticmethod
    def _parse_npm_package_name(raw: str) -> str:
        """从 npm spec 中提取包名（支持 scoped package）。"""
        val = (raw or "").strip()
        if not val:
            return ""
        if val.startswith("@"):
            # scoped: @scope/name 或 @scope/name@^1.2.3
            return val.rsplit("@", 1)[0] if "@" in val[1:] else val
        return val.split("@", 1)[0]

    def _load_host_npm_dependency_names(self) -> set[str]:
        """读取宿主 web-antd package.json 中声明的依赖名。"""
        import json

        host_pkg = (
            Path(__file__).resolve().parents[4]
            / "frontend"
            / "apps"
            / "web-antd"
            / "package.json"
        )
        if not host_pkg.is_file():
            return set()

        try:
            data = json.loads(host_pkg.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to read host package.json for npm deps: %s", exc)
            return set()

        names: set[str] = set()
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            deps = data.get(key, {})
            if isinstance(deps, dict):
                names.update(deps.keys())
        return names

    def get_dependency_status(self, plugin: Plugin) -> dict:
        """
        计算插件依赖状态。

        - Python 依赖：按环境标记过滤后逐包检查
        - npm 依赖：仅 DEBUG 模式检查（生产模式 UMD 不要求 npm 依赖）
        """
        from app.core.config import settings

        manifest = plugin.manifest or {}
        dependencies = manifest.get("dependencies", {}) if isinstance(manifest, dict) else {}
        raw_python_deps = dependencies.get("python", []) if isinstance(dependencies, dict) else []

        # 1) Python 依赖（考虑 marker）
        required_python_names: list[str] = []
        for raw in raw_python_deps if isinstance(raw_python_deps, list) else []:
            raw_text = str(raw or "").strip()
            if not raw_text:
                continue
            try:
                from packaging.requirements import Requirement

                req = Requirement(raw_text)
                if req.marker and not req.marker.evaluate():
                    continue
                required_python_names.append(req.name)
            except Exception:
                normalized = self._normalize_python_package_name(raw_text)
                if normalized:
                    required_python_names.append(normalized)

        # 去重保序
        required_python_names = list(dict.fromkeys(required_python_names))
        missing_python = [
            name
            for name in required_python_names
            if not self._is_python_distribution_installed(name)
        ]

        # 2) npm 依赖（仅 dev 模式需要）
        extensions = manifest.get("extensions", {}) if isinstance(manifest, dict) else {}
        frontend = extensions.get("frontend", {}) if isinstance(extensions, dict) else {}
        raw_npm_deps = (
            frontend.get("npm_dependencies", [])
            if isinstance(frontend, dict)
            else []
        )
        npm_declared = [self._parse_npm_package_name(str(v or "")) for v in raw_npm_deps]
        npm_declared = [v for v in npm_declared if v]
        npm_declared = list(dict.fromkeys(npm_declared))

        if settings.DEBUG:
            host_npm_names = self._load_host_npm_dependency_names()
            missing_npm = [name for name in npm_declared if name not in host_npm_names]
            npm_state = "installed" if not missing_npm else "missing"
        else:
            # 生产模式插件前端使用预编译 UMD 包，不要求宿主安装 npm 依赖
            missing_npm = []
            npm_state = "not_required"

        overall_ready = len(missing_python) == 0 and len(missing_npm) == 0

        return {
            "overall": "installed" if overall_ready else "missing",
            "production_mode": not settings.DEBUG,
            "python": {
                "declared": len(required_python_names),
                "installed": len(required_python_names) - len(missing_python),
                "missing": missing_python,
                "state": "installed" if len(missing_python) == 0 else "missing",
            },
            "npm": {
                "declared": len(npm_declared),
                "installed": len(npm_declared) - len(missing_npm),
                "missing": missing_npm,
                "state": npm_state,
            },
        }
