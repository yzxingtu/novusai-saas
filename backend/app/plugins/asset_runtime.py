"""Plugin asset runtime access gate. / 插件静态资源运行时访问闸门。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Request
from sqlalchemy import select
from starlette.responses import Response

from app.captcha.runtime import resolve_public_captcha_plugin_bundle
from app.configs.service import ConfigService
from app.core.security import (
    TOKEN_SCOPE_ADMIN,
    TOKEN_SCOPE_TENANT_ADMIN,
    TOKEN_TYPE_ACCESS,
    decode_token,
)
from app.middleware.tenant import get_tenant_context
from app.models.system.plugin import Plugin
from app.plugins.runtime_gate import (
    PluginRuntimeGateResult,
    evaluate_plugin_runtime_gate,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class PluginAssetAccessResult:
    """Resolved plugin asset access decision. / 插件静态资源访问判定结果。"""

    allowed: bool
    reason_code: str
    token_scope: str | None = None
    tenant_id: int | None = None
    gate: PluginRuntimeGateResult | None = None


PLUGIN_ASSET_TOKEN_COOKIE = "novus_plugin_asset_token"
PLUGIN_ASSET_COOKIE_PATHS = (
    "/",
    "/plugin-assets",
    "/plugin-icons",
    "/plugin-public-assets",
)


def _get_cookie_domain_variants(hostname: str) -> list[str]:
    """Resolve cookie domain variants for cleanup. / 解析 Cookie 清理需要覆盖的域名变体。"""
    normalized_host = (hostname or "").strip().lower()
    if (
        not normalized_host
        or normalized_host == "localhost"
        or normalized_host.replace(".", "").isdigit()
    ):
        return []

    segments = [segment for segment in normalized_host.split(".") if segment]
    variants: list[str] = [normalized_host]
    for index in range(1, len(segments) - 1):
        candidate = ".".join(segments[index:])
        if candidate not in variants:
            variants.append(candidate)
    return variants


def clear_plugin_asset_access_cookie(response: Response, request: Request) -> None:
    """Expire historical asset auth cookies on public asset responses. / 在公开资源响应上清理历史鉴权 Cookie。"""
    secure = request.url.scheme == "https"
    domains = _get_cookie_domain_variants(request.url.hostname or "")

    for path in PLUGIN_ASSET_COOKIE_PATHS:
        response.delete_cookie(
            PLUGIN_ASSET_TOKEN_COOKIE,
            path=path,
            secure=secure,
            samesite="lax",
        )
        for domain in domains:
            response.delete_cookie(
                PLUGIN_ASSET_TOKEN_COOKIE,
                path=path,
                domain=domain,
                secure=secure,
                samesite="lax",
            )


def extract_plugin_asset_access_token(request: Request) -> str | None:
    """Read access token from header or cookie. / 从请求头或 Cookie 读取访问令牌。"""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip() or None

    cookie_token = request.cookies.get(PLUGIN_ASSET_TOKEN_COOKIE, "").strip()
    return cookie_token or None


async def authorize_plugin_asset_request(
    db: AsyncSession,
    request: Request,
    plugin_name: str,
    *,
    require_enabled: bool = True,
) -> PluginAssetAccessResult:
    """
    Authorize plugin static asset request via unified runtime gate.
    / 通过统一运行时闸门鉴权插件静态资源请求。
    """
    token = extract_plugin_asset_access_token(request)
    if not token:
        return PluginAssetAccessResult(
            allowed=False,
            reason_code="missing_token",
        )

    payload = await decode_token(token)
    if not payload or payload.get("type") != TOKEN_TYPE_ACCESS:
        return PluginAssetAccessResult(
            allowed=False,
            reason_code="invalid_token",
        )

    token_scope = payload.get("scope")
    tenant_id: int | None = None
    enforce_scope = False

    if token_scope == TOKEN_SCOPE_ADMIN:
        enforce_scope = False
    elif token_scope == TOKEN_SCOPE_TENANT_ADMIN:
        tenant_id = payload.get("tenant_id")
        if tenant_id is None:
            return PluginAssetAccessResult(
                allowed=False,
                reason_code="missing_tenant_id",
                token_scope=token_scope,
            )
        enforce_scope = True
    else:
        return PluginAssetAccessResult(
            allowed=False,
            reason_code="unsupported_scope",
            token_scope=str(token_scope or ""),
        )

    gate = await evaluate_plugin_runtime_gate(
        db,
        plugin_name,
        tenant_id=tenant_id,
        require_enabled=require_enabled,
        enforce_scope=enforce_scope,
    )
    if not gate.allowed:
        return PluginAssetAccessResult(
            allowed=False,
            reason_code=gate.reason_code,
            token_scope=token_scope,
            tenant_id=tenant_id,
            gate=gate,
        )

    return PluginAssetAccessResult(
        allowed=True,
        reason_code="allowed",
        token_scope=token_scope,
        tenant_id=tenant_id,
        gate=gate,
    )


async def authorize_plugin_icon_request(
    db: AsyncSession,
    request: Request,
    plugin_name: str,
) -> PluginAssetAccessResult:
    """
    Authorize admin-visible plugin metadata icon request.
    / 鉴权管理态可见的插件元数据图标请求。
    """
    token = extract_plugin_asset_access_token(request)
    if not token:
        return PluginAssetAccessResult(
            allowed=False,
            reason_code="missing_token",
        )

    payload = await decode_token(token)
    if not payload or payload.get("type") != TOKEN_TYPE_ACCESS:
        return PluginAssetAccessResult(
            allowed=False,
            reason_code="invalid_token",
        )

    token_scope = payload.get("scope")
    if token_scope != TOKEN_SCOPE_ADMIN:
        return PluginAssetAccessResult(
            allowed=False,
            reason_code="unsupported_scope",
            token_scope=str(token_scope or ""),
        )

    result = await db.execute(
        select(Plugin.id).where(
            Plugin.name == plugin_name,
            Plugin.is_deleted.is_(False),
        )
    )
    plugin_id = result.scalar_one_or_none()
    if plugin_id is None:
        return PluginAssetAccessResult(
            allowed=False,
            reason_code="not_found",
            token_scope=TOKEN_SCOPE_ADMIN,
        )

    return PluginAssetAccessResult(
        allowed=True,
        reason_code="allowed",
        token_scope=TOKEN_SCOPE_ADMIN,
    )


async def authorize_public_captcha_asset_request(
    db: AsyncSession,
    request: Request,
    plugin_name: str,
    public_endpoint: str,
) -> PluginAssetAccessResult:
    """
    Authorize public captcha plugin assets for login pages.
    / 为登录页公开验证码插件静态资源做鉴权。
    """
    endpoint = str(public_endpoint or "").strip().lower()
    if endpoint not in {"admin", "tenant", "user"}:
        return PluginAssetAccessResult(
            allowed=False,
            reason_code="invalid_public_endpoint",
        )

    config_service = ConfigService(db)
    if endpoint == "admin":
        provider_code = await config_service.get_platform_config(
            "captcha_provider",
            default=None,
        )
    else:
        tenant_ctx = get_tenant_context(request)
        tenant = tenant_ctx.tenant if tenant_ctx and tenant_ctx.is_resolved else None
        if tenant is None:
            return PluginAssetAccessResult(
                allowed=False,
                reason_code="tenant_not_resolved",
            )
        provider_code = await config_service.get_tenant_config(
            int(tenant.id),
            "tenant_captcha_provider",
            default=None,
        )

    bundle = await resolve_public_captcha_plugin_bundle(
        db,
        request,
        provider_code,
        endpoint,
    )
    if bundle is None or bundle.plugin_name != plugin_name:
        return PluginAssetAccessResult(
            allowed=False,
            reason_code="captcha_plugin_not_active",
        )

    return PluginAssetAccessResult(
        allowed=True,
        reason_code="allowed",
    )
