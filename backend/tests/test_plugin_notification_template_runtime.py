"""Regression tests for plugin notification template runtime semantics."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.plugins.context import PluginContext
from app.plugins.context_primitives import RequestContext
from app.plugins.exceptions import PluginSecurityError
from app.plugins.lifecycle import PluginLifecycle
from app.plugins.registry import ExtensionRegistry


@pytest.mark.asyncio
async def test_sync_inserts_template_when_missing():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.add = MagicMock()

    lifecycle = PluginLifecycle(db)
    notification = SimpleNamespace(
        code="biz.crm_lead_assigned",
        title={"en": "New Lead"},
        channels=["ws"],
        category="biz",
    )

    await lifecycle._sync_plugin_notification_templates("demo-plugin", [notification])

    assert db.add.call_count == 1
    template = db.add.call_args.args[0]
    assert template.code == "plugin.demo-plugin.biz.crm_lead_assigned"
    assert template.category == "biz"
    assert template.title_template == "New Lead"
    assert template.channels == ["ws"]
    assert template.scope == "plugin"
    assert template.source == "plugin"
    assert template.plugin_name == "demo-plugin"
    assert template.is_enabled is True
    db.add.assert_called_once_with(template)
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_restores_existing_template():
    db = AsyncMock()
    result = MagicMock()
    existing = SimpleNamespace(
        is_deleted=True,
        deleted_at="old",
        channels=["old"],
        category="old",
        title_template="Old",
        updated_at="old",
        scope="platform",
        source="core",
        plugin_name=None,
        is_enabled=False,
    )
    result.scalar_one_or_none.return_value = existing
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.add = MagicMock()

    lifecycle = PluginLifecycle(db)

    notification = SimpleNamespace(
        code="plugin.demo-plugin.biz.reconcile",
        title={"en": "Reconciled"},
        channels=None,
        category="biz",
    )

    await lifecycle._sync_plugin_notification_templates("demo-plugin", [notification])

    assert existing.is_deleted is False
    assert existing.deleted_at is None
    assert existing.channels == ["ws", "inbox"]
    assert existing.category == "biz"
    assert existing.title_template == "Reconciled"
    assert existing.scope == "plugin"
    assert existing.source == "plugin"
    assert existing.plugin_name == "demo-plugin"
    assert existing.is_enabled is True
    db.add.assert_not_called()
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_plugin_notification_templates_flushes_when_rows_removed():
    db = AsyncMock()
    db.flush = AsyncMock()
    result = MagicMock()
    result.rowcount = 2
    db.execute = AsyncMock(return_value=result)
    lifecycle = PluginLifecycle(db)

    await lifecycle._delete_plugin_notification_templates("demo-plugin")

    db.flush.assert_awaited_once()
    delete_expr = db.execute.await_args.args[0]
    compiled = str(delete_expr.compile(compile_kwargs={"literal_binds": True}))
    assert "plugin.demo-plugin.%" in compiled
    assert "plugin_name = 'demo-plugin'" in compiled
    assert "scope = 'plugin'" in compiled


@pytest.mark.asyncio
async def test_delete_plugin_notification_templates_skips_flush_when_empty():
    db = AsyncMock()
    db.flush = AsyncMock()
    result = MagicMock()
    result.rowcount = 0
    db.execute = AsyncMock(return_value=result)
    lifecycle = PluginLifecycle(db)

    await lifecycle._delete_plugin_notification_templates("demo-plugin")

    db.flush.assert_not_awaited()


def test_register_notification_records_template_and_cleans_registry():
    ExtensionRegistry.reset()
    registry = ExtensionRegistry.get_instance()
    try:
        registry.register_notification(
            "demo-plugin",
            "biz.crm_notification",
            {"en": "CRM Alert"},
            None,
            "biz",
        )

        stored = registry.get_plugin_notification(
            "plugin.demo-plugin.biz.crm_notification"
        )
        assert stored is not None
        assert stored["channels"] == ["ws", "inbox"]
        assert stored["title"] == {"en": "CRM Alert"}
        assert stored["category"] == "biz"
        assert registry.get_registered_count("demo-plugin") == 1
    finally:
        registry.unregister_all("demo-plugin")
        ExtensionRegistry.reset()

    assert ExtensionRegistry.get_instance().get_registered_count("demo-plugin") == 0
    assert (
        ExtensionRegistry.get_instance().get_plugin_notification(
            "plugin.demo-plugin.biz.crm_notification"
        )
        is None
    )


@pytest.mark.asyncio
async def test_plugin_send_notification_rejects_cross_tenant_targets():
    db = AsyncMock()
    context = PluginContext(
        "demo-plugin",
        manifest=SimpleNamespace(),
        db=db,
        granted_capabilities=["notifications:send"],
        request_context=RequestContext(
            tenant_id=10, user_id=3, user_role="tenant_admin"
        ),
    )

    with pytest.raises(PluginSecurityError):
        await context.send_notification(
            tenant_id=11,
            user_ids=[7],
            template_code="plugin.demo-plugin.biz.alert",
            variables={},
        )

    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_plugin_send_notification_rejects_foreign_plugin_template():
    db = AsyncMock()
    context = PluginContext(
        "demo-plugin",
        manifest=SimpleNamespace(),
        db=db,
        granted_capabilities=["notifications:send"],
        request_context=RequestContext(
            tenant_id=10, user_id=3, user_role="tenant_admin"
        ),
    )

    with pytest.raises(PluginSecurityError):
        await context.send_notification(
            tenant_id=10,
            user_ids=[7],
            template_code="plugin.other.biz.alert",
            variables={},
        )

    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_plugin_send_notification_rejects_non_owned_recipient():
    db = AsyncMock()
    result = MagicMock()
    result.scalar.return_value = 0
    db.execute = AsyncMock(return_value=result)
    context = PluginContext(
        "demo-plugin",
        manifest=SimpleNamespace(),
        db=db,
        granted_capabilities=["notifications:send"],
        request_context=RequestContext(
            tenant_id=10, user_id=3, user_role="tenant_admin"
        ),
    )

    with pytest.raises(PluginSecurityError):
        await context.send_notification(
            tenant_id=10,
            user_ids=[7],
            template_code="plugin.demo-plugin.biz.alert",
            variables={},
        )

    db.execute.assert_awaited_once()
