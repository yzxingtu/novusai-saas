"""
DNS provider readiness unit tests / DNS provider 可用性单元测试

覆盖目标 / Coverage:
1. Cloudflare 配置完整时 readiness=true
2. legacy provider（aliyun/dnspod）被识别并阻断
3. manual 模式不会被自动化签发流程接受
4. get_dns_provider() 只返回可用的 Cloudflare provider
5. 平台 SSL 配置保存时拒绝 legacy provider，并在 DEBUG 下允许 manual
"""

from __future__ import annotations

import pytest

from app.enums.error_code import ErrorCode
from app.exceptions import BusinessException
from app.services.system.dns_provider import (
    CloudflareDnsProvider,
    audit_dns_provider_config,
    ensure_dns_provider_ready,
    get_dns_provider,
    validate_platform_ssl_config_patch,
)


class _FakeConfigService:
    """简单的 ConfigService 替身 / Minimal ConfigService stub."""

    def __init__(self, values: dict[str, object]):
        self._values = values

    async def get_platform_config(self, key: str, default=None):
        return self._values.get(key, default)


@pytest.mark.asyncio
async def test_audit_dns_provider_config_ready_for_cloudflare(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cloudflare 配置完整时应判定为 ready / Cloudflare with full credentials should be ready."""
    monkeypatch.setattr(
        "app.services.system.dns_provider.ConfigService",
        lambda _db: _FakeConfigService(
            {
                "dns_provider": "cloudflare",
                "dns_cloudflare_api_token": "token-123",
                "dns_cloudflare_zone_id": "zone-123",
            }
        ),
    )
    monkeypatch.setattr(
        "app.services.system.dns_provider.settings.DEBUG",
        False,
        raising=False,
    )

    audit = await audit_dns_provider_config(object())

    assert audit["provider_type"] == "cloudflare"
    assert audit["ready"] is True
    assert audit["supported"] is True
    assert audit["issues"] == []


@pytest.mark.asyncio
async def test_audit_dns_provider_config_marks_legacy_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """legacy provider 应被识别为不可用 / Legacy provider should be marked unsupported."""
    monkeypatch.setattr(
        "app.services.system.dns_provider.ConfigService",
        lambda _db: _FakeConfigService({"dns_provider": "aliyun"}),
    )
    monkeypatch.setattr(
        "app.services.system.dns_provider.settings.DEBUG",
        False,
        raising=False,
    )

    audit = await audit_dns_provider_config(object())

    assert audit["ready"] is False
    assert audit["supported"] is False
    assert audit["issues"][0]["code"] == "legacy_unsupported_provider"


@pytest.mark.asyncio
async def test_ensure_dns_provider_ready_rejects_manual(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """manual 模式不可用于自动化签发 / Manual mode must be rejected for automated issuance."""
    monkeypatch.setattr(
        "app.services.system.dns_provider.ConfigService",
        lambda _db: _FakeConfigService({"dns_provider": "manual"}),
    )
    monkeypatch.setattr(
        "app.services.system.dns_provider.settings.DEBUG",
        False,
        raising=False,
    )

    with pytest.raises(BusinessException) as exc_info:
        await ensure_dns_provider_ready(object())

    assert exc_info.value.code == ErrorCode.CONFIG_VALIDATION_FAILED


@pytest.mark.asyncio
async def test_get_dns_provider_returns_cloudflare_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """仅在 ready 时返回 Cloudflare provider / Return Cloudflare provider only when config is ready."""
    monkeypatch.setattr(
        "app.services.system.dns_provider.ConfigService",
        lambda _db: _FakeConfigService(
            {
                "dns_provider": "cloudflare",
                "dns_cloudflare_api_token": "token-abc",
                "dns_cloudflare_zone_id": "zone-abc",
            }
        ),
    )
    monkeypatch.setattr(
        "app.services.system.dns_provider.settings.DEBUG",
        False,
        raising=False,
    )

    provider = await get_dns_provider(object())

    assert isinstance(provider, CloudflareDnsProvider)


@pytest.mark.asyncio
async def test_validate_platform_ssl_config_patch_rejects_legacy_provider() -> None:
    """保存配置时应拒绝 legacy provider / Reject legacy provider at config-save time."""
    configs = {"dns_provider": "dnspod"}

    with pytest.raises(BusinessException) as exc_info:
        await validate_platform_ssl_config_patch(configs)

    assert exc_info.value.code == ErrorCode.CONFIG_VALIDATION_FAILED


@pytest.mark.asyncio
async def test_validate_platform_ssl_config_patch_allows_manual_in_debug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEBUG 环境下允许保存 manual 以兼容开发调试 / Allow manual in DEBUG for local debugging."""
    configs = {"dns_provider": " Manual "}
    monkeypatch.setattr(
        "app.services.system.dns_provider.settings.DEBUG",
        True,
        raising=False,
    )

    await validate_platform_ssl_config_patch(configs)

    assert configs["dns_provider"] == "manual"
