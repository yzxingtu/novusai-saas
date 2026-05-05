"""
Command helpers for skill registry service.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.ai.skills.packaging import get_skill_storage_dir
from app.core.github_source_policy import validate_github_source_url
from app.exceptions import BusinessException, NotFoundException
from app.services.ai.skill_registry_query_service import SkillRegistryQueryService
from app.services.ai.skill_registry_support import SkillRegistrySupport


class SkillRegistryCommandService:
    """Write workflows extracted from SkillRegistryService."""

    def __init__(
        self,
        support: SkillRegistrySupport,
        query_service: SkillRegistryQueryService,
    ) -> None:
        self.support = support
        self.query_service = query_service

    async def install_package(
        self,
        slug: str,
        *,
        fetch_package_detail_fn: Callable[..., Awaitable[dict]] | None = None,
        build_installed_map_fn: Callable[[], Awaitable[dict[str, object]]]
        | None = None,
        download_archive_fn: Callable[..., Awaitable[None]] | None = None,
        select_source_fn: Callable[[], Awaitable[str]] | None = None,
    ) -> dict:
        detail = await (
            fetch_package_detail_fn or self.query_service.fetch_package_detail
        )(slug)
        installed = await (build_installed_map_fn or self.support.build_installed_map)()
        if slug in installed:
            raise BusinessException(
                message=f"Skill registry package already installed: {slug}"
            )

        version = str(detail.get("version") or "1.0.0")
        download_url = str(detail.get("download_url") or "").strip()
        if not download_url:
            raise BusinessException(
                message=f"Skill registry package has no download_url: {slug}"
            )
        try:
            download_url = validate_github_source_url(download_url)
        except ValueError as exc:
            raise BusinessException(
                message=f"Skill registry package download URL must be hosted on GitHub: {slug}"
            ) from exc
        source_url = await (select_source_fn or self.support.select_source)()

        temp_dir = Path(tempfile.mkdtemp(prefix="novusai_skill_registry_"))
        archive_path = temp_dir / f"{slug}-{version}.zip"
        try:
            await (download_archive_fn or self.support.download_archive)(
                download_url=download_url,
                archive_path=archive_path,
            )

            from app.api.shared._skill_package_upload import (
                process_skill_package_archive,
            )
            from app.services.ai.skill_package_service import AdminSkillPackageService
            from app.services.ai.skill_service import AdminSkillService

            pkg, skill_name, skill_version = await process_skill_package_archive(
                db=self.support.db,
                archive_path=archive_path,
                original_filename=archive_path.name,
                package_service=AdminSkillPackageService(self.support.db),
                skill_service=AdminSkillService(self.support.db),
                tenant_id=None,
                is_system=False,
                extra_skill_fields={
                    "source_ref": f"skill_registry:{slug}",
                    "config": {
                        "registry_download_url": download_url,
                        "registry_slug": slug,
                        "registry_source_url": source_url,
                        "registry_source_locked": True,
                        "registry_version": version,
                    },
                },
            )
            await self.support.db.commit()
            return {
                "package_id": pkg.id,
                "package_name": pkg.name,
                "skill_name": skill_name,
                "skill_version": skill_version,
                "registry_slug": slug,
                "status": "installed",
            }
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def upgrade_package(
        self,
        slug: str,
        *,
        fetch_package_detail_fn: Callable[..., Awaitable[dict]] | None = None,
        build_installed_map_fn: Callable[[], Awaitable[dict[str, object]]]
        | None = None,
        download_archive_fn: Callable[..., Awaitable[None]] | None = None,
        load_archive_payload_fn: Callable[..., Awaitable[dict]] | None = None,
        select_source_fn: Callable[[], Awaitable[str]] | None = None,
        copytree_fn: Callable[[Path, Path], object] | None = None,
        rmtree_fn: Callable[..., object] | None = None,
    ) -> dict:
        installed = await (build_installed_map_fn or self.support.build_installed_map)()
        current = installed.get(slug)
        if not current:
            raise NotFoundException(
                message=f"Installed skill registry package not found: {slug}"
            )

        source_locked = bool(current.get("source_locked", True))
        locked_source_url = str(current.get("source_url") or "").strip() or None
        detail = await (
            fetch_package_detail_fn or self.query_service.fetch_package_detail
        )(
            slug,
            source_url=locked_source_url if source_locked else None,
        )

        latest_version = str(detail.get("version") or "").strip() or None
        installed_version = str(current.get("version") or "").strip() or None
        if not self.support.is_newer_version(latest_version, installed_version):
            raise BusinessException(
                message=f"Skill registry package is already up to date: {slug}"
            )

        download_url = str(detail.get("download_url") or "").strip()
        if not download_url:
            raise BusinessException(
                message=f"Skill registry package has no download_url: {slug}"
            )
        try:
            download_url = validate_github_source_url(download_url)
        except ValueError as exc:
            raise BusinessException(
                message=f"Skill registry package download URL must be hosted on GitHub: {slug}"
            ) from exc

        package_id = int(current.get("package_id") or 0)
        skill_id = int(current.get("skill_id") or 0)
        if package_id <= 0 or skill_id <= 0:
            raise BusinessException(
                message=f"Skill registry install metadata incomplete: {slug}"
            )

        temp_dir = Path(tempfile.mkdtemp(prefix="novusai_skill_registry_upgrade_"))
        archive_path = temp_dir / f"{slug}-{latest_version or 'latest'}.zip"
        try:
            await (download_archive_fn or self.support.download_archive)(
                download_url=download_url,
                archive_path=archive_path,
            )

            payload = await (
                load_archive_payload_fn or self.support.load_archive_payload
            )(
                archive_path=archive_path,
                slug=slug,
            )

            from app.services.ai.skill_package_service import AdminSkillPackageService
            from app.services.ai.skill_service import AdminSkillService

            package_service = AdminSkillPackageService(self.support.db)
            skill_service = AdminSkillService(self.support.db)

            existing_package = await package_service.get_by_id(package_id)
            existing_skill = await skill_service.get_by_id(skill_id)
            if not existing_package or not existing_skill:
                raise NotFoundException(
                    message=f"Installed skill registry package target missing: {slug}"
                )

            await package_service.update(
                package_id,
                {
                    "name": payload["skill_name"],
                    "description": payload["skill_desc"],
                    "avatar": payload["skill_icon"],
                    "valves_schema": payload["valves_schema"],
                },
            )
            merged_skill_config = {
                **(existing_skill.config or {}),
                "version": latest_version,
                "env_requires": payload["env_requires"],
                "registry_download_url": download_url,
                "registry_slug": slug,
                "registry_source_locked": source_locked,
                "registry_source_url": locked_source_url
                if source_locked
                else await (select_source_fn or self.support.select_source)(),
                "registry_version": latest_version,
            }
            await skill_service.update(
                skill_id,
                {
                    "name": payload["skill_name"],
                    "description": payload["skill_desc"],
                    "avatar": payload["skill_icon"],
                    "version": latest_version or existing_skill.version,
                    "toolkit_content": payload["toolkit_content"],
                    "config": merged_skill_config,
                },
            )

            storage_dir = get_skill_storage_dir(package_id)
            if storage_dir.exists():
                (rmtree_fn or shutil.rmtree)(storage_dir)
            (copytree_fn or shutil.copytree)(payload["extract_dir"], storage_dir)

            await self.support.db.commit()
            return {
                "package_id": package_id,
                "package_name": payload["skill_name"],
                "registry_slug": slug,
                "previous_version": installed_version,
                "latest_version": latest_version,
                "source_locked": source_locked,
                "source_url": locked_source_url
                if source_locked
                else merged_skill_config.get("registry_source_url"),
                "status": "upgraded",
            }
        finally:
            (rmtree_fn or shutil.rmtree)(temp_dir, ignore_errors=True)

    async def batch_upgrade(
        self,
        *,
        slugs: list[str] | None = None,
        list_installed_updates_fn: Callable[[], Awaitable[list[dict]]] | None = None,
        upgrade_package_fn: Callable[[str], Awaitable[dict]] | None = None,
    ) -> dict:
        candidates = await (
            list_installed_updates_fn or self.query_service.list_installed_updates
        )()
        selected = (
            [item for item in candidates if item["slug"] in set(slugs or [])]
            if slugs
            else candidates
        )
        upgraded: list[dict] = []
        failed: list[dict] = []
        for item in selected:
            slug = str(item.get("slug") or "").strip()
            if not slug:
                continue
            try:
                result = await (upgrade_package_fn or self.upgrade_package)(slug)
                upgraded.append(result)
            except Exception as exc:
                failed.append(
                    {
                        "slug": slug,
                        "error": str(exc),
                    }
                )
        return {
            "requested": len(selected),
            "upgraded": upgraded,
            "failed": failed,
        }

    async def sync_official_starter_packs(
        self,
        *,
        pack_keys: list[str] | None = None,
        install_missing: bool = True,
        upgrade_existing: bool = False,
        dry_run: bool = False,
        list_official_starter_packs_fn: Callable[[], Awaitable[dict[str, object]]]
        | None = None,
        install_package_fn: Callable[[str], Awaitable[dict]] | None = None,
        upgrade_package_fn: Callable[[str], Awaitable[dict]] | None = None,
    ) -> dict[str, object]:
        catalog = await (
            list_official_starter_packs_fn
            or self.query_service.list_official_starter_packs
        )()
        all_packs = list(catalog.get("packs") or [])
        key_filter = {str(key).strip() for key in (pack_keys or []) if str(key).strip()}

        if key_filter:
            selected_packs = [
                pack for pack in all_packs if str(pack.get("key") or "") in key_filter
            ]
            missing_keys = sorted(
                key_filter - {str(pack.get("key") or "") for pack in selected_packs}
            )
        else:
            selected_packs = all_packs
            missing_keys = []

        installed: list[dict[str, object]] = []
        upgraded: list[dict[str, object]] = []
        skipped: list[dict[str, object]] = []
        failed: list[dict[str, object]] = []

        for pack in selected_packs:
            pack_key = str(pack.get("key") or "")
            for package in list(pack.get("packages") or []):
                slug = str(package.get("slug") or "").strip()
                if not slug:
                    continue
                available_in_catalog = bool(package.get("available_in_catalog"))
                is_installed = bool(package.get("is_installed"))
                can_upgrade = bool(package.get("can_upgrade"))
                if not available_in_catalog:
                    skipped.append(
                        {
                            "pack_key": pack_key,
                            "slug": slug,
                            "reason": "missing_in_catalog",
                        }
                    )
                    continue
                try:
                    if can_upgrade and upgrade_existing:
                        if dry_run:
                            skipped.append(
                                {
                                    "pack_key": pack_key,
                                    "slug": slug,
                                    "reason": "dry_run_upgrade",
                                }
                            )
                            continue
                        upgraded.append(
                            await (upgrade_package_fn or self.upgrade_package)(slug)
                        )
                        continue
                    if (not is_installed) and install_missing:
                        if dry_run:
                            skipped.append(
                                {
                                    "pack_key": pack_key,
                                    "slug": slug,
                                    "reason": "dry_run_install",
                                }
                            )
                            continue
                        installed.append(
                            await (install_package_fn or self.install_package)(slug)
                        )
                        continue
                    skipped.append(
                        {
                            "pack_key": pack_key,
                            "slug": slug,
                            "reason": "already_satisfied",
                        }
                    )
                except Exception as exc:
                    failed.append(
                        {
                            "pack_key": pack_key,
                            "slug": slug,
                            "error": str(exc),
                        }
                    )

        return {
            "selected_pack_keys": [
                str(pack.get("key") or "") for pack in selected_packs
            ],
            "missing_pack_keys": missing_keys,
            "install_missing": bool(install_missing),
            "upgrade_existing": bool(upgrade_existing),
            "dry_run": bool(dry_run),
            "installed": installed,
            "upgraded": upgraded,
            "skipped": skipped,
            "failed": failed,
            "automatic_agent_grant": False,
            "binding_mode": "manual_agent_skill_grant",
        }


__all__ = ["SkillRegistryCommandService"]
