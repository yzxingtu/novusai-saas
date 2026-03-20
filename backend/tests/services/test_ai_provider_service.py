import pytest

from app.exceptions import ValidationException
from app.services.ai.provider_service import AIProviderService


def test_normalize_connection_settings_infers_responses_wire_api():
    base_url, config, config_changed = AIProviderService._normalize_connection_settings(
        provider_type='openai_compatible',
        base_url='https://code.respyun.com/v1/responses',
        config=None,
    )

    assert base_url == 'https://code.respyun.com/v1'
    assert config == {'wire_api': 'responses'}
    assert config_changed is True


def test_normalize_connection_settings_infers_chat_completions_wire_api():
    base_url, config, config_changed = AIProviderService._normalize_connection_settings(
        provider_type='openai_compatible',
        base_url='https://api.example.com/v1/chat/completions',
        config={'timeout': 30},
    )

    assert base_url == 'https://api.example.com/v1'
    assert config == {'timeout': 30, 'wire_api': 'chat_completions'}
    assert config_changed is True


def test_normalize_connection_settings_rejects_invalid_base_url():
    with pytest.raises(ValidationException):
        AIProviderService._normalize_connection_settings(
            provider_type='openai_compatible',
            base_url='ftp://api.example.com/v1',
            config=None,
        )


def test_normalize_connection_settings_keeps_custom_provider_endpoint_untouched():
    base_url, config, config_changed = AIProviderService._normalize_connection_settings(
        provider_type='custom',
        base_url='https://plugins.example.com/responses',
        config=None,
    )

    assert base_url == 'https://plugins.example.com/responses'
    assert config is None
    assert config_changed is False
