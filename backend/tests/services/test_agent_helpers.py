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


def test_build_agent_base_item_filters_deleted_and_inactive_skills():
    active_skill = SimpleNamespace(id=10, name="active", is_deleted=False, is_active=True)
    deleted_skill = SimpleNamespace(id=11, name="deleted", is_deleted=True, is_active=True)
    inactive_skill = SimpleNamespace(id=12, name="inactive", is_deleted=False, is_active=False)
    grants = [
        SimpleNamespace(skill=active_skill, is_deleted=False, enabled=True),
        SimpleNamespace(skill=deleted_skill, is_deleted=False, enabled=True),
        SimpleNamespace(skill=inactive_skill, is_deleted=False, enabled=True),
        SimpleNamespace(skill=active_skill, is_deleted=True, enabled=True),
        SimpleNamespace(skill=active_skill, is_deleted=False, enabled=False),
    ]
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
        input_variables=[],
        created_at=None,
        updated_at=None,
        model=None,
        skill_grants=grants,
    )

    item = build_agent_base_item(agent)

    assert item["skills"] == [{"id": 10, "name": "active"}]
