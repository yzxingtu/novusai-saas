"""Test type: structural / behavioral.

中文: 覆盖 AI 管理写入 schema 对旧运行时字段的 fail-close 行为。
EN: Covers fail-closed AI admin write schemas for retired runtime fields.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.ai.provider import AIProviderCreate, AIProviderUpdate
from app.schemas.ai.skill import SkillCreate, SkillUpdate
from app.schemas.ai.skill_package import SkillPackageCreate, SkillPackageUpdate


@pytest.mark.parametrize(
    ("schema_cls", "payload"),
    [
        (
            AIProviderCreate,
            {
                "name": "Provider",
                "type": "openai_compatible",
                "wire_api": "responses",
            },
        ),
        (AIProviderUpdate, {"allow_adapter_cross_protocol_fallback": True}),
        (
            SkillCreate,
            {
                "package_id": 1,
                "name": "Weather",
                "selected_tool_names": ["web_search"],
            },
        ),
        (SkillUpdate, {"preview_tool_names": ["fetch_url"]}),
        (SkillPackageCreate, {"name": "Online Search", "web_search": True}),
        (SkillPackageUpdate, {"search_provider": "legacy"}),
    ],
)
def test_ai_admin_write_schemas_reject_top_level_retired_runtime_fields(
    schema_cls,
    payload: dict,
) -> None:
    with pytest.raises(ValidationError):
        schema_cls(**payload)


@pytest.mark.parametrize(
    ("schema_cls", "payload"),
    [
        (
            AIProviderCreate,
            {
                "name": "Provider",
                "type": "openai_compatible",
                "config": {
                    "protocol_capabilities": {
                        "wire_api": "responses",
                    },
                },
            },
        ),
        (
            AIProviderUpdate,
            {
                "config": {
                    "allow_adapter_cross_protocol_fallback": True,
                },
            },
        ),
        (
            SkillCreate,
            {
                "package_id": 1,
                "name": "Skill",
                "config": {"selected_tool_names": ["web_search"]},
            },
        ),
        (
            SkillUpdate,
            {
                "toolkit_meta": {"preview_tool_names": ["fetch_url"]},
            },
        ),
        (
            SkillCreate,
            {
                "package_id": 1,
                "name": "Skill",
                "input_schema": {
                    "properties": {
                        "page_context": {"type": "object"},
                    },
                },
            },
        ),
        (
            SkillUpdate,
            {
                "toolkit_content": "class Tools:\n    def web_search(self):\n        pass\n",
            },
        ),
    ],
)
def test_ai_admin_write_schemas_reject_nested_retired_runtime_fields(
    schema_cls,
    payload: dict,
) -> None:
    with pytest.raises(ValidationError):
        schema_cls(**payload)
