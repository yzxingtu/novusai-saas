"""
Test type: behavioral
Scope: AI provider payload validation and response projection.
Mocked dependencies: service dependencies use local fakes where needed; validation
logic executes real code.
"""

from types import SimpleNamespace

import pytest

from app.exceptions import ValidationException
from app.schemas.ai.provider import (
    AIProviderCreate,
    AIProviderResponse,
    AIProviderUpdate,
)
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


def test_validate_provider_payload_fills_web_search_defaults() -> None:
    payload = {
        "type": "openai_compatible",
        "config": {
            "web_search": {
                "enabled": True,
            }
        },
    }

    validated = AIProviderService._validate_provider_payload(payload)
    web_search = (validated.get("config") or {}).get("web_search") or {}

    assert web_search.get("enabled") is True
    assert web_search.get("max_results_cap") == 8
    assert web_search.get("native_timeout_seconds") == 20
    assert web_search.get("fallback_provider") == "baidu"
    assert web_search.get("fallback_timeout_seconds") == 15
    assert "strategy" not in web_search
    assert "public_timeout_seconds" not in web_search
    assert "public_providers" not in web_search
    assert "prefer_hosted_tool" not in web_search


def test_validate_provider_payload_strips_legacy_public_provider_list() -> None:
    payload = {
        "type": "openai_compatible",
        "config": {
            "web_search": {
                "enabled": True,
                "public_timeout_seconds": 12,
                "public_providers": ["baidu", "legacy_public"],
            }
        },
    }

    validated = AIProviderService._validate_provider_payload(payload)
    web_search = (validated.get("config") or {}).get("web_search") or {}

    assert web_search.get("fallback_provider") == "baidu"
    assert web_search.get("fallback_timeout_seconds") == 15
    assert "public_timeout_seconds" not in web_search
    assert "public_providers" not in web_search


def test_validate_provider_payload_drops_legacy_non_baidu_public_provider_list() -> None:
    validated = AIProviderService._validate_provider_payload(
        {
            "type": "openai_compatible",
            "config": {
                "web_search": {
                    "enabled": True,
                    "public_providers": ["legacy_public"],
                }
            },
        }
    )

    web_search = (validated.get("config") or {}).get("web_search") or {}

    assert web_search.get("fallback_provider") == "baidu"
    assert "public_providers" not in web_search


def test_validate_provider_payload_strips_legacy_advanced_web_search_fields() -> None:
    payload = {
        "type": "openai_compatible",
        "config": {
            "web_search": {
                "enabled": True,
                "prefer_hosted_tool": True,
                "allow_unverified_runtime_target": True,
                "verified_native_target": {
                    "provider_code": "openai",
                    "model_code": "gpt-5.4",
                },
            }
        },
    }

    validated = AIProviderService._validate_provider_payload(payload)
    web_search = (validated.get("config") or {}).get("web_search") or {}

    assert "prefer_hosted_tool" not in web_search
    assert "allow_unverified_runtime_target" not in web_search
    assert "verified_native_target" not in web_search


def test_validate_provider_payload_drops_legacy_web_search_strategy() -> None:
    validated = AIProviderService._validate_provider_payload(
        {
            "type": "openai_compatible",
            "config": {
                "web_search": {
                    "enabled": True,
                    "strategy": "always_native_no_fallback",
                }
            },
        }
    )

    web_search = (validated.get("config") or {}).get("web_search") or {}

    assert web_search.get("fallback_provider") == "baidu"
    assert "strategy" not in web_search


def test_validate_provider_payload_rejects_invalid_web_search_timeout() -> None:
    with pytest.raises(ValidationException):
        AIProviderService._validate_provider_payload(
            {
                "type": "openai_compatible",
                "config": {
                    "web_search": {
                        "enabled": True,
                        "native_timeout_seconds": 0,
                    }
                },
            }
        )


def test_validate_provider_payload_rejects_invalid_web_search_result_cap() -> None:
    with pytest.raises(ValidationException):
        AIProviderService._validate_provider_payload(
            {
                "type": "openai_compatible",
                "config": {
                    "web_search": {
                        "enabled": True,
                        "max_results_cap": 99,
                    }
                },
            }
        )


def test_build_web_search_runtime_summary_marks_native_ready_for_openai_compatible_responses() -> None:
    runtime = AIProviderService.build_web_search_runtime_summary(
        SimpleNamespace(
            type="openai_compatible",
            config={
                "wire_api": "responses",
                "web_search": {
                    "enabled": True,
                    "public_providers": ["baidu", "legacy_public"],
                },
            },
        )
    )

    assert runtime.native_supported is True
    assert runtime.native_provider == "openai_compatible"
    assert runtime.reason.startswith("native_ready:")
    assert "Baidu fallback" in runtime.reason


def test_build_web_search_runtime_summary_marks_native_denied_when_wire_api_is_not_responses() -> None:
    runtime = AIProviderService.build_web_search_runtime_summary(
        SimpleNamespace(
            type="openai_compatible",
            config={
                "wire_api": "chat_completions",
                "web_search": {
                    "enabled": True,
                },
            },
        )
    )

    assert runtime.native_supported is False
    assert runtime.native_provider == "openai_compatible"
    assert runtime.reason.startswith("native_denied:")
    assert "wire_api=responses" in runtime.reason


def test_provider_response_schema_declares_web_search_runtime_read_only_field() -> None:
    # runtime capability summary must be returned by response only, not accepted in create/update payloads
    assert "web_search_runtime" in AIProviderResponse.model_fields
    assert "web_search_runtime" not in AIProviderCreate.model_fields
    assert "web_search_runtime" not in AIProviderUpdate.model_fields
