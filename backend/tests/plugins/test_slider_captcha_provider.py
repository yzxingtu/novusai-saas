from __future__ import annotations

import asyncio
import sys
from types import ModuleType
from typing import Any

from PIL import Image

from app.plugins.module_loader import load_plugin_handler


def _load_provider_module() -> ModuleType:
    provider_cls = load_plugin_handler(
        "slider-captcha",
        "captcha_provider.SliderCaptchaProvider",
    )
    if not isinstance(provider_cls, type):
        raise AssertionError("SliderCaptchaProvider handler did not resolve to a class")
    return sys.modules[provider_cls.__module__]


def _patch_provider_dependencies(
    monkeypatch: Any,
    provider_module: ModuleType,
    *,
    background_color: tuple[int, int, int],
) -> dict[str, Any]:
    store: dict[str, Any] = {}

    async def fake_cache_get(key: str):
        return store.get(key)

    async def fake_cache_set(key: str, value: Any, ttl: int | None = None):
        _ = ttl
        store[key] = value
        return True

    async def fake_cache_delete(key: str):
        store.pop(key, None)
        return 1

    async def fake_background(_self, _config: dict[str, Any]):
        return Image.new("RGB", (320, 180), color=background_color)

    monkeypatch.setattr(provider_module, "cache_get", fake_cache_get)
    monkeypatch.setattr(provider_module, "cache_set", fake_cache_set)
    monkeypatch.setattr(provider_module, "cache_delete", fake_cache_delete)
    monkeypatch.setattr(
        provider_module.SliderCaptchaProvider,
        "_load_background_image",
        fake_background,
    )
    return store


def test_generate_challenge_includes_vector_geometry_for_client_render(monkeypatch):
    provider_module = _load_provider_module()
    store = _patch_provider_dependencies(
        monkeypatch,
        provider_module,
        background_color=(120, 160, 210),
    )
    provider = provider_module.SliderCaptchaProvider()

    async def scenario():
        challenge = await provider.generate_challenge(
            {
                "action": "login",
                "difficulty": "medium",
                "endpoint": "admin",
                "ip": "127.0.0.1",
            }
        )
        assert "piece_x" not in challenge.payload
        assert "board_image" in challenge.payload
        assert "piece_image" in challenge.payload
        assert "piece_geometry" in challenge.payload
        assert "piece_capture_left" in challenge.payload
        geom = challenge.payload["piece_geometry"]
        assert {"circle_radius", "origin_x", "origin_y", "square_length"} <= set(
            geom.keys()
        )

        stored = store[
            provider_module._CHALLENGE_KEY_PREFIX + f":{challenge.challenge_id}"
        ]
        ok = await provider.verify(
            challenge.challenge_id,
            str(stored["expected_offset"]),
            {"action": "login", "endpoint": "admin", "ip": "127.0.0.1"},
        )
        assert ok.ok is True

    asyncio.run(scenario())


def test_verify_rejects_context_mismatch(monkeypatch):
    provider_module = _load_provider_module()
    store = _patch_provider_dependencies(
        monkeypatch,
        provider_module,
        background_color=(80, 110, 160),
    )
    provider = provider_module.SliderCaptchaProvider()

    async def scenario():
        challenge = await provider.generate_challenge(
            {
                "action": "login",
                "difficulty": "medium",
                "endpoint": "admin",
                "ip": "127.0.0.1",
            }
        )
        stored = store[
            provider_module._CHALLENGE_KEY_PREFIX + f":{challenge.challenge_id}"
        ]
        result = await provider.verify(
            challenge.challenge_id,
            str(stored["expected_offset"]),
            {"action": "register", "endpoint": "admin", "ip": "127.0.0.1"},
        )
        assert result.ok is False
        assert result.reason == "invalid_context"

    asyncio.run(scenario())


def test_verify_exhausts_attempts_on_mismatch(monkeypatch):
    provider_module = _load_provider_module()
    store = _patch_provider_dependencies(
        monkeypatch,
        provider_module,
        background_color=(150, 120, 90),
    )
    provider = provider_module.SliderCaptchaProvider()

    async def scenario():
        challenge = await provider.generate_challenge(
            {
                "action": "login",
                "difficulty": "medium",
                "endpoint": "admin",
                "ip": "127.0.0.1",
            }
        )
        challenge_key = provider_module._CHALLENGE_KEY_PREFIX + (
            f":{challenge.challenge_id}"
        )
        for _ in range(provider_module._MAX_VERIFY_ATTEMPTS):
            result = await provider.verify(
                challenge.challenge_id,
                "0",
                {"action": "login", "endpoint": "admin", "ip": "127.0.0.1"},
            )
            assert result.ok is False

        assert challenge_key not in store

    asyncio.run(scenario())
