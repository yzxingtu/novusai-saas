"""
Capability Description Builder / 能力描述构建器

Converts skills, knowledge bases, and other capabilities into natural language
descriptions that LLMs can understand.
将技能、知识库等能力信息转换为 LLM 可理解的自然语言描述。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.ai.runtime.types import capability_pack_descriptor_is_live
from app.ai.skills.activation import activated_tools_for_turn
from app.ai.tools.semantic_defaults import normalize_semantic_family


@dataclass
class CapabilityDescription:
    """
    Capability description / 能力描述

    Represents a category of capabilities (skills, knowledge bases, etc.)
    with a title and list of items.
    表示一类能力（技能、知识库等），包含标题和项目列表。
    """

    category: str  # skills / knowledge_bases / memory
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

        tools = list(activated_tools_for_turn(skill_result))
        descriptors = list(getattr(skill_result, "capability_descriptors", []) or [])
        activation = getattr(skill_result, "turn_activation", None)
        if activation is not None and not activation.applied:
            tools = []
            descriptors = []
        elif activation is not None and activation.applied:
            activated_skill_names = {
                str(name or "").strip()
                for name in activation.activated_skill_names or []
                if str(name or "").strip()
            }
            if activated_skill_names:
                descriptors = [
                    descriptor
                    for descriptor in descriptors
                    if str(getattr(descriptor, "name", "") or "").strip()
                    in activated_skill_names
                ]
            else:
                descriptors = []

        if not tools and not descriptors:
            return []

        if not descriptors and tools:
            return self._build_skill_descriptions_from_tools(tools)

        # Group skills by family
        skill_groups: dict[str, list[str]] = {}

        for descriptor in descriptors:
            if not capability_pack_descriptor_is_live(descriptor):
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

    def _build_skill_descriptions_from_tools(
        self,
        tools: list[Any],
    ) -> list[CapabilityDescription]:
        skill_groups: dict[str, list[str]] = {}
        for tool in tools:
            skill_name = str(getattr(tool, "source_skill_name", "") or "").strip()
            if not skill_name:
                continue
            family = self._determine_tool_skill_family(tool)
            tool_name = str(getattr(tool, "name", "") or "").strip()
            if not tool_name:
                continue
            bucket = skill_groups.setdefault(family, [])
            item = f"{skill_name}: exposes {tool_name}"
            if item not in bucket:
                bucket.append(item)

        descriptions: list[CapabilityDescription] = []
        for family, items in skill_groups.items():
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

    @staticmethod
    def _determine_tool_skill_family(tool: Any) -> str:
        family = CapabilityDescriptionBuilder._normalize_skill_family(
            getattr(tool, "semantic_family", None)
        )
        if family:
            return family
        family = CapabilityDescriptionBuilder._infer_family_from_text(
            getattr(tool, "description", None)
        )
        if family:
            return family
        package_name = str(getattr(tool, "source_package_name", "") or "").strip()
        skill_type = str(getattr(tool, "source_skill_type", "") or "").strip()
        if package_name.startswith("plugin."):
            return "plugin"
        if skill_type:
            return skill_type
        return "general"

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

        valid_bindings: list[dict[str, Any]] = []
        total_documents = 0
        for binding in kb_bindings:
            kb_name = str(binding.get("kb_name") or "").strip()
            if not kb_name:
                continue
            valid_bindings.append(binding)
            total_documents += int(binding.get("kb_document_count") or 0)

        items: list[str] = []
        displayed_documents = 0
        for binding in valid_bindings[: self.max_items_per_category]:
            kb_name = str(binding.get("kb_name") or "").strip()
            kb_description = str(binding.get("kb_description") or "").strip()
            kb_document_count = int(binding.get("kb_document_count") or 0)

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
            displayed_documents += kb_document_count

        if not items:
            return None

        return CapabilityDescription(
            category="knowledge_bases",
            title="Knowledge Bases",
            items=items,
            metadata={
                "total_count": len(valid_bindings),
                "displayed_count": len(items),
                "total_documents": total_documents,
                "displayed_documents": displayed_documents,
            },
        )

    def build_memory_description(
        self,
        memory_enabled: bool,
        long_term_memory_enabled: bool,
        memory_policy: dict[str, Any] | None = None,
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
        items: list[str] = []
        policy = dict(memory_policy or {})

        if policy:
            if bool(policy.get("session_memory_runtime_enabled")):
                if bool(policy.get("session_memory_read_enabled")) and bool(
                    policy.get("session_memory_write_enabled")
                ):
                    items.append(
                        "Session memory: Available (reads and writes facts within this conversation)"
                    )
                else:
                    state = str(
                        policy.get("session_memory_state") or "runtime_without_scope"
                    ).strip()
                    items.append(f"Session memory: Degraded ({state})")

            if bool(policy.get("long_term_memory_runtime_enabled")):
                if bool(policy.get("long_term_memory_recall_enabled")):
                    items.append(
                        "Long-term memory: Available (recalls durable user preferences and history)"
                    )
                else:
                    state = str(
                        policy.get("long_term_memory_recall_state") or "disabled"
                    ).strip()
                    reason = str(policy.get("external_context_reason") or "").strip()
                    suffix = f"{state}; {reason}" if reason else state
                    items.append(f"Long-term memory: Degraded ({suffix})")
        else:
            if memory_enabled:
                items.append(
                    "Session memory: Available (maintains conversation context within this session)"
                )

            if long_term_memory_enabled:
                items.append(
                    "Long-term memory: Available (recalls user preferences and history across sessions)"
                )

        if not items:
            return None

        return CapabilityDescription(
            category="memory",
            title="Memory Capabilities",
            items=items,
            metadata={
                "session_memory": memory_enabled,
                "long_term_memory": long_term_memory_enabled,
            },
        )

    def build_prompt_sections(
        self,
        descriptions: list[CapabilityDescription | Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        """中文: 从能力描述构建 prompt 模板可消费的段落结构。

        EN: Build prompt-template sections from capability descriptions.
        """
        sections: list[dict[str, Any]] = []
        for description in descriptions:
            category = self._extract_descriptor_category(description)
            title = self._extract_descriptor_title(description)
            items = self._extract_descriptor_items(description)
            if not items:
                continue
            metadata = self._extract_descriptor_metadata(description)
            total_count = self._coerce_count(metadata.get("total_count"), len(items))
            displayed_count = self._coerce_count(
                metadata.get("displayed_count"),
                len(items),
            )
            omitted_count = max(total_count - displayed_count, 0)
            sections.append(
                {
                    "category": category,
                    "title": title or category.replace("_", " ").title(),
                    "items": items,
                    "total_count": total_count,
                    "displayed_count": displayed_count,
                    "omitted_count": omitted_count,
                }
            )
        return sections

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

        family = self._family_from_descriptor_metadata(metadata)
        if family:
            return family

        family = self._infer_family_from_text(getattr(descriptor, "description", None))
        if family:
            return family

        # Fallback: infer platform-owned families from skill name.
        skill_name = str(descriptor.name or "").lower()

        if "time" in skill_name or "date" in skill_name:
            return "time"

        return "general"

    def _format_skill_family_title(self, family: str) -> str:
        """
        Format skill family as a readable title.
        将技能家族格式化为可读标题。
        """
        family_titles = {
            "time": "Time & Date Skills",
            "time_ops": "Time & Date Skills",
            "general": "General Skills",
        }

        if family in family_titles:
            return family_titles[family]
        label = family.replace("_", " ").title()
        if not label:
            return "Skills"
        return label if label.endswith("Skills") else f"{label} Skills"

    @staticmethod
    def _normalize_skill_family(value: Any) -> str:
        family = normalize_semantic_family(value)
        if not family or family == "none":
            return ""
        if family in {"time", "date", "time_ops", "date_ops"}:
            return "time"
        return family

    @classmethod
    def _family_from_descriptor_metadata(cls, metadata: Any) -> str:
        if not isinstance(metadata, Mapping):
            return ""
        direct_family = cls._normalize_skill_family(metadata.get("semantic_family"))
        if direct_family:
            return direct_family
        for key in (
            "semantic_families",
            "preview_semantic_families",
            "startup_preview_semantic_families",
            "resolved_semantic_families",
            "tool_semantic_families",
        ):
            raw_values = metadata.get(key)
            if not isinstance(raw_values, (list, tuple, set)):
                continue
            for raw_value in raw_values:
                family = cls._normalize_skill_family(raw_value)
                if family:
                    return family
        return ""

    @classmethod
    def _infer_family_from_text(cls, value: Any) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return ""
        if any(term in text for term in ("current date", "current time", "日期")):
            return "time"
        return ""

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

    @staticmethod
    def _extract_descriptor_title(
        desc: CapabilityDescription | Mapping[str, Any],
    ) -> str:
        if isinstance(desc, Mapping):
            title_value = desc.get("title")
        else:
            title_value = getattr(desc, "title", None)
        return str(title_value or "").strip()

    @staticmethod
    def _extract_descriptor_category(
        desc: CapabilityDescription | Mapping[str, Any],
    ) -> str:
        if isinstance(desc, Mapping):
            category_value = desc.get("category")
        else:
            category_value = getattr(desc, "category", None)
        return str(category_value or "").strip()

    @staticmethod
    def _extract_descriptor_metadata(
        desc: CapabilityDescription | Mapping[str, Any],
    ) -> dict[str, Any]:
        if isinstance(desc, Mapping):
            raw_metadata = desc.get("metadata")
        else:
            raw_metadata = getattr(desc, "metadata", None)
        return dict(raw_metadata or {}) if isinstance(raw_metadata, Mapping) else {}

    @staticmethod
    def _extract_descriptor_items(
        desc: CapabilityDescription | Mapping[str, Any],
    ) -> list[str]:
        if isinstance(desc, Mapping):
            raw_items = desc.get("items")
        else:
            raw_items = getattr(desc, "items", None)

        if callable(raw_items) and not isinstance(raw_items, (str, bytes)):
            try:
                raw_items = raw_items()
            except TypeError:
                raw_items = None

        if raw_items is None:
            return []

        if isinstance(raw_items, (str, bytes)):
            raw_items = [raw_items]

        try:
            iterable_items = list(raw_items)
        except TypeError:
            return []

        return [
            str(item or "").strip()
            for item in iterable_items
            if str(item or "").strip()
        ]

    @staticmethod
    def _coerce_count(value: Any, default: int) -> int:
        try:
            return max(int(value), 0)
        except (TypeError, ValueError):
            return max(int(default), 0)
