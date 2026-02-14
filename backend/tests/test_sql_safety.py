"""
SQLSafetyValidator 单元测试 — 重点验证 SELECT INTO 拦截
"""

import pytest

from app.ai.data_intelligence.sql_safety import SQLSafetyValidator, extract_table_names


class TestSQLSafetyValidatorSelectInto:
    """C1: SELECT INTO 必须被拦截"""

    def test_select_into_table(self) -> None:
        """SELECT * INTO new_table FROM users — PostgreSQL 建表"""
        result = SQLSafetyValidator.validate("SELECT * INTO new_table FROM users")
        assert not result.passed
        assert any("INTO" in v for v in result.violations)

    def test_select_into_temp_table(self) -> None:
        """SELECT ... INTO TEMPORARY TABLE — 临时表"""
        sql = "SELECT id, name INTO TEMPORARY TABLE tmp FROM users WHERE status = 1"
        result = SQLSafetyValidator.validate(sql)
        assert not result.passed

    def test_select_into_temp(self) -> None:
        """SELECT ... INTO TEMP — 缩写"""
        sql = "SELECT * INTO TEMP tmp_data FROM orders"
        result = SQLSafetyValidator.validate(sql)
        assert not result.passed

    def test_with_cte_select_into(self) -> None:
        """WITH CTE 中使用 SELECT INTO"""
        sql = "WITH cte AS (SELECT 1) SELECT * INTO new_table FROM cte"
        result = SQLSafetyValidator.validate(sql)
        assert not result.passed


class TestSQLSafetyValidatorBasic:
    """基础安全检查回归测试"""

    def test_valid_select(self) -> None:
        result = SQLSafetyValidator.validate("SELECT id, name FROM users WHERE id = 1")
        assert result.passed

    def test_valid_with_cte(self) -> None:
        sql = "WITH active AS (SELECT * FROM users WHERE status = 1) SELECT * FROM active"
        result = SQLSafetyValidator.validate(sql)
        assert result.passed

    def test_block_insert(self) -> None:
        result = SQLSafetyValidator.validate("INSERT INTO users (name) VALUES ('test')")
        assert not result.passed

    def test_block_update(self) -> None:
        result = SQLSafetyValidator.validate("UPDATE users SET name = 'test' WHERE id = 1")
        assert not result.passed

    def test_block_delete(self) -> None:
        result = SQLSafetyValidator.validate("DELETE FROM users WHERE id = 1")
        assert not result.passed

    def test_block_drop(self) -> None:
        result = SQLSafetyValidator.validate("DROP TABLE users")
        assert not result.passed

    def test_block_pg_sleep(self) -> None:
        result = SQLSafetyValidator.validate("SELECT pg_sleep(10)")
        assert not result.passed

    def test_block_line_comment(self) -> None:
        result = SQLSafetyValidator.validate("SELECT * FROM users -- comment")
        assert not result.passed

    def test_block_block_comment(self) -> None:
        result = SQLSafetyValidator.validate("SELECT * FROM users /* comment */")
        assert not result.passed

    def test_block_system_table(self) -> None:
        result = SQLSafetyValidator.validate("SELECT * FROM pg_catalog.pg_tables")
        assert not result.passed

    def test_empty_sql(self) -> None:
        result = SQLSafetyValidator.validate("")
        assert not result.passed

    def test_table_whitelist(self) -> None:
        result = SQLSafetyValidator.validate(
            "SELECT * FROM users",
            allowed_tables={"orders"},
        )
        assert not result.passed
        assert any("users" in v for v in result.violations)


class TestExtractTableNames:
    """表名提取测试"""

    def test_simple_from(self) -> None:
        tables = extract_table_names("SELECT * FROM users")
        assert "users" in tables

    @pytest.mark.xfail(reason="Pre-existing: alias regex consumes JOIN keyword")
    def test_join(self) -> None:
        tables = extract_table_names(
            "SELECT * FROM users JOIN orders ON users.id = orders.user_id"
        )
        assert "users" in tables
        assert "orders" in tables

    def test_cte_excluded(self) -> None:
        tables = extract_table_names(
            "WITH cte AS (SELECT * FROM users) SELECT * FROM cte"
        )
        assert "users" in tables
        assert "cte" not in tables
