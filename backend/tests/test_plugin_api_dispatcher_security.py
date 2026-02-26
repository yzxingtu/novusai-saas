"""
Plugin API dispatcher / sandbox security regression tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.plugins.api_dispatcher import _context_has_db_capability, _handler_accepts_param
from app.plugins.context import PluginDbProxy
from app.plugins.exceptions import PluginSecurityError


class _OwnTableModel:
    __tablename__ = "px_demo_items"


class _ForeignTableModel:
    __tablename__ = "users"


class _CtxWithCap:
    def has_capability(self, cap: str) -> bool:
        return cap == "db:own_tables"


class _CtxWithoutCap:
    def has_capability(self, cap: str) -> bool:
        return False


def test_handler_accepts_param_by_name() -> None:
    def handler(request, ctx):
        return request, ctx

    assert _handler_accepts_param(handler, "request") is True
    assert _handler_accepts_param(handler, "ctx") is True
    assert _handler_accepts_param(handler, "db") is False


def test_handler_accepts_param_by_kwargs() -> None:
    def handler(request, **kwargs):
        return request, kwargs

    assert _handler_accepts_param(handler, "db") is True


def test_context_has_db_capability() -> None:
    assert _context_has_db_capability(_CtxWithCap()) is True
    assert _context_has_db_capability(_CtxWithoutCap()) is False


@pytest.mark.asyncio
async def test_plugin_db_proxy_blocks_raw_session_access() -> None:
    proxy = PluginDbProxy(AsyncMock(), "demo")

    with pytest.raises(PluginSecurityError):
        _ = proxy.session


@pytest.mark.asyncio
async def test_plugin_db_proxy_blocks_foreign_model_get() -> None:
    proxy = PluginDbProxy(AsyncMock(), "demo")

    with pytest.raises(PluginSecurityError):
        await proxy.get(_ForeignTableModel, 1)


@pytest.mark.asyncio
async def test_plugin_db_proxy_allows_own_table_model_add_all() -> None:
    db = MagicMock()
    proxy = PluginDbProxy(db, "demo")

    proxy.add_all([_OwnTableModel()])

    db.add_all.assert_called_once()
