from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.public.platform import get_platform_public_config
from app.api.public.tenant import (
    get_tenant_legal_privacy,
    get_tenant_legal_terms,
    get_tenant_public_config,
)


class _FakePlatformConfigService:
    def __init__(self, groups: dict[str, dict[str, object]]):
        self._groups = groups

    async def get_platform_configs_by_group(self, group_code: str):
        return self._groups.get(group_code, {})


class _FakeTenantConfigService:
    def __init__(self, groups: dict[str, dict[str, object]]):
        self._groups = groups

    async def get_platform_configs_by_group(self, group_code: str):
        return self._groups.get(group_code, {})

    async def get_tenant_configs_by_group(
        self,
        tenant_id: int,
        group_code: str,
    ):
        _ = tenant_id
        return self._groups.get(group_code, {})


async def _return_none(*_args, **_kwargs):
    return None


@pytest.mark.asyncio
async def test_platform_public_config_reads_domain_group(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.public.platform.ConfigService",
        lambda _db: _FakePlatformConfigService(
            {
                "platform_general": {
                    "site_name": "Platform Site",
                },
                "platform_domain": {
                    "tenant_domain_suffix": ".tenant.example.com",
                    "domain_verification_prefix": "_verify",
                },
                "platform_security": {},
                "platform_ai_toolkit": {},
                "platform_storage": {},
            }
        ),
    )
    monkeypatch.setattr(
        "app.api.public.platform.resolve_public_captcha_plugin_bundle",
        _return_none,
    )
    monkeypatch.setattr(
        "app.api.public.platform.settings.PLATFORM_DOMAINS",
        "localhost",
        raising=False,
    )

    response = await get_platform_public_config(object())

    assert response["data"]["tenant_domain_suffix"] == ".tenant.example.com"
    assert response["data"]["domain_verification_prefix"] == "_verify"


@pytest.mark.asyncio
async def test_tenant_public_config_reads_registration_group(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant = SimpleNamespace(code="acme", id=1, name="Acme")
    request = SimpleNamespace(url=SimpleNamespace(scheme="https"))

    monkeypatch.setattr(
        "app.api.public.tenant.get_tenant_context",
        lambda _request: SimpleNamespace(is_resolved=True, tenant=tenant),
    )
    monkeypatch.setattr(
        "app.api.public.tenant.ConfigService",
        lambda _db: _FakeTenantConfigService(
            {
                "tenant_general": {},
                "tenant_appearance": {},
                "tenant_registration": {
                    "tenant_allow_registration": False,
                    "tenant_registration_approval": True,
                    "user_privacy_policy_url": "https://example.com/privacy",
                    "user_terms_url": "https://example.com/terms",
                    "user_privacy_policy_html": "<p>privacy</p>",
                    "user_terms_html": "<p>terms</p>",
                    "user_registration_captcha_enabled": False,
                },
                "tenant_features": {
                    "tenant_allow_profile_edit": True,
                },
                "tenant_storage": {},
                "platform_general": {
                    "site_name": "Platform Site",
                    "site_description": "Platform Description",
                    "site_copyright": "Platform Copyright",
                    "site_icp": "ICP 123456",
                },
                "platform_storage": {},
            }
        ),
    )
    monkeypatch.setattr(
        "app.api.public.tenant.resolve_public_captcha_plugin_bundle",
        _return_none,
    )
    monkeypatch.setattr(
        "app.api.public.tenant.settings.TENANT_DOMAIN_SUFFIX",
        ".tenant.example.com",
        raising=False,
    )

    response = await get_tenant_public_config(request, object())

    assert response["data"]["allow_registration"] is False
    assert response["data"]["registration_approval"] is True
    assert response["data"]["privacy_policy_url"] == "https://example.com/privacy"
    assert response["data"]["terms_url"] == "https://example.com/terms"
    assert response["data"]["user_registration_captcha_enabled"] is False


@pytest.mark.asyncio
async def test_tenant_legal_documents_read_registration_group(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant = SimpleNamespace(code="acme", id=1, name="Acme")
    request = SimpleNamespace(url=SimpleNamespace(scheme="https"))

    monkeypatch.setattr(
        "app.api.public.tenant.get_tenant_context",
        lambda _request: SimpleNamespace(is_resolved=True, tenant=tenant),
    )
    monkeypatch.setattr(
        "app.api.public.tenant.ConfigService",
        lambda _db: _FakeTenantConfigService(
            {
                "tenant_registration": {
                    "user_privacy_policy_html": "<p>privacy</p>",
                    "user_terms_html": "<p>terms</p>",
                }
            }
        ),
    )

    privacy = await get_tenant_legal_privacy(request, object())
    terms = await get_tenant_legal_terms(request, object())

    assert privacy["data"]["html"] == "<p>privacy</p>"
    assert terms["data"]["html"] == "<p>terms</p>"
