"""
插件市场客户端

从 GitHub/Gitee 索引仓库获取插件列表、详情，下载插件包。
支持自动选源、Redis 缓存、下载重试。
"""

from __future__ import annotations

import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from app.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# 默认索引仓库 URL
_DEFAULT_GITHUB_URL = "https://raw.githubusercontent.com/novusai/plugin-marketplace/main"
_DEFAULT_GITEE_URL = "https://gitee.com/novusai/plugin-marketplace/raw/main"
_DEFAULT_CACHE_TTL = 3600

# Redis 缓存 key 前缀（多 worker 共享）
_CACHE_PREFIX = "marketplace:"


class MarketplaceClient:
    """插件市场客户端"""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._db = db
        self._github_url: str = _DEFAULT_GITHUB_URL
        self._gitee_url: str = _DEFAULT_GITEE_URL
        self._preferred_source: str = "auto"
        self._cache_ttl: int = _DEFAULT_CACHE_TTL
        self._selected_source: str | None = None

    async def _load_config(self) -> None:
        """从平台配置加载市场设置"""
        if not self._db:
            return
        try:
            from app.services.common.config_service import ConfigService

            svc = ConfigService(self._db)
            self._github_url = (
                await svc.get_value("marketplace_github_url") or _DEFAULT_GITHUB_URL
            )
            self._gitee_url = (
                await svc.get_value("marketplace_gitee_url") or _DEFAULT_GITEE_URL
            )
            self._preferred_source = (
                await svc.get_value("marketplace_preferred_source") or "auto"
            )
            ttl = await svc.get_value("marketplace_cache_ttl")
            if ttl:
                self._cache_ttl = int(ttl)
        except Exception as exc:
            logger.warning("Failed to load marketplace config: %s", exc)

    async def _select_source(self) -> str:
        """
        根据配置和网络环境选择源。

        auto 模式：并发 ping 两个源，选响应更快的。
        """
        if self._selected_source:
            return self._selected_source

        await self._load_config()

        if self._preferred_source == "github":
            self._selected_source = self._github_url
        elif self._preferred_source == "gitee":
            self._selected_source = self._gitee_url
        else:
            # auto: 尝试 GitHub 优先，超时 3s 则用 Gitee
            self._selected_source = await self._ping_and_select()

        logger.info("Marketplace source selected: %s", self._selected_source)
        return self._selected_source

    async def _ping_and_select(self) -> str:
        """并发 ping 两个源，返回更快响应的"""
        import asyncio

        async def _ping(url: str) -> tuple[str, float]:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    start = time.perf_counter()
                    await client.head(f"{url}/registry.json")
                    return url, time.perf_counter() - start
            except Exception:
                return url, 999.0

        results = await asyncio.gather(
            _ping(self._github_url),
            _ping(self._gitee_url),
        )
        fastest = min(results, key=lambda r: r[1])
        if fastest[1] >= 999.0:
            # 都不通，默认 GitHub
            return self._github_url
        return fastest[0]

    # ── 缓存 ──

    async def _get_cached(self, key: str) -> object | None:
        """从 Redis 缓存读取（多 worker 共享）"""
        try:
            from app.core.redis import cache_get
            return await cache_get(f"{_CACHE_PREFIX}{key}")
        except Exception:
            return None

    async def _set_cached(self, key: str, value: object) -> None:
        """写入 Redis 缓存（多 worker 共享）"""
        try:
            from app.core.redis import cache_set
            await cache_set(f"{_CACHE_PREFIX}{key}", value, ttl=self._cache_ttl)
        except Exception as exc:
            logger.debug("Marketplace cache_set failed for %s: %s", key, exc)

    # ── 本地回退 ──

    def _get_local_registry(self) -> list[dict]:
        """从本地 registry.json 加载（远程不可用时回退）"""
        import json

        local_path = Path(__file__).parent / "marketplace_registry" / "registry.json"
        if not local_path.is_file():
            return []
        try:
            data = json.loads(local_path.read_text(encoding="utf-8"))
            return data.get("plugins", []) if isinstance(data, dict) else []
        except Exception as exc:
            logger.warning("Failed to load local registry: %s", exc)
            return []

    # ── 公开方法 ──

    async def fetch_registry(self) -> list[dict]:
        """
        获取全部插件索引。

        缓存 TTL = marketplace_cache_ttl。
        网络失败时返回缓存数据（如果有）。
        """
        cache_key = "marketplace:registry"
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached  # type: ignore

        try:
            source = await self._select_source()
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{source}/registry.json")
                resp.raise_for_status()
                data = resp.json()

            plugins = data.get("plugins", data) if isinstance(data, dict) else data
            if isinstance(plugins, list):
                await self._set_cached(cache_key, plugins)
                return plugins
            return []
        except Exception as exc:
            logger.warning("Failed to fetch marketplace registry: %s", exc)
            # 返回 Redis 中的过期缓存（如果有）
            stale = await self._get_cached(cache_key)
            if stale:
                return stale  # type: ignore
            # 最后回退到本地 registry
            local = self._get_local_registry()
            if local:
                await self._set_cached(cache_key, local)
            return local

    async def list_plugins(
        self,
        search: str = "",
        category: str = "",
        sort: str = "-downloads",
        page_number: int = 1,
        page_size: int = 24,
    ) -> dict:
        """
        获取市场插件列表，支持搜索/分类/排序/分页，标记已安装状态。

        Returns:
            {"items": [...], "total": N}
        """
        registry = await self.fetch_registry()
        if not registry:
            return {"items": [], "total": 0}

        # 查询已安装插件
        installed_map: dict[str, str] = {}
        if self._db:
            from sqlalchemy import select

            from app.models.system.plugin import Plugin

            result = await self._db.execute(
                select(Plugin.name, Plugin.version, Plugin.marketplace_slug).where(
                    Plugin.is_deleted.is_(False),
                )
            )
            for row in result.all():
                slug = row[2] or row[0]
                installed_map[slug] = row[1]

        # 搜索
        items = registry
        if search:
            kw = search.lower()
            items = [
                p for p in items
                if kw in (p.get("display_name") or "").lower()
                or kw in (p.get("name") or "").lower()
                or kw in (p.get("description") or "").lower()
                or any(kw in t.lower() for t in (p.get("tags") or []))
            ]

        # 分类筛选
        if category:
            items = [
                p for p in items
                if p.get("category") == category
                or category in (p.get("tags") or [])
            ]

        # 排序
        reverse = sort.startswith("-")
        sort_field = sort.lstrip("-")
        items.sort(
            key=lambda p: p.get(sort_field, 0) or 0,
            reverse=reverse,
        )

        total = len(items)

        # 分页
        start = (page_number - 1) * page_size
        items = items[start:start + page_size]

        # 标记已安装状态
        for item in items:
            slug = item.get("slug") or item.get("name", "")
            if slug in installed_map:
                item["is_installed"] = True
                item["installed_version"] = installed_map[slug]
            else:
                item["is_installed"] = False
                item["installed_version"] = None

        return {"items": items, "total": total}

    async def fetch_plugin_detail(self, slug: str) -> dict | None:
        """获取单个插件详细元数据"""
        cache_key = f"marketplace:plugin:{slug}"
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached  # type: ignore

        base_url = await self._select_source()
        url = f"{base_url}/plugins/{slug}.json"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code != 404:
                    resp.raise_for_status()
                    data = resp.json()
                    await self._set_cached(cache_key, data)
                    return data
                logger.info(
                    "Marketplace detail %s not found at %s, trying registry fallback",
                    slug,
                    url,
                )
        except Exception as exc:
            logger.warning("Failed to fetch plugin detail for %s: %s", slug, exc)

        # 回退：部分索引源仅提供 registry.json，不提供 plugins/{slug}.json
        # 此时从 registry 中按 slug/name 查找，保证 confirm-install 可继续执行。
        registry = await self.fetch_registry()
        for item in registry:
            item_slug = item.get("slug") or item.get("name", "")
            item_name = item.get("name", "")
            if item_slug == slug or item_name == slug:
                detail = dict(item)
                await self._set_cached(cache_key, detail)
                logger.info(
                    "Marketplace detail fallback hit from registry: slug=%s",
                    slug,
                )
                return detail

        logger.warning("Marketplace plugin detail not found for slug=%s", slug)

        # 最后尝试读取可能存在的旧缓存（兼容 cache backend 间歇异常）
        stale = await self._get_cached(cache_key)
        if stale:
            return stale  # type: ignore
        return None

    async def fetch_readme(self, slug: str, locale: str = "zh-CN") -> str | None:
        """获取插件 README"""
        base_url = await self._select_source()

        # 尝试多语言 README
        for readme_name in [f"README.{locale}.md", "README.md"]:
            url = f"{base_url}/plugins/{slug}/{readme_name}"
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        return resp.text
            except Exception:
                continue
        return None

    async def download_plugin(self, slug: str, version: str) -> Path:
        """
        从市场下载插件 .zip 包。

        Returns:
            下载的本地 .zip 文件路径
        """
        detail = await self.fetch_plugin_detail(slug)
        if not detail:
            from app.plugins.exceptions import PluginNotFoundError

            raise PluginNotFoundError(
                message=f"Plugin '{slug}' not found in marketplace",
            )

        # 查找下载 URL
        download_url = detail.get("download_url")
        if not download_url:
            # 尝试从 releases 构建
            repo_url = detail.get("repository_url", "")
            if "github.com" in repo_url or "gitee.com" in repo_url:
                download_url = f"{repo_url}/releases/download/v{version}/{slug}-{version}.zip"
            else:
                from app.plugins.exceptions import PluginError

                raise PluginError(
                    message=f"No download URL available for '{slug}' v{version}",
                )

        # 下载（重试 2 次）
        from app.plugins.exceptions import PluginInstallError
        from app.plugins.package_security import (
            ensure_package_size_limit,
            validate_plugin_zip_archive,
        )

        tmp_dir = Path(tempfile.mkdtemp(prefix="novusai_plugin_"))
        zip_path = tmp_dir / f"{slug}-{version}.zip"

        for attempt in range(3):
            try:
                async with (
                    httpx.AsyncClient(timeout=60.0) as client,
                    client.stream("GET", download_url, follow_redirects=True) as resp,
                ):
                    resp.raise_for_status()

                    downloaded = 0
                    with open(zip_path, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=1024 * 1024):
                            if not chunk:
                                continue
                            downloaded += len(chunk)
                            ensure_package_size_limit(downloaded)
                            f.write(chunk)

                validate_plugin_zip_archive(zip_path)

                logger.info(
                    "Downloaded plugin %s v%s (%d bytes)",
                    slug, version, zip_path.stat().st_size,
                )
                return zip_path

            except PluginInstallError:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                raise
            except Exception as exc:
                zip_path.unlink(missing_ok=True)
                if attempt < 2:
                    logger.warning(
                        "Download attempt %d failed for %s: %s, retrying...",
                        attempt + 1, slug, exc,
                    )
                    continue

                # DEBUG 回退：当远程包不存在时生成最小桩包，
                # 保障本地回归可以覆盖 marketplace 安装链路。
                from app.core.config import settings
                if settings.DEBUG:
                    try:
                        stub_zip = self._build_debug_stub_package(
                            tmp_dir=tmp_dir,
                            slug=slug,
                            version=version,
                            detail=detail,
                        )
                        validate_plugin_zip_archive(stub_zip)
                        logger.warning(
                            "Using DEBUG marketplace stub package for %s v%s "
                            "because remote download failed: %s",
                            slug,
                            version,
                            exc,
                        )
                        return stub_zip
                    except Exception as stub_exc:
                        logger.warning(
                            "Failed to build DEBUG marketplace stub for %s: %s",
                            slug,
                            stub_exc,
                        )

                shutil.rmtree(tmp_dir, ignore_errors=True)
                raise PluginInstallError(
                    message=f"Failed to download plugin '{slug}' after 3 attempts: {exc}",
                )

        return zip_path  # unreachable but satisfies type checker

    def _build_debug_stub_package(
        self,
        *,
        tmp_dir: Path,
        slug: str,
        version: str,
        detail: dict,
    ) -> Path:
        """构建 DEBUG 用最小插件包（仅开发环境回退）"""
        import re

        def _yaml_quote(value: object) -> str:
            text = str(value or "")
            return "'" + text.replace("'", "''") + "'"

        display_name = detail.get("display_name") or slug
        description = detail.get("description") or (
            f"DEBUG marketplace stub package for '{slug}'"
        )

        class_base = "".join(
            part.capitalize()
            for part in re.split(r"[^0-9a-zA-Z]+", slug)
            if part
        )
        if not class_base:
            class_base = "MarketplaceStub"
        class_name = f"{class_base}Plugin"

        plugin_yaml = (
            f"name: {slug}\n"
            f"version: \"{version}\"\n"
            "display_name:\n"
            f"  en: {_yaml_quote(display_name)}\n"
            f"  zh-CN: {_yaml_quote(display_name)}\n"
            "description:\n"
            f"  en: {_yaml_quote(description)}\n"
            f"  zh-CN: {_yaml_quote(description)}\n"
            "author: 'NovusAI DEBUG Marketplace'\n"
            "scope: admin_only\n"
            "tags: ['marketplace', 'debug', 'stub']\n"
            "capabilities: []\n"
            "extensions: {}\n"
            "dependencies:\n"
            "  python: []\n"
            "  plugins: []\n"
            "pricing:\n"
            "  type: free\n"
        )

        main_py = (
            "from app.plugins.base import PluginBase\n\n\n"
            f"class {class_name}(PluginBase):\n"
            "    async def on_install(self, ctx):\n"
            "        return None\n\n"
            "    async def on_enable(self, ctx):\n"
            "        return None\n\n"
            "    async def on_disable(self, ctx):\n"
            "        return None\n\n"
            "    async def on_uninstall(self, ctx):\n"
            "        return None\n"
        )

        readme = (
            f"# {display_name}\n\n"
            "This is a DEBUG fallback package generated locally because "
            "the remote marketplace package could not be downloaded.\n"
        )

        stub_zip = tmp_dir / f"{slug}-{version}-debug-stub.zip"
        with zipfile.ZipFile(stub_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("plugin.yaml", plugin_yaml)
            zf.writestr("README.md", readme)
            zf.writestr("backend/__init__.py", "")
            zf.writestr("backend/main.py", main_py)

        return stub_zip

    async def check_for_updates(
        self, installed_plugins: list[dict],
    ) -> list[dict]:
        """
        检查已安装插件的可用更新。

        Args:
            installed_plugins: [{name, version, marketplace_slug}, ...]

        Returns:
            有更新的插件列表 [{name, current_version, latest_version, slug}, ...]
        """
        registry = await self.fetch_registry()
        if not registry:
            return []

        # 构建市场插件版本索引
        market_versions: dict[str, str] = {}
        for plugin in registry:
            slug = plugin.get("slug") or plugin.get("name", "")
            ver = plugin.get("version", "")
            if slug and ver:
                market_versions[slug] = ver

        updates: list[dict] = []
        for installed in installed_plugins:
            slug = installed.get("marketplace_slug") or installed.get("name", "")
            if not slug:
                continue
            market_ver = market_versions.get(slug)
            if market_ver and market_ver != installed.get("version"):
                updates.append({
                    "name": installed.get("name"),
                    "current_version": installed.get("version"),
                    "latest_version": market_ver,
                    "slug": slug,
                })

        return updates
