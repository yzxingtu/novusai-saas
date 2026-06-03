"""
Skill registry support helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select

from app.ai.text_semantics import build_semver_sort_key, slugify_ascii_identifier
from app.core.github_source_policy import (
    open_github_only_stream,
    validate_github_source_url,
)
from app.core.logging import get_logger
from app.models.ai.skill import Skill
from app.models.ai.skill_package import SkillPackage
from app.repositories.ai.retired_skill_catalog_filters import (
    not_retired_skill_condition,
    not_retired_skill_package_condition,
)

logger = get_logger("app.services.ai.skill_registry_service")

_DEFAULT_GITHUB_URL = "https://raw.githubusercontent.com/novusai/skill-marketplace/main"
_DEFAULT_CACHE_TTL = 3600
_CACHE_PREFIX = "skill_registry:"
_OFFICIAL_STARTER_PACKS: tuple[dict[str, object], ...] = (
    {
        "key": "novusai-runtime-ops",
        "display_name": "NovusAI Runtime Ops",
        "description": "Operational diagnostics starter pack for AI runtime.",
        "package_slugs": (
            "novusai-doctor",
            "novusai-root-cause",
            "novusai-smoke",
            "novusai-plugin-audit",
        ),
    },
    {
        "key": "novusai-capability-awareness",
        "display_name": "NovusAI Capability Awareness",
        "description": "Runtime capability awareness starter pack.",
        "package_slugs": (
            "novusai-capabilities",
            "novusai-kb-status",
            "novusai-memory-status",
            "novusai-tool-status",
        ),
    },
)


@dataclass(slots=True)
class SkillRegistrySupport:
    db: Any
    github_url: str = _DEFAULT_GITHUB_URL
    cache_ttl: int = _DEFAULT_CACHE_TTL
    _selected_source: str | None = field(default=None, init=False)

    async def load_config(self) -> None:
        try:
            from app.configs.service import ConfigService

            svc = ConfigService(self.db)
            self.github_url = (
                await svc.get_platform_config(
                    "skill_registry_github_url", default=_DEFAULT_GITHUB_URL
                )
                or _DEFAULT_GITHUB_URL
            )
            ttl = await svc.get_platform_config(
                "skill_registry_cache_ttl", default=_DEFAULT_CACHE_TTL
            )
            if ttl:
                self.cache_ttl = int(ttl)
        except Exception as exc:
            logger.warning("Failed to load skill registry config: {}", exc)

    async def select_source(self) -> str:
        if self._selected_source:
            return self._selected_source

        await self.load_config()
        self._selected_source = self.github_url
        return self._selected_source

    async def get_cached(self, key: str) -> object | None:
        try:
            from app.core.redis import cache_get

            return await cache_get(f"{_CACHE_PREFIX}{key}")
        except Exception:
            return None

    async def set_cached(self, key: str, value: object) -> None:
        try:
            from app.core.redis import cache_set

            await cache_set(f"{_CACHE_PREFIX}{key}", value, ttl=self.cache_ttl)
        except Exception as exc:
            logger.debug("Skill registry cache_set failed for {}: {}", key, exc)

    def get_local_registry(self) -> list[dict]:
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

    def cache_key(self, prefix: str, source_url: str | None = None) -> str:
        if not source_url:
            return prefix
        safe = slugify_ascii_identifier(source_url)
        return f"{prefix}:{safe or 'default'}"

    @staticmethod
    def starter_pack_definitions() -> list[dict[str, object]]:
        return [dict(item) for item in _OFFICIAL_STARTER_PACKS]

    @staticmethod
    def version_key(version: str | None) -> tuple:
        return build_semver_sort_key(version)

    @classmethod
    def is_newer_version(
        cls, latest_version: str | None, installed_version: str | None
    ) -> bool:
        if not latest_version:
            return False
        if not installed_version:
            return True
        return cls.version_key(latest_version) > cls.version_key(installed_version)

    async def build_installed_map(
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
            )
            .join(SkillPackage, Skill.package_id == SkillPackage.id)
            .where(
                Skill.is_deleted.is_(False),
                SkillPackage.is_deleted.is_(False),
                Skill.type == "toolkit",
                not_retired_skill_condition(Skill),
                not_retired_skill_package_condition(SkillPackage),
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

    async def download_archive(
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

    async def load_archive_payload(
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


__all__ = [
    "SkillRegistrySupport",
    "_DEFAULT_GITHUB_URL",
    "_DEFAULT_CACHE_TTL",
    "_CACHE_PREFIX",
    "_OFFICIAL_STARTER_PACKS",
]
