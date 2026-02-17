"""
Tests for crud_executor column name and table name safety validation.

Covers:
- _validate_column_names: rejects SQL injection payloads, special chars
- _validate_table_name: rejects unsafe table names
- _SAFE_COLUMN_NAME_RE / _SAFE_TABLE_NAME_RE: regex correctness
"""

from __future__ import annotations

import pytest

from app.ai.tools.executors.crud_executor import (
    _SAFE_COLUMN_NAME_RE,
    _SAFE_TABLE_NAME_RE,
    _validate_column_names,
    _validate_table_name,
)


# ============================================
# _SAFE_COLUMN_NAME_RE tests
# ============================================

class TestSafeColumnNameRegex:
    """Test the column name safety regex directly."""

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
        assert _SAFE_COLUMN_NAME_RE.match(name) is not None

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
        assert _SAFE_COLUMN_NAME_RE.match(name) is None


# ============================================
# _validate_column_names tests
# ============================================

class TestValidateColumnNames:
    """Test the _validate_column_names function."""

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
        """Simulate LLM passing SQL injection as column name."""
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
    """Test the _validate_table_name function."""

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
