"""
动态 CORS 策略 / Dynamic CORS policy.

统一 HTTP 与 Socket.IO 的 Origin 判定规则。
Provides shared Origin checks for both HTTP and Socket.IO.
"""

from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.middleware.tenant import parse_tenant_from_host
from app.models.tenant.tenant_domain import TenantDomain

logger = get_logger(__name__)

_DEV_LOCAL_HOSTS = {"127.0.0.1", "localhost"}
_verified_custom_domain_hosts: set[str] = set()

DEFAULT_EXPOSE_HEADERS = "X-Trace-ID"
DEFAULT_ALLOW_METHODS = "DELETE,GET,OPTIONS,PATCH,POST,PUT"
DEFAULT_ALLOW_HEADERS = "Authorization,Content-Type,Origin,X-Language,X-Trace-ID"


def _normalize_origin_host(value: str | None) -> str:
    if not value:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    return (parsed.hostname or raw.split(":")[0]).strip().lower()


def _is_local_debug_origin(host: str) -> bool:
    return bool(settings.DEBUG and host in _DEV_LOCAL_HOSTS)


def _is_platform_origin(host: str) -> bool:
    platform_hosts = {
        _normalize_origin_host(item) for item in settings.platform_domains_list
    }
    return host in platform_hosts


def _is_tenant_subdomain_origin(host: str) -> bool:
    tenant_code, domain_type = parse_tenant_from_host(host)
    return bool(tenant_code and domain_type == "subdomain")


def remember_verified_custom_domain(host: str | None) -> None:
    normalized = _normalize_origin_host(host)
    if normalized:
        _verified_custom_domain_hosts.add(normalized)


def forget_verified_custom_domain(host: str | None) -> None:
    normalized = _normalize_origin_host(host)
    if normalized:
        _verified_custom_domain_hosts.discard(normalized)


def list_verified_custom_domains() -> set[str]:
    return set(_verified_custom_domain_hosts)


def is_origin_allowed_sync(origin: str | None, _environ=None) -> bool:
    """
    同步 Origin 判定 / Synchronous Origin check.

    供 Socket.IO 的 `cors_allowed_origins` callable 复用。
    Used by the Socket.IO `cors_allowed_origins` callable.
    """
    if not origin:
        return False
    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"}:
        return False

    host = _normalize_origin_host(origin)
    if not host:
        return False
    if _is_local_debug_origin(host):
        return True
    if _is_platform_origin(host):
        return True
    if _is_tenant_subdomain_origin(host):
        return True
    return host in _verified_custom_domain_hosts


async def is_origin_allowed(origin: str | None) -> bool:
    """
    异步 Origin 判定 / Asynchronous Origin check.

    HTTP 层在需要时会回查 `tenant_domains` 表，
    并同步更新进程内 cache。
    HTTP requests may query `tenant_domains` for verified custom domains and
    refresh the in-process cache.
    """
    if is_origin_allowed_sync(origin):
        return True
    if not origin:
        return False

    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"}:
        return False

    host = _normalize_origin_host(origin)
    if not host:
        return False

    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(TenantDomain.domain).where(
                    TenantDomain.domain == host,
                    TenantDomain.is_verified.is_(True),
                    TenantDomain.is_deleted.is_(False),
                )
            )
            domain = result.scalar_one_or_none()
            if domain:
                remember_verified_custom_domain(domain)
                return True
    except Exception as exc:
        logger.debug("Failed to resolve CORS custom domain {}: {}", host, str(exc))

    return False


async def refresh_verified_custom_domain_cache() -> None:
    """刷新已验证自定义域名缓存 / Refresh verified custom-domain cache."""
    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(TenantDomain.domain).where(
                    TenantDomain.is_verified.is_(True),
                    TenantDomain.is_deleted.is_(False),
                )
            )
            domains = {
                _normalize_origin_host(domain)
                for domain in result.scalars().all()
                if _normalize_origin_host(domain)
            }
    except Exception as exc:
        logger.warning("Failed to refresh verified custom domain cache: {}", str(exc))
        return

    _verified_custom_domain_hosts.clear()
    _verified_custom_domain_hosts.update(domains)


def build_cors_headers(
    *,
    origin: str,
    allow_headers: str | None = None,
    preflight: bool = False,
) -> dict[str, str]:
    """
    构建 CORS 头 / Build CORS headers.
    """
    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Expose-Headers": DEFAULT_EXPOSE_HEADERS,
        "Vary": "Origin",
    }
    if preflight:
        headers.update(
            {
                "Access-Control-Allow-Headers": allow_headers or DEFAULT_ALLOW_HEADERS,
                "Access-Control-Allow-Methods": DEFAULT_ALLOW_METHODS,
            }
        )
    return headers


async def get_cors_headers_for_origin(
    origin: str | None,
    *,
    allow_headers: str | None = None,
    preflight: bool = False,
) -> dict[str, str]:
    """
    获取允许 Origin 的 CORS 头 / Get CORS headers for an allowed origin.
    """
    if not origin or not await is_origin_allowed(origin):
        return {}
    return build_cors_headers(
        origin=origin,
        allow_headers=allow_headers,
        preflight=preflight,
    )


__all__ = [
    "DEFAULT_ALLOW_HEADERS",
    "DEFAULT_ALLOW_METHODS",
    "DEFAULT_EXPOSE_HEADERS",
    "build_cors_headers",
    "forget_verified_custom_domain",
    "get_cors_headers_for_origin",
    "is_origin_allowed",
    "is_origin_allowed_sync",
    "list_verified_custom_domains",
    "refresh_verified_custom_domain_cache",
    "remember_verified_custom_domain",
]
