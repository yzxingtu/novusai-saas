"""
Skill registry service / 技能注册表服务
"""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

import httpx
from sqlalchemy import select

from app.core.github_source_policy import (
    open_github_only_stream,
    validate_github_source_url,
)
from app.core.logging import get_logger
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.skill import Skill

logger = get_logger(__name__)

_DEFAULT_GITHUB_URL = "https://raw.githubusercontent.com/novusai/skill-marketplace/main"
_DEFAULT_CACHE_TTL = 3600
_CACHE_PREFIX = "skill_registry:"
_SEMVER_TOKEN_RE = re.compile(r"[0-9]+|[A-Za-z]+")


class SkillRegistryService:
    def __init__(self, db) -> None:
        self.db = db
        self._github_url = _DEFAULT_GITHUB_URL
        self._cache_ttl = _DEFAULT_CACHE_TTL
        self._selected_source: str | None = None

    async def _load_config(self) -> None:
        try:
            from app.configs.service import ConfigService

            svc = ConfigService(self.db)
            self._github_url = (
                await svc.get_platform_config(
                    "skill_registry_github_url", default=_DEFAULT_GITHUB_URL
                )
                or _DEFAULT_GITHUB_URL
            )
            ttl = await svc.get_platform_config(
                "skill_registry_cache_ttl", default=_DEFAULT_CACHE_TTL
            )
            if ttl:
                self._cache_ttl = int(ttl)
        except Exception as exc:
            logger.warning("Failed to load skill registry config: {}", exc)

    async def _select_source(self) -> str:
        if self._selected_source:
            return self._selected_source

        await self._load_config()
        self._selected_source = self._github_url
        return self._selected_source

    async def _get_cached(self, key: str) -> object | None:
        try:
            from app.core.redis import cache_get

            return await cache_get(f"{_CACHE_PREFIX}{key}")
        except Exception:
            return None

    async def _set_cached(self, key: str, value: object) -> None:
        try:
            from app.core.redis import cache_set

            await cache_set(f"{_CACHE_PREFIX}{key}", value, ttl=self._cache_ttl)
        except Exception as exc:
            logger.debug("Skill registry cache_set failed for {}: {}", key, exc)

    def _get_local_registry(self) -> list[dict]:
        import json

        local_path = Path(__file__).resolve().parent / "registry_data" / "registry.json"
        if not local_path.is_file():
            return []
        try:
            data = json.loads(local_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load local skill registry: {}", exc)
            return []
        return data.get("packages", data) if isinstance(data, dict) else []

    def _cache_key(self, prefix: str, source_url: str | None = None) -> str:
        if not source_url:
            return prefix
        safe = re.sub(r"[^a-zA-Z0-9]+", "_", source_url.strip().lower()).strip("_")
        return f"{prefix}:{safe or 'default'}"

    @staticmethod
    def _version_key(version: str | None) -> tuple:
        normalized = str(version or "").strip()
        if not normalized:
            return ()
        if normalized.startswith("v"):
            normalized = normalized[1:]
        parts = re.split(r"[.+-]", normalized)
        key: list[tuple[int, int | str]] = []
        for part in parts:
            if not part:
                continue
            tokens = _SEMVER_TOKEN_RE.findall(part)
            if not tokens:
                continue
            for token in tokens:
                if token.isdigit():
                    key.append((0, int(token)))
                else:
                    key.append((1, token.lower()))
        return tuple(key)

    @classmethod
    def _is_newer_version(
        cls, latest_version: str | None, installed_version: str | None
    ) -> bool:
        if not latest_version:
            return False
        if not installed_version:
            return True
        return cls._version_key(latest_version) > cls._version_key(installed_version)

    async def _build_installed_map(
        self,
    ) -> dict[str, dict[str, str | int | bool | None]]:
        result = await self.db.execute(
            select(
                Skill.id,
                Skill.package_id,
                Skill.name,
                Skill.version,
                Skill.source_ref,
                Skill.config,
            ).where(
                Skill.is_deleted.is_(False),
                Skill.type == "toolkit",
            )
        )
        installed: dict[str, dict[str, str | int | None]] = {}
        for row in result.all():
            config = row[5] if isinstance(row[5], dict) else {}
            slug = str(config.get("registry_slug") or "").strip()
            if (
                not slug
                and isinstance(row[4], str)
                and row[4].startswith("skill_registry:")
            ):
                slug = row[4].split(":", 1)[1].strip()
            if not slug:
                continue
            installed[slug] = {
                "skill_id": int(row[0]),
                "package_id": int(row[1]),
                "name": str(row[2] or ""),
                "version": str(config.get("registry_version") or row[3] or ""),
                "source_ref": str(row[4] or "") or None,
                "source_url": str(config.get("registry_source_url") or "").strip()
                or None,
                "source_locked": bool(config.get("registry_source_locked", True)),
            }
        return installed

    async def fetch_registry(self, *, source_url: str | None = None) -> list[dict]:
        cache_key = self._cache_key("registry", source_url)
        cached = await self._get_cached(cache_key)
        if isinstance(cached, list):
            return cached

        try:
            source = source_url or await self._select_source()
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{source.rstrip('/')}/registry.json")
                resp.raise_for_status()
                data = resp.json()
            packages = data.get("packages", data) if isinstance(data, dict) else data
            if isinstance(packages, list):
                await self._set_cached(cache_key, packages)
                return packages
        except Exception as exc:
            logger.warning("Failed to fetch skill registry: {}", exc)

        local = self._get_local_registry()
        if local:
            await self._set_cached(cache_key, local)
        return local

    async def list_packages(
        self,
        *,
        search: str = "",
        sort: str = "-downloads",
        tag: str = "",
        page_number: int = 1,
        page_size: int = 24,
    ) -> dict:
        items = await self.fetch_registry()
        installed = await self._build_installed_map()

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
                    "can_upgrade": self._is_newer_version(
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
        cache_key = self._cache_key(f"detail:{slug}", source_url)
        cached = await self._get_cached(cache_key)
        if isinstance(cached, dict):
            return cached

        source = source_url or await self._select_source()
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"{source.rstrip('/')}/packages/{slug}.json")
                if resp.status_code == 200:
                    data = resp.json()
                    await self._set_cached(cache_key, data)
                    return data
            except Exception as exc:
                logger.warning(
                    "Failed to fetch skill registry detail {}: {}", slug, exc
                )

        registry = await self.fetch_registry(source_url=source)
        for item in registry:
            if str(item.get("slug") or item.get("name") or "").strip() == slug:
                await self._set_cached(cache_key, item)
                return item
        raise NotFoundException(message=f"Skill registry package not found: {slug}")

    async def _download_archive(
        self,
        *,
        download_url: str,
        archive_path: Path,
    ) -> None:
        validated_url = validate_github_source_url(download_url)
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await open_github_only_stream(client, validated_url)
            try:
                resp.raise_for_status()
                with open(archive_path, "wb") as file_handle:
                    async for chunk in resp.aiter_bytes(chunk_size=1024 * 1024):
                        if chunk:
                            file_handle.write(chunk)
            finally:
                await resp.aclose()

    async def _load_archive_payload(
        self,
        *,
        archive_path: Path,
        slug: str,
    ) -> dict:
        from app.ai.skills.env_parser import parse_env_example
        from app.ai.skills.packaging import extract_skill_package, read_env_example
        from app.ai.skills.server_converter import convert_server_to_toolkit

        extract_dir = archive_path.parent / "extracted"
        metadata = extract_skill_package(archive_path, extract_dir)
        skill_name = str(metadata.get("name") or "").strip() or slug
        skill_desc = str(metadata.get("description") or "").strip() or None
        raw_icon = metadata.get("icon", "")
        skill_icon = raw_icon if isinstance(raw_icon, str) and ":" in raw_icon else None

        env_requires: list[str] = []
        meta_block = metadata.get("metadata", {})
        if isinstance(meta_block, dict):
            clawdbot = meta_block.get("clawdbot", {})
            if isinstance(clawdbot, dict):
                requires = clawdbot.get("requires", {})
                if isinstance(requires, dict):
                    env_requires = list(requires.get("env", []) or [])

        valves_schema = None
        env_example_content = read_env_example(extract_dir)
        if env_example_content:
            valves_schema = (
                parse_env_example(
                    env_example_content,
                    required_vars=env_requires,
                )
                or None
            )

        toolkit_content = ""
        server_dir = extract_dir / "server"
        if server_dir.exists():
            toolkit_content = convert_server_to_toolkit(
                server_dir,
                metadata,
                env_schema=valves_schema,
            )

        return {
            "extract_dir": extract_dir,
            "skill_name": skill_name,
            "skill_desc": skill_desc,
            "skill_icon": skill_icon,
            "env_requires": env_requires,
            "valves_schema": valves_schema,
            "toolkit_content": toolkit_content,
        }

    async def install_preview(self, slug: str) -> dict:
        detail = await self.fetch_package_detail(slug)
        installed = await self._build_installed_map()
        current = installed.get(slug) or {}
        installed_version = str(current.get("version") or "").strip() or None
        latest_version = str(detail.get("version") or "").strip() or None
        return {
            **detail,
            "is_installed": slug in installed,
            "installed_version": installed_version,
            "latest_version": latest_version,
            "can_upgrade": self._is_newer_version(latest_version, installed_version),
            "source_locked": bool(current.get("source_locked", True))
            if slug in installed
            else None,
            "source_url": current.get("source_url"),
        }

    async def upgrade_preview(self, slug: str) -> dict:
        installed = await self._build_installed_map()
        current = installed.get(slug)
        if not current:
            raise NotFoundException(
                message=f"Installed skill registry package not found: {slug}"
            )

        source_locked = bool(current.get("source_locked", True))
        locked_source_url = str(current.get("source_url") or "").strip() or None
        detail = await self.fetch_package_detail(
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
            "can_upgrade": self._is_newer_version(latest_version, installed_version),
            "source_locked": source_locked,
            "source_url": locked_source_url,
            "download_url": detail.get("download_url"),
            "changelog": detail.get("changelog"),
            "readme": detail.get("readme"),
        }

    async def install_package(self, slug: str) -> dict:
        detail = await self.fetch_package_detail(slug)
        installed = await self._build_installed_map()
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
        source_url = await self._select_source()

        temp_dir = Path(tempfile.mkdtemp(prefix="novusai_skill_registry_"))
        archive_path = temp_dir / f"{slug}-{version}.zip"
        try:
            await self._download_archive(
                download_url=download_url,
                archive_path=archive_path,
            )

            from app.api.shared._skill_package_upload import (
                process_skill_package_archive,
            )
            from app.services.ai.skill_package_service import AdminSkillPackageService
            from app.services.ai.skill_service import AdminSkillService

            pkg, skill_name, skill_version = await process_skill_package_archive(
                db=self.db,
                archive_path=archive_path,
                original_filename=archive_path.name,
                package_service=AdminSkillPackageService(self.db),
                skill_service=AdminSkillService(self.db),
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
            await self.db.commit()
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

    async def list_installed_updates(self) -> list[dict]:
        installed = await self._build_installed_map()
        updates: list[dict] = []
        for slug, info in installed.items():
            source_url = (
                str(info.get("source_url") or "").strip() or None
                if bool(info.get("source_locked", True))
                else None
            )
            try:
                detail = await self.fetch_package_detail(slug, source_url=source_url)
            except Exception as exc:
                logger.warning(
                    "Failed to fetch skill registry update detail {}: {}", slug, exc
                )
                continue
            latest_version = str(detail.get("version") or "").strip() or None
            installed_version = str(info.get("version") or "").strip() or None
            if not self._is_newer_version(latest_version, installed_version):
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

    async def upgrade_package(self, slug: str) -> dict:
        installed = await self._build_installed_map()
        current = installed.get(slug)
        if not current:
            raise NotFoundException(
                message=f"Installed skill registry package not found: {slug}"
            )

        source_locked = bool(current.get("source_locked", True))
        locked_source_url = str(current.get("source_url") or "").strip() or None
        detail = await self.fetch_package_detail(
            slug,
            source_url=locked_source_url if source_locked else None,
        )

        latest_version = str(detail.get("version") or "").strip() or None
        installed_version = str(current.get("version") or "").strip() or None
        if not self._is_newer_version(latest_version, installed_version):
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
            await self._download_archive(
                download_url=download_url,
                archive_path=archive_path,
            )

            from app.ai.skills.packaging import get_skill_storage_dir
            from app.services.ai.skill_package_service import AdminSkillPackageService
            from app.services.ai.skill_service import AdminSkillService

            payload = await self._load_archive_payload(
                archive_path=archive_path,
                slug=slug,
            )

            package_service = AdminSkillPackageService(self.db)
            skill_service = AdminSkillService(self.db)

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
                else await self._select_source(),
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
                shutil.rmtree(storage_dir)
            shutil.copytree(payload["extract_dir"], storage_dir)

            await self.db.commit()
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
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def batch_upgrade(
        self,
        *,
        slugs: list[str] | None = None,
    ) -> dict:
        candidates = await self.list_installed_updates()
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
                result = await self.upgrade_package(slug)
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


__all__ = ["SkillRegistryService"]
