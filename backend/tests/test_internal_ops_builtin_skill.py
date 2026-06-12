"""
Issue #22: 运营 Copilot 内置技能包接入完整性测试
Test type: behavioral
Scope: internal_ops builtin skill test executor + resolver
Real dependencies: build_internal_ops_tool_definitions, resolve_builtin, _test_builtin
Mocked dependencies: Skill model via SimpleNamespace
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.internal_ops.tools import (
    INTERNAL_OPS_BUILTIN_TYPE,
    TOOL_DESCRIBE_OPERATION,
    TOOL_INVOKE_OPERATION,
    TOOL_LIST_OPERATIONS,
    build_internal_ops_tool_definitions,
)
from app.ai.skills.resolver_parts.builtin import resolve_builtin
from app.api.shared._skill_test import _test_builtin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_internal_ops_skill(**overrides):
    """Build a minimal skill namespace for internal_ops tests."""
    defaults = dict(
        id=42,
        name="internal_ops_skill",
        type="builtin",
        timeout=30,
        input_schema=None,
        description="Internal operations meta-tool skill",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_resolve_result():
    """Build a minimal resolve result namespace."""
    return SimpleNamespace(
        tools=[],
        tool_consent_modes={},
        capability_descriptors=[],
        warnings=[],
        resolution_issues=[],
    )


# ---------------------------------------------------------------------------
# build_internal_ops_tool_definitions
# ---------------------------------------------------------------------------

class TestBuildInternalOpsToolDefinitions:
    def test_returns_three_meta_tools(self):
        tools = build_internal_ops_tool_definitions()
        assert len(tools) == 3
        names = {t.name for t in tools}
        assert names == {
            TOOL_LIST_OPERATIONS,
            TOOL_DESCRIBE_OPERATION,
            TOOL_INVOKE_OPERATION,
        }

    def test_tool_type_is_internal_api(self):
        tools = build_internal_ops_tool_definitions()
        for tool in tools:
            assert tool.tool_type == "internal_api"

    def test_passes_skill_id_and_name(self):
        skill = _make_internal_ops_skill(id=99, name="my_ops")
        tools = build_internal_ops_tool_definitions(skill=skill)
        for tool in tools:
            assert tool.source_skill_id == 99
            assert tool.source_skill_name == "my_ops"


# ---------------------------------------------------------------------------
# _test_builtin (skill test executor)
# ---------------------------------------------------------------------------

class TestBuiltinTestExecutor:
    """Test _test_builtin() for internal_ops code-defined builtin skills."""

    def test_internal_ops_skill_passes(self):
        skill = _make_internal_ops_skill()
        config = {"builtin_type": INTERNAL_OPS_BUILTIN_TYPE}
        result = _test_builtin(skill, config)
        assert result["success"] is True
        assert result["details"]["tool_count"] == 3
        assert set(result["details"]["tool_names"]) == {
            TOOL_LIST_OPERATIONS,
            TOOL_DESCRIBE_OPERATION,
            TOOL_INVOKE_OPERATION,
        }

    def test_regular_builtin_still_works(self):
        skill = _make_internal_ops_skill()
        config = {"builtin_name": "get_current_time"}
        result = _test_builtin(skill, config)
        assert result["success"] is True
        assert result["details"]["builtin_name"] == "get_current_time"

    def test_builtin_without_name_fails(self):
        skill = _make_internal_ops_skill()
        config = {}
        result = _test_builtin(skill, config)
        assert result["success"] is False

    def test_import_path_is_shared_not_admin(self):
        """Verify _test_builtin is importable from shared module (Issue #22 fix)."""
        from app.api.shared._skill_test import test_skill  # noqa: F401


# ---------------------------------------------------------------------------
# resolve_builtin (SkillResolver builtin part)
# ---------------------------------------------------------------------------

class TestResolveBuiltinInternalOps:
    """Test resolve_builtin() for internal_ops code-defined builtin skills."""

    def test_resolves_three_tools(self):
        skill = _make_internal_ops_skill()
        config = {"builtin_type": INTERNAL_OPS_BUILTIN_TYPE}
        result = _make_resolve_result()
        resolve_builtin(
            skill=skill,
            config=config,
            result=result,
            build_params_from_schema=lambda p: [],
        )
        assert len(result.tools) == 3
        names = {t.name for t in result.tools}
        assert names == {
            TOOL_LIST_OPERATIONS,
            TOOL_DESCRIBE_OPERATION,
            TOOL_INVOKE_OPERATION,
        }

    def test_regular_builtin_config_tools_still_works(self):
        skill = _make_internal_ops_skill()
        config = {
            "tools": [
                {"name": "custom_tool", "description": "A custom tool"},
            ]
        }
        result = _make_resolve_result()
        resolve_builtin(
            skill=skill,
            config=config,
            result=result,
            build_params_from_schema=lambda p: [],
        )
        assert len(result.tools) == 1
        assert result.tools[0].name == "custom_tool"

    def test_internal_ops_does_not_pollute_config_tools_path(self):
        """internal_ops branch must return early, not fall through to config.tools."""
        skill = _make_internal_ops_skill()
        # Even if config has tools key, internal_ops should use code-defined tools
        config = {
            "builtin_type": INTERNAL_OPS_BUILTIN_TYPE,
            "tools": [{"name": "should_not_appear"}],
        }
        result = _make_resolve_result()
        resolve_builtin(
            skill=skill,
            config=config,
            result=result,
            build_params_from_schema=lambda p: [],
        )
        names = {t.name for t in result.tools}
        assert "should_not_appear" not in names
        assert len(result.tools) == 3
