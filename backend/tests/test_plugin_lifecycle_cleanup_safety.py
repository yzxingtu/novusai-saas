"""Regression tests for plugin lifecycle database cleanup safety. / 插件"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.plugins.lifecycle_migrations as lifecycle_migrations
from app.plugins.exceptions import PluginError, PluginInstallError
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


def test_lifecycle_table_prefix_resolution_fails_when_manifest_invalid() -> None:
    """中文: Test type: behavioral. lifecycle facade 不得在 manifest 无效时回退默认前缀。

    EN: Test type: behavioral. The lifecycle facade must not fall back to a
    default prefix when the manifest is invalid.
    """
    lifecycle = PluginLifecycle(AsyncMock())
    lifecycle._loader = SimpleNamespace(
        load_manifest=lambda _name: (_ for _ in ()).throw(RuntimeError("bad yaml")),
    )

    with pytest.raises(PluginError, match="Cannot resolve DB table prefixes"):
        lifecycle._resolve_plugin_table_prefixes("demo-plugin")


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
        raise AssertionError(f"Unexpected SQL in test: {sql}")

    db.execute = AsyncMock(side_effect=_execute)

    lifecycle = PluginLifecycle(db)
    lifecycle._loader = SimpleNamespace(
        load_manifest=lambda _name: SimpleNamespace(db_table_prefixes=[]),
    )
    monkeypatch.setattr(lifecycle, "_plugin_has_migrations", lambda *_: False)

    await lifecycle._cleanup_plugin_database("demo-plugin")

    assert dropped_sql == ['DROP TABLE IF EXISTS "px_demo_plugin_orders" CASCADE']


@pytest.mark.asyncio
async def test_cleanup_plugin_database_blocks_residual_tables_after_migration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """中文: Test type: behavioral. 迁移回退后仍残留插件表时必须失败关闭。

    EN: Test type: behavioral. Cleanup must fail closed when plugin tables remain after migration downgrade.
    """
    plugins_root = tmp_path / "plugins"
    migrations_dir = (
        plugins_root / "demo-plugin" / "backend" / "migrations" / "versions"
    )
    migrations_dir.mkdir(parents=True)
    (migrations_dir / "001_demo.py").write_text(
        'revision = "demo_001"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(lifecycle_migrations, "PLUGINS_DIR", plugins_root)

    db = AsyncMock()
    db.flush = AsyncMock()

    @asynccontextmanager
    async def _nested():
        yield

    db.begin_nested = MagicMock(side_effect=lambda: _nested())
    dropped_sql: list[str] = []

    async def _execute(statement, params=None):  # type: ignore[no-untyped-def]
        _ = params
        sql = str(statement)
        if "SELECT 1 FROM alembic_version" in sql:
            return MagicMock(scalar=lambda: None)
        if "SELECT tablename FROM pg_tables" in sql:
            return _RowsResult([("px_demo_plugin_orders",)])
        if sql.startswith('DROP TABLE IF EXISTS "'):
            dropped_sql.append(sql)
            return MagicMock()
        raise AssertionError(f"Unexpected SQL in test: {sql}")

    db.execute = AsyncMock(side_effect=_execute)

    lifecycle = PluginLifecycle(db)
    lifecycle._loader = SimpleNamespace(
        load_manifest=lambda _name: SimpleNamespace(db_table_prefixes=[]),
    )

    with pytest.raises(PluginInstallError, match="left plugin tables behind"):
        await lifecycle._cleanup_plugin_database("demo-plugin")

    assert dropped_sql == []


@pytest.mark.asyncio
async def test_cleanup_plugin_database_blocks_residual_table_query_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """中文: Test type: behavioral. 残留表清理查询失败时必须阻断插件清理。

    EN: Test type: behavioral. Cleanup must fail closed when residual table
    discovery fails.
    """
    db = AsyncMock()
    db.flush = AsyncMock()

    @asynccontextmanager
    async def _nested():
        yield

    db.begin_nested = MagicMock(side_effect=lambda: _nested())

    async def _execute(statement, params=None):  # type: ignore[no-untyped-def]
        _ = params
        sql = str(statement)
        if "SELECT tablename FROM pg_tables" in sql:
            raise RuntimeError("catalog unavailable")
        raise AssertionError(f"Unexpected SQL in test: {sql}")

    db.execute = AsyncMock(side_effect=_execute)

    lifecycle = PluginLifecycle(db)
    lifecycle._loader = SimpleNamespace(
        load_manifest=lambda _name: SimpleNamespace(db_table_prefixes=[]),
    )
    monkeypatch.setattr(lifecycle, "_plugin_has_migrations", lambda *_: False)

    with pytest.raises(PluginInstallError, match="residual table cleanup failed"):
        await lifecycle._cleanup_plugin_database("demo-plugin")

    db.flush.assert_not_awaited()
