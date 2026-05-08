"""
Test type: behavioral
Scope: AI provider payload validation and response projection.
Mocked dependencies: service dependencies use local fakes where needed; validation
logic executes real code.
"""

from types import SimpleNamespace

import pytest

from app.exceptions import ValidationException
from app.services.ai.provider_service import AIProviderService


def test_validate_provider_payload_rejects_openai_endpoint_style_url() -> None:
    with pytest.raises(ValidationException):
        AIProviderService._validate_provider_payload(
            {
                "type": "openai_compatible",
                "base_url": "https://code.respyun.com/v1/responses",
                "config": {
                    "protocol_capabilities": {
                        "primary_wire_api": "responses",
                        "allowed_wire_apis": ["responses"],
                    }
                },
            }
        )


@pytest.mark.parametrize(
    "retired_field, value",
    [
        ("wire_api", "responses"),
        ("allow_adapter_cross_protocol_fallback", False),
        ("allowed_cross_protocol_fallbacks", {}),
    ],
)
def test_validate_provider_payload_rejects_top_level_retired_protocol_fields(
    retired_field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationException):
        AIProviderService._validate_provider_payload(
            {
                "type": "openai_compatible",
                "base_url": "https://code.respyun.com/v1",
                "config": {retired_field: value},
            }
        )


@pytest.mark.parametrize(
    "retired_field, value",
    [
        ("wire_api", "responses"),
        ("allow_adapter_cross_protocol_fallback", False),
        ("allowed_cross_protocol_fallbacks", {}),
    ],
)
def test_validate_provider_payload_rejects_nested_retired_protocol_fields(
    retired_field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationException):
        AIProviderService._validate_provider_payload(
            {
                "type": "openai_compatible",
                "base_url": "https://code.respyun.com/v1",
                "config": {
                    "protocol_capabilities": {
                        "primary_wire_api": "responses",
                        "allowed_wire_apis": ["responses"],
                        retired_field: value,
                    },
                },
            }
        )


def test_validate_provider_payload_rejects_deep_retired_protocol_fields() -> None:
    with pytest.raises(ValidationException):
        AIProviderService._validate_provider_payload(
            {
                "type": "openai_compatible",
                "base_url": "https://code.respyun.com/v1",
                "config": {
                    "profiles": [
                        {
                            "name": "legacy",
                            "transport": {"wire_api": "responses"},
                        }
                    ]
                },
            }
        )


def test_validate_provider_payload_keeps_custom_provider_endpoint_untouched() -> None:
    payload = {
        "type": "custom",
        "base_url": "https://plugins.example.com/responses",
    }

    validated = AIProviderService._validate_provider_payload(payload)
    assert validated["type"] == "custom"
    assert validated["base_url"] == "https://plugins.example.com/responses"


def test_validate_provider_payload_rejects_invalid_base_url() -> None:
    with pytest.raises(ValidationException):
        AIProviderService._validate_provider_payload(
            {
                "type": "openai_compatible",
                "base_url": "ftp://api.example.com/v1",
            }
        )


def test_validate_provider_payload_normalizes_blank_base_url_to_null() -> None:
    payload = {
        "type": "openai_compatible",
        "base_url": "   ",
    }

    validated = AIProviderService._validate_provider_payload(payload)
    assert validated["type"] == "openai_compatible"
    assert validated["base_url"] is None


def test_validate_provider_payload_uses_existing_provider_type_for_updates() -> None:
    with pytest.raises(ValidationException):
        AIProviderService._validate_provider_payload(
            {
                "base_url": "https://code.respyun.com/v1/chat/completions",
            },
            existing_provider=SimpleNamespace(type="openai_compatible"),
        )
