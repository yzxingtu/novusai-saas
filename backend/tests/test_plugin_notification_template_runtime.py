"""Regression tests for plugin notification template runtime semantics."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

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

    await lifecycle._sync_plugin_notification_templates(
        "demo-plugin", [notification]
    )

    assert db.add.call_count == 1
    template = db.add.call_args.args[0]
    assert template.code == "plugin.demo-plugin.biz.crm_lead_assigned"
    assert template.category == "biz"
    assert template.title_template == "New Lead"
    assert template.channels == ["ws"]
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

    await lifecycle._sync_plugin_notification_templates(
        "demo-plugin", [notification]
    )

    assert existing.is_deleted is False
    assert existing.deleted_at is None
    assert existing.channels == ["ws", "inbox"]
    assert existing.category == "biz"
    assert existing.title_template == "Reconciled"
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
    clause = getattr(delete_expr, "whereclause", None)
    assert clause is not None
    assert getattr(clause.right, "value", "") == "plugin.demo-plugin.%"


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

        stored = registry.get_plugin_notification("plugin.demo-plugin.biz.crm_notification")
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
