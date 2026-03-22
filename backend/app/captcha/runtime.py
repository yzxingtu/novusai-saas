"""Captcha plugin runtime helpers. / 验证码插件运行时辅助工具。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.captcha.registry import registry
from app.middleware.tenant import get_tenant_context
from app.plugins.runtime_gate import evaluate_plugin_runtime_gate

_PUBLIC_CAPTCHA_ENDPOINTS = {"admin", "tenant", "user"}


@dataclass(slots=True)
class CaptchaPluginBundle:
    """Resolved captcha plugin bundle / 已解析的验证码插件运行时包"""

    plugin_name: str
    plugin_config: dict[str, Any]
    frontend_runtime: dict[str, str]
    public_endpoint: str

    def to_public_payload(self) -> dict[str, Any]:
        """Serialize public runtime payload / 序列化公开运行时载荷"""
        return {
            "frontend_runtime": dict(self.frontend_runtime or {}),
            "plugin_name": self.plugin_name,
            "public_endpoint": self.public_endpoint,
        }


def _normalize_public_endpoint(endpoint: str | None) -> str | None:
    raw = str(endpoint or "").strip().lower()
    if raw in _PUBLIC_CAPTCHA_ENDPOINTS:
        return raw
    return None


def _resolve_public_tenant_id(request: Request | None, endpoint: str) -> int | None:
    if endpoint not in {"tenant", "user"} or request is None:
        return None

    tenant_ctx = get_tenant_context(request)
    if tenant_ctx and tenant_ctx.is_resolved and tenant_ctx.tenant:
        return int(tenant_ctx.tenant.id)
    return None


async def resolve_public_captcha_plugin_bundle(
    db: AsyncSession,
    request: Request | None,
    provider_code: str | None,
    endpoint: str | None,
) -> CaptchaPluginBundle | None:
    """Resolve public captcha plugin bundle for login pages / 为登录页解析公开验证码插件运行时包"""
    code = str(provider_code or "").strip()
    normalized_endpoint = _normalize_public_endpoint(endpoint)
    if not code or not normalized_endpoint:
        return None

    metadata = registry.get_metadata(code)
    if metadata is None or not metadata.plugin_name:
        return None
    if normalized_endpoint not in set(metadata.public_endpoints or []):
        return None

    tenant_id = _resolve_public_tenant_id(request, normalized_endpoint)
    enforce_scope = normalized_endpoint in {"tenant", "user"}
    if enforce_scope and tenant_id is None:
        return None

    gate = await evaluate_plugin_runtime_gate(
        db,
        metadata.plugin_name,
        tenant_id=tenant_id,
        require_enabled=True,
        enforce_scope=enforce_scope,
    )
    if not gate.allowed:
        return None

    return CaptchaPluginBundle(
        plugin_name=metadata.plugin_name,
        plugin_config=dict(gate.config or {}),
        frontend_runtime=dict(metadata.frontend_runtime or {}),
        public_endpoint=normalized_endpoint,
    )


__all__ = ["CaptchaPluginBundle", "resolve_public_captcha_plugin_bundle"]
