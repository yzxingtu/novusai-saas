"""Test type: behavioral.

Scope: plain input selected-text AI policy aggregation.
Mocked dependencies: config, preference, and account AI profile services.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest

from app.configs.service import PLATFORM_TENANT_ID
from app.exceptions import AuthorizationException
from app.services.ai.plain_text_input_ai_policy_service import (
    PLATFORM_ADMIN_ENABLED_KEY,
    PLATFORM_ALLOW_TENANT_ENABLE_KEY,
    PLATFORM_TENANT_DEFAULT_ENABLED_KEY,
    TENANT_ENABLED_KEY,
    PlainTextInputAiPolicyService,
    is_plain_text_input_surface,
)
from app.services.common.user_preference_service import (
    SCOPE_ADMIN,
    SCOPE_TENANT_ADMIN,
)


def _service(
    *,
    account_profile: dict,
    config_service: AsyncMock | None = None,
    preference_value: bool = True,
) -> PlainTextInputAiPolicyService:
    service = PlainTextInputAiPolicyService.__new__(PlainTextInputAiPolicyService)
    service._config_service = config_service or AsyncMock()
    service._preference_service = AsyncMock()
    service._account_access_service = AsyncMock()
    service._preference_service.get_effective = AsyncMock(
        return_value={"plain_text_input_ai_enabled": preference_value}
    )
    service._account_access_service.get_platform_admin_ai_availability_profile = (
        AsyncMock(return_value=account_profile)
    )
    service._account_access_service.get_tenant_admin_ai_availability_profile = (
        AsyncMock(return_value=account_profile)
    )
    return service


def test_plain_text_input_surface_detection_fails_closed_on_conflict() -> None:
    assert is_plain_text_input_surface("plain_text_input", "novusdoc") is True
    assert is_plain_text_input_surface("rich_text_editor", "plain_text_input") is True
    assert is_plain_text_input_surface("", "plain_text_input") is True
    assert is_plain_text_input_surface("rich_text_editor", "novusdoc") is False


@pytest.mark.asyncio
async def test_admin_policy_requires_account_platform_and_personal_enabled() -> None:
    config_service = AsyncMock()
    config_service.get_platform_config = AsyncMock(
        side_effect=[
            False,
            True,
            True,
        ]
    )
    service = _service(
        account_profile={
            "ai_unavailable_reason": None,
            "effective_ai_enabled": True,
        },
        config_service=config_service,
        preference_value=True,
    )

    policy = await service.get_admin_policy(SimpleNamespace(id=12))

    assert policy["enabled"] is False
    assert policy["account_ai_enabled"] is True
    assert policy["platform_admin_enabled"] is False
    assert policy["personal_enabled"] is True
    assert config_service.get_platform_config.await_args_list == [
        call(PLATFORM_ADMIN_ENABLED_KEY, default=True),
        call(PLATFORM_ALLOW_TENANT_ENABLE_KEY, default=True),
        call(PLATFORM_TENANT_DEFAULT_ENABLED_KEY, default=True),
    ]
    service._preference_service.get_effective.assert_awaited_once_with(
        scope=SCOPE_ADMIN,
        tenant_id=PLATFORM_TENANT_ID,
        user_id=12,
    )


@pytest.mark.asyncio
async def test_admin_policy_fails_closed_when_account_profile_key_is_missing() -> None:
    config_service = AsyncMock()
    config_service.get_platform_config = AsyncMock(return_value=True)
    service = _service(
        account_profile={"ai_unavailable_reason": None},
        config_service=config_service,
        preference_value=True,
    )

    policy = await service.get_admin_policy(SimpleNamespace(id=12))

    assert policy["enabled"] is False
    assert policy["account_ai_enabled"] is False


@pytest.mark.asyncio
async def test_require_admin_enabled_raises_with_policy_payload_when_disabled() -> None:
    config_service = AsyncMock()
    config_service.get_platform_config = AsyncMock(
        side_effect=[
            True,
            True,
            True,
        ]
    )
    service = _service(
        account_profile={
            "ai_unavailable_reason": "account_ai_disabled",
            "effective_ai_enabled": False,
        },
        config_service=config_service,
        preference_value=True,
    )

    with pytest.raises(AuthorizationException) as exc_info:
        await service.require_admin_enabled(SimpleNamespace(id=12))

    assert exc_info.value.status_code == 403
    assert exc_info.value.extra["feature"] == "plain_text_input_ai"
    assert exc_info.value.extra["reason"] == "plain_text_input_ai_disabled"
    assert exc_info.value.extra["policy"]["account_ai_enabled"] is False


@pytest.mark.asyncio
async def test_require_admin_enabled_rejects_missing_plain_input_field_policy() -> None:
    config_service = AsyncMock()
    config_service.get_platform_config = AsyncMock(return_value=True)
    service = _service(
        account_profile={
            "ai_unavailable_reason": None,
            "effective_ai_enabled": True,
        },
        config_service=config_service,
        preference_value=True,
    )

    with pytest.raises(AuthorizationException) as exc_info:
        await service.require_admin_enabled(
            SimpleNamespace(id=12),
            action="rewrite",
            field_policy=None,
        )

    assert exc_info.value.extra["policy"]["field_policy"] == {
        "action": "rewrite",
        "allowed_actions": [],
        "enabled": None,
        "field_kind": None,
    }


@pytest.mark.asyncio
async def test_require_admin_enabled_rejects_field_policy_action_not_allowed() -> None:
    config_service = AsyncMock()
    config_service.get_platform_config = AsyncMock(return_value=True)
    service = _service(
        account_profile={
            "ai_unavailable_reason": None,
            "effective_ai_enabled": True,
        },
        config_service=config_service,
        preference_value=True,
    )

    with pytest.raises(AuthorizationException) as exc_info:
        await service.require_admin_enabled(
            SimpleNamespace(id=12),
            action="format",
            field_policy={
                "allowed_actions": ["proofread", "rewrite"],
                "enabled": True,
                "field_kind": "plain",
            },
        )

    assert exc_info.value.extra["policy"]["field_policy"] == {
        "action": "format",
        "allowed_actions": ["proofread", "rewrite"],
        "enabled": True,
        "field_kind": "plain",
    }


@pytest.mark.asyncio
async def test_require_admin_enabled_rejects_disabled_field_kind() -> None:
    config_service = AsyncMock()
    config_service.get_platform_config = AsyncMock(return_value=True)
    service = _service(
        account_profile={
            "ai_unavailable_reason": None,
            "effective_ai_enabled": True,
        },
        config_service=config_service,
        preference_value=True,
    )

    with pytest.raises(AuthorizationException) as exc_info:
        await service.require_admin_enabled(
            SimpleNamespace(id=12),
            action="rewrite",
            field_policy={
                "allowed_actions": ["rewrite"],
                "enabled": True,
                "field_kind": "secret",
            },
        )

    assert exc_info.value.extra["policy"]["field_policy"]["field_kind"] == "secret"


@pytest.mark.asyncio
async def test_require_admin_enabled_accepts_allowed_plain_input_action() -> None:
    config_service = AsyncMock()
    config_service.get_platform_config = AsyncMock(return_value=True)
    service = _service(
        account_profile={
            "ai_unavailable_reason": None,
            "effective_ai_enabled": True,
        },
        config_service=config_service,
        preference_value=True,
    )

    await service.require_admin_enabled(
        SimpleNamespace(id=12),
        action="rewrite",
        field_policy={
            "allowed_actions": ["proofread", "rewrite"],
            "enabled": True,
            "field_kind": "title",
        },
    )


@pytest.mark.asyncio
async def test_tenant_policy_uses_platform_default_when_tenant_has_no_override() -> (
    None
):
    config_service = AsyncMock()
    config_service.get_platform_config = AsyncMock(
        side_effect=[
            True,
            False,
        ]
    )
    config_service.get_tenant_config_override = AsyncMock(return_value=None)
    service = _service(
        account_profile={
            "ai_unavailable_reason": None,
            "effective_ai_enabled": True,
        },
        config_service=config_service,
        preference_value=True,
    )

    policy = await service.get_tenant_policy(SimpleNamespace(id=8, tenant_id=5))

    assert policy["enabled"] is False
    assert policy["platform_allow_tenant_enable"] is True
    assert policy["platform_tenant_default_enabled"] is False
    assert policy["tenant_enabled"] is False
    config_service.get_tenant_config_override.assert_awaited_once_with(
        5,
        TENANT_ENABLED_KEY,
    )


@pytest.mark.asyncio
async def test_tenant_policy_requires_platform_allow_tenant_personal_and_account() -> (
    None
):
    config_service = AsyncMock()
    config_service.get_platform_config = AsyncMock(
        side_effect=[
            False,
            True,
        ]
    )
    config_service.get_tenant_config_override = AsyncMock(return_value=True)
    service = _service(
        account_profile={
            "ai_unavailable_reason": None,
            "effective_ai_enabled": True,
        },
        config_service=config_service,
        preference_value=True,
    )

    policy = await service.get_tenant_policy(SimpleNamespace(id=8, tenant_id=5))

    assert policy["enabled"] is False
    assert policy["platform_allow_tenant_enable"] is False
    assert policy["tenant_enabled"] is True
    assert policy["personal_enabled"] is True
    service._preference_service.get_effective.assert_awaited_once_with(
        scope=SCOPE_TENANT_ADMIN,
        tenant_id=5,
        user_id=8,
    )
