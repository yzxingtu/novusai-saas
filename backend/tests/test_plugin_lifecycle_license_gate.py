"""插件启用阶段 license gate 回归测试。 / Plugin enable license gate regression tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.plugins.exceptions import PluginLicenseError, PluginSecurityError
from app.plugins.lifecycle import PluginLifecycle


class _ScalarResult:
    def __init__(self, item):
        self._item = item

    def scalar_one_or_none(self):
        return self._item


class _NestedTransaction:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        self._db.begin_nested_calls += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self._db.poisoned = False
        return False


class _PermissionPoisonDB:
    def __init__(self, plugin):
        self._plugin = plugin
        self.poisoned = False
        self.begin_nested_calls = 0
        self.flush = AsyncMock()

    async def execute(self, *_args, **_kwargs):
        return _ScalarResult(self._plugin)

    def begin_nested(self):
        return _NestedTransaction(self)


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
    monkeypatch.setattr(
        lifecycle._loader, "load_manifest", lambda _name: _build_manifest()
    )

    emitter = MagicMock()
    emitter.emit_step = AsyncMock()
    emitter.emit_done = AsyncMock()
    emitter.emit_error = AsyncMock()
    monkeypatch.setattr(
        "app.plugins.progress.PluginProgressEmitter", lambda *_args, **_kwargs: emitter
    )

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


@pytest.mark.asyncio
async def test_enable_impl_isolates_permission_sync_failure_with_savepoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin = SimpleNamespace(
        id=8,
        name="demo-plugin",
        status="disabled",
        pricing_type="free",
        config={},
        granted_capabilities=[],
        error_count=0,
        enabled_at=None,
        error_message=None,
    )

    db = _PermissionPoisonDB(plugin)
    lifecycle = PluginLifecycle(db)
    lifecycle._loader.plugins_dir = Path("E:/nonexistent-plugin-root")
    monkeypatch.setattr(
        lifecycle._loader, "load_manifest", lambda _name: _build_manifest()
    )
    monkeypatch.setattr("app.core.config.settings.DEBUG", False, raising=False)
    monkeypatch.setattr(
        "app.plugins.frontend_contract.validate_runtime_frontend_contract",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.plugins.license.assert_plugin_license_active",
        AsyncMock(),
    )
    monkeypatch.setattr(
        lifecycle,
        "_assert_plugin_dependencies_ready",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.plugins._extension_registrar.register_all_extensions",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.plugins._extension_registrar.get_failed_extensions",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "app.plugins.context_factory.create_plugin_context",
        lambda **_kwargs: object(),
    )

    class _PluginImpl:
        async def on_enable(self, _ctx):
            return None

    monkeypatch.setattr(
        lifecycle._loader, "load_plugin_class", lambda _name: _PluginImpl
    )

    class _FailingPermissionSyncService:
        def __init__(self, session):
            self._db = session

        async def sync_plugin_permissions(self, _plugin_name: str):
            self._db.poisoned = True
            raise RuntimeError("permission sync flush failed")

    monkeypatch.setattr(
        "app.rbac.sync.PermissionSyncService",
        _FailingPermissionSyncService,
    )

    async def _assert_session_clean(*_args, **_kwargs):
        if db.poisoned:
            raise AssertionError("session remained poisoned")

    lifecycle._set_plugin_permissions_enabled = AsyncMock(
        side_effect=_assert_session_clean
    )
    lifecycle._auto_grant_plugin_menus_to_plans = AsyncMock()

    from app.plugins.exceptions import PluginError

    with pytest.raises(PluginError):
        await lifecycle._enable_impl(plugin.id)

    assert plugin.status == "error"
    assert plugin.error_count == 1
    assert db.begin_nested_calls == 0
    lifecycle._set_plugin_permissions_enabled.assert_awaited_once_with(
        plugin.name,
        False,
    )
    lifecycle._auto_grant_plugin_menus_to_plans.assert_not_awaited()


@pytest.mark.asyncio
async def test_enable_impl_fail_closes_when_security_scan_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin = SimpleNamespace(
        id=9,
        name="suspicious-plugin",
        status="disabled",
        pricing_type="free",
        config={},
        granted_capabilities=[],
        error_count=0,
        enabled_at=None,
        error_message=None,
    )

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarResult(plugin))
    db.flush = AsyncMock()

    lifecycle = PluginLifecycle(db)
    emitter = MagicMock()
    emitter.emit_step = AsyncMock()
    emitter.emit_done = AsyncMock()
    emitter.emit_error = AsyncMock()
    monkeypatch.setattr(
        "app.plugins.progress.PluginProgressEmitter",
        lambda *_args, **_kwargs: emitter,
    )
    monkeypatch.setattr(
        "app.plugins.security_scan.assert_plugin_security_clean",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            PluginSecurityError(message="blocked by security scan")
        ),
    )

    with pytest.raises(PluginSecurityError):
        await lifecycle._enable_impl(plugin.id)

    assert plugin.status == "error"
    assert plugin.error_message == "blocked by security scan"
    assert plugin.error_count == 1
    db.flush.assert_awaited_once()
    emitter.emit_error.assert_awaited_once()
