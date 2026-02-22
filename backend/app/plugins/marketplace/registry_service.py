"""
插件注册中心服务

职责：
1. 从远程（GitHub/Gitee）拉取 registry.json，或回退到本地开发数据
2. 内存缓存（TTL 可配置，支持 force_refresh）
3. 与本地已安装插件比对，标记 install_status
4. 提供搜索/过滤/排序
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import LogManager
from app.plugins.github_client import (
    async_get,
    build_raw_url,
    get_mirror,
    get_repo_for_mirror,
)
from app.schemas.system.marketplace import (
    InstallStatus,
    MarketplaceListResponse,
    MarketplacePluginResponse,
    RegistryCategory,
    RegistryPluginRepo,
)

logger = LogManager.get_logger("app")

# 本地 registry.json 路径（开发/测试用回退）
_LOCAL_REGISTRY = Path(__file__).parent / "registry.json"


class PluginRegistryService:
    """
    插件注册中心服务（单例）

    缓存策略：
    - 内存缓存 registry 数据 + 时间戳
    - TTL 由 PLUGIN_REGISTRY_CACHE_TTL 配置（默认 3600 秒）
    - force_refresh 忽略缓存直接拉取
    - 网络异常降级返回过期缓存或本地数据
    """

    _instance: PluginRegistryService | None = None
    _cache_data: dict[str, Any] | None = None
    _cache_time: datetime | None = None

    def __new__(cls) -> PluginRegistryService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ========================================
    # 核心：获取 registry 数据
    # ========================================

    async def get_registry(
        self, *, force_refresh: bool = False,
    ) -> dict[str, Any]:
        """
        获取 registry 数据（带缓存）

        Args:
            force_refresh: 强制刷新缓存

        Returns:
            registry.json 解析后的 dict
        """
        if not force_refresh and self._is_cache_valid():
            return self._cache_data  # type: ignore[return-value]

        try:
            data = await self._fetch_remote()
            self._cache_data = data
            self._cache_time = datetime.now(timezone.utc)
            logger.info(
                "Registry refreshed: %d plugins from %s",
                len(data.get("plugins", [])),
                get_mirror(),
            )
            return data
        except Exception as exc:
            logger.warning(
                "Failed to fetch remote registry: %s. Falling back.",
                str(exc),
            )
            if self._cache_data:
                logger.info("Using stale cache (%s)", self._cache_time)
                return self._cache_data
            return self._load_local()

    # ========================================
    # 市场列表（含安装状态比对）
    # ========================================

    async def get_marketplace_list(
        self,
        db: AsyncSession,
        *,
        keyword: str | None = None,
        category: str | None = None,
        official: bool | None = None,
        install_status: str | None = None,
        plugin_type: str | None = None,
        sort: str | None = None,
        force_refresh: bool = False,
        mirror_override: str | None = None,
    ) -> MarketplaceListResponse:
        """
        获取市场插件列表（含安装状态比对）

        Args:
            db: 数据库会话
            keyword: 关键词搜索（模糊匹配 name/description/tags）
            category: 分类精确过滤
            official: 官方/社区过滤
            install_status: 安装状态过滤（not_installed/installed/update_available）
            plugin_type: 插件类型过滤
            sort: 排序（name/-name/downloads_count/-downloads_count）
            force_refresh: 强制刷新缓存
        """
        # 确定本次请求使用的镜像
        effective_mirror = mirror_override or get_mirror()

        registry = await self.get_registry(force_refresh=force_refresh)
        raw_plugins = registry.get("plugins", [])
        raw_categories = registry.get("categories", [])

        # 获取本地已安装插件（name → {version, id}）
        local_plugins = await self._get_local_plugins(db)

        # 转换 + 标记安装状态
        items: list[MarketplacePluginResponse] = []
        for raw in raw_plugins:
            item = self._parse_plugin_entry(raw, local_plugins)
            items.append(item)

        # 过滤
        if keyword:
            kw = keyword.lower()
            items = [
                i for i in items
                if kw in (i.name or "").lower()
                or kw in (i.description or "").lower()
                or kw in (i.display_name or "").lower()
                or any(kw in t.lower() for t in (i.tags or []))
            ]

        if category:
            items = [i for i in items if i.category == category]

        if official is not None:
            items = [i for i in items if i.official == official]

        if plugin_type:
            items = [i for i in items if i.plugin_type == plugin_type]

        if install_status:
            items = [i for i in items if i.install_status.value == install_status]

        # 排序
        items = self._sort_items(items, sort)

        # 转换分类
        categories = [
            RegistryCategory(**cat) for cat in raw_categories
        ]

        return MarketplaceListResponse(
            items=items,
            total=len(items),
            categories=categories,
            mirror=effective_mirror,
        )

    # ========================================
    # 单个插件查询
    # ========================================

    async def get_plugin_by_slug(
        self,
        slug: str,
        db: AsyncSession | None = None,
    ) -> MarketplacePluginResponse | None:
        """
        根据 slug 获取单个市场插件

        Args:
            slug: 插件 slug
            db: 数据库会话（用于比对安装状态）
        """
        registry = await self.get_registry()
        raw_plugins = registry.get("plugins", [])

        local_plugins: dict[str, dict[str, Any]] = {}
        if db:
            local_plugins = await self._get_local_plugins(db)

        for raw in raw_plugins:
            if raw.get("slug") == slug:
                return self._parse_plugin_entry(raw, local_plugins)

        return None

    # ========================================
    # 更新检查
    # ========================================

    async def check_updates(
        self, db: AsyncSession,
    ) -> list[dict[str, Any]]:
        """
        检查已安装插件是否有可用更新

        Returns:
            有更新的插件列表
        """
        registry = await self.get_registry()
        raw_plugins = registry.get("plugins", [])
        local_plugins = await self._get_local_plugins(db)

        updates: list[dict[str, Any]] = []
        for raw in raw_plugins:
            name = raw.get("name", "")
            local = local_plugins.get(name)
            if not local:
                continue

            registry_version = raw.get("version", "")
            local_version = local.get("version", "")

            if self._is_newer_version(registry_version, local_version):
                updates.append({
                    "name": name,
                    "slug": raw.get("slug", ""),
                    "display_name": raw.get("display_name", name),
                    "current_version": local_version,
                    "latest_version": registry_version,
                    "changelog_url": raw.get("changelog_url"),
                    "local_plugin_id": local.get("id"),
                })

        return updates

    # ========================================
    # 内部方法
    # ========================================

    def _is_cache_valid(self) -> bool:
        """缓存是否在 TTL 内"""
        if self._cache_data is None or self._cache_time is None:
            return False
        elapsed = (datetime.now(timezone.utc) - self._cache_time).total_seconds()
        return elapsed < settings.PLUGIN_REGISTRY_CACHE_TTL

    async def _fetch_remote(self) -> dict[str, Any]:
        """从远程拉取 registry.json"""
        url = settings.PLUGIN_REGISTRY_URL
        if not url:
            # 未配置远程 URL，使用本地
            return self._load_local()

        data = await async_get(url)
        if not isinstance(data, dict):
            raise ValueError("Registry response is not a JSON object")

        schema_version = data.get("schema_version")
        if schema_version != "1.0":
            logger.warning(
                "Unexpected registry schema_version: %s (expected 1.0)",
                schema_version,
            )

        return data

    def _load_local(self) -> dict[str, Any]:
        """加载本地 registry.json（开发/测试回退）"""
        if _LOCAL_REGISTRY.exists():
            with open(_LOCAL_REGISTRY, encoding="utf-8") as f:
                data = json.load(f)
            logger.info(
                "Loaded local registry: %d plugins",
                len(data.get("plugins", [])),
            )
            return data
        logger.warning("No local registry.json found at %s", _LOCAL_REGISTRY)
        return {"schema_version": "1.0", "plugins": [], "categories": []}

    @staticmethod
    async def _get_local_plugins(db: AsyncSession) -> dict[str, dict[str, Any]]:
        """
        查询本地已安装插件 (name → {version, id, marketplace_slug})
        """
        from app.models.system.plugin import Plugin

        stmt = select(
            Plugin.id, Plugin.name, Plugin.version, Plugin.marketplace_slug,
        ).where(Plugin.is_deleted.is_(False))
        result = await db.execute(stmt)

        return {
            row.name: {
                "id": row.id,
                "version": row.version,
                "marketplace_slug": row.marketplace_slug,
            }
            for row in result.all()
        }

    @staticmethod
    def _parse_plugin_entry(
        raw: dict[str, Any],
        local_plugins: dict[str, dict[str, Any]],
    ) -> MarketplacePluginResponse:
        """将 registry.json 条目转为 MarketplacePluginResponse"""
        name = raw.get("name", "")
        local = local_plugins.get(name)

        # 确定安装状态
        if local is None:
            status = InstallStatus.NOT_INSTALLED
            installed_version = None
            local_plugin_id = None
        else:
            local_version = local.get("version", "")
            registry_version = raw.get("version", "")
            if PluginRegistryService._is_newer_version(registry_version, local_version):
                status = InstallStatus.UPDATE_AVAILABLE
            else:
                status = InstallStatus.INSTALLED
            installed_version = local_version
            local_plugin_id = local.get("id")

        # 解析 repo
        raw_repo = raw.get("repo", {})
        if isinstance(raw_repo, str):
            repo = RegistryPluginRepo(github=raw_repo, gitee=raw_repo)
        elif isinstance(raw_repo, dict):
            repo = RegistryPluginRepo(**raw_repo)
        else:
            repo = RegistryPluginRepo()

        return MarketplacePluginResponse(
            name=name,
            slug=raw.get("slug", name),
            display_name=raw.get("display_name", name),
            version=raw.get("version", "0.0.0"),
            description=raw.get("description"),
            author=raw.get("author"),
            plugin_type=raw.get("plugin_type", "composite"),
            category=raw.get("category"),
            tags=raw.get("tags"),
            repo=repo,
            official=raw.get("official", False),
            icon=raw.get("icon"),
            screenshots=raw.get("screenshots"),
            min_platform_version=raw.get("min_platform_version"),
            license=raw.get("license"),
            changelog_url=raw.get("changelog_url"),
            checksum_sha256=raw.get("checksum_sha256"),
            file_size_bytes=raw.get("file_size_bytes"),
            install_status=status,
            installed_version=installed_version,
            local_plugin_id=local_plugin_id,
        )

    @staticmethod
    def _is_newer_version(remote: str, local: str) -> bool:
        """简单 semver 比较：remote > local"""
        try:
            def parse(v: str) -> list[int]:
                return [int(x) for x in v.split("-")[0].split("+")[0].split(".")]
            return parse(remote) > parse(local)
        except (ValueError, IndexError):
            return remote != local

    @staticmethod
    def _sort_items(
        items: list[MarketplacePluginResponse],
        sort: str | None,
    ) -> list[MarketplacePluginResponse]:
        """排序插件列表"""
        if not sort:
            # 默认：官方优先，然后按名称
            return sorted(items, key=lambda i: (not i.official, i.name))

        desc = sort.startswith("-")
        field = sort.lstrip("-")

        key_map = {
            "name": lambda i: (i.name or "").lower(),
            "display_name": lambda i: (i.display_name or "").lower(),
            "version": lambda i: i.version,
        }

        key_fn = key_map.get(field)
        if key_fn:
            return sorted(items, key=key_fn, reverse=desc)

        return items

    # ========================================
    # 单例管理
    # ========================================

    @classmethod
    def reset(cls) -> None:
        """重置单例（仅用于测试）"""
        cls._instance = None
        cls._cache_data = None
        cls._cache_time = None
