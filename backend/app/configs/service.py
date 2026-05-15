"""
Configuration read/write service / 配置读写服务

Provides CRUD operations for configs, supporting platform and tenant configs.
提供配置的 CRUD 操作，支持平台配置和企业配置
"""

import json
import math
import re
import time
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.meta import ConfigMeta
from app.configs.registry import ConfigRegistry, config_registry
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.config import ConfigScope, ConfigValueType
from app.enums.error_code import ErrorCode
from app.exceptions import BusinessException
from app.models.system.config import (
    SystemConfig,
    SystemConfigGroup,
    SystemConfigValue,
)
from app.utils.config_html_sanitize import sanitize_config_html

logger = LogManager.get_logger("app")

# Platform-level configs use tenant_id = 0 / 平台级配置使用 tenant_id = 0
PLATFORM_TENANT_ID = 0

# In-memory TTL cache (process-level, shared across requests) / 内存 TTL 缓存（进程级，跨请求共享）
_config_id_cache: dict[tuple[str | None, str], tuple[int | None, float]] = {}
_config_value_cache: dict[str, tuple[Any, float]] = {}
_CONFIG_ID_TTL = (
    300  # config key → id mapping rarely changes, cache 5 min / 缓存 5 分钟
)
_CONFIG_VALUE_TTL = 60  # Config value cache 60 seconds / 配置值缓存 60 秒


class ConfigService:
    """
    Configuration read/write service / 配置读写服务

    Provides config value read and write functionality.
    提供配置值的读取和写入功能

    Usage:
        service = ConfigService(db)

        # Get platform config / 获取平台配置

        value = await service.get_platform_config("site_name")

        # Set platform config / 设置平台配置

        await service.set_platform_config("site_name", "My SaaS")

        # Get tenant config (falls back to platform default) / 获取企业配置（会回退到平台默认值）

        value = await service.get_tenant_config(tenant_id, "theme_color")
    """

    def __init__(
        self,
        db: AsyncSession,
        registry: ConfigRegistry | None = None,
    ):
        """Initialize service / 初始化服务

        Args:
            db: Database session / 数据库会话
            registry: Config registry, defaults to global instance / 配置注册中心，默认使用全局实例
        """
        self.db = db
        self.registry = registry or config_registry

    # ==========================================
    # Platform config operations / 平台配置操作
    # ==========================================

    async def get_platform_config(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """Get platform config value / 获取平台配置值

        Args:
            key: Config key / 配置键名
            default: Default value / 默认值

        Returns:
            Config value (deserialized) / 配置值（已反序列化）
        """
        return await self._get_config_value(
            key=key,
            tenant_id=PLATFORM_TENANT_ID,
            scope=ConfigScope.ADMIN_ONLY,
            default=default,
        )

    async def set_platform_config(
        self,
        key: str,
        value: Any,
    ) -> None:
        """Set platform config value / 设置平台配置值

        Args:
            key: Config key / 配置键名
            value: Config value / 配置值
        """
        await self._set_config_value(
            key=key,
            tenant_id=PLATFORM_TENANT_ID,
            value=value,
        )

    async def get_platform_configs_by_group(
        self,
        group_code: str,
    ) -> dict[str, Any]:
        """Get all config values under a platform config group / 获取平台配置分组下的所有配置值

        Args:
            group_code: Group code / 分组代码

        Returns:
            {config_key: value, ...}
        """
        return await self._get_configs_by_group(
            group_code=group_code,
            tenant_id=PLATFORM_TENANT_ID,
        )

    # ==========================================
    # Tenant config operations / 企业配置操作
    # ==========================================

    async def get_tenant_config(
        self,
        tenant_id: int,
        key: str,
        default: Any = None,
    ) -> Any:
        """Get tenant config value / 获取企业配置值

        Falls back in order if tenant has not set the config:
        如果企业未设置该配置，会依次回退：
        1. Tenant-set value / 企业设置的值
        2. Platform default (for tenant scope) / 平台设置的默认值
        3. Code-defined default / 代码定义的默认值
        4. Passed-in default param / 传入的 default 参数

        Args:
            tenant_id: Tenant ID / 企业 ID
            key: Config key / 配置键名
            default: Default value / 默认值

        Returns:
            Config value (deserialized) / 配置值（已反序列化）
        """
        # Try to get tenant-set value first / 先尝试获取企业设置的值
        value = await self._get_config_value(
            key=key,
            tenant_id=tenant_id,
            scope=ConfigScope.ALL_TENANTS,
            default=None,
            skip_default=True,
        )

        if value is not None:
            return value

        # Fall back to config metadata default / 回退到配置元数据的默认值
        config_meta = self.registry.get_config_by_key(key)
        if config_meta and config_meta.default_value is not None:
            return config_meta.default_value

        return default

    async def get_tenant_config_override(
        self,
        tenant_id: int,
        key: str,
    ) -> Any:
        """中文: 获取企业显式保存的配置值，不回退到元数据默认值。

        EN: Return an explicitly stored tenant config value without metadata defaults.
        """

        return await self._get_config_value(
            key=key,
            tenant_id=tenant_id,
            scope=ConfigScope.ALL_TENANTS,
            default=None,
            skip_default=True,
        )

    async def set_tenant_config(
        self,
        tenant_id: int,
        key: str,
        value: Any,
    ) -> None:
        """Set tenant config value / 设置企业配置值

        Args:
            tenant_id: Tenant ID / 企业 ID
            key: Config key / 配置键名
            value: Config value / 配置值
        """
        await self._set_config_value(
            key=key,
            tenant_id=tenant_id,
            value=value,
        )

    async def get_tenant_configs_by_group(
        self,
        tenant_id: int,
        group_code: str,
    ) -> dict[str, Any]:
        """Get all config values under a tenant config group / 获取企业配置分组下的所有配置值

        Args:
            tenant_id: Tenant ID / 企业 ID
            group_code: Group code / 分组代码

        Returns:
            {config_key: value, ...}
        """
        return await self._get_configs_by_group(
            group_code=group_code,
            tenant_id=tenant_id,
        )

    async def ensure_tenant_configs(self, tenant_id: int) -> int:
        """Ensure tenant configs are initialized / 确保企业配置已初始化

        Creates default value records for all tenant-scoped configs.
        为企业创建所有 tenant 作用域配置的默认值记录

        Args:
            tenant_id: Tenant ID / 企业 ID

        Returns:
            Number of config values created / 创建的配置值数量
        """
        created_count = 0

        # Get all tenant-scoped configs / 获取所有企业作用域的配置
        tenant_configs = self.registry.get_configs_by_scope(ConfigScope.ALL_TENANTS)

        for config_meta in tenant_configs:
            # Check if value already exists / 检查是否已有值
            config_id = await self._get_config_id(
                config_meta.key,
                group_code=config_meta.group_code,
            )
            if not config_id:
                continue

            existing = await self.db.execute(
                select(SystemConfigValue).where(
                    and_(
                        SystemConfigValue.config_id == config_id,
                        SystemConfigValue.tenant_id == tenant_id,
                        SystemConfigValue.is_deleted.is_(False),
                    )
                )
            )

            if existing.scalar_one_or_none():
                continue

            # Create default value record / 创建默认值记录
            default_value = self._serialize_value(config_meta.default_value)
            value_record = SystemConfigValue(
                config_id=config_id,
                tenant_id=tenant_id,
                value=default_value,
            )
            self.db.add(value_record)
            created_count += 1

        if created_count > 0:
            await self.db.flush()
            logger.info(f"Created {created_count} config values for tenant {tenant_id}")

        return created_count

    # ==========================================
    # Batch retrieval (with metadata) / 批量获取（含元数据）
    # ==========================================

    async def get_configs_with_meta(
        self,
        scope: ConfigScope,
        tenant_id: int | None = None,
        group_code: str | None = None,
    ) -> list[dict]:
        """Get config list (with metadata) / 获取配置列表（含元数据）

        Args:
            scope: Scope / 作用域
            tenant_id: Tenant ID (required for tenant scope) / 企业 ID
            group_code: Group code (optional) / 分组代码

        Returns:
            Config list, each item contains: / 配置列表，每项包含：
            - key, name_key, description_key, value_type
            - value, default_value, options
            - is_required, is_encrypted, group_code
        """
        actual_tenant_id = (
            PLATFORM_TENANT_ID if scope == ConfigScope.ADMIN_ONLY else tenant_id
        )

        # Get groups / 获取分组
        if group_code:
            groups = [self.registry.get_group(group_code)]
            groups = [g for g in groups if g]
        else:
            groups = self.registry.get_groups_by_scope(scope)

        result = []

        for group in groups:
            configs = group.configs
            for config_meta in configs:
                if not config_meta.is_visible:
                    continue
                payload = await self._build_config_payload(
                    config_meta,
                    actual_tenant_id=actual_tenant_id,
                    scope=scope,
                )
                result.append(payload)

        return sorted(result, key=lambda x: (x["group_code"], x["sort_order"]))

    async def get_groups_with_configs(
        self,
        scope: ConfigScope,
        tenant_id: int | None = None,
    ) -> list[dict]:
        """Get group list (with config items) / 获取分组列表（含配置项）

        Args:
            scope: Scope / 作用域
            tenant_id: Tenant ID (required for tenant scope) / 企业 ID

        Returns:
            Group list with group info and config items / 分组列表
        """
        actual_tenant_id = (
            PLATFORM_TENANT_ID if scope == ConfigScope.ADMIN_ONLY else tenant_id
        )
        groups = self.registry.get_groups_by_scope(scope)

        result = []

        for group in groups:
            if not group.is_active:
                continue

            configs = []
            for config_meta in group.configs:
                if not config_meta.is_visible:
                    continue
                payload = await self._build_config_payload(
                    config_meta,
                    actual_tenant_id=actual_tenant_id,
                    scope=scope,
                )
                configs.append(payload)

            result.append(
                {
                    "code": group.code,
                    "name_key": group.name_key,
                    "description_key": group.description_key,
                    "icon": group.icon,
                    "sort_order": group.sort_order,
                    "configs": sorted(configs, key=lambda x: x["sort_order"]),
                }
            )

        return sorted(result, key=lambda x: x["sort_order"])

    # ==========================================
    # Internal methods / 内部方法
    # ==========================================

    async def _get_config_value(
        self,
        key: str,
        tenant_id: int,
        scope: ConfigScope,
        default: Any = None,
        skip_default: bool = False,
        group_code: str | None = None,
    ) -> Any:
        """Get config value (with in-memory cache) / 获取配置值（带内存缓存）"""
        _ = scope
        if group_code is None:
            config_meta = self.registry.get_config_by_key(key)
            group_code = config_meta.group_code if config_meta else None
        cache_key = f"{tenant_id}:{group_code or '*'}:{key}"
        now = time.monotonic()
        cached = _config_value_cache.get(cache_key)
        if cached and (now - cached[1]) < _CONFIG_VALUE_TTL:
            val = cached[0]
            if val is not None:
                return val
            return default if not skip_default else None

        # Get config item ID / 获取配置项 ID
        config_id = await self._get_config_id(key, group_code=group_code)
        if not config_id:
            _config_value_cache[cache_key] = (None, now)
            return default if not skip_default else None

        # Query config value / 查询配置值
        result = await self.db.execute(
            select(SystemConfigValue).where(
                and_(
                    SystemConfigValue.config_id == config_id,
                    SystemConfigValue.tenant_id == tenant_id,
                    SystemConfigValue.is_deleted.is_(False),
                )
            )
        )
        value_record = result.scalar_one_or_none()

        if value_record and value_record.value is not None:
            deserialized = self._deserialize_value(value_record.value)
            _config_value_cache[cache_key] = (deserialized, now)
            return deserialized

        _config_value_cache[cache_key] = (None, now)
        if skip_default:
            return None

        # Return default / 返回默认值
        return default

    async def _build_config_payload(
        self,
        config_meta: ConfigMeta,
        actual_tenant_id: int,
        scope: ConfigScope,
        parent_value: Any | None = None,
    ) -> dict[str, Any]:
        value = parent_value
        if value is None:
            value = await self._get_config_value(
                key=config_meta.key,
                tenant_id=actual_tenant_id,
                scope=scope,
                default=config_meta.default_value,
                group_code=config_meta.group_code,
            )

        payload = {
            "key": config_meta.key,
            "name_key": config_meta.name_key,
            "description_key": config_meta.description_key,
            "value_type": config_meta.value_type.value,
            "value": value,
            "default_value": config_meta.default_value,
            "options": [opt.to_dict() for opt in config_meta.options],
            "validation_rules": [
                rule.to_dict() for rule in config_meta.validation_rules
            ],
            "is_required": config_meta.is_required,
            "is_encrypted": config_meta.is_encrypted,
            "group_code": config_meta.group_code,
            "sort_order": config_meta.sort_order,
            "display_rules": [rule.to_dict() for rule in config_meta.display_rules],
            "value_path": config_meta.value_path,
            "tag_separator": config_meta.tag_separator,
            "file_accept": config_meta.file_accept,
        }

        if config_meta.children:
            children_payloads = []
            for child in config_meta.children:
                child_value = None
                if child.value_path:
                    child_value = self._get_value_by_path(value, child.value_path)
                    if child_value is None:
                        child_value = child.default_value
                    payload_parent = child_value
                else:
                    payload_parent = None
                child_payload = await self._build_config_payload(
                    child,
                    actual_tenant_id=actual_tenant_id,
                    scope=scope,
                    parent_value=payload_parent,
                )
                children_payloads.append(child_payload)
            payload["children"] = children_payloads
        else:
            payload["children"] = []

        return payload

    def _get_value_by_path(self, data: Any, path: str) -> Any:
        if data is None:
            return None
        current = data
        for segment in path.split("."):
            if isinstance(current, dict) and segment in current:
                current = current[segment]
            else:
                return None
        return current

    async def _set_config_value(
        self,
        key: str,
        tenant_id: int,
        value: Any,
    ) -> None:
        """Set config value / 设置配置值"""
        config_meta = self.registry.get_config_by_key(key)
        group_code = config_meta.group_code if config_meta else None

        # Get config item ID / 获取配置项 ID
        config_id = await self._get_config_id(key, group_code=group_code)
        if not config_id:
            raise ValueError(f"Config '{key}' not found")

        # Query existing record / 查询现有记录
        result = await self.db.execute(
            select(SystemConfigValue).where(
                and_(
                    SystemConfigValue.config_id == config_id,
                    SystemConfigValue.tenant_id == tenant_id,
                    SystemConfigValue.is_deleted.is_(False),
                )
            )
        )
        value_record = result.scalar_one_or_none()

        if config_meta and config_meta.value_type == ConfigValueType.HTML:
            if value is None:
                value = ""
            elif not isinstance(value, str):
                value = str(value)
            value = sanitize_config_html(value)

        if config_meta is not None:
            value = self._normalize_and_validate_config_value(config_meta, value)

        serialized_value = self._serialize_value(value)

        if value_record:
            # Update existing record / 更新现有记录
            value_record.value = serialized_value
        else:
            # Create new record / 创建新记录
            value_record = SystemConfigValue(
                config_id=config_id,
                tenant_id=tenant_id,
                value=serialized_value,
            )
            self.db.add(value_record)

        await self.db.flush()

        # Invalidate cache after write / 写入后立即失效缓存
        cache_key = f"{tenant_id}:{group_code or '*'}:{key}"
        _config_value_cache.pop(cache_key, None)

    def _raise_config_validation_failed(self) -> None:
        raise BusinessException(
            message=_("error.config.validation_failed"),
            code=ErrorCode.CONFIG_VALIDATION_FAILED,
        )

    def _normalize_and_validate_config_value(
        self,
        config_meta: ConfigMeta,
        value: Any,
    ) -> Any:
        normalized = self._normalize_config_value(config_meta, value)
        self._validate_required_config_value(config_meta, normalized)
        self._validate_config_rules(config_meta, normalized)
        return normalized

    def _normalize_config_value(self, config_meta: ConfigMeta, value: Any) -> Any:
        if value is None:
            return None

        value_type = config_meta.value_type
        if value_type == ConfigValueType.BOOLEAN:
            return self._normalize_boolean_config_value(value)
        if value_type == ConfigValueType.NUMBER:
            return self._normalize_number_config_value(value)
        if value_type == ConfigValueType.SELECT:
            return self._normalize_select_config_value(config_meta, value)
        if value_type == ConfigValueType.MULTI_SELECT:
            return self._normalize_multi_select_config_value(config_meta, value)
        if value_type == ConfigValueType.JSON:
            return self._normalize_json_config_value(value)
        if value_type == ConfigValueType.TAG:
            return self._normalize_tag_config_value(config_meta, value)
        if value_type in {
            ConfigValueType.COLOR,
            ConfigValueType.FILE,
            ConfigValueType.HTML,
            ConfigValueType.IMAGE,
            ConfigValueType.PASSWORD,
            ConfigValueType.STRING,
            ConfigValueType.TEXT,
        }:
            return str(value)
        return value

    def _normalize_boolean_config_value(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        self._raise_config_validation_failed()

    def _normalize_number_config_value(self, value: Any) -> int | float:
        if isinstance(value, bool):
            self._raise_config_validation_failed()
        try:
            number = float(value)
        except (TypeError, ValueError):
            self._raise_config_validation_failed()
        if not math.isfinite(number):
            self._raise_config_validation_failed()
        return int(number) if number.is_integer() else number

    def _normalize_select_config_value(
        self,
        config_meta: ConfigMeta,
        value: Any,
    ) -> Any:
        if not config_meta.options:
            return value
        for option in config_meta.options:
            if value == option.value or str(value) == str(option.value):
                return option.value
        if config_meta.allow_dynamic_options:
            return value
        self._raise_config_validation_failed()

    def _normalize_multi_select_config_value(
        self,
        config_meta: ConfigMeta,
        value: Any,
    ) -> list[Any]:
        if not isinstance(value, (list, tuple, set)):
            self._raise_config_validation_failed()
        raw_values = list(value)
        if not config_meta.options:
            return raw_values

        normalized_values: list[Any] = []
        for raw_value in raw_values:
            matched = False
            for option in config_meta.options:
                if raw_value == option.value or str(raw_value) == str(option.value):
                    normalized_values.append(option.value)
                    matched = True
                    break
            if not matched and config_meta.allow_dynamic_options:
                normalized_values.append(raw_value)
            elif not matched:
                self._raise_config_validation_failed()
        return normalized_values

    def _normalize_json_config_value(self, value: Any) -> Any:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                self._raise_config_validation_failed()
        try:
            json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            self._raise_config_validation_failed()
        return value

    def _normalize_tag_config_value(self, config_meta: ConfigMeta, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple, set)):
            separator = config_meta.tag_separator or ","
            return separator.join(
                str(item).strip() for item in value if str(item).strip()
            )
        self._raise_config_validation_failed()

    def _validate_required_config_value(
        self,
        config_meta: ConfigMeta,
        value: Any,
    ) -> None:
        if not config_meta.is_required:
            return
        if value is None:
            self._raise_config_validation_failed()
        if isinstance(value, str) and not value.strip():
            self._raise_config_validation_failed()
        if isinstance(value, (list, tuple, set, dict)) and not value:
            self._raise_config_validation_failed()

    def _validate_config_rules(
        self,
        config_meta: ConfigMeta,
        value: Any,
    ) -> None:
        if value is None:
            return
        for rule in config_meta.validation_rules:
            rule_type = str(rule.type or "").strip()
            if rule_type in {"min", "min_value"}:
                if self._normalize_number_config_value(
                    value
                ) < self._coerce_rule_number(rule.value):
                    self._raise_config_validation_failed()
            elif rule_type in {"max", "max_value"}:
                if self._normalize_number_config_value(
                    value
                ) > self._coerce_rule_number(rule.value):
                    self._raise_config_validation_failed()
            elif rule_type == "min_length":
                if len(str(value)) < int(rule.value):
                    self._raise_config_validation_failed()
            elif rule_type == "max_length":
                if len(str(value)) > int(rule.value):
                    self._raise_config_validation_failed()
            elif rule_type == "pattern":
                try:
                    matched = re.fullmatch(str(rule.value), str(value))
                except re.error:
                    self._raise_config_validation_failed()
                if not matched:
                    self._raise_config_validation_failed()

    def _coerce_rule_number(self, value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            self._raise_config_validation_failed()
        if not math.isfinite(number):
            self._raise_config_validation_failed()
        return number

    async def _get_configs_by_group(
        self,
        group_code: str,
        tenant_id: int,
    ) -> dict[str, Any]:
        """Get all config values under a group / 获取分组下的所有配置值"""
        group = self.registry.get_group(group_code)
        if not group:
            return {}

        result = {}
        for config_meta in group.configs:
            value = await self._get_config_value(
                key=config_meta.key,
                tenant_id=tenant_id,
                scope=config_meta.scope,
                default=config_meta.default_value,
                group_code=config_meta.group_code,
            )
            result[config_meta.key] = value

        return result

    async def _get_config_id(
        self,
        key: str,
        *,
        group_code: str | None = None,
    ) -> int | None:
        """Get config item ID by key (with in-memory cache) / 根据 key 获取配置项 ID（带内存缓存）"""
        now = time.monotonic()
        if group_code is None:
            config_meta = self.registry.get_config_by_key(key)
            group_code = config_meta.group_code if config_meta else None

        cache_key = (group_code, key)
        cached = _config_id_cache.get(cache_key)
        if cached and (now - cached[1]) < _CONFIG_ID_TTL:
            return cached[0]

        stmt = (
            select(SystemConfig.id)
            .join(SystemConfigGroup, SystemConfigGroup.id == SystemConfig.group_id)
            .where(
                and_(
                    SystemConfig.key == key,
                    SystemConfig.is_deleted.is_(False),
                )
            )
            .order_by(SystemConfig.id.asc())
            .limit(2)
        )
        if group_code:
            stmt = stmt.where(
                and_(
                    SystemConfigGroup.code == group_code,
                    SystemConfigGroup.is_deleted.is_(False),
                )
            )

        result = await self.db.execute(
            stmt,
        )
        ids = list(result.scalars().all())
        config_id = ids[0] if ids else None
        if len(ids) > 1:
            logger.warning(
                "Duplicate system_configs detected for group='{}' key='{}', using id={} and ignoring {} extra row(s)",
                group_code or "*",
                key,
                config_id,
                len(ids) - 1,
            )
        _config_id_cache[cache_key] = (config_id, now)
        return config_id

    def _serialize_value(self, value: Any) -> str | None:
        """Serialize value to JSON string / 序列化值为 JSON 字符串"""
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    def _deserialize_value(self, value: str) -> Any:
        """Deserialize JSON string to value / 反序列化 JSON 字符串为值"""
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value


# Convenience function / 便捷函数
async def get_config_service(db: AsyncSession) -> ConfigService:
    """Get config service instance / 获取配置服务实例"""
    return ConfigService(db)


__all__ = [
    "ConfigService",
    "get_config_service",
    "PLATFORM_TENANT_ID",
]
