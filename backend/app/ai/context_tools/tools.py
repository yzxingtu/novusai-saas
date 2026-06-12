"""
System context tool definitions.

These tools expose knowledge-base search and long-term memory operations to the
LLM as normal tool calls. They are code-defined runtime builtins, separate from
the internal-ops API meta-tools because they operate on agent context rather
than management-console APIs.
"""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition, ToolParameter
from app.enums.agent import ToolTypeEnum

CONTEXT_TOOLS_BUILTIN_TYPE = "context_tools"
CONTEXT_TOOLS_SEMANTIC_FAMILY = "context_tools"

TOOL_SEARCH_AGENT_KNOWLEDGE_BASE = "search_agent_knowledge_base"
TOOL_SAVE_LONG_TERM_MEMORY = "save_long_term_memory"
TOOL_RECALL_LONG_TERM_MEMORY = "recall_long_term_memory"

CONTEXT_TOOLS_SEMANTIC_TAGS: list[str] = [
    "知识库",
    "资料",
    "文档",
    "检索",
    "查找",
    "记住",
    "记忆",
    "回忆",
    "偏好",
    "约束",
    "事实",
    "knowledge base",
    "documents",
    "search",
    "memory",
    "remember",
    "recall",
]


def build_context_tool_definitions(
    *,
    skill: Any | None = None,
    config: dict[str, Any] | None = None,
) -> list[ToolDefinition]:
    base_config = dict(config or {})
    base_config["builtin_type"] = CONTEXT_TOOLS_BUILTIN_TYPE
    configured_tools = base_config.get("tools")
    allowed_tool_names = {
        str(item or "").strip()
        for item in configured_tools
        if str(item or "").strip()
    } if isinstance(configured_tools, list) else set()

    common: dict[str, Any] = {
        "tool_type": ToolTypeEnum.CONTEXT_TOOL.value,
        "config": base_config,
        "enabled": True,
        "source_skill_id": getattr(skill, "id", None),
        "source_skill_name": getattr(skill, "name", None) or "system_context_tools",
        "source_skill_type": getattr(skill, "type", None) or "builtin",
        "semantic_family": CONTEXT_TOOLS_SEMANTIC_FAMILY,
        "semantic_tags": list(CONTEXT_TOOLS_SEMANTIC_TAGS),
    }

    search_kb = ToolDefinition(
        name=TOOL_SEARCH_AGENT_KNOWLEDGE_BASE,
        description=(
            "Search the knowledge bases bound to the current agent. Use this "
            "when the answer may depend on project docs, uploaded files, "
            "policies, URLs, or domain knowledge not already present in the "
            "conversation. The tool returns matching snippets and citation "
            "sources; use the returned evidence when answering."
        ),
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                description="The focused search query to run against bound KBs.",
                required=True,
            ),
            ToolParameter(
                name="top_k",
                type="integer",
                description="Maximum snippets to return. Defaults to agent RAG config.",
                required=False,
            ),
        ],
        timeout=45,
        **common,
    )

    save_memory = ToolDefinition(
        name=TOOL_SAVE_LONG_TERM_MEMORY,
        description=(
            "Save durable user memory for this agent when the user explicitly "
            "asks you to remember something, or when an important stable "
            "preference, constraint, decision, or fact should be preserved for "
            "future turns. Do not save transient chit-chat."
        ),
        parameters=[
            ToolParameter(
                name="content",
                type="string",
                description="The concise memory text to save.",
                required=True,
            ),
            ToolParameter(
                name="memory_type",
                type="string",
                description="Memory category.",
                required=False,
                enum=[
                    "preference",
                    "constraint",
                    "fact",
                    "decision",
                    "pattern",
                    "task_summary",
                    "correction",
                    "relationship",
                ],
            ),
        ],
        timeout=30,
        **common,
    )

    recall_memory = ToolDefinition(
        name=TOOL_RECALL_LONG_TERM_MEMORY,
        description=(
            "Recall durable memory saved for this user and agent. Use this "
            "when the user asks what you remember, references previous "
            "preferences or constraints, or the answer may depend on stable "
            "memory from earlier turns."
        ),
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                description="The memory recall query.",
                required=True,
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="Maximum memory records to return. Defaults to 5.",
                required=False,
            ),
        ],
        timeout=30,
        **common,
    )

    tools = [search_kb, save_memory, recall_memory]
    if allowed_tool_names:
        return [tool for tool in tools if tool.name in allowed_tool_names]
    return tools


__all__ = [
    "CONTEXT_TOOLS_BUILTIN_TYPE",
    "CONTEXT_TOOLS_SEMANTIC_FAMILY",
    "TOOL_RECALL_LONG_TERM_MEMORY",
    "TOOL_SAVE_LONG_TERM_MEMORY",
    "TOOL_SEARCH_AGENT_KNOWLEDGE_BASE",
    "build_context_tool_definitions",
]
