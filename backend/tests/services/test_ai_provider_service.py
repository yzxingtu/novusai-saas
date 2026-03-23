import pytest

from types import SimpleNamespace

from app.exceptions import ValidationException
from app.services.ai.provider_service import AIProviderService


def test_validate_provider_payload_rejects_openai_endpoint_style_url() -> None:
    with pytest.raises(ValidationException):
        AIProviderService._validate_provider_payload(
            {
                "type": "openai_compatible",
                "base_url": "https://code.respyun.com/v1/responses",
                "config": {"wire_api": "responses"},
            }
        )


def test_validate_provider_payload_keeps_custom_provider_endpoint_untouched() -> None:
    payload = {
        "type": "custom",
        "base_url": "https://plugins.example.com/responses",
    }

    assert AIProviderService._validate_provider_payload(payload) == payload


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

    assert AIProviderService._validate_provider_payload(payload) == {
        "type": "openai_compatible",
        "base_url": None,
    }


def test_validate_provider_payload_uses_existing_provider_type_for_updates() -> None:
    with pytest.raises(ValidationException):
        AIProviderService._validate_provider_payload(
            {
                "base_url": "https://code.respyun.com/v1/chat/completions",
            },
            existing_provider=SimpleNamespace(type="openai_compatible"),
        )
