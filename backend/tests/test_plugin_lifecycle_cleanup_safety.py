"""Regression tests for plugin lifecycle database cleanup safety. / 插件"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.plugins.lifecycle import PluginLifecycle
from app.plugins.lifecycle_support import escape_like_pattern, is_safe_plugin_table_name


class _RowsResult:
    def __init__(self, rows: list[tuple[str]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[str]]:
        return self._rows


class _DeleteResult:
    def __init__(self, rowcount: int = 0) -> None:
        self.rowcount = rowcount


def test_is_safe_plugin_table_name_filters_unsafe_patterns() -> None:
    prefix = "px_demo_plugin_"
    assert is_safe_plugin_table_name("px_demo_plugin_orders", prefix) is True
    assert is_safe_plugin_table_name("px_demo_plugin_orders_2026", prefix) is True
    assert is_safe_plugin_table_name("users", prefix) is False
    assert is_safe_plugin_table_name("px_demo_plugin_orders;drop", prefix) is False
    assert is_safe_plugin_table_name('px_demo_plugin_orders"hack', prefix) is False
    assert is_safe_plugin_table_name("px_demo_plugin_orders%", prefix) is False


def test_escape_like_pattern_escapes_wildcards() -> None:
    raw = r"px_demo_plugin_%_abc\name"
    escaped = escape_like_pattern(raw)
    assert escaped == r"px\_demo\_plugin\_\%\_abc\\name"


@pytest.mark.asyncio
async def test_cleanup_plugin_database_drops_only_safe_prefixed_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    db.flush = AsyncMock()

    @asynccontextmanager
    async def _nested():
        yield

    db.begin_nested = MagicMock(side_effect=lambda: _nested())

    dropped_sql: list[str] = []
    delete_sql: list[str] = []

    async def _execute(statement, params=None):  # type: ignore[no-untyped-def]
        sql = str(statement)
        _ = params
        if "SELECT tablename FROM pg_tables" in sql:
            return _RowsResult(
                [
                    ("px_demo_plugin_orders",),
                    ("px_demo_plugin_%_wild",),
                    ('px_demo_plugin_bad"name',),
                    ("users",),
                ]
            )
        if sql.startswith('DROP TABLE IF EXISTS "'):
            dropped_sql.append(sql)
            return MagicMock()
        if "DELETE FROM alembic_version WHERE version_num LIKE :prefix" in sql:
            delete_sql.append(sql)
            return _DeleteResult(0)
        raise AssertionError(f"Unexpected SQL in test: {sql}")

    db.execute = AsyncMock(side_effect=_execute)

    lifecycle = PluginLifecycle(db)
    monkeypatch.setattr(lifecycle, "_plugin_has_migrations", lambda *_: False)

    await lifecycle._cleanup_plugin_database("demo-plugin")

    assert dropped_sql == ['DROP TABLE IF EXISTS "px_demo_plugin_orders" CASCADE']
    assert delete_sql
    assert "ESCAPE '\\'" in delete_sql[0]
