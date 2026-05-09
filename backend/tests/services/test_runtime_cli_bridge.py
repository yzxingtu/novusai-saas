"""Test type: structural
Scope: AI runtime CLI bridge must fail closed instead of returning not_available.
Mock strategy: replace dynamic imports with local service stubs; no runtime service result mocks beyond bridge dispatch shape.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.ai import runtime_cli_bridge
from app.services.ai.runtime_cli_bridge import (
    AIRuntimeCliBridge,
    RuntimeCliDependencyMissing,
    RuntimeCliScope,
)


@pytest.mark.asyncio
async def test_runtime_cli_bridge_dispatches_current_service(monkeypatch) -> None:
    class RuntimeDiagnosticsService:
        def __init__(self, db) -> None:  # noqa: ANN001
            self.db = db

        async def run_doctor(self, *, tenant_id=None, agent_id=None, **_kwargs):
            return {
                "status": "passed",
                "db_seen": self.db == "db-session",
                "tenant_id": tenant_id,
                "agent_id": agent_id,
            }

    monkeypatch.setattr(
        runtime_cli_bridge,
        "import_module",
        lambda _name: SimpleNamespace(
            RuntimeDiagnosticsService=RuntimeDiagnosticsService
        ),
    )

    result = await AIRuntimeCliBridge("db-session").run_doctor(
        RuntimeCliScope(tenant_id=7, agent_id=59)
    )

    assert result == {
        "status": "passed",
        "db_seen": True,
        "tenant_id": 7,
        "agent_id": 59,
    }


@pytest.mark.asyncio
async def test_runtime_cli_bridge_fails_closed_when_service_import_fails(
    monkeypatch,
) -> None:
    def _raise_import_error(_name: str):
        raise ImportError("diagnostics service missing")

    monkeypatch.setattr(runtime_cli_bridge, "import_module", _raise_import_error)

    with pytest.raises(RuntimeCliDependencyMissing, match="diagnostics service missing"):
        await AIRuntimeCliBridge("db-session").run_smoke(RuntimeCliScope(agent_id=59))


@pytest.mark.asyncio
async def test_runtime_cli_bridge_fails_closed_when_method_missing(
    monkeypatch,
) -> None:
    class RuntimeDiagnosticsService:
        def __init__(self, db) -> None:  # noqa: ANN001
            self.db = db

    monkeypatch.setattr(
        runtime_cli_bridge,
        "import_module",
        lambda _name: SimpleNamespace(
            RuntimeDiagnosticsService=RuntimeDiagnosticsService
        ),
    )

    with pytest.raises(RuntimeCliDependencyMissing, match="real-dialogue-smoke"):
        await AIRuntimeCliBridge("db-session").run_real_dialogue_smoke(
            RuntimeCliScope(agent_id=59),
            {"scenario_ids": ["SMOKE-001"]},
        )
