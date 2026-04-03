"""
Plugin sensitive config encryption/decryption/masking / 插件敏感配置加密/解密/脱敏

Based on x-encrypted markers in plugin.yaml config_schema,
automatically performs Fernet encryption for storage, runtime decryption, and API response masking.
/
基于 plugin.yaml 中 config_schema 的 x-encrypted 标记，
自动对标记字段进行 Fernet 加密存储、运行时解密、API 响应脱敏。

Reuses existing app.core.security.encrypt_data / decrypt_data.
/ 复用已有的 app.core.security.encrypt_data / decrypt_data。
"""

from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger(__name__)

_FERNET_PREFIX = "gAAAAA"


def _walk_schema_value(
    value,
    schema: dict,
    *,
    transform,
):
    """Recursively walk config data with JSON Schema metadata.

    Supports nested object properties and arrays while preserving unknown keys.
    """
    if not isinstance(schema, dict):
        return value

    if schema.get("x-encrypted"):
        return transform(value)

    schema_type = str(schema.get("type") or "").strip().lower()
    if schema_type == "object" and isinstance(value, dict):
        result = dict(value)
        properties = schema.get("properties") or {}
        for name, prop_schema in properties.items():
            if name not in result:
                continue
            result[name] = _walk_schema_value(
                result[name],
                prop_schema if isinstance(prop_schema, dict) else {},
                transform=transform,
            )
        return result

    if schema_type == "array" and isinstance(value, list):
        item_schema = schema.get("items") or {}
        if not isinstance(item_schema, dict):
            return list(value)
        return [
            _walk_schema_value(item, item_schema, transform=transform) for item in value
        ]

    return value


def encrypt_plugin_config(config: dict, schema: dict) -> dict:
    """
    Pre-save encryption: encrypt field values marked with x-encrypted.
    / 保存前加密：将标记 x-encrypted 的字段值加密。

    Already encrypted values (starting with gAAAAA) won't be re-encrypted.
    / 已加密的值（以 gAAAAA 开头）不会重复加密。
    """
    from app.core.security import encrypt_data

    def _encrypt_leaf(val):
        if val and isinstance(val, str) and not val.startswith(_FERNET_PREFIX):
            try:
                return encrypt_data(val)
            except Exception as exc:
                logger.warning("Failed to encrypt config field: {}", exc)
        return val

    return _walk_schema_value(dict(config), schema, transform=_encrypt_leaf)


def decrypt_plugin_config(config: dict, schema: dict) -> dict:
    """
    Runtime decryption: decrypt field values marked with x-encrypted to plaintext.
    / 运行时解密：将标记 x-encrypted 的字段值解密为明文。

    Used internally by PluginContext.get_config().
    / 用于 PluginContext.get_config() 内部调用。
    """
    from app.core.security import decrypt_data

    def _decrypt_leaf(val):
        if val and isinstance(val, str) and val.startswith(_FERNET_PREFIX):
            try:
                return decrypt_data(val)
            except Exception as exc:
                logger.warning("Failed to decrypt config field: {}", exc)
                return ""
        return val

    return _walk_schema_value(dict(config), schema, transform=_decrypt_leaf)


def mask_plugin_config(config: dict, schema: dict) -> dict:
    """
    API response masking: display field values marked with x-encrypted as sk-***123 format.
    / API 响应脱敏：将标记 x-encrypted 的字段值显示为 sk-***123 形式。

    Used for response processing when viewing plugin config in admin panel.
    / 用于管理端查看插件配置时的响应处理。
    """

    def _mask_leaf(val):
        if val and isinstance(val, str):
            if len(val) > 6:
                return val[:3] + "***" + val[-3:]
            return "***"
        return val

    return _walk_schema_value(dict(config), schema, transform=_mask_leaf)
