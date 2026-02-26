"""插件 License 验签策略（DEBUG/生产）回归测试。"""

from __future__ import annotations

import base64
import json


def _build_license_key(plugin_name: str) -> str:
    payload = {
        "plugin": plugin_name,
        "scope": "*",
        "buyer": "tester@example.com",
        "issued_at": 1700000000,
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("ascii")
    return f"NOVUS-{payload_b64}.signature-placeholder"


def test_verify_license_key_without_public_key_fails_in_production(monkeypatch) -> None:
    from app.plugins.license import verify_license_key

    monkeypatch.delenv("NOVUSAI_LICENSE_PUBLIC_KEY", raising=False)
    monkeypatch.setattr("app.core.config.settings.DEBUG", False, raising=False)

    key = _build_license_key("demo-plugin")
    assert verify_license_key(key, "demo-plugin") is None


def test_verify_license_key_without_public_key_allows_debug_fallback(monkeypatch) -> None:
    from app.plugins.license import verify_license_key

    monkeypatch.delenv("NOVUSAI_LICENSE_PUBLIC_KEY", raising=False)
    monkeypatch.setattr("app.core.config.settings.DEBUG", True, raising=False)

    key = _build_license_key("demo-plugin")
    parsed = verify_license_key(key, "demo-plugin")

    assert parsed is not None
    assert parsed.get("plugin") == "demo-plugin"
