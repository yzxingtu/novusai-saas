"""Plugin scheduler refresh regression tests. / 插件调度刷新。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.plugins.exceptions import PluginError
from app.plugins.lifecycle import PluginLifecycle
from app.plugins.scheduler_refresh import refresh_plugin_schedule_or_raise


class _ScalarRows:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _ExecuteResult:
    def __init__(self, rows: list[object] | None = None, rowcount: int = 0) -> None:
        self._rows = rows or []
        self.rowcount = rowcount

    def scalars(self) -> _ScalarRows:
        return _ScalarRows(self._rows)


def test_refresh_plugin_schedule_or_raise_raises_plugin_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.tasks.scheduler.refresh_schedule",
        MagicMock(side_effect=RuntimeError("scheduler boom")),
    )

    with pytest.raises(PluginError) as exc_info:
        refresh_plugin_schedule_or_raise("demo-plugin", action="enable")

    assert "demo-plugin" in str(exc_info.value)
    assert exc_info.value.data == {
        "plugin_name": "demo-plugin",
        "schedule_action": "enable",
    }


@pytest.mark.asyncio
async def test_sync_plugin_task_definitions_raises_when_refresh_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ExecuteResult())
    db.flush = AsyncMock()
    db.add = MagicMock()

    lifecycle = PluginLifecycle(db)
    monkeypatch.setattr(
        "app.tasks.scheduler.refresh_schedule",
        MagicMock(side_effect=RuntimeError("scheduler boom")),
    )

    tasks = [
        SimpleNamespace(
            name="digest",
            schedule_type=None,
            description={"zh-CN": "Digest"},
            cron_expression=None,
            interval_seconds=60,
        )
    ]

    with pytest.raises(PluginError):
        await lifecycle._sync_plugin_task_definitions("demo-plugin", tasks)

    db.flush.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "action"),
    [
        ("_deactivate_plugin_task_definitions", "disable"),
        ("_delete_plugin_task_definitions", "uninstall"),
    ],
)
async def test_plugin_task_definition_mutations_fail_closed_on_refresh_error(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    action: str,
) -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ExecuteResult(rowcount=1))
    db.flush = AsyncMock()

    lifecycle = PluginLifecycle(db)
    monkeypatch.setattr(
        "app.tasks.scheduler.refresh_schedule",
        MagicMock(side_effect=RuntimeError("scheduler boom")),
    )

    method = getattr(lifecycle, method_name)

    with pytest.raises(PluginError) as exc_info:
        await method("demo-plugin")

    assert exc_info.value.data == {
        "plugin_name": "demo-plugin",
        "schedule_action": action,
    }
    db.flush.assert_awaited_once()
