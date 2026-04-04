"""Tests for crud_executor column name and table name safety validation. / 测试

Covers:
- _validate_column_names: rejects SQL injection payloads, special chars
- _validate_table_name: rejects unsafe table names
- is_safe_sql_identifier: identifier safety correctness
- _normalize_agent_data: only canonical ResourceScopeEnum values; legacy aliases rejected; invalid scope raises"""

from __future__ import annotations

import pytest

from app.ai.data_intelligence.sql_analysis import is_safe_sql_identifier
from app.ai.tools.executors.crud_executor import (
    _normalize_agent_data,
    _validate_column_names,
    _validate_table_name,
)

# ============================================
# is_safe_sql_identifier tests
# ============================================

class TestSafeSqlIdentifier:
    """Test the column name safety helper directly. / 测试"""

    @pytest.mark.parametrize("name", [
        "name",
        "user_name",
        "id",
        "created_at",
        "a1",
        "_private",
        "tenant_id",
        "is_deleted",
        "x",
        "column_123_test",
    ])
    def test_valid_column_names(self, name: str) -> None:
        assert is_safe_sql_identifier(name) is True

    @pytest.mark.parametrize("name", [
        "Name",              # uppercase
        "userName",          # camelCase
        "user-name",         # hyphen
        "user name",         # space
        "1column",           # starts with digit
        "col;DROP",          # semicolon
        "col'OR'1",          # single quote
        'col"test',          # double quote
        "col()",             # parentheses
        "col--comment",      # SQL comment
        "",                  # empty string
        "col/**/name",       # block comment
        "col\nname",         # newline
        "col\tname",         # tab
        "名前",              # non-ASCII
        "col.name",          # dot
        "col=1",             # equals
        "col,name",          # comma
    ])
    def test_invalid_column_names(self, name: str) -> None:
        assert is_safe_sql_identifier(name) is False


# ============================================
# _validate_column_names tests
# ============================================

class TestValidateColumnNames:
    """Test the _validate_column_names function. / 测试"""

    def test_all_valid_columns(self) -> None:
        data = {"name": "test", "email": "a@b.com", "age": 25}
        result = _validate_column_names(data)
        assert result is None

    def test_empty_data(self) -> None:
        result = _validate_column_names({})
        assert result is None

    def test_single_invalid_column(self) -> None:
        data = {"name": "test", "user-email": "a@b.com"}
        result = _validate_column_names(data)
        assert result is not None
        assert "user-email" in result

    def test_multiple_invalid_columns(self) -> None:
        data = {
            "name": "test",
            "User-Email": "a@b.com",
            "col;DROP TABLE": "x",
        }
        result = _validate_column_names(data)
        assert result is not None
        # Both invalid columns should be mentioned
        assert "User-Email" in result

    def test_sql_injection_payload_column(self) -> None:
        """Simulate LLM passing SQL injection as column name. / 说明"""
        data = {"name; DROP TABLE users--": "malicious"}
        result = _validate_column_names(data)
        assert result is not None

    def test_sql_injection_subquery_column(self) -> None:
        data = {"(SELECT password FROM users LIMIT 1)": "x"}
        result = _validate_column_names(data)
        assert result is not None

    def test_valid_with_underscores_and_numbers(self) -> None:
        data = {"field_1": "a", "field_2": "b", "_hidden": "c"}
        result = _validate_column_names(data)
        assert result is None


# ============================================
# _validate_table_name tests
# ============================================

class TestValidateTableName:
    """Test the _validate_table_name function. / 测试"""

    @pytest.mark.parametrize("name", [
        "users",
        "ai_agents",
        "tenant_plans",
        "_internal",
        "t1",
    ])
    def test_valid_table_names(self, name: str) -> None:
        assert _validate_table_name(name) is None

    @pytest.mark.parametrize("name", [
        "Users",
        "user-table",
        "1table",
        "table;DROP",
        "table' OR '1'='1",
        "",
    ])
    def test_invalid_table_names(self, name: str) -> None:
        result = _validate_table_name(name)
        assert result is not None


# ============================================
# _normalize_agent_data tests (agents service path)
# ============================================

class TestNormalizeAgentData:
    """Test agent data normalization for CRUD executor agents path."""

    @pytest.mark.parametrize("legacy_scope", ["platform", "all", "global"])
    def test_legacy_scope_aliases_raise(self, legacy_scope: str) -> None:
        """Non-canonical scope strings are rejected (strict-zero, no silent mapping)."""
        data = {"name": "Test", "scope": legacy_scope, "model_id": 1}
        with pytest.raises(ValueError) as exc_info:
            _normalize_agent_data(data)
        assert legacy_scope in str(exc_info.value)

    def test_canonical_global_shared_passes(self) -> None:
        data = {"name": "Test", "scope": "global_shared", "model_id": 1}
        payload, tenant_ids, want_publish = _normalize_agent_data(data)
        assert payload["scope"] == "global_shared"
        assert tenant_ids is None
        assert want_publish is False

    @pytest.mark.parametrize("field", ["distribution_mode", "owner_type", "legacy_scope"])
    def test_rejected_legacy_fields_raise(self, field: str) -> None:
        data = {"name": "Test", "model_id": 1, "scope": "global_shared", field: "anything"}
        with pytest.raises(ValueError) as exc_info:
            _normalize_agent_data(data)
        assert field in str(exc_info.value)

    def test_invalid_scope_raises(self) -> None:
        data = {"name": "Test", "scope": "invalid_scope_value", "model_id": 1}
        with pytest.raises(ValueError, match="invalid_scope_value"):
            _normalize_agent_data(data)

    def test_status_published_sets_want_publish(self) -> None:
        data = {"name": "Test", "model_id": 1, "status": "published"}
        _, _, want_publish = _normalize_agent_data(data)
        assert want_publish is True

    def test_strips_system_fields(self) -> None:
        data = {
            "name": "Test",
            "model_id": 1,
            "published_version": 99,
            "delete_level": "tenant",
            "id": 999,
        }
        payload, _, _ = _normalize_agent_data(data)
        assert "published_version" not in payload
        assert "delete_level" not in payload
        assert "id" not in payload
