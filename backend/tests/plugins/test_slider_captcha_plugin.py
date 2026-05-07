from __future__ import annotations

from typing import Any

import pytest
from PIL import Image

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
    stored_challenges: dict[str, dict[str, Any]] = {}

    async def _store_challenge(challenge_id: str, data: dict[str, Any]) -> None:
        stored_challenges[challenge_id] = dict(data)

    async def _load_stored_challenge(challenge_id: str) -> dict[str, Any] | None:
        data = stored_challenges.get(challenge_id)
        return dict(data) if data is not None else None

    async def _delete_stored_challenge(challenge_id: str) -> None:
        stored_challenges.pop(challenge_id, None)

    async def _load_background_image(_plugin_config: dict[str, Any]) -> Image.Image:
        return Image.new("RGB", (320, 180), color=(96, 144, 192))

    provider._store_challenge = _store_challenge  # type: ignore[method-assign]
    provider._load_stored_challenge = _load_stored_challenge  # type: ignore[method-assign]
    provider._delete_stored_challenge = _delete_stored_challenge  # type: ignore[method-assign]
    provider._load_background_image = _load_background_image  # type: ignore[method-assign]

    challenge = await provider.generate_challenge(
        {
            "plugin_config": {
                "background_1": "11",
                "background_2": "12",
                "background_3": "13",
                "background_4": "14",
                "square_length": 40,
                "tolerance_px": 5,
            },
        }
    )

    assert challenge.type == "slider"
    assert str(challenge.payload["board_image"]).startswith("data:image/png;base64,")
    assert str(challenge.payload["piece_image"]).startswith("data:image/png;base64,")
    assert challenge.payload["piece_geometry"]["square_length"] == 40
    assert challenge.payload["tolerance_px"] == 5

    result = await provider.verify(
        challenge.challenge_id,
        str(challenge.payload["piece_capture_left"]),
        {},
    )
    assert result.ok is True


def test_inject_captcha_provider_options_filters_by_endpoint() -> None:
    provider_code = "slider-test-provider"
    existing_providers = [
        (
            code,
            captcha_registry.get(code),
            captcha_registry.get_metadata(code),
        )
        for code, _metadata in captcha_registry.items()
        if code != "image"
    ]

    for code, _provider, _metadata in existing_providers:
        captcha_registry.unregister(code)

    captcha_registry.register(
        provider_code,
        captcha_registry.get_default(),
        metadata=CaptchaProviderMetadata(
            display_name={"en": "Slider Test", "zh-CN": "滑块测试"},
            public_endpoints=["admin", "tenant", "user"],
        ),
    )

    try:
        configs = [
            {
                "key": "tenant_captcha_provider",
                "options": [
                    {
                        "value": "image",
                        "label_key": "config.tenant.captcha_provider.image",
                    }
                ],
                "value": "image",
                "value_type": "select",
            }
        ]

        inject_captcha_provider_options(
            configs,
            required_endpoints={"tenant", "user"},
            unavailable_label_key="config.tenant.captcha_provider.unavailable_option",
        )

        option_values = [opt["value"] for opt in configs[0]["options"]]
        assert option_values == ["image", provider_code]
    finally:
        captcha_registry.unregister(provider_code)
        for code, provider, metadata in existing_providers:
            if provider is None:
                continue
            captcha_registry.register(code, provider, metadata=metadata)
