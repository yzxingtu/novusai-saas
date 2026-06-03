"""Test type: behavioral
Scope: shared skill API helpers preserve plugin-skill runtime identity.
Real dependencies: enrich_plugin_skill_info and ToolDefinition projection.
Mocked dependencies: DB source_plugin lookup and plugin registry lookup only.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ai.tools.types import ToolDefinition
from app.api.shared._skill_helpers import enrich_plugin_skill_info


@pytest.mark.asyncio
async def test_enrich_plugin_skill_info_uses_stable_plugin_skill_identity(
    monkeypatch,
) -> None:
    skill = SimpleNamespace(
        id=901,
        package_id=44,
        key="demo-plugin:beta-skill",
        source_ref="demo-plugin:beta-skill",
        config={},
    )
    data = SimpleNamespace(source_plugin=None, plugin_tools=None)
    db_result = SimpleNamespace(scalar_one_or_none=lambda: "demo-plugin")
    db = SimpleNamespace(execute=AsyncMock(return_value=db_result))
    registry_calls: list[tuple[str, str | None]] = []

    def _resolver(_skill, _config):
        return [ToolDefinition(name="beta_tool", description="Beta tool")]

    registry_stub = SimpleNamespace(
        get_plugin_skill_resolver=lambda plugin_name, skill_name=None: (
            registry_calls.append((plugin_name, skill_name)) or _resolver
            if skill_name == "beta-skill"
            else None
        )
    )
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry_stub,
    )

    await enrich_plugin_skill_info(db, skill, data)

    assert data.source_plugin == "demo-plugin"
    assert registry_calls == [("demo-plugin", "beta-skill")]
    assert [tool.name for tool in data.plugin_tools] == ["beta_tool"]
