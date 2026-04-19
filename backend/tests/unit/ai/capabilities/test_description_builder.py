"""
Unit tests for CapabilityDescriptionBuilder
能力描述构建器单元测试
"""

import pytest

from app.ai.capabilities.description_builder import (
    CapabilityDescriptionBuilder,
)


class TestCapabilityDescriptionBuilder:
    """Test CapabilityDescriptionBuilder"""

    def test_build_skill_descriptions_empty(self):
        """Test with no skills"""
        builder = CapabilityDescriptionBuilder()
        result = builder.build_skill_descriptions(None)
        assert result == []

    def test_build_skill_descriptions_web_research(self):
        """Test web research skill descriptions"""
        # Mock skill result
        class MockDescriptor:
            def __init__(self, name, description, kind="capability_pack", metadata=None):
                self.name = name
                self.description = description
                self.kind = kind
                self.metadata = metadata or {}

        class MockSkillResult:
            def __init__(self):
                self.tools = []
                self.capability_descriptors = [
                    MockDescriptor(
                        name="web_search",
                        description="Search the web for recent information",
                        metadata={
                            "family": "web_research",
                            "available_tables": [
                                {"name": "users", "comment": "用户"},
                                {"name": "agents", "comment": "智能体"},
                            ],
                        },
                    ),
                    MockDescriptor(
                        name="fetch_url",
                        description="Read webpage details",
                        metadata={
                            "family": "web_research",
                            "allowed_operations": ["fetch"],
                        },
                    ),
                ]

        builder = CapabilityDescriptionBuilder(style="detailed")
        result = builder.build_skill_descriptions(MockSkillResult())

        assert len(result) == 1
        assert result[0].category == "skills"
        assert result[0].title == "Web Research Skills"
        assert len(result[0].items) == 2
        assert "web_search" in result[0].items[0]
        assert "users(用户)" in result[0].items[0]
        assert "fetch_url" in result[0].items[1]

    def test_build_skill_descriptions_multiple_families(self):
        """Test skills from multiple families"""

        class MockDescriptor:
            def __init__(self, name, description, kind="capability_pack", metadata=None):
                self.name = name
                self.description = description
                self.kind = kind
                self.metadata = metadata or {}

        class MockSkillResult:
            def __init__(self):
                self.tools = []
                self.capability_descriptors = [
                    MockDescriptor(
                        name="web_search",
                        description="Search the web",
                        metadata={"family": "web_research"},
                    ),
                    MockDescriptor(
                        name="get_weather",
                        description="Get weather information",
                        metadata={"family": "weather"},
                    ),
                    MockDescriptor(
                        name="get_current_time",
                        description="Get current time",
                        metadata={"family": "time"},
                    ),
                ]

        builder = CapabilityDescriptionBuilder()
        result = builder.build_skill_descriptions(MockSkillResult())

        assert len(result) == 3
        families = {desc.metadata["family"] for desc in result}
        assert families == {"web_research", "weather", "time"}

    def test_build_skill_descriptions_ignores_non_prompt_and_blank_names(self):
        """Test non-prompt descriptors and blank names are skipped"""

        class MockDescriptor:
            def __init__(self, name, description, kind="capability_pack", metadata=None):
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
                        description="Not a prompt skill",
                        kind="context_provider",
                    ),
                ]

        builder = CapabilityDescriptionBuilder()
        result = builder.build_skill_descriptions(MockSkillResult())

        assert result == []

    def test_build_skill_descriptions_skips_descriptor_only_skills_without_tools(self):
        """Test catalog-only descriptors do not appear as live skills"""

        class MockDescriptor:
            def __init__(self, name, description, kind="capability_pack", metadata=None):
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
                    MockDescriptor("fetch_news", "Fetch the latest news"),
                    MockDescriptor("weather_helper", "Check the weather"),
                    MockDescriptor("date_helper", "Read the date"),
                    MockDescriptor("custom_helper", "General utility"),
                ]

        builder = CapabilityDescriptionBuilder(style="concise")
        result = builder.build_skill_descriptions(MockSkillResult())

        assert [desc.title for desc in result] == [
            "General Skills",
            "Web Research Skills",
            "Weather Skills",
            "Time & Date Skills",
        ]
        assert result[0].items == [
            "database_lookup: Lookup records",
            "custom_helper: General utility",
        ]
        assert result[1].items == ["fetch_news: Fetch the latest news"]

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

    def test_build_page_context_description_empty(self):
        """Test with no page context"""
        builder = CapabilityDescriptionBuilder()
        result = builder.build_page_context_description(None)
        assert result is None

    def test_build_page_context_description_with_thin_runtime_hints(self):
        """Test page context with thin runtime hints"""
        page_context = {
            "page_key": "user_management",
            "page_title": "用户管理页面",
            "active_surface_id": "drawer-user-edit",
            "active_form_summary": {
                "mode": "edit",
                "stage": "ready_to_submit",
            },
        }

        builder = CapabilityDescriptionBuilder()
        result = builder.build_page_context_description(page_context)

        assert result is not None
        assert result.category == "page_context"
        assert result.title == "Current Page Context"
        assert len(result.items) == 3
        assert "用户管理页面" in result.items[0]
        assert "Active surface: drawer-user-edit" in result.items[1]
        assert "Active form: mode=edit, stage=ready_to_submit" in result.items[2]

    def test_build_page_context_description_falls_back_to_page_key(self):
        """Test page key fallback when title is missing"""
        page_context = {
            "page_key": "admin.logs",
            "suggested_tools": {"primary": ["", "   "]},
        }

        builder = CapabilityDescriptionBuilder()
        result = builder.build_page_context_description(page_context)

        assert result is not None
        assert result.items == ["Current page: admin.logs"]

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
