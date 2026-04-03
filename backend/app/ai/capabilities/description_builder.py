"""
Capability Description Builder / 能力描述构建器

Converts skills, knowledge bases, and other capabilities into natural language
descriptions that LLMs can understand.
将技能、知识库等能力信息转换为 LLM 可理解的自然语言描述。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CapabilityDescription:
    """
    Capability description / 能力描述

    Represents a category of capabilities (skills, knowledge bases, etc.)
    with a title and list of items.
    表示一类能力（技能、知识库等），包含标题和项目列表。
    """

    category: str  # skills / knowledge_bases / page_context / memory
    title: str
    items: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class CapabilityDescriptionBuilder:
    """
    Capability description builder / 能力描述构建器

    Builds natural language descriptions of agent capabilities for LLM context.
    为 LLM 上下文构建智能体能力的自然语言描述。
    """

    def __init__(
        self,
        *,
        style: str = "detailed",
        max_items_per_category: int = 20,
    ) -> None:
        """
        Args:
            style: Description style - "detailed" or "concise"
            max_items_per_category: Maximum items per category (prevents prompt bloat)
        """
        self.style = style
        self.max_items_per_category = max_items_per_category

    def build_skill_descriptions(
        self,
        skill_result: Any,
    ) -> list[CapabilityDescription]:
        """
        Build skill descriptions from SkillResolveResult.
        从 SkillResolveResult 构建技能描述。

        Args:
            skill_result: SkillResolveResult instance with tools and capability_descriptors

        Returns:
            List of CapabilityDescription, grouped by skill family
        """
        if not skill_result:
            return []

        tools = list(getattr(skill_result, "tools", []) or [])
        descriptors = list(getattr(skill_result, "capability_descriptors", []) or [])

        if not tools and not descriptors:
            return []

        # Group skills by family
        skill_groups: dict[str, list[str]] = {}

        for descriptor in descriptors:
            if descriptor.kind != "prompt_skill":
                continue

            skill_name = str(descriptor.name or "").strip()
            if not skill_name:
                continue

            # Determine skill family
            family = self._determine_skill_family(descriptor)

            # Build skill description
            skill_desc = self._build_single_skill_description(descriptor)

            if family not in skill_groups:
                skill_groups[family] = []

            skill_groups[family].append(skill_desc)

        # Convert to CapabilityDescription list
        descriptions: list[CapabilityDescription] = []

        for family, items in skill_groups.items():
            # Limit items per category
            limited_items = items[: self.max_items_per_category]

            descriptions.append(
                CapabilityDescription(
                    category="skills",
                    title=self._format_skill_family_title(family),
                    items=limited_items,
                    metadata={
                        "family": family,
                        "total_count": len(items),
                        "displayed_count": len(limited_items),
                    },
                )
            )

        return descriptions

    def build_knowledge_base_descriptions(
        self,
        kb_bindings: list[dict[str, Any]],
    ) -> CapabilityDescription | None:
        """
        Build knowledge base descriptions from bindings.
        从知识库绑定构建知识库描述。

        Args:
            kb_bindings: List of knowledge base binding dicts with:
                - kb_id: Knowledge base ID
                - kb_name: Knowledge base name
                - kb_description: Knowledge base description
                - kb_document_count: Number of documents

        Returns:
            CapabilityDescription or None if no bindings
        """
        if not kb_bindings:
            return None

        items: list[str] = []
        total_documents = 0

        for binding in kb_bindings[: self.max_items_per_category]:
            kb_name = str(binding.get("kb_name") or "").strip()
            kb_description = str(binding.get("kb_description") or "").strip()
            kb_document_count = int(binding.get("kb_document_count") or 0)

            if not kb_name:
                continue

            # Build description
            if self.style == "detailed":
                if kb_description and kb_document_count > 0:
                    item = (
                        f"{kb_name}: {kb_description} ({kb_document_count} documents)"
                    )
                elif kb_description:
                    item = f"{kb_name}: {kb_description}"
                elif kb_document_count > 0:
                    item = f"{kb_name} ({kb_document_count} documents)"
                else:
                    item = kb_name
            else:  # concise
                item = kb_name

            items.append(item)
            total_documents += kb_document_count

        if not items:
            return None

        return CapabilityDescription(
            category="knowledge_bases",
            title="Knowledge Bases",
            items=items,
            metadata={
                "total_count": len(kb_bindings),
                "displayed_count": len(items),
                "total_documents": total_documents,
            },
        )

    def build_page_context_description(
        self,
        page_context: dict[str, Any] | None,
    ) -> CapabilityDescription | None:
        """
        Build page context description.
        从页面上下文构建描述。

        Args:
            page_context: Page context dict with:
                - page_key: Page identifier
                - page_title: Page title
                - page_data: Page data with available_operations

        Returns:
            CapabilityDescription or None if no page context
        """
        if not page_context:
            return None

        page_key = str(page_context.get("page_key") or "").strip()
        page_title = str(page_context.get("page_title") or "").strip()
        page_data = page_context.get("page_data")

        if not page_key and not page_title:
            return None

        items: list[str] = []

        # Add page info
        if page_title:
            items.append(f"Current page: {page_title}")
        elif page_key:
            items.append(f"Current page: {page_key}")

        # Add available operations
        if isinstance(page_data, dict):
            operations = page_data.get("available_operations", [])
            if operations:
                operation_names = [
                    str(op.get("name") or "").strip()
                    for op in operations
                    if isinstance(op, dict) and op.get("name")
                ]
                if operation_names:
                    items.append(
                        f"Available operations: {', '.join(operation_names[:10])}"
                    )

        if not items:
            return None

        return CapabilityDescription(
            category="page_context",
            title="Current Page Context",
            items=items,
            metadata={"page_key": page_key, "page_title": page_title},
        )

    def build_memory_description(
        self,
        memory_enabled: bool,
        long_term_memory_enabled: bool,
    ) -> CapabilityDescription | None:
        """
        Build memory capability description.
        从记忆配置构建描述。

        Args:
            memory_enabled: Whether session memory is enabled
            long_term_memory_enabled: Whether long-term memory is enabled

        Returns:
            CapabilityDescription or None if no memory enabled
        """
        if not memory_enabled and not long_term_memory_enabled:
            return None

        items: list[str] = []

        if memory_enabled:
            items.append(
                "Session memory: Enabled (maintains conversation context within this session)"
            )

        if long_term_memory_enabled:
            items.append(
                "Long-term memory: Enabled (recalls user preferences and history across sessions)"
            )

        return CapabilityDescription(
            category="memory",
            title="Memory Capabilities",
            items=items,
            metadata={
                "session_memory": memory_enabled,
                "long_term_memory": long_term_memory_enabled,
            },
        )

    def format_as_system_prompt_block(
        self,
        descriptions: list[CapabilityDescription],
    ) -> str:
        """
        Format capability descriptions as a system prompt block.
        将能力描述格式化为 system prompt 区块。

        Args:
            descriptions: List of CapabilityDescription

        Returns:
            Formatted system prompt block
        """
        if not descriptions:
            return ""

        lines: list[str] = [
            "",
            "---",
            "[CAPABILITIES]",
            "You have access to the following capabilities:",
            "",
        ]

        for desc in descriptions:
            # Add category title
            lines.append(f"## {desc.title}")

            # Add items
            for item in desc.items:
                lines.append(f"- {item}")

            lines.append("")  # Empty line between categories

        # Add usage instructions
        lines.extend(
            [
                "When the user asks questions, you should:",
                "1. Check if any of your skills can help answer the question",
                "2. Search relevant knowledge bases for information",
                "3. Use tools proactively instead of saying 'I cannot do that'",
                "4. If you have page context, use available operations to interact with the page",
            ]
        )

        return "\n".join(lines)

    # ========================================
    # Helper Methods / 辅助方法
    # ========================================

    def _determine_skill_family(self, descriptor: Any) -> str:
        """
        Determine skill family from descriptor.
        从描述符确定技能家族。
        """
        metadata = getattr(descriptor, "metadata", {}) or {}
        family = metadata.get("family")

        if family:
            return str(family).strip()

        # Fallback: infer from skill name
        skill_name = str(descriptor.name or "").lower()

        if "data" in skill_name or "query" in skill_name or "database" in skill_name:
            return "data_intelligence"
        if "web" in skill_name or "search" in skill_name or "fetch" in skill_name:
            return "web_research"
        if "weather" in skill_name:
            return "weather"
        if "time" in skill_name or "date" in skill_name:
            return "time"

        return "general"

    def _format_skill_family_title(self, family: str) -> str:
        """
        Format skill family as a readable title.
        将技能家族格式化为可读标题。
        """
        family_titles = {
            "data_intelligence": "Data Intelligence Skills",
            "web_research": "Web Research Skills",
            "weather": "Weather Skills",
            "time": "Time & Date Skills",
            "general": "General Skills",
        }

        return family_titles.get(family, family.replace("_", " ").title())

    def _build_single_skill_description(self, descriptor: Any) -> str:
        """
        Build description for a single skill.
        为单个技能构建描述。
        """
        skill_name = str(descriptor.name or "").strip()
        skill_description = str(descriptor.description or "").strip()
        metadata = getattr(descriptor, "metadata", {}) or {}

        if self.style == "concise":
            return (
                f"{skill_name}: {skill_description}"
                if skill_description
                else skill_name
            )

        # Detailed style: include metadata hints
        parts = [skill_name]

        if skill_description:
            parts.append(skill_description)

        # Add table hints for data skills
        if "available_tables" in metadata:
            tables = metadata["available_tables"]
            if tables:
                table_names = [
                    f"{t.get('name')}({t.get('comment', '')})"
                    if t.get("comment")
                    else t.get("name")
                    for t in tables[:5]  # Limit to 5 tables
                    if isinstance(t, dict) and t.get("name")
                ]
                if table_names:
                    parts.append(f"Available tables: {', '.join(table_names)}")

        # Add operation hints for data modification skills
        if "allowed_operations" in metadata:
            operations = metadata["allowed_operations"]
            if operations:
                parts.append(f"Allowed operations: {', '.join(operations)}")

        return ": ".join(parts) if len(parts) > 1 else parts[0]
