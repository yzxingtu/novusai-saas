"""
Test type: structural
Scope: shared agent list-item projection contract.
Mock strategy: SimpleNamespace fixtures only; assertions inspect projected fields.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

_HELPERS_PATH = (
    Path(__file__).resolve().parents[2] / "app" / "api" / "shared" / "_agent_helpers.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "test_agent_helpers_module", _HELPERS_PATH
)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
build_agent_base_item = _MODULE.build_agent_base_item


def test_build_agent_base_item_preserves_input_variables_list():
    input_variables = [{"name": "customer", "type": "string"}]
    agent = SimpleNamespace(
        id=1,
        tenant_id=None,
        name="agent",
        avatar=None,
        description="current",
        status="published",
        scope="admin_only",
        execution_mode="conversation",
        is_system=False,
        published_version=None,
        welcome_message=None,
        suggested_questions=None,
        input_variables=input_variables,
        created_at=None,
        updated_at=None,
        model=None,
        skill_grants=[],
    )

    item = build_agent_base_item(agent)

    assert item["input_variables"] == input_variables


def test_build_agent_base_item_filters_deleted_and_inactive_skills():
    active_skill = SimpleNamespace(
        id=10, name="active", is_deleted=False, is_active=True
    )
    deleted_skill = SimpleNamespace(
        id=11, name="deleted", is_deleted=True, is_active=True
    )
    inactive_skill = SimpleNamespace(
        id=12, name="inactive", is_deleted=False, is_active=False
    )
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
        name="active-agent",
        avatar=None,
        description="current",
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


def test_build_agent_base_item_derives_owner_type_from_owner_tenant_id_only():
    agent = SimpleNamespace(
        id=1,
        tenant_id=None,
        owner_tenant_id=None,
        owner_type="tenant",
        name="platform-agent",
        avatar=None,
        description=None,
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
        skill_grants=[],
    )

    item = build_agent_base_item(agent)

    assert item["owner_type"] == "platform"
    assert item["tenant_id"] is None
    assert item["owner_tenant_id"] is None


def test_build_agent_base_item_includes_skill_package_summary():
    package = SimpleNamespace(id=7, name="Research Pack")
    skill = SimpleNamespace(
        id=10,
        name="Search",
        package=package,
        package_id=7,
        type="toolkit",
        is_deleted=False,
        is_active=True,
    )
    agent = SimpleNamespace(
        id=1,
        tenant_id=None,
        name="agent-with-package",
        avatar=None,
        description=None,
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
        skill_grants=[SimpleNamespace(skill=skill, is_deleted=False, enabled=True)],
    )

    item = build_agent_base_item(agent)

    assert item["skills"] == [
        {
            "id": 10,
            "name": "Search",
            "package_id": 7,
            "package_name": "Research Pack",
            "type": "toolkit",
        }
    ]


def test_build_agent_base_item_includes_enabled_knowledge_base_summary():
    knowledge_base = SimpleNamespace(id=21, name="FAQ 库", is_deleted=False)
    disabled_knowledge_base = SimpleNamespace(id=22, name="旧库", is_deleted=False)
    agent = SimpleNamespace(
        id=1,
        tenant_id=None,
        name="agent-with-kb",
        avatar=None,
        description=None,
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
        skill_grants=[],
        kb_bindings=[
            SimpleNamespace(
                knowledge_base=knowledge_base,
                knowledge_base_id=21,
                is_deleted=False,
                enabled=True,
            ),
            SimpleNamespace(
                knowledge_base=disabled_knowledge_base,
                knowledge_base_id=22,
                is_deleted=False,
                enabled=False,
            ),
        ],
    )

    item = build_agent_base_item(agent)

    assert item["knowledge_base_ids"] == [21]
    assert item["knowledge_bases"] == [
        {
            "enabled": True,
            "knowledge_base_id": 21,
            "kb_name": "FAQ 库",
            "name": "FAQ 库",
        }
    ]
