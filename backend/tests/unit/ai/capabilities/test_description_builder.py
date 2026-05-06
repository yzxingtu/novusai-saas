"""
Test type: structural / behavioral
Scope: CapabilityDescriptionBuilder item grouping, limits, and turn activation.
Mocked dependencies: none.
"""

import pytest

from app.ai.capabilities.description_builder import (
    CapabilityDescriptionBuilder,
)
from app.ai.skills.activation import TurnSkillActivation


class TestCapabilityDescriptionBuilder:
    """Test CapabilityDescriptionBuilder"""

    def test_build_skill_descriptions_empty(self):
        """Test with no skills"""
        builder = CapabilityDescriptionBuilder()
        result = builder.build_skill_descriptions(None)
        assert result == []

    def test_build_skill_descriptions_ignores_non_capability_pack_and_blank_names(
        self,
    ):
        """Test non-capability-pack descriptors and blank names are skipped"""

        class MockDescriptor:
            def __init__(
                self, name, description, kind="capability_pack", metadata=None
            ):
                self.name = name
                self.description = description
                self.kind = kind
                self.metadata = metadata or {}

        class MockSkillResult:
            def __init__(self):
                self.tools = []
                self.capability_descriptors = [
                    MockDescriptor(
                        name="",
                        description="Blank name should be ignored",
                    ),
                    MockDescriptor(
                        name="context_provider",
                        description="Not a capability pack",
                        kind="context_provider",
                    ),
                ]

        builder = CapabilityDescriptionBuilder()
        result = builder.build_skill_descriptions(MockSkillResult())

        assert result == []

    def test_build_skill_descriptions_skips_descriptor_only_skills_without_tools(self):
        """Test catalog-only descriptors do not appear as live skills"""

        class MockDescriptor:
            def __init__(
                self, name, description, kind="capability_pack", metadata=None
            ):
                self.name = name
                self.description = description
                self.kind = kind
                self.metadata = metadata or {}

        class MockSkillResult:
            def __init__(self):
                self.tools = []
                self.capability_descriptors = [
                    MockDescriptor(
                        name="catalog_only",
                        description="Pack metadata only",
                        metadata={"has_execution_tools": False},
                    ),
                    MockDescriptor(
                        name="live_skill",
                        description="Actually executable",
                        metadata={"has_execution_tools": True},
                    ),
                ]

        builder = CapabilityDescriptionBuilder()
        result = builder.build_skill_descriptions(MockSkillResult())

        assert len(result) == 1
        assert result[0].items == ["live_skill: Actually executable"]

    def test_build_skill_descriptions_infers_family_in_concise_mode(self):
        """Test family inference and concise output"""

        class MockDescriptor:
            def __init__(self, name, description, metadata=None):
                self.name = name
                self.description = description
                self.kind = "capability_pack"
                self.metadata = metadata or {}

        class MockSkillResult:
            def __init__(self):
                self.tools = []
                self.capability_descriptors = [
                    MockDescriptor("database_lookup", "Lookup records"),
                    MockDescriptor("policy_summary", "Summarize policy records"),
                    MockDescriptor("weather_helper", "Check the weather"),
                    MockDescriptor("date_helper", "Read the date"),
                    MockDescriptor("custom_helper", "General utility"),
                ]

        builder = CapabilityDescriptionBuilder(style="concise")
        result = builder.build_skill_descriptions(MockSkillResult())

        assert [desc.title for desc in result] == [
            "General Skills",
            "Weather Skills",
            "Time & Date Skills",
        ]
        assert result[0].items == [
            "database_lookup: Lookup records",
            "policy_summary: Summarize policy records",
            "custom_helper: General utility",
        ]
        assert result[1].items == ["weather_helper: Check the weather"]

    def test_build_knowledge_base_descriptions_empty(self):
        """Test with no knowledge bases"""
        builder = CapabilityDescriptionBuilder()
        result = builder.build_knowledge_base_descriptions([])
        assert result is None

    def test_build_knowledge_base_descriptions_detailed(self):
        """Test knowledge base descriptions in detailed style"""
        kb_bindings = [
            {
                "kb_id": 1,
                "kb_name": "产品文档库",
                "kb_description": "包含产品使用手册和API文档",
                "kb_document_count": 120,
            },
            {
                "kb_id": 2,
                "kb_name": "客户案例库",
                "kb_description": "客户成功案例和最佳实践",
                "kb_document_count": 45,
            },
        ]

        builder = CapabilityDescriptionBuilder(style="detailed")
        result = builder.build_knowledge_base_descriptions(kb_bindings)

        assert result is not None
        assert result.category == "knowledge_bases"
        assert result.title == "Knowledge Bases"
        assert len(result.items) == 2
        assert "产品文档库" in result.items[0]
        assert "120 documents" in result.items[0]
        assert "客户案例库" in result.items[1]
        assert "45 documents" in result.items[1]
        assert result.metadata["total_documents"] == 165

    def test_build_knowledge_base_descriptions_concise(self):
        """Test knowledge base descriptions in concise style"""
        kb_bindings = [
            {
                "kb_id": 1,
                "kb_name": "产品文档库",
                "kb_description": "包含产品使用手册和API文档",
                "kb_document_count": 120,
            },
        ]

        builder = CapabilityDescriptionBuilder(style="concise")
        result = builder.build_knowledge_base_descriptions(kb_bindings)

        assert result is not None
        assert len(result.items) == 1
        assert result.items[0] == "产品文档库"

    def test_build_knowledge_base_descriptions_handles_sparse_metadata(self):
        """Test knowledge base descriptions with partial metadata"""
        kb_bindings = [
            {
                "kb_id": 1,
                "kb_name": "",
                "kb_description": "should be skipped",
                "kb_document_count": 99,
            },
            {
                "kb_id": 2,
                "kb_name": "FAQ",
                "kb_description": "Common answers",
                "kb_document_count": 0,
            },
            {
                "kb_id": 3,
                "kb_name": "Playbooks",
                "kb_description": "",
                "kb_document_count": 5,
            },
            {
                "kb_id": 4,
                "kb_name": "Policies",
                "kb_description": "",
                "kb_document_count": 0,
            },
        ]

        builder = CapabilityDescriptionBuilder(style="detailed")
        result = builder.build_knowledge_base_descriptions(kb_bindings)

        assert result is not None
        assert result.items == [
            "FAQ: Common answers",
            "Playbooks (5 documents)",
            "Policies",
        ]
        assert result.metadata["total_documents"] == 5

    def test_build_knowledge_base_descriptions_returns_none_when_names_are_blank(self):
        """Test blank knowledge base names produce no description"""
        builder = CapabilityDescriptionBuilder()
        result = builder.build_knowledge_base_descriptions(
            [
                {
                    "kb_id": 1,
                    "kb_name": "",
                    "kb_description": "ignored",
                    "kb_document_count": 1,
                }
            ]
        )

        assert result is None

    def test_build_memory_description_none(self):
        """Test with no memory enabled"""
        builder = CapabilityDescriptionBuilder()
        result = builder.build_memory_description(
            memory_enabled=False,
            long_term_memory_enabled=False,
        )
        assert result is None

    def test_build_memory_description_session_only(self):
        """Test with session memory only"""
        builder = CapabilityDescriptionBuilder()
        result = builder.build_memory_description(
            memory_enabled=True,
            long_term_memory_enabled=False,
        )

        assert result is not None
        assert result.category == "memory"
        assert len(result.items) == 1
        assert "Session memory" in result.items[0]

    def test_build_memory_description_both(self):
        """Test with both memory types enabled"""
        builder = CapabilityDescriptionBuilder()
        result = builder.build_memory_description(
            memory_enabled=True,
            long_term_memory_enabled=True,
        )

        assert result is not None
        assert len(result.items) == 2
        assert "Session memory" in result.items[0]
        assert "Long-term memory" in result.items[1]

    def test_max_items_per_category_limit(self):
        """Test that max_items_per_category is respected"""

        class MockDescriptor:
            def __init__(self, name):
                self.name = name
                self.description = f"Description for {name}"
                self.kind = "capability_pack"
                self.metadata = {"family": "test"}

        class MockSkillResult:
            def __init__(self, count):
                self.tools = []
                self.capability_descriptors = [
                    MockDescriptor(f"skill_{i}") for i in range(count)
                ]

        builder = CapabilityDescriptionBuilder(max_items_per_category=5)
        result = builder.build_skill_descriptions(MockSkillResult(10))

        assert len(result) == 1
        assert len(result[0].items) == 5  # Limited to 5
        assert result[0].metadata["total_count"] == 10
        assert result[0].metadata["displayed_count"] == 5

    def test_turn_activation_suppresses_unactivated_skill_inventory(self):
        """
        中文: 测试类型 behavioral；普通回合不会把全量技能库存写进能力描述。
        EN: Test type behavioral; ordinary turns do not describe the full skill inventory.
        """

        class MockDescriptor:
            def __init__(self, name, description):
                self.name = name
                self.description = description
                self.kind = "capability_pack"
                self.metadata = {
                    "family": "general",
                    "has_execution_tools": True,
                }

        class MockSkillResult:
            def __init__(self):
                self.tools = []
                self.capability_descriptors = [
                    MockDescriptor("live_skill", "Actually executable")
                ]
                self.turn_activation = TurnSkillActivation(
                    applied=False,
                    reason="no_turn_skill_activation",
                )

        builder = CapabilityDescriptionBuilder()
        result = builder.build_skill_descriptions(MockSkillResult())

        assert result == []

    def test_turn_activation_filters_to_selected_skill_names(self):
        """
        中文: 测试类型 behavioral；显式激活时只描述本轮选中的技能。
        EN: Test type behavioral; applied activation only describes turn-selected skills.
        """

        class MockDescriptor:
            def __init__(self, name, description):
                self.name = name
                self.description = description
                self.kind = "capability_pack"
                self.metadata = {
                    "family": "general",
                    "has_execution_tools": True,
                }

        class MockSkillResult:
            def __init__(self):
                self.tools = []
                self.capability_descriptors = [
                    MockDescriptor("active_skill", "Active description"),
                    MockDescriptor("inactive_skill", "Inactive description"),
                ]
                self.turn_activation = TurnSkillActivation(
                    applied=True,
                    activated_skill_names=["active_skill"],
                    reason="requested_skill_selection",
                )

        builder = CapabilityDescriptionBuilder()
        result = builder.build_skill_descriptions(MockSkillResult())

        assert len(result) == 1
        assert result[0].items == ["active_skill: Active description"]

    def test_build_prompt_sections_preserves_counts_for_template(self):
        """中文: 测试类型 structural。EN: Test type structural."""
        builder = CapabilityDescriptionBuilder(max_items_per_category=1)
        description = builder.build_knowledge_base_descriptions(
            [
                {
                    "kb_id": 1,
                    "kb_name": "产品文档库",
                    "kb_description": "API docs",
                    "kb_document_count": 12,
                },
                {
                    "kb_id": 2,
                    "kb_name": "政策库",
                    "kb_description": "Policies",
                    "kb_document_count": 8,
                },
            ]
        )
        assert description is not None

        sections = builder.build_prompt_sections([description])

        assert sections == [
            {
                "category": "knowledge_bases",
                "title": "Knowledge Bases",
                "items": ["产品文档库: API docs (12 documents)"],
                "total_count": 2,
                "displayed_count": 1,
                "omitted_count": 1,
            }
        ]

    def test_knowledge_base_totals_ignore_blank_names_before_limiting(self):
        """
        中文: 测试类型 behavioral；知识库统计先过滤有效绑定再按租户上限展示。
        EN: Test type behavioral; KB totals filter valid bindings before tenant display limits.
        """
        builder = CapabilityDescriptionBuilder(max_items_per_category=1)
        description = builder.build_knowledge_base_descriptions(
            [
                {
                    "kb_id": 0,
                    "kb_name": "",
                    "kb_description": "blank should not count",
                    "kb_document_count": 99,
                },
                {
                    "kb_id": 1,
                    "kb_name": "产品文档库",
                    "kb_description": "API docs",
                    "kb_document_count": 12,
                },
                {
                    "kb_id": 2,
                    "kb_name": "政策库",
                    "kb_description": "Policies",
                    "kb_document_count": 8,
                },
            ]
        )

        assert description is not None
        assert description.items == ["产品文档库: API docs (12 documents)"]
        assert description.metadata["total_count"] == 2
        assert description.metadata["displayed_count"] == 1
        assert description.metadata["total_documents"] == 20
        assert description.metadata["displayed_documents"] == 12

    def test_memory_description_uses_policy_degraded_state(self):
        """
        中文: 测试类型 behavioral；记忆能力描述使用运行时策略而不是原始开关夸大能力。
        EN: Test type behavioral; memory descriptions use runtime policy instead of overstating raw flags.
        """
        builder = CapabilityDescriptionBuilder()
        description = builder.build_memory_description(
            memory_enabled=True,
            long_term_memory_enabled=True,
            memory_policy={
                "session_memory_runtime_enabled": True,
                "session_memory_read_enabled": False,
                "session_memory_write_enabled": False,
                "session_memory_state": "runtime_without_scope",
                "long_term_memory_runtime_enabled": True,
                "long_term_memory_recall_enabled": False,
                "long_term_memory_recall_state": "suppressed_external_context",
                "external_context_reason": "external_context_polluted",
            },
        )

        assert description is not None
        assert "Session memory: Degraded (runtime_without_scope)" in description.items
        assert (
            "Long-term memory: Degraded (suppressed_external_context; external_context_polluted)"
            in description.items
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
