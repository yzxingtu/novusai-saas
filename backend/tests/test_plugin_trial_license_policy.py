"""Plugin trial-license policy regression tests. / 插件试用授权策略回归测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.plugins.exceptions import PluginLicenseError
from app.plugins.license import create_trial_license


class _ScalarResult:
    def __init__(self, item):
        self._item = item

    def scalar_one_or_none(self):
        return self._item


@pytest.mark.asyncio
async def test_create_trial_license_rejects_paid_plugin_when_trial_disabled() -> None:
    plugin = SimpleNamespace(
        id=7,
        name="workflow-orchestration",
        pricing_type="paid",
        manifest={
            "pricing": {
                "type": "paid",
                "trial": {
                    "enabled": False,
                    "days": 14,
                },
            },
        },
    )

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarResult(plugin))
    db.flush = AsyncMock()

    with pytest.raises(PluginLicenseError, match="Trial is disabled for this plugin"):
        await create_trial_license(plugin.id, db)

    db.flush.assert_not_awaited()
