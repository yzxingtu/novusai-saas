"""Regression tests for plugin helper transaction semantics. / 插件"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.plugins.backup import _get_plugin_table_prefixes, backup_plugin_data
from app.plugins.exceptions import PluginError
from app.plugins.lifecycle import PluginLifecycle


class _OneOrNoneResult:
    def __init__(self, row):
        self._row = row

    def one_or_none(self):
        return self._row


class _RowsResult:
    def __init__(self, rows: list[tuple[str]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[str]]:
        return self._rows


def test_backup_table_prefix_resolution_fails_when_manifest_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """中文: Test type: behavioral. 备份不能在 manifest 解析失败时猜默认表前缀继续执行。

    EN: Test type: behavioral. Backup must not guess default table prefixes when manifest parsing fails.
    """
    monkeypatch.setattr(
        "app.plugins.backup.PluginLoader",
        lambda: SimpleNamespace(
            load_manifest=lambda _name: (_ for _ in ()).throw(RuntimeError("bad yaml")),
        ),
    )

    with pytest.raises(PluginError, match="Cannot resolve table prefixes"):
        _get_plugin_table_prefixes("demo-plugin")


@pytest.mark.asyncio
async def test_backup_plugin_data_uses_savepoint_without_outer_rollback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr("app.plugins.backup.BACKUPS_DIR", tmp_path / ".backups")
    monkeypatch.setattr("app.plugins.backup.PLUGINS_DIR", tmp_path / "plugins")
    monkeypatch.setattr(
        "app.plugins.backup.PluginLoader",
        lambda: SimpleNamespace(
            load_manifest=lambda _name: SimpleNamespace(db_table_prefixes=[]),
        ),
    )

    db = AsyncMock()
    db.rollback = AsyncMock()

    nested_calls = 0

    @asynccontextmanager
    async def _nested():
        nonlocal nested_calls
        nested_calls += 1
        yield

    db.begin_nested = MagicMock(side_effect=lambda: _nested())
    db.execute = AsyncMock(
        side_effect=[
            _OneOrNoneResult(None),  # config snapshot query
            RuntimeError("table list failed"),  # data table query
        ]
    )

    await backup_plugin_data("demo-plugin", "1.0.0", db)

    assert nested_calls >= 2
    assert db.rollback.await_count == 0


@pytest.mark.asyncio
async def test_cleanup_plugin_database_savepoint_failure_does_not_rollback_outer_tx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()

    nested_calls = 0
    dropped_sql: list[str] = []

    @asynccontextmanager
    async def _nested():
        nonlocal nested_calls
        nested_calls += 1
        yield

    db.begin_nested = MagicMock(side_effect=lambda: _nested())

    async def _execute(statement, params=None):  # type: ignore[no-untyped-def]
        _ = params
        sql = str(statement)
        if "SELECT tablename FROM pg_tables" in sql:
            return _RowsResult([("px_demo_plugin_orders",)])
        if sql.startswith('DROP TABLE IF EXISTS "'):
            dropped_sql.append(sql)
            return MagicMock()
        if "DELETE FROM alembic_version" in sql:
            raise RuntimeError("delete failed")
        raise AssertionError(f"Unexpected SQL in test: {sql}")

    db.execute = AsyncMock(side_effect=_execute)

    lifecycle = PluginLifecycle(db)
    lifecycle._loader = SimpleNamespace(
        load_manifest=lambda _name: SimpleNamespace(db_table_prefixes=[]),
    )
    monkeypatch.setattr(lifecycle, "_plugin_has_migrations", lambda *_: False)

    await lifecycle._cleanup_plugin_database("demo-plugin")

    assert nested_calls >= 2
    assert dropped_sql == ['DROP TABLE IF EXISTS "px_demo_plugin_orders" CASCADE']
    assert db.rollback.await_count == 0
