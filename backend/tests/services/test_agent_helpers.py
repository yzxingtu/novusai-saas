from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

_HELPERS_PATH = (
    Path(__file__).resolve().parents[2] / "app" / "api" / "shared" / "_agent_helpers.py"
)
_SPEC = importlib.util.spec_from_file_location("test_agent_helpers_module", _HELPERS_PATH)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
build_agent_base_item = _MODULE.build_agent_base_item


def test_build_agent_base_item_normalizes_legacy_input_variables_dict():
    agent = SimpleNamespace(
        id=1,
        tenant_id=None,
        name="legacy-agent",
        avatar=None,
        description="legacy",
        status="published",
        scope="admin_only",
        execution_mode="conversation",
        is_system=False,
        published_version=None,
        welcome_message=None,
        suggested_questions=None,
        input_variables={},
        created_at=None,
        updated_at=None,
        model=None,
        skill_grants=[],
    )

    item = build_agent_base_item(agent)

    assert item["input_variables"] == []
