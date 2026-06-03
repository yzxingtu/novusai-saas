"""
Plugin install preview workflow service. / 插件预安装与市场工作流服务。

Keeps marketplace/upload install-preview orchestration out of admin API modules.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jose import ExpiredSignatureError, JWTError, jwt

from app.core.base_model import utc_now
from app.core.config import settings
from app.core.i18n import _
from app.core.logging import get_logger
from app.services.system.plugin_read_model_service import PluginReadModelService
from app.services.system.plugin_service import PluginService

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]*$")
_INSTALL_PREVIEW_TOKEN_TYPE = "plugin_install_preview"
_logger = get_logger(__name__)


def sanitize_marketplace_slug(slug: str) -> None:
    """Validate marketplace slug to prevent path traversal."""
    if not slug or not _SLUG_PATTERN.match(slug) or len(slug) > 128:
        from app.exceptions.base import ValidationException

        raise ValidationException(
            message=_("plugin.error.invalid_marketplace_slug").format(slug=slug),
        )


def assert_marketplace_package_identity(
    *,
    slug: str,
    detail: dict,
    manifest,
) -> None:
    from app.plugins.exceptions import PluginInstallError

    expected_name = str(detail.get("name") or slug)
    expected_version = detail.get("version")

    if manifest.name != expected_name:
        raise PluginInstallError(
            message=(
                f"Marketplace package mismatch for '{slug}': expected plugin "
                f"'{expected_name}', got '{manifest.name}'"
            ),
        )

    if expected_version and manifest.version != expected_version:
        raise PluginInstallError(
            message=(
                f"Marketplace package version mismatch for '{slug}': expected "
                f"'{expected_version}', got '{manifest.version}'"
            ),
        )


def create_install_preview_token(
    *,
    source: str,
    plugin_name: str,
    version: str,
    admin_id: int | None,
    marketplace_slug: str | None = None,
) -> str:
    issued_at = utc_now()
    payload = {
        "sub": f"plugin-preview:{source}:{plugin_name}",
        "type": _INSTALL_PREVIEW_TOKEN_TYPE,
        "source": source,
        "plugin_name": plugin_name,
        "version": version,
        "iat": issued_at,
        "exp": issued_at + timedelta(seconds=15 * 60),
    }
    if admin_id is not None:
        payload["admin_id"] = int(admin_id)
    if marketplace_slug:
        payload["marketplace_slug"] = marketplace_slug
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_install_preview_token(token: str) -> dict[str, Any]:
    from app.exceptions.base import ValidationException

    if not token:
        raise ValidationException(message=_("plugin.error.install_preview_required"))

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except ExpiredSignatureError as exc:
        raise ValidationException(
            message=_("plugin.error.install_preview_expired")
        ) from exc
    except JWTError as exc:
        raise ValidationException(
            message=_("plugin.error.install_preview_invalid")
        ) from exc

    if payload.get("type") != _INSTALL_PREVIEW_TOKEN_TYPE:
        raise ValidationException(message=_("plugin.error.install_preview_invalid"))
    return payload


def assert_install_preview_token(
    payload: dict[str, Any],
    *,
    source: str,
    plugin_name: str | None = None,
    version: str | None = None,
    marketplace_slug: str | None = None,
    admin_id: int | None = None,
) -> None:
    from app.exceptions.base import ValidationException

    if payload.get("source") != source:
        raise ValidationException(message=_("plugin.error.install_preview_invalid"))
    if (
        marketplace_slug is not None
        and payload.get("marketplace_slug") != marketplace_slug
    ):
        raise ValidationException(message=_("plugin.error.install_preview_invalid"))
    if admin_id is not None and payload.get("admin_id") not in {None, int(admin_id)}:
        raise ValidationException(message=_("plugin.error.install_preview_invalid"))
    if plugin_name is not None and payload.get("plugin_name") != plugin_name:
        raise ValidationException(message=_("plugin.error.install_preview_stale"))
    if version is not None and payload.get("version") != version:
        raise ValidationException(message=_("plugin.error.install_preview_stale"))


async def test_registry_connection(
    *,
    source_url: str,
    default_url: str,
    log_label: str,
) -> dict[str, Any]:
    """Probe registry URL and return connectivity payload."""
    import ipaddress
    import time as _time

    import httpx as _httpx

    if not source_url:
        source_url = default_url

    allowed_schemes = {"http", "https"}
    allowed_hosts = {
        "github.com",
        "raw.githubusercontent.com",
        "api.github.com",
        "objects.githubusercontent.com",
    }

    parsed = urlparse(source_url)
    if parsed.scheme not in allowed_schemes:
        from app.exceptions.base import ValidationException

        raise ValidationException(message=_("plugin.error.invalid_registry_url_scheme"))

    hostname = (parsed.hostname or "").lower()
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            from app.exceptions.base import ValidationException

            raise ValidationException(
                message=_("plugin.error.invalid_registry_private_ip")
            )
    except ValueError as exc:
        if hostname not in allowed_hosts:
            from app.exceptions.base import ValidationException

            raise ValidationException(
                message=_("plugin.error.invalid_registry_host").format(host=hostname),
            ) from exc

    registry_url = f"{source_url.rstrip('/')}/registry.json"
    try:
        started = _time.perf_counter()
        async with _httpx.AsyncClient(timeout=5.0) as client:
            response = await client.head(registry_url)
        latency_ms = int((_time.perf_counter() - started) * 1000)
        return {
            "ok": response.status_code < 400,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        _logger.warning(
            "{} connection test failed for {}: {}",
            log_label,
            source_url,
            exc,
        )
        return {
            "ok": False,
            "error": _("plugin.error.registry_connection_failed"),
            "latency_ms": -1,
        }


def extract_plugin_from_zip(file_content: bytes, filename: str) -> tuple[Path, Path]:
    """Extract plugin ZIP into temp dir and return (staging_dir, plugin_dir)."""
    from app.plugins.package_security import (
        ensure_package_size_limit,
        extract_plugin_zip_safely,
    )

    staging_dir = Path(tempfile.mkdtemp(prefix="novusai_plugin_"))
    safe_filename = Path(filename).name if filename else "plugin.zip"
    ensure_package_size_limit(len(file_content))

    zip_path = staging_dir / safe_filename
    with open(zip_path, "wb") as file:
        file.write(file_content)

    try:
        extract_dir = staging_dir / "extracted"
        plugin_dir = extract_plugin_zip_safely(zip_path, extract_dir)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise

    return staging_dir, plugin_dir


class PluginInstallPreviewService:
    """Own marketplace/upload install-preview orchestration."""

    def __init__(self, db) -> None:
        self._db = db
        self._plugin_service = PluginService(db)
        self._read_model_service = PluginReadModelService(db)

    async def marketplace_list(
        self,
        *,
        category: str,
        sort: str,
        search: str,
        page_number: int,
        page_size: int,
    ) -> dict[str, Any]:
        from app.plugins.marketplace import MarketplaceClient

        page_size = max(1, min(page_size, 100))
        page_number = max(1, page_number)
        client = MarketplaceClient(self._db)
        result = await client.list_plugins(
            search=search,
            category=category,
            sort=sort,
            page_number=page_number,
            page_size=page_size,
        )
        return {
            "items": result["items"],
            "total": result["total"],
            "page": page_number,
            "page_size": page_size,
        }

    async def marketplace_detail(self, *, slug: str) -> dict[str, Any]:
        from app.plugins.exceptions import PluginNotFoundError
        from app.plugins.marketplace import MarketplaceClient

        sanitize_marketplace_slug(slug)
        client = MarketplaceClient(self._db)
        detail = await client.fetch_plugin_detail(slug)
        if not detail:
            raise PluginNotFoundError(
                message=_("plugin.error.marketplace_not_found").format(slug=slug),
            )

        readme = await client.fetch_readme(slug)
        detail["readme"] = readme

        compat = detail.get("compatibility", {})
        detail["compatibility_ok"] = True
        if compat.get("platform_version"):
            detail["platform_version_required"] = compat["platform_version"]
        return detail

    async def marketplace_preview_install(
        self,
        *,
        slug: str,
        admin_id: int | None,
    ) -> dict[str, Any]:
        from app.plugins.exceptions import PluginNotFoundError
        from app.plugins.loader import PluginLoader
        from app.plugins.marketplace import MarketplaceClient
        from app.plugins.package_security import extract_plugin_zip_safely
        from app.plugins.preview import generate_preview

        sanitize_marketplace_slug(slug)
        client = MarketplaceClient(self._db)
        detail = await client.fetch_plugin_detail(slug)
        if not detail:
            raise PluginNotFoundError(
                message=_("plugin.error.marketplace_not_found").format(slug=slug),
            )

        version = detail.get("version", "1.0.0")
        zip_path = await client.download_plugin(slug, version)

        try:
            extract_dir = zip_path.parent / "extracted"
            plugin_dir = extract_plugin_zip_safely(zip_path, extract_dir)
            loader = PluginLoader(plugins_dir=plugin_dir.parent)
            manifest = loader.load_manifest_from_path(plugin_dir)
            assert_marketplace_package_identity(
                slug=slug,
                detail=detail,
                manifest=manifest,
            )
            preview = await generate_preview(plugin_dir, loader, db=self._db)
            preview.preview_token = create_install_preview_token(
                source="marketplace",
                plugin_name=manifest.name,
                version=manifest.version,
                admin_id=admin_id,
                marketplace_slug=slug,
            )
            return preview.model_dump()
        finally:
            shutil.rmtree(zip_path.parent, ignore_errors=True)

    async def marketplace_confirm_install(
        self,
        *,
        slug: str,
        body,
        admin_id: int | None,
    ) -> dict[str, Any]:
        from app.enums.plugin import PluginInstallSourceEnum
        from app.plugins.exceptions import PluginNotFoundError
        from app.plugins.loader import PluginLoader
        from app.plugins.marketplace import MarketplaceClient
        from app.plugins.package_security import extract_plugin_zip_safely
        from app.services.common.notification_service import notify

        sanitize_marketplace_slug(slug)
        preview_payload = decode_install_preview_token(body.preview_token)
        assert_install_preview_token(
            preview_payload,
            source="marketplace",
            marketplace_slug=slug,
            admin_id=admin_id,
        )

        client = MarketplaceClient(self._db)
        detail = await client.fetch_plugin_detail(slug)
        if not detail:
            raise PluginNotFoundError(
                message=_("plugin.error.marketplace_not_found").format(slug=slug),
            )

        version = detail.get("version", "1.0.0")
        assert_install_preview_token(
            preview_payload,
            source="marketplace",
            version=str(version),
            admin_id=admin_id,
            marketplace_slug=slug,
        )
        zip_path = await client.download_plugin(slug, version)

        try:
            extract_dir = zip_path.parent / "extracted"
            plugin_dir = extract_plugin_zip_safely(zip_path, extract_dir)
            loader = PluginLoader()
            manifest = loader.load_manifest_from_path(plugin_dir)
            assert_marketplace_package_identity(
                slug=slug,
                detail=detail,
                manifest=manifest,
            )
            assert_install_preview_token(
                preview_payload,
                source="marketplace",
                plugin_name=manifest.name,
                version=manifest.version,
                admin_id=admin_id,
                marketplace_slug=slug,
            )
            _logger.info(
                "Marketplace confirm install: slug={} plugin={}",
                slug,
                manifest.name,
            )
            plugin = await self._plugin_service.install_from_path(
                plugin_dir, body.config
            )
            plugin.install_source = PluginInstallSourceEnum.MARKETPLACE.value
            plugin.marketplace_slug = slug
            await self._db.flush()

            if admin_id is not None:
                await notify(
                    self._db,
                    "biz.plugin_installed",
                    [("admin", admin_id)],
                    data={
                        "plugin_name": plugin.display_name or plugin.name,
                        "version": plugin.version or "1.0.0",
                    },
                )
            return plugin.to_dict()
        finally:
            shutil.rmtree(zip_path.parent, ignore_errors=True)

    async def preview_upload_install(
        self,
        *,
        content: bytes,
        filename: str,
        admin_id: int | None,
    ) -> dict[str, Any]:
        from app.plugins.loader import PluginLoader
        from app.plugins.preview import generate_preview

        staging_dir, plugin_dir = extract_plugin_from_zip(content, filename)
        try:
            loader = PluginLoader(plugins_dir=plugin_dir.parent)
            preview = await generate_preview(plugin_dir, loader, db=self._db)
            manifest = loader.load_manifest_from_path(plugin_dir)
            preview.preview_token = create_install_preview_token(
                source="upload",
                plugin_name=manifest.name,
                version=manifest.version,
                admin_id=admin_id,
            )
            return preview.model_dump()
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

    async def install_upload_plugin(
        self,
        *,
        content: bytes,
        filename: str,
        preview_token: str,
        admin_id: int | None,
    ) -> dict[str, Any]:
        import yaml

        from app.services.common.notification_service import notify

        preview_payload = decode_install_preview_token(preview_token)
        assert_install_preview_token(
            preview_payload,
            source="upload",
            admin_id=admin_id,
        )

        staging_dir, plugin_dir = extract_plugin_from_zip(content, filename)
        try:
            with open(plugin_dir / "plugin.yaml", encoding="utf-8") as yaml_file:
                manifest_data = yaml.safe_load(yaml_file)
            plugin_name = manifest_data.get("name", plugin_dir.name)
            plugin_version = str(manifest_data.get("version", ""))
            assert_install_preview_token(
                preview_payload,
                source="upload",
                plugin_name=str(plugin_name),
                version=plugin_version,
                admin_id=admin_id,
            )

            await self._read_model_service.assert_name_available(str(plugin_name))
            plugin = await self._plugin_service.install_from_path(
                plugin_dir,
                operator_id=admin_id,
            )

            if admin_id is not None:
                await notify(
                    self._db,
                    "biz.plugin_installed",
                    [("admin", admin_id)],
                    data={
                        "plugin_name": plugin.display_name or plugin.name,
                        "version": plugin.version or "1.0.0",
                    },
                )
            return plugin.to_dict()
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)


__all__ = [
    "PluginInstallPreviewService",
    "assert_install_preview_token",
    "assert_marketplace_package_identity",
    "create_install_preview_token",
    "decode_install_preview_token",
    "extract_plugin_from_zip",
    "sanitize_marketplace_slug",
    "test_registry_connection",
]
