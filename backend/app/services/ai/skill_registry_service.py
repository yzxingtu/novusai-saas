"""
Skill registry service / 技能注册表服务
"""

from __future__ import annotations

import shutil  # noqa: F401

from app.services.ai.skill_registry_command_service import SkillRegistryCommandService
from app.services.ai.skill_registry_query_service import SkillRegistryQueryService
from app.services.ai.skill_registry_support import SkillRegistrySupport


class SkillRegistryService:
    def __init__(self, db) -> None:
        self.db = db
        self._support = SkillRegistrySupport(db)
        self._query_service = SkillRegistryQueryService(self._support)
        self._command_service = SkillRegistryCommandService(
            self._support,
            self._query_service,
        )

    async def _get_cached(self, key: str) -> object | None:
        return await self._support.get_cached(key)

    async def _set_cached(self, key: str, value: object) -> None:
        await self._support.set_cached(key, value)

    async def _select_source(self) -> str:
        return await self._support.select_source()

    def _get_local_registry(self) -> list[dict]:
        return self._support.get_local_registry()

    async def _build_installed_map(self) -> dict[str, object]:
        return await self._support.build_installed_map()

    async def _download_archive(self, *, download_url: str, archive_path) -> None:
        await self._support.download_archive(
            download_url=download_url,
            archive_path=archive_path,
        )

    async def _load_archive_payload(self, *, archive_path, slug: str) -> dict:
        return await self._support.load_archive_payload(
            archive_path=archive_path,
            slug=slug,
        )

    async def fetch_registry(self, *, source_url: str | None = None) -> list[dict]:
        return await self._query_service.fetch_registry(
            source_url=source_url,
            get_cached_fn=self._get_cached,
            set_cached_fn=self._set_cached,
            select_source_fn=self._select_source,
            get_local_registry_fn=self._get_local_registry,
        )

    async def list_packages(
        self,
        *,
        search: str = "",
        sort: str = "-downloads",
        tag: str = "",
        page_number: int = 1,
        page_size: int = 24,
    ) -> dict:
        return await self._query_service.list_packages(
            search=search,
            sort=sort,
            tag=tag,
            page_number=page_number,
            page_size=page_size,
            fetch_registry_fn=self.fetch_registry,
            build_installed_map_fn=self._build_installed_map,
        )

    async def fetch_package_detail(
        self,
        slug: str,
        *,
        source_url: str | None = None,
    ) -> dict:
        return await self._query_service.fetch_package_detail(
            slug,
            source_url=source_url,
        )

    async def install_preview(self, slug: str) -> dict:
        return await self._query_service.install_preview(
            slug,
            fetch_package_detail_fn=self.fetch_package_detail,
            build_installed_map_fn=self._build_installed_map,
        )

    async def upgrade_preview(self, slug: str) -> dict:
        return await self._query_service.upgrade_preview(
            slug,
            fetch_package_detail_fn=self.fetch_package_detail,
            build_installed_map_fn=self._build_installed_map,
        )

    async def install_package(self, slug: str) -> dict:
        return await self._command_service.install_package(
            slug,
            fetch_package_detail_fn=self.fetch_package_detail,
            build_installed_map_fn=self._build_installed_map,
            download_archive_fn=self._download_archive,
            select_source_fn=self._select_source,
        )

    async def list_installed_updates(self) -> list[dict]:
        return await self._query_service.list_installed_updates(
            fetch_package_detail_fn=self.fetch_package_detail,
            build_installed_map_fn=self._build_installed_map,
        )

    async def upgrade_package(self, slug: str) -> dict:
        return await self._command_service.upgrade_package(
            slug,
            fetch_package_detail_fn=self.fetch_package_detail,
            build_installed_map_fn=self._build_installed_map,
            download_archive_fn=self._download_archive,
            load_archive_payload_fn=self._load_archive_payload,
            select_source_fn=self._select_source,
            copytree_fn=shutil.copytree,
            rmtree_fn=shutil.rmtree,
        )

    async def batch_upgrade(
        self,
        *,
        slugs: list[str] | None = None,
    ) -> dict:
        return await self._command_service.batch_upgrade(
            slugs=slugs,
            list_installed_updates_fn=self.list_installed_updates,
            upgrade_package_fn=self.upgrade_package,
        )

    async def list_official_starter_packs(self) -> dict[str, object]:
        return await self._query_service.list_official_starter_packs(
            fetch_registry_fn=self.fetch_registry,
            build_installed_map_fn=self._build_installed_map,
        )

    async def sync_official_starter_packs(
        self,
        *,
        pack_keys: list[str] | None = None,
        install_missing: bool = True,
        upgrade_existing: bool = False,
        dry_run: bool = False,
    ) -> dict[str, object]:
        return await self._command_service.sync_official_starter_packs(
            pack_keys=pack_keys,
            install_missing=install_missing,
            upgrade_existing=upgrade_existing,
            dry_run=dry_run,
            list_official_starter_packs_fn=self.list_official_starter_packs,
            install_package_fn=self.install_package,
            upgrade_package_fn=self.upgrade_package,
        )


__all__ = ["SkillRegistryService"]
