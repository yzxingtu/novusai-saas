"""Targeted regression tests for shared AI runtime helpers."""

from __future__ import annotations

import pytest

from app.ai.tools.sql_analysis import (
    extract_group_by_expressions,
    extract_select_aggregates,
    extract_table_name_list,
)
from app.ai.rag.text_cleaner import clean_for_embedding
from app.ai.tools.security import (
    OutputSanitizer,
    SqlInjectionBlockedError,
    SqlValidator,
)


def test_extract_select_aggregates_and_group_by_are_structured() -> None:
    sql = """
    SELECT date_trunc('day', created_at) AS day, COUNT(*), SUM(total_amount)
    FROM orders
    GROUP BY date_trunc('day', created_at), status
    ORDER BY day DESC
    """
    assert extract_select_aggregates(sql) == ["COUNT(*)", "SUM(total_amount)"]
    assert extract_group_by_expressions(sql, max_items=4) == [
        "date_trunc('day', created_at)",
        "status",
    ]


def test_extract_table_name_list_includes_real_tables_inside_cte() -> None:
    sql = """
    WITH active_users AS (
        SELECT * FROM users WHERE status = 1
    )
    SELECT active_users.id, o.total_amount
    FROM active_users
    JOIN orders o ON o.user_id = active_users.id
    """
    tables = extract_table_name_list(sql)
    assert "users" in tables
    assert "orders" in tables
    assert "active_users" not in tables


def test_output_sanitizer_masks_assignment_bearer_and_prefixed_keys() -> None:
    output = "\n".join(
        [
            'api_key = "super-secret-token"',
            "Authorization: bearer abcdefghijklmnop",
            "public sk-ABCDEFGHIJKLMNOP",
        ]
    )
    sanitized, truncated = OutputSanitizer.sanitize(output)
    assert truncated is False
    assert "super-secret-token" not in sanitized
    assert "abcdefghijklmnop" not in sanitized.lower()
    assert "sk-ABCDEFGHIJKLMNOP" not in sanitized
    assert "***MASKED***" in sanitized
    assert "***MASKED_KEY***" in sanitized


def test_sql_validator_blocks_write_keywords_and_injects_limit() -> None:
    SqlValidator.validate("SELECT * FROM users")
    with pytest.raises(SqlInjectionBlockedError):
        SqlValidator.validate("UPDATE users SET name = 'x'")
    assert SqlValidator.inject_limit("SELECT * FROM users;", 50) == "SELECT * FROM users LIMIT 50;"


def test_clean_for_embedding_removes_urls_tags_emoji_and_noise() -> None:
    raw = "你好 [玫瑰][系统消息] 访问 https://example.com/path?x=1 😊   \n\n\n继续"
    cleaned = clean_for_embedding(raw)
    assert "https://example.com" not in cleaned
    assert "[玫瑰]" not in cleaned
    assert "[系统消息]" not in cleaned
    assert "😊" not in cleaned
    assert "继续" in cleaned
    assert "\n\n\n" not in cleaned

