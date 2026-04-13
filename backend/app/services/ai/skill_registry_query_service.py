"""
Query helpers for skill registry service.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.exceptions import NotFoundException
from app.services.ai.skill_registry_support import SkillRegistrySupport, logger


class SkillRegistryQueryService:
    """Read-focused queries extracted from SkillRegistryService."""

    def __init__(self, support: SkillRegistrySupport) -> None:
        self.support = support

    async def fetch_registry(
        self,
        *,
        source_url: str | None = None,
        get_cached_fn: Callable[[str], Awaitable[object | None]] | None = None,
        set_cached_fn: Callable[[str, object], Awaitable[None]] | None = None,
        select_source_fn: Callable[[], Awaitable[str]] | None = None,
        get_local_registry_fn: Callable[[], list[dict]] | None = None,
    ) -> list[dict]:
        get_cached = get_cached_fn or self.support.get_cached
        set_cached = set_cached_fn or self.support.set_cached
        select_source = select_source_fn or self.support.select_source
        get_local_registry = get_local_registry_fn or self.support.get_local_registry
        cache_key = self.support.cache_key("registry", source_url)
        cached = await get_cached(cache_key)
        if isinstance(cached, list):
            return cached

        try:
            source = source_url or await select_source()
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{source.rstrip('/')}/registry.json")
                resp.raise_for_status()
                data = resp.json()
            packages = data.get("packages", data) if isinstance(data, dict) else data
            if isinstance(packages, list):
                await set_cached(cache_key, packages)
                return packages
        except Exception as exc:
            logger.warning("Failed to fetch skill registry: {}", exc)

        local = get_local_registry()
        if local:
            await set_cached(cache_key, local)
        return local

    async def list_packages(
        self,
        *,
        search: str = "",
        sort: str = "-downloads",
        tag: str = "",
        page_number: int = 1,
        page_size: int = 24,
        fetch_registry_fn: Callable[..., Awaitable[list[dict]]] | None = None,
        build_installed_map_fn: Callable[[], Awaitable[dict[str, Any]]] | None = None,
    ) -> dict:
        items = await (fetch_registry_fn or self.fetch_registry)()
        installed = await (build_installed_map_fn or self.support.build_installed_map)()

        if search:
            keyword = search.lower()
            items = [
                item
                for item in items
                if keyword
                in str(item.get("display_name") or item.get("name") or "").lower()
                or keyword in str(item.get("description") or "").lower()
                or any(
                    keyword in str(tag_item).lower()
                    for tag_item in item.get("tags") or []
                )
            ]

        if tag:
            items = [item for item in items if tag in (item.get("tags") or [])]

        reverse = sort.startswith("-")
        sort_field = sort.lstrip("-")
        items.sort(key=lambda item: item.get(sort_field) or 0, reverse=reverse)

        total = len(items)
        start = max(page_number - 1, 0) * page_size
        sliced = items[start : start + page_size]
        hydrated: list[dict] = []
        for item in sliced:
            slug = str(item.get("slug") or item.get("name") or "").strip()
            install_info = installed.get(slug) or {}
            latest_version = str(item.get("version") or "").strip() or None
            installed_version = str(install_info.get("version") or "").strip() or None
            hydrated.append(
                {
                    **item,
                    "is_installed": slug in installed,
                    "installed_version": installed_version,
                    "latest_version": latest_version,
                    "can_upgrade": self.support.is_newer_version(
                        latest_version,
                        installed_version,
                    ),
                    "source_locked": bool(install_info.get("source_locked", True))
                    if slug in installed
                    else None,
                }
            )

        return {"items": hydrated, "total": total}

    async def fetch_package_detail(
        self,
        slug: str,
        *,
        source_url: str | None = None,
    ) -> dict:
        cache_key = self.support.cache_key(f"detail:{slug}", source_url)
        cached = await self.support.get_cached(cache_key)
        if isinstance(cached, dict):
            return cached

        source = source_url or await self.support.select_source()
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"{source.rstrip('/')}/packages/{slug}.json")
                if resp.status_code == 200:
                    data = resp.json()
                    await self.support.set_cached(cache_key, data)
                    return data
            except Exception as exc:
                logger.warning(
                    "Failed to fetch skill registry detail {}: {}", slug, exc
                )

        registry = await self.fetch_registry(source_url=source)
        for item in registry:
            if str(item.get("slug") or item.get("name") or "").strip() == slug:
                await self.support.set_cached(cache_key, item)
                return item
        raise NotFoundException(message=f"Skill registry package not found: {slug}")

    async def install_preview(
        self,
        slug: str,
        *,
        fetch_package_detail_fn: Callable[..., Awaitable[dict]] | None = None,
        build_installed_map_fn: Callable[[], Awaitable[dict[str, Any]]] | None = None,
    ) -> dict:
        detail = await (fetch_package_detail_fn or self.fetch_package_detail)(slug)
        installed = await (build_installed_map_fn or self.support.build_installed_map)()
        current = installed.get(slug) or {}
        installed_version = str(current.get("version") or "").strip() or None
        latest_version = str(detail.get("version") or "").strip() or None
        return {
            **detail,
            "is_installed": slug in installed,
            "installed_version": installed_version,
            "latest_version": latest_version,
            "can_upgrade": self.support.is_newer_version(
                latest_version,
                installed_version,
            ),
            "source_locked": bool(current.get("source_locked", True))
            if slug in installed
            else None,
            "source_url": current.get("source_url"),
        }

    async def upgrade_preview(
        self,
        slug: str,
        *,
        fetch_package_detail_fn: Callable[..., Awaitable[dict]] | None = None,
        build_installed_map_fn: Callable[[], Awaitable[dict[str, Any]]] | None = None,
    ) -> dict:
        installed = await (build_installed_map_fn or self.support.build_installed_map)()
        current = installed.get(slug)
        if not current:
            raise NotFoundException(
                message=f"Installed skill registry package not found: {slug}"
            )

        source_locked = bool(current.get("source_locked", True))
        locked_source_url = str(current.get("source_url") or "").strip() or None
        detail = await (fetch_package_detail_fn or self.fetch_package_detail)(
            slug,
            source_url=locked_source_url if source_locked else None,
        )
        installed_version = str(current.get("version") or "").strip() or None
        latest_version = str(detail.get("version") or "").strip() or None
        return {
            "slug": slug,
            "display_name": detail.get("display_name") or detail.get("name") or slug,
            "installed_version": installed_version,
            "latest_version": latest_version,
            "can_upgrade": self.support.is_newer_version(
                latest_version,
                installed_version,
            ),
            "source_locked": source_locked,
            "source_url": locked_source_url,
            "download_url": detail.get("download_url"),
            "changelog": detail.get("changelog"),
            "readme": detail.get("readme"),
        }

    async def list_installed_updates(
        self,
        *,
        fetch_package_detail_fn: Callable[..., Awaitable[dict]] | None = None,
        build_installed_map_fn: Callable[[], Awaitable[dict[str, Any]]] | None = None,
    ) -> list[dict]:
        installed = await (build_installed_map_fn or self.support.build_installed_map)()
        updates: list[dict] = []
        for slug, info in installed.items():
            source_url = (
                str(info.get("source_url") or "").strip() or None
                if bool(info.get("source_locked", True))
                else None
            )
            try:
                detail = await (fetch_package_detail_fn or self.fetch_package_detail)(
                    slug,
                    source_url=source_url,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to fetch skill registry update detail {}: {}", slug, exc
                )
                continue
            latest_version = str(detail.get("version") or "").strip() or None
            installed_version = str(info.get("version") or "").strip() or None
            if not self.support.is_newer_version(latest_version, installed_version):
                continue
            updates.append(
                {
                    "slug": slug,
                    "display_name": detail.get("display_name")
                    or detail.get("name")
                    or slug,
                    "package_id": info.get("package_id"),
                    "skill_id": info.get("skill_id"),
                    "installed_version": installed_version,
                    "latest_version": latest_version,
                    "source_locked": bool(info.get("source_locked", True)),
                    "source_url": info.get("source_url"),
                }
            )
        updates.sort(
            key=lambda item: (
                str(item.get("display_name") or item.get("slug") or "").lower(),
                str(item.get("latest_version") or ""),
            )
        )
        return updates

    async def list_official_starter_packs(
        self,
        *,
        fetch_registry_fn: Callable[..., Awaitable[list[dict]]] | None = None,
        build_installed_map_fn: Callable[[], Awaitable[dict[str, Any]]] | None = None,
    ) -> dict[str, object]:
        registry_items = await (fetch_registry_fn or self.fetch_registry)()
        installed = await (build_installed_map_fn or self.support.build_installed_map)()
        registry_map: dict[str, dict] = {}
        for item in registry_items:
            slug = str(item.get("slug") or item.get("name") or "").strip()
            if not slug:
                continue
            registry_map[slug] = item

        packs: list[dict[str, object]] = []
        for definition in self.support.starter_pack_definitions():
            raw_slugs = definition.get("package_slugs") or ()
            package_entries: list[dict[str, object]] = []
            missing_in_catalog = 0
            installed_count = 0
            upgradable_count = 0
            for raw_slug in raw_slugs:
                slug = str(raw_slug or "").strip()
                if not slug:
                    continue
                detail = registry_map.get(slug) or {}
                install_info = installed.get(slug) or {}
                latest_version = str(detail.get("version") or "").strip() or None
                installed_version = (
                    str(install_info.get("version") or "").strip() or None
                )
                available_in_catalog = slug in registry_map
                is_installed = slug in installed
                can_upgrade = self.support.is_newer_version(
                    latest_version, installed_version
                )
                if not available_in_catalog:
                    missing_in_catalog += 1
                if is_installed:
                    installed_count += 1
                if is_installed and can_upgrade:
                    upgradable_count += 1
                package_entries.append(
                    {
                        "slug": slug,
                        "display_name": detail.get("display_name")
                        or detail.get("name")
                        or slug,
                        "description": detail.get("description"),
                        "available_in_catalog": available_in_catalog,
                        "is_installed": is_installed,
                        "installed_version": installed_version,
                        "latest_version": latest_version,
                        "can_upgrade": can_upgrade,
                        "source_locked": bool(install_info.get("source_locked", True))
                        if is_installed
                        else None,
                        "source_url": install_info.get("source_url")
                        if is_installed
                        else None,
                    }
                )
            total_packages = len(package_entries)
            packs.append(
                {
                    "key": str(definition.get("key") or ""),
                    "display_name": str(
                        definition.get("display_name")
                        or definition.get("key")
                        or "starter-pack"
                    ),
                    "description": str(definition.get("description") or "").strip()
                    or None,
                    "packages": package_entries,
                    "summary": {
                        "total": total_packages,
                        "missing_in_catalog": missing_in_catalog,
                        "installed": installed_count,
                        "upgradable": upgradable_count,
                    },
                }
            )
        return {
            "packs": packs,
            "automatic_agent_grant": False,
            "binding_mode": "manual_agent_skill_grant",
        }


__all__ = ["SkillRegistryQueryService"]
