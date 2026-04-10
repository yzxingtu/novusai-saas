"""Helpers for plugin install preview token and marketplace package validation."""

from __future__ import annotations

import re
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
            message=_("plugin.error.invalid_registry_url_scheme"),
        )

    hostname = (parsed.hostname or "").lower()
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            from app.exceptions.base import ValidationException

            raise ValidationException(
                message=_("plugin.error.invalid_registry_private_ip"),
            )
    except ValueError as exc:
        if hostname not in allowed_hosts:
            from app.exceptions.base import ValidationException

            raise ValidationException(
                message=_("plugin.error.invalid_registry_host").format(
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
            "error": _("plugin.error.registry_connection_failed"),
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
