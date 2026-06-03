"""Tests for plugin config crypto helpers."""

from __future__ import annotations

from app.plugins.crypto import (
    decrypt_plugin_config,
    encrypt_plugin_config,
    mask_plugin_config,
)


def test_plugin_crypto_supports_nested_object_fields() -> None:
    schema = {
        "type": "object",
        "properties": {
            "providers": {
                "type": "object",
                "properties": {
                    "tencent-cos": {
                        "type": "object",
                        "properties": {
                            "secret_id": {"type": "string", "x-encrypted": True},
                            "secret_key": {"type": "string", "x-encrypted": True},
                            "region": {"type": "string"},
                        },
                    }
                },
            }
        },
    }
    config = {
        "providers": {
            "tencent-cos": {
                "secret_id": "abc123456",
                "secret_key": "xyz654321",
                "region": "ap-shanghai",
            }
        }
    }

    encrypted = encrypt_plugin_config(config, schema)
    nested = encrypted["providers"]["tencent-cos"]
    assert nested["secret_id"] != "abc123456"
    assert nested["secret_key"] != "xyz654321"
    assert nested["region"] == "ap-shanghai"

    decrypted = decrypt_plugin_config(encrypted, schema)
    assert decrypted == config

    masked = mask_plugin_config(decrypted, schema)
    assert masked["providers"]["tencent-cos"]["secret_id"].startswith("abc")
    assert "***" in masked["providers"]["tencent-cos"]["secret_key"]
    assert masked["providers"]["tencent-cos"]["region"] == "ap-shanghai"
