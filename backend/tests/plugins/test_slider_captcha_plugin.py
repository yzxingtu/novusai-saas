from __future__ import annotations

import pytest

from app.api.shared._captcha_helpers import inject_captcha_provider_options
from app.captcha.provider import CaptchaProviderMetadata
from app.captcha.registry import registry as captcha_registry
from app.plugins.module_loader import load_plugin_handler


@pytest.mark.asyncio
async def test_slider_captcha_provider_roundtrip() -> None:
    provider_cls = load_plugin_handler(
        "slider-captcha",
        "captcha_provider.SliderCaptchaProvider",
    )
    assert provider_cls is not None

    provider = provider_cls() if isinstance(provider_cls, type) else provider_cls
    challenge = await provider.generate_challenge({
        "plugin_config": {
            "background_1": "11",
            "background_2": "12",
            "background_3": "13",
            "background_4": "14",
            "square_length": 40,
            "tolerance_px": 5,
        },
    })

    assert challenge.type == "slider"
    assert challenge.payload["background_url"].startswith("/api/public/attachments/")
    assert challenge.payload["square_length"] == 40
    assert challenge.payload["tolerance_px"] == 5

    result = await provider.verify(
        challenge.challenge_id,
        str(challenge.payload["piece_x"]),
        {},
    )
    assert result.ok is True


def test_inject_captcha_provider_options_filters_by_endpoint() -> None:
    provider_code = "slider-test-provider"
    captcha_registry.register(
        provider_code,
        captcha_registry.get_default(),
        metadata=CaptchaProviderMetadata(
            display_name={"en": "Slider Test", "zh-CN": "滑块测试"},
            public_endpoints=["admin", "tenant", "user"],
        ),
    )

    try:
        configs = [{
            "key": "tenant_captcha_provider",
            "options": [{"value": "image", "label_key": "config.tenant.captcha_provider.image"}],
            "value": "image",
            "value_type": "select",
        }]

        inject_captcha_provider_options(
            configs,
            required_endpoints={"tenant", "user"},
            unavailable_label_key="config.tenant.captcha_provider.unavailable_option",
        )

        option_values = [opt["value"] for opt in configs[0]["options"]]
        assert option_values == ["image", provider_code]
    finally:
        captcha_registry.unregister(provider_code)
