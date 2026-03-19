from __future__ import annotations

from types import SimpleNamespace

from app.api.shared._agent_helpers import build_agent_base_item


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
        skill_bindings=[],
    )

    item = build_agent_base_item(agent)

    assert item["input_variables"] == []
