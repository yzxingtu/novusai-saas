from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services.system.plugin_cleanup_service import (
    PluginCleanupService,
    _escape_like_pattern,
)


def test_escape_like_pattern_escapes_like_wildcards() -> None:
    raw = r"demo_plugin_%\name"
    escaped = _escape_like_pattern(raw)
    assert escaped == r"demo\_plugin\_\%\\name"


@pytest.mark.asyncio
async def test_purge_alembic_versions_by_plugin_name_escapes_like_prefix() -> None:
    db = AsyncMock()
    service = PluginCleanupService(db)

    await service.purge_alembic_versions_by_plugin_name("demo-plugin")

    db.execute.assert_awaited_once()
    statement, params = db.execute.await_args.args
    assert "ESCAPE '\\'" in str(statement)
    assert params == {"prefix": r"demo\_plugin\_%"}
