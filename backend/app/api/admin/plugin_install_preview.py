"""Helpers for plugin install preview token and marketplace package validation."""

from __future__ import annotations

import re
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from fastapi import File, Form, Response, UploadFile
from jose import ExpiredSignatureError, JWTError, jwt

from app.api.admin.plugin_admin_contracts import PluginInstallConfirmBody
from app.core.base_model import utc_now
from app.core.config import settings
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _ as translate
from app.core.logging import get_logger
from app.core.response import created, paginated, success
from app.rbac.decorators import action_create, action_read
from app.services.system.plugin_read_model_service import PluginReadModelService

if TYPE_CHECKING:
    from app.core.base_controller import GlobalController

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]*$")
_INSTALL_PREVIEW_TOKEN_TYPE = "plugin_install_preview"
_logger = get_logger(__name__)


def sanitize_marketplace_slug(slug: str) -> None:
    """Validate marketplace slug to prevent path traversal."""
    if not slug or not _SLUG_PATTERN.match(slug) or len(slug) > 128:
        from app.exceptions.base import ValidationException

        raise ValidationException(
            message=translate("plugin.error.invalid_marketplace_slug").format(
                slug=slug
            ),
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
        raise ValidationException(
            message=translate("plugin.error.install_preview_required")
        )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except ExpiredSignatureError as exc:
        raise ValidationException(
            message=translate("plugin.error.install_preview_expired")
        ) from exc
    except JWTError as exc:
        raise ValidationException(
            message=translate("plugin.error.install_preview_invalid")
        ) from exc

    if payload.get("type") != _INSTALL_PREVIEW_TOKEN_TYPE:
        raise ValidationException(
            message=translate("plugin.error.install_preview_invalid")
        )
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
        raise ValidationException(
            message=translate("plugin.error.install_preview_invalid")
        )
    if (
        marketplace_slug is not None
        and payload.get("marketplace_slug") != marketplace_slug
    ):
        raise ValidationException(
            message=translate("plugin.error.install_preview_invalid")
        )
    if admin_id is not None and payload.get("admin_id") not in {None, int(admin_id)}:
        raise ValidationException(
            message=translate("plugin.error.install_preview_invalid")
        )
    if plugin_name is not None and payload.get("plugin_name") != plugin_name:
        raise ValidationException(
            message=translate("plugin.error.install_preview_stale")
        )
    if version is not None and payload.get("version") != version:
        raise ValidationException(
            message=translate("plugin.error.install_preview_stale")
        )


async def test_registry_connection(
    *,
    source_url: str,
    default_url: str,
    log_label: str,
) -> dict[str, Any]:
    """Probe registry URL and return connectivity payload for controller response."""
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

        raise ValidationException(
            message=translate("plugin.error.invalid_registry_url_scheme"),
        )

    hostname = (parsed.hostname or "").lower()
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            from app.exceptions.base import ValidationException

            raise ValidationException(
                message=translate("plugin.error.invalid_registry_private_ip"),
            )
    except ValueError as exc:
        if hostname not in allowed_hosts:
            from app.exceptions.base import ValidationException

            raise ValidationException(
                message=translate("plugin.error.invalid_registry_host").format(
                    host=hostname,
                ),
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
            "error": translate("plugin.error.registry_connection_failed"),
            "latency_ms": -1,
        }


def extract_plugin_from_zip(file_content: bytes, filename: str) -> tuple[Path, Path]:
    """Extract plugin ZIP into system temp dir and return (staging_dir, plugin_dir)."""
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
        import shutil

        shutil.rmtree(staging_dir, ignore_errors=True)
        raise

    return staging_dir, plugin_dir


def register_plugin_install_preview_routes(controller: GlobalController) -> None:
    """Register marketplace and upload preview/install routes."""

    @controller.router.post("/marketplace/test-connection")
    @action_read("action.plugin.list")
    async def marketplace_test_connection(
        db: DbSession,
        admin: ActiveAdmin,
        source_url: str = "",
    ):
        _ = db, admin
        from app.plugins.marketplace import _DEFAULT_GITHUB_URL

        return success(
            data=await test_registry_connection(
                source_url=source_url,
                default_url=_DEFAULT_GITHUB_URL,
                log_label="Marketplace",
            )
        )

    @controller.router.post("/skill-registry/test-connection")
    @action_read("action.plugin.list")
    async def skill_registry_test_connection(
        db: DbSession,
        admin: ActiveAdmin,
        source_url: str = "",
    ):
        _ = db, admin
        from app.services.ai.skill_registry_service import (
            _DEFAULT_GITHUB_URL as _SKILL_DEFAULT_GITHUB_URL,
        )

        return success(
            data=await test_registry_connection(
                source_url=source_url,
                default_url=_SKILL_DEFAULT_GITHUB_URL,
                log_label="Skill registry",
            )
        )

    @controller.router.get("/marketplace")
    @action_read("action.plugin.list")
    async def marketplace_list(
        db: DbSession,
        admin: ActiveAdmin,
        response: Response,
        category: str = "",
        sort: str = "-downloads",
        search: str = "",
        page_number: int = 1,
        page_size: int = 20,
    ):
        _ = admin
        from app.plugins.marketplace import MarketplaceClient

        page_size = max(1, min(page_size, 100))
        page_number = max(1, page_number)
        client = MarketplaceClient(db)
        result = await client.list_plugins(
            search=search,
            category=category,
            sort=sort,
            page_number=page_number,
            page_size=page_size,
        )
        response.headers["Cache-Control"] = "private, max-age=60"
        return paginated(
            items=result["items"],
            total=result["total"],
            page=page_number,
            page_size=page_size,
        )

    @controller.router.get("/marketplace/{slug}")
    @action_read("action.plugin.list")
    async def marketplace_detail(
        slug: str,
        db: DbSession,
        admin: ActiveAdmin,
        response: Response,
    ):
        _ = admin
        from app.plugins.marketplace import MarketplaceClient

        client = MarketplaceClient(db)
        detail = await client.fetch_plugin_detail(slug)
        if not detail:
            from app.plugins.exceptions import PluginNotFoundError

            raise PluginNotFoundError(
                message=translate("plugin.error.marketplace_not_found").format(
                    slug=slug,
                )
            )

        readme = await client.fetch_readme(slug)
        detail["readme"] = readme

        compat = detail.get("compatibility", {})
        detail["compatibility_ok"] = True
        if compat.get("platform_version"):
            detail["platform_version_required"] = compat["platform_version"]

        response.headers["Cache-Control"] = "private, max-age=120"
        return success(data=detail)

    @controller.router.post("/marketplace/{slug}/install")
    @action_create("action.plugin.install")
    async def marketplace_preview_install(
        slug: str,
        db: DbSession = None,
        admin: ActiveAdmin = None,
    ):
        sanitize_marketplace_slug(slug)

        from app.plugins.loader import PluginLoader
        from app.plugins.marketplace import MarketplaceClient
        from app.plugins.package_security import extract_plugin_zip_safely
        from app.plugins.preview import generate_preview

        client = MarketplaceClient(db)
        detail = await client.fetch_plugin_detail(slug)
        if not detail:
            from app.plugins.exceptions import PluginNotFoundError

            raise PluginNotFoundError(
                message=translate("plugin.error.marketplace_not_found").format(
                    slug=slug,
                )
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
            preview = await generate_preview(plugin_dir, loader, db=db)
            preview.preview_token = create_install_preview_token(
                source="marketplace",
                plugin_name=manifest.name,
                version=manifest.version,
                admin_id=getattr(admin, "id", None),
                marketplace_slug=slug,
            )
            return success(data=preview.model_dump())
        finally:
            shutil.rmtree(zip_path.parent, ignore_errors=True)

    @controller.router.post("/marketplace/{slug}/confirm-install")
    @action_create("action.plugin.install")
    async def marketplace_confirm_install(
        slug: str,
        body: PluginInstallConfirmBody,
        db: DbSession = None,
        admin: ActiveAdmin = None,
    ):
        from app.enums.plugin import PluginInstallSourceEnum
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
            admin_id=getattr(admin, "id", None),
        )

        client = MarketplaceClient(db)
        detail = await client.fetch_plugin_detail(slug)
        if not detail:
            from app.plugins.exceptions import PluginNotFoundError

            raise PluginNotFoundError(
                message=translate("plugin.error.marketplace_not_found").format(
                    slug=slug,
                )
            )

        version = detail.get("version", "1.0.0")
        assert_install_preview_token(
            preview_payload,
            source="marketplace",
            version=str(version),
            admin_id=getattr(admin, "id", None),
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
                admin_id=getattr(admin, "id", None),
                marketplace_slug=slug,
            )
            _logger.info(
                "Marketplace confirm install: slug={} plugin={}",
                slug,
                manifest.name,
            )
            service = controller.get_service(db)
            plugin = await service.install_from_path(plugin_dir, body.config)
            plugin.install_source = PluginInstallSourceEnum.MARKETPLACE.value
            plugin.marketplace_slug = slug
            await db.flush()

            await notify(
                db,
                "biz.plugin_installed",
                [("admin", admin.id)],
                data={
                    "plugin_name": plugin.display_name or plugin.name,
                    "version": plugin.version or "1.0.0",
                },
            )

            return created(data=plugin.to_dict())
        finally:
            shutil.rmtree(zip_path.parent, ignore_errors=True)

    @controller.router.post("/preview")
    @action_create("action.plugin.preview")
    async def preview_install(
        file: UploadFile = File(...),
        db: DbSession = None,
        admin: ActiveAdmin = None,
    ):
        from app.plugins.loader import PluginLoader
        from app.plugins.preview import generate_preview

        content = await file.read()
        staging_dir, plugin_dir = extract_plugin_from_zip(
            content, file.filename or "plugin.zip"
        )

        try:
            loader = PluginLoader(plugins_dir=plugin_dir.parent)
            preview = await generate_preview(plugin_dir, loader, db=db)
            manifest = loader.load_manifest_from_path(plugin_dir)
            preview.preview_token = create_install_preview_token(
                source="upload",
                plugin_name=manifest.name,
                version=manifest.version,
                admin_id=getattr(admin, "id", None),
            )
            return success(data=preview.model_dump())
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

    @controller.router.post("/upload")
    @action_create("action.plugin.install")
    async def install_plugin(
        file: UploadFile = File(...),
        preview_token: str = Form(""),
        db: DbSession = None,
        admin: ActiveAdmin = None,
    ):
        import yaml

        from app.services.common.notification_service import notify

        preview_payload = decode_install_preview_token(preview_token)
        assert_install_preview_token(
            preview_payload,
            source="upload",
            admin_id=getattr(admin, "id", None),
        )

        content = await file.read()
        staging_dir, plugin_dir = extract_plugin_from_zip(
            content, file.filename or "plugin.zip"
        )

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
                admin_id=getattr(admin, "id", None),
            )

            await PluginReadModelService(db).assert_name_available(str(plugin_name))

            service = controller.get_service(db)
            plugin = await service.install_from_path(plugin_dir, operator_id=admin.id)

            await notify(
                db,
                "biz.plugin_installed",
                [("admin", admin.id)],
                data={
                    "plugin_name": plugin.display_name or plugin.name,
                    "version": plugin.version or "1.0.0",
                },
            )

            return created(data=plugin.to_dict())
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)
