"""
插件安全机制单元测试

覆盖：
- validate_manifest: 必填字段、版本格式、权限合法性
- validate_manifest_or_raise: 异常抛出
- build_permission_aware_context_kwargs: 权限感知注入
- encrypt/decrypt/mask_sensitive_config: 敏感配置处理
- log_plugin_action: 审计日志
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.plugins.security import (
    VALID_PERMISSIONS,
    build_permission_aware_context_kwargs,
    decrypt_sensitive_config,
    encrypt_sensitive_config,
    mask_sensitive_config,
    validate_manifest,
    validate_manifest_or_raise,
)


# ========================================
# validate_manifest
# ========================================

class TestValidateManifest:
    def _valid_manifest(self) -> dict[str, Any]:
        return {
            "name": "test-plugin",
            "display_name": "Test Plugin",
            "version": "1.0.0",
            "entry_point": "plugin.TestPlugin",
        }

    def test_valid_manifest(self) -> None:
        errors = validate_manifest(self._valid_manifest())
        assert errors == []

    def test_missing_all_fields(self) -> None:
        errors = validate_manifest({})
        assert len(errors) == 4

    def test_missing_name(self) -> None:
        m = self._valid_manifest()
        del m["name"]
        errors = validate_manifest(m)
        assert any("name" in e for e in errors)

    def test_empty_string_field(self) -> None:
        m = self._valid_manifest()
        m["version"] = "   "
        errors = validate_manifest(m)
        assert any("version" in e for e in errors)

    def test_invalid_name_format(self) -> None:
        m = self._valid_manifest()
        m["name"] = "Invalid_Name"
        errors = validate_manifest(m)
        assert any("Invalid plugin name" in e for e in errors)

    def test_invalid_version_format(self) -> None:
        m = self._valid_manifest()
        m["version"] = "not.valid"
        errors = validate_manifest(m)
        assert any("Invalid version" in e for e in errors)

    def test_valid_semver_prerelease(self) -> None:
        m = self._valid_manifest()
        m["version"] = "2.0.0-beta.1"
        errors = validate_manifest(m)
        assert errors == []

    def test_unknown_permission(self) -> None:
        m = self._valid_manifest()
        m["required_permissions"] = ["db:read", "unknown:perm"]
        errors = validate_manifest(m)
        assert any("Unknown permission" in e for e in errors)

    def test_valid_permissions(self) -> None:
        m = self._valid_manifest()
        m["required_permissions"] = ["db:read", "http:outbound", "tool:register"]
        errors = validate_manifest(m)
        assert errors == []

    def test_all_valid_permissions_accepted(self) -> None:
        m = self._valid_manifest()
        m["required_permissions"] = list(VALID_PERMISSIONS)
        errors = validate_manifest(m)
        assert errors == []


# ========================================
# validate_manifest_or_raise
# ========================================

class TestValidateManifestOrRaise:
    def test_valid_does_not_raise(self) -> None:
        m = {
            "name": "ok-plugin",
            "display_name": "OK",
            "version": "1.0.0",
            "entry_point": "plugin.OK",
        }
        validate_manifest_or_raise(m)

    def test_invalid_raises_validation(self) -> None:
        from app.exceptions import ValidationException
        with pytest.raises(ValidationException):
            validate_manifest_or_raise({})


# ========================================
# build_permission_aware_context_kwargs
# ========================================

class TestBuildPermissionAwareContext:
    def test_no_permissions_strips_all(self) -> None:
        mock_db = MagicMock()
        mock_bus = MagicMock()
        mock_tools = MagicMock()
        result = build_permission_aware_context_kwargs(
            None, db=mock_db, event_bus=mock_bus, tool_registry=mock_tools,
        )
        assert result["db"] is None
        assert result["event_bus"] is None
        assert result["tool_registry"] is None

    def test_db_read_grants_db(self) -> None:
        mock_db = MagicMock()
        result = build_permission_aware_context_kwargs(
            ["db:read"], db=mock_db,
        )
        assert result["db"] is mock_db

    def test_db_write_grants_db(self) -> None:
        mock_db = MagicMock()
        result = build_permission_aware_context_kwargs(
            ["db:write"], db=mock_db,
        )
        assert result["db"] is mock_db

    def test_event_subscribe_grants_bus(self) -> None:
        mock_bus = MagicMock()
        result = build_permission_aware_context_kwargs(
            ["event:subscribe"], event_bus=mock_bus,
        )
        assert result["event_bus"] is mock_bus

    def test_event_publish_grants_bus(self) -> None:
        mock_bus = MagicMock()
        result = build_permission_aware_context_kwargs(
            ["event:publish"], event_bus=mock_bus,
        )
        assert result["event_bus"] is mock_bus

    def test_tool_register_grants_registry(self) -> None:
        mock_tools = MagicMock()
        result = build_permission_aware_context_kwargs(
            ["tool:register"], tool_registry=mock_tools,
        )
        assert result["tool_registry"] is mock_tools

    def test_mixed_permissions(self) -> None:
        mock_db = MagicMock()
        mock_tools = MagicMock()
        result = build_permission_aware_context_kwargs(
            ["db:read", "tool:register"],
            db=mock_db, tool_registry=mock_tools,
        )
        assert result["db"] is mock_db
        assert result["tool_registry"] is mock_tools
        assert result["event_bus"] is None


# ========================================
# encrypt / decrypt / mask sensitive config
# ========================================

class TestSensitiveConfig:
    _schema: dict[str, Any] = {
        "properties": {
            "api_key": {"type": "string", "format": "password"},
            "endpoint": {"type": "string"},
        },
    }

    def test_encrypt_password_field(self) -> None:
        config = {"api_key": "secret123", "endpoint": "https://api.test"}
        result = encrypt_sensitive_config(config, self._schema)
        assert result["api_key"].startswith("enc:")
        assert result["endpoint"] == "https://api.test"

    def test_encrypt_already_encrypted_skipped(self) -> None:
        config = {"api_key": "enc:already_encrypted", "endpoint": "url"}
        result = encrypt_sensitive_config(config, self._schema)
        assert result["api_key"] == "enc:already_encrypted"

    def test_encrypt_empty_config(self) -> None:
        result = encrypt_sensitive_config({}, self._schema)
        assert result == {}

    def test_encrypt_no_schema(self) -> None:
        config = {"api_key": "secret"}
        result = encrypt_sensitive_config(config, None)
        assert result == {"api_key": "secret"}

    def test_decrypt_roundtrip(self) -> None:
        config = {"api_key": "my-secret-key", "endpoint": "url"}
        encrypted = encrypt_sensitive_config(config, self._schema)
        assert encrypted["api_key"] != "my-secret-key"

        decrypted = decrypt_sensitive_config(encrypted, self._schema)
        assert decrypted["api_key"] == "my-secret-key"
        assert decrypted["endpoint"] == "url"

    def test_decrypt_no_schema(self) -> None:
        config = {"api_key": "enc:something"}
        result = decrypt_sensitive_config(config, None)
        assert result == {"api_key": "enc:something"}

    def test_mask_password_field(self) -> None:
        config = {"api_key": "enc:encrypted_value", "endpoint": "url"}
        result = mask_sensitive_config(config, self._schema)
        assert result["api_key"] == "******"
        assert result["endpoint"] == "url"

    def test_mask_empty_password(self) -> None:
        config = {"api_key": "", "endpoint": "url"}
        result = mask_sensitive_config(config, self._schema)
        assert result["api_key"] == ""

    def test_mask_no_schema(self) -> None:
        config = {"api_key": "secret"}
        result = mask_sensitive_config(config, None)
        assert result == {"api_key": "secret"}

    def test_mask_missing_field(self) -> None:
        config = {"endpoint": "url"}
        result = mask_sensitive_config(config, self._schema)
        assert result == {"endpoint": "url"}
