"""
Issue #20 (PR #40 review): context_tools required fallback regression.

Test type: behavioral.

Original symptom: user sends "你好" (plain greeting) with context skill bound
but no effective knowledge base and long_term_memory_enabled=False. The system
promoted the direct_reply to context_tools_query with ToolUsePolicy(mode="required"),
forcing the model to call search_agent_knowledge_base / save_long_term_memory /
recall_long_term_memory before answering a simple greeting.

Expected: when context tools are only present via the unconditional default
fallback (no semantic match, no pending confirmation), they must remain
optional (mode="auto") so the model can freely answer with plain text.

Real dependencies: plan_execution_tools, _default_context_tools_for_direct_reply.
Mocked dependencies: none.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.ai.engine.prepare_execution_tool_helpers import plan_execution_tools
from app.ai.engine.types import ExecutionRequest, IntentPlan
from app.ai.tools.types import ToolDefinition


def _build_context_tools() -> list[ToolDefinition]:
    """Build the 3 context skill tools (same names as the real seed)."""
    return [
        ToolDefinition(
            name="search_agent_knowledge_base",
            description="Search the knowledge base bound to this agent.",
            semantic_family="context_tools",
            semantic_tags=["知识库", "knowledge base", "rag", "search"],
        ),
        ToolDefinition(
            name="save_long_term_memory",
            description="Save a fact to long-term memory.",
            semantic_family="context_tools",
            semantic_tags=["记忆", "memory", "save"],
        ),
        ToolDefinition(
            name="recall_long_term_memory",
            description="Recall facts from long-term memory.",
            semantic_family="context_tools",
            semantic_tags=["记忆", "memory", "recall"],
        ),
    ]


def _build_diagnostics_direct_reply() -> dict:
    return {
        "intent_plan": [
            IntentPlan(
                intent_id="intent-1",
                kind="direct_reply",
                family="none",
                order=1,
                user_visible_label="direct_reply",
                source_text="你好",
                requires_tools=False,
                shortcircuit=True,
            ).to_dict()
        ]
    }


def test_greeting_with_context_tools_no_required_fallback() -> None:
    """'你好' + context tools bound + no KB + no memory → must NOT be required."""
    context_tools = _build_context_tools()
    request = ExecutionRequest(agent_id=1, tenant_id=0, messages=[])
    messages = [SimpleNamespace(role="user", content="你好")]

    plan = plan_execution_tools(
        agent_id=1,
        conversation_id=100,
        request=request,
        messages=messages,  # type: ignore[arg-type]
        tools=list(context_tools),
        all_tools=list(context_tools),
        diagnostics=_build_diagnostics_direct_reply(),
    )

    # Policy must be auto, NOT required
    assert plan.tool_use_policy.mode == "auto"
    assert plan.tool_use_policy.family == "none"
    assert plan.tool_use_policy.reason == "direct_reply_optional_context_tools"
    assert plan.tool_use_policy.retry_on_contract_breach is False

    # Intent must remain direct_reply, NOT promoted to context_tools_query
    intent = plan.intent_plan[0]
    assert intent.kind == "direct_reply"
    assert intent.family == "none"
    assert intent.requires_tools is False
    assert intent.shortcircuit is True

    # Context tools should still be visible as optional candidates
    assert set(plan.tool_use_policy.allowed_tool_names) == {
        "search_agent_knowledge_base",
        "save_long_term_memory",
        "recall_long_term_memory",
    }


def test_semantic_match_still_promotes_to_required() -> None:
    """When user query semantically matches a tool, promotion to required still works."""
    tools = [
        ToolDefinition(
            name="search_agent_knowledge_base",
            description="Search the knowledge base bound to this agent.",
            semantic_family="context_tools",
            semantic_tags=["知识库", "knowledge base", "rag", "search"],
        ),
    ]
    request = ExecutionRequest(agent_id=1, tenant_id=0, messages=[])
    # This query should match "知识库" semantic tag
    messages = [SimpleNamespace(role="user", content="帮我查一下知识库里的内容")]

    plan = plan_execution_tools(
        agent_id=1,
        conversation_id=101,
        request=request,
        messages=messages,  # type: ignore[arg-type]
        tools=list(tools),
        all_tools=list(tools),
        diagnostics={
            "intent_plan": [
                IntentPlan(
                    intent_id="intent-1",
                    kind="direct_reply",
                    family="none",
                    order=1,
                    user_visible_label="direct_reply",
                    source_text="帮我查一下知识库里的内容",
                    requires_tools=False,
                    shortcircuit=True,
                ).to_dict()
            ]
        },
    )

    # Semantic match should promote to required
    intent = plan.intent_plan[0]
    assert intent.kind != "direct_reply"
    assert intent.requires_tools is True
    assert plan.tool_use_policy.mode == "required"
