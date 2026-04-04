from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.api.admin.plugins import AdminPluginController, MenuOverrideItem
from app.core.config import settings
from app.core.i18n import _, set_locale
from app.core.response import deleted
from app.enums.plugin import PluginStatusEnum
from app.exceptions.base import BusinessException


def _build_manifest():
    return SimpleNamespace(
        dependencies=SimpleNamespace(python=[]),
        extensions=SimpleNamespace(
            frontend=SimpleNamespace(),
            notifications=[],
            skills=[],
            tasks=[],
        ),
        ai_requirements=None,
    )


def _get_endpoint(path: str, method: str):
    router = AdminPluginController.get_router()
    for route in router.routes:
        if getattr(route, "path", None) == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found: {method} {path}")


@asynccontextmanager
async def _lock_context(_plugin_id: int):
    yield


@pytest.fixture(autouse=True)
def _use_english_locale():
    set_locale("en")
    yield
    set_locale("zh_CN")


@pytest.mark.asyncio
async def test_admin_repair_extension_load_failure_disables_permissions_and_unregisters_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(AdminPluginController, "_instance", None)
    monkeypatch.setattr(AdminPluginController, "_router", None)

    plugin = SimpleNamespace(
        id=11,
        name="broken-plugin",
        status=PluginStatusEnum.ERROR.value,
        error_count=0,
        error_message=None,
        config={},
    )
    service = SimpleNamespace(get_by_id=AsyncMock(return_value=plugin))

    loader = SimpleNamespace(
        plugins_dir=tmp_path / "plugins",
        load_manifest=lambda _plugin_name: _build_manifest(),
    )
    lifecycle = SimpleNamespace(
        _assert_plugin_runtime_enable_guards=AsyncMock(),
        _deactivate_plugin_skill_records=AsyncMock(),
        _ensure_plugin_ai_features=AsyncMock(),
        _ensure_plugin_skill_records=AsyncMock(),
        _install_python_deps=AsyncMock(return_value=[]),
        _restore_plugin_permissions=AsyncMock(),
        _sync_plugin_notification_templates=AsyncMock(),
        _sync_plugin_task_definitions=AsyncMock(),
        run_alembic_upgrade=AsyncMock(),
        _set_plugin_permissions_enabled=AsyncMock(),
    )
    emitter = SimpleNamespace(
        emit_step=AsyncMock(),
        emit_error=AsyncMock(),
        emit_done=AsyncMock(),
    )
    registry = MagicMock()

    monkeypatch.setattr(AdminPluginController, "get_service", lambda self, db: service)
    monkeypatch.setattr("app.plugins.loader.PluginLoader", lambda: loader)
    monkeypatch.setattr("app.plugins.lifecycle.PluginLifecycle", lambda db: lifecycle)
    monkeypatch.setattr("app.plugins.lifecycle._plugin_lock", _lock_context)
    monkeypatch.setattr("app.plugins.registry.ExtensionRegistry.get_instance", lambda: registry)
    monkeypatch.setattr(
        "app.plugins.progress.PluginProgressEmitter",
        lambda *_args, **_kwargs: emitter,
    )
    monkeypatch.setattr(
        "app.plugins.frontend_contract.validate_runtime_frontend_contract",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.plugins._extension_registrar.register_all_extensions",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.plugins._extension_registrar.get_failed_extensions",
        lambda _plugin_name: [{"type": "page", "entry_point": "BrokenPage"}],
    )

    endpoint = _get_endpoint("/plugins/{plugin_id}/repair", "POST")
    db = AsyncMock()
    db.flush = AsyncMock()
    admin = SimpleNamespace(id=1)

    with pytest.raises(BusinessException) as exc:
        await endpoint(plugin.id, db, admin)

    assert exc.value.message == _("plugin.error.repair_extensions_failed").format(count=1)
    registry.unregister_all.assert_called_once_with(plugin.name)
    lifecycle._deactivate_plugin_skill_records.assert_awaited_once_with(plugin.name)
    lifecycle._set_plugin_permissions_enabled.assert_awaited_once_with(plugin.name, False)
    db.flush.assert_awaited_once()
    emitter.emit_error.assert_awaited_once()
    emitter.emit_done.assert_not_awaited()
    assert plugin.status == PluginStatusEnum.ERROR.value
    assert plugin.error_count == 1
    assert "extension load failed" in (plugin.error_message or "")


@pytest.mark.asyncio
async def test_admin_repair_unexpected_failure_still_fail_closes_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(AdminPluginController, "_instance", None)
    monkeypatch.setattr(AdminPluginController, "_router", None)

    plugin = SimpleNamespace(
        id=12,
        name="broken-plugin",
        status=PluginStatusEnum.ENABLED.value,
        error_count=2,
        error_message="old error",
        config={},
    )
    service = SimpleNamespace(get_by_id=AsyncMock(return_value=plugin))

    loader = SimpleNamespace(
        plugins_dir=tmp_path / "plugins",
        load_manifest=lambda _plugin_name: _build_manifest(),
    )
    lifecycle = SimpleNamespace(
        _assert_plugin_runtime_enable_guards=AsyncMock(),
        _deactivate_plugin_skill_records=AsyncMock(),
        _ensure_plugin_ai_features=AsyncMock(),
        _ensure_plugin_skill_records=AsyncMock(),
        _install_python_deps=AsyncMock(return_value=[]),
        _restore_plugin_permissions=AsyncMock(),
        _sync_plugin_notification_templates=AsyncMock(),
        _sync_plugin_task_definitions=AsyncMock(),
        run_alembic_upgrade=AsyncMock(),
        _set_plugin_permissions_enabled=AsyncMock(),
    )
    emitter = SimpleNamespace(
        emit_step=AsyncMock(),
        emit_error=AsyncMock(),
        emit_done=AsyncMock(),
    )
    registry = MagicMock()

    monkeypatch.setattr(AdminPluginController, "get_service", lambda self, db: service)
    monkeypatch.setattr("app.plugins.loader.PluginLoader", lambda: loader)
    monkeypatch.setattr("app.plugins.lifecycle.PluginLifecycle", lambda db: lifecycle)
    monkeypatch.setattr("app.plugins.lifecycle._plugin_lock", _lock_context)
    monkeypatch.setattr("app.plugins.registry.ExtensionRegistry.get_instance", lambda: registry)
    monkeypatch.setattr(
        "app.plugins.progress.PluginProgressEmitter",
        lambda *_args, **_kwargs: emitter,
    )
    monkeypatch.setattr(
        "app.plugins.frontend_contract.validate_runtime_frontend_contract",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.plugins._extension_registrar.register_all_extensions",
        MagicMock(side_effect=RuntimeError("repair boom")),
    )
    monkeypatch.setattr(
        "app.plugins._extension_registrar.get_failed_extensions",
        lambda _plugin_name: [],
    )

    endpoint = _get_endpoint("/plugins/{plugin_id}/repair", "POST")
    db = AsyncMock()
    db.flush = AsyncMock()
    admin = SimpleNamespace(id=1)

    original_debug = settings.DEBUG
    settings.DEBUG = False
    try:
        with pytest.raises(BusinessException) as exc:
            await endpoint(plugin.id, db, admin)
    finally:
        settings.DEBUG = original_debug

    assert exc.value.message == _("plugin.error.repair_failed")
    registry.unregister_all.assert_called_once_with(plugin.name)
    lifecycle._deactivate_plugin_skill_records.assert_awaited_once_with(plugin.name)
    lifecycle._set_plugin_permissions_enabled.assert_awaited_once_with(plugin.name, False)
    db.flush.assert_awaited_once()
    emitter.emit_error.assert_awaited_once()
    emitter.emit_done.assert_not_awaited()
    assert plugin.status == PluginStatusEnum.ERROR.value
    assert plugin.error_count == 3
    assert plugin.error_message == _("plugin.error.repair_failed")


def test_menu_override_item_accepts_hyphenated_parent_codes() -> None:
    item = MenuOverrideItem(
        name="demo_menu",
        parent="system-maintenance",
        tenant_parent="tenant-root-menu",
    )
    assert item.parent == "system-maintenance"
    assert item.tenant_parent == "tenant-root-menu"


def test_menu_override_item_rejects_invalid_parent_characters() -> None:
    with pytest.raises(ValidationError):
        MenuOverrideItem(
            name="demo_menu",
            parent="system maintenance",
            tenant_parent="tenant_root",
        )


@pytest.mark.asyncio
async def test_admin_uninstall_returns_deleted_when_plugin_already_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AdminPluginController, "_instance", None)
    monkeypatch.setattr(AdminPluginController, "_router", None)

    service = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    monkeypatch.setattr(AdminPluginController, "get_service", lambda self, db: service)

    endpoint = _get_endpoint("/plugins/{plugin_id}", "DELETE")
    response = await endpoint(
        1089,
        AsyncMock(),
        SimpleNamespace(id=1),
        False,
        False,
    )

    assert response == deleted(
        message=_("plugin.deleted_already").format(plugin_id=1089)
    )
