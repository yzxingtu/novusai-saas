"""插件启用阶段 license gate 回归测试。 / Plugin enable license gate regression tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.plugins.exceptions import PluginLicenseError
from app.plugins.lifecycle import PluginLifecycle


class _ScalarResult:
    def __init__(self, item):
        self._item = item

    def scalar_one_or_none(self):
        return self._item


def _build_manifest():
    return SimpleNamespace(
        compatibility=None,
        dependencies=SimpleNamespace(plugins=[], python=[]),
        extensions=SimpleNamespace(
            frontend=None,
            skills=[],
            notifications=[],
            tasks=[],
        ),
        ai_requirements=None,
    )


@pytest.mark.asyncio
async def test_enable_impl_blocks_paid_plugin_when_license_inactive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin = SimpleNamespace(
        id=7,
        name="paid-plugin",
        status="disabled",
        pricing_type="paid",
        config={},
    )

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarResult(plugin))
    db.flush = AsyncMock()

    lifecycle = PluginLifecycle(db)
    monkeypatch.setattr(lifecycle._loader, "load_manifest", lambda _name: _build_manifest())

    emitter = MagicMock()
    emitter.emit_step = AsyncMock()
    emitter.emit_done = AsyncMock()
    emitter.emit_error = AsyncMock()
    monkeypatch.setattr("app.plugins.progress.PluginProgressEmitter", lambda *_args, **_kwargs: emitter)

    guard = AsyncMock(side_effect=PluginLicenseError(message="license inactive"))
    monkeypatch.setattr("app.plugins.license.assert_plugin_license_active", guard)
    lifecycle.run_alembic_upgrade = AsyncMock()

    with pytest.raises(PluginLicenseError):
        await lifecycle._enable_impl(plugin.id)

    guard.assert_awaited_once_with(
        plugin.id,
        plugin.pricing_type,
        db,
        plugin_name=plugin.name,
        operation="enable",
    )
    lifecycle.run_alembic_upgrade.assert_not_called()
