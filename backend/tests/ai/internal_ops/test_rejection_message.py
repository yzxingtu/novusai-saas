"""Unit tests for _build_rejection_message helper.

验证用户取消授权确认卡片时，后端正确注入拒绝消息。
"""

from __future__ import annotations

import pytest


class TestBuildRejectionMessage:
    """Test the _build_rejection_message helper function."""

    def test_returns_none_when_updates_is_none(self) -> None:
        from app.services.ai.agent_chat_command_service import _build_rejection_message

        assert _build_rejection_message(None) is None

    def test_returns_none_when_updates_is_empty(self) -> None:
        from app.services.ai.agent_chat_command_service import _build_rejection_message

        assert _build_rejection_message([]) is None

    def test_returns_none_when_no_rejection(self) -> None:
        from app.services.ai.agent_chat_command_service import _build_rejection_message

        updates = [{"kind": "pending_confirmation", "rejected": False}]
        assert _build_rejection_message(updates) is None

    def test_returns_message_on_rejection(self) -> None:
        from app.services.ai.agent_chat_command_service import _build_rejection_message

        updates = [{"kind": "pending_confirmation", "rejected": True}]
        result = _build_rejection_message(updates)
        assert result == "取消"

    def test_returns_message_on_rejection_with_tool_name(self) -> None:
        from app.services.ai.agent_chat_command_service import _build_rejection_message

        updates = [
            {
                "kind": "pending_confirmation",
                "rejected": True,
                "tool_name": "invoke_internal_operation",
            }
        ]
        result = _build_rejection_message(updates)
        assert result == "取消"

    def test_ignores_non_confirmation_updates(self) -> None:
        from app.services.ai.agent_chat_command_service import _build_rejection_message

        updates = [{"kind": "other_kind", "rejected": True}]
        assert _build_rejection_message(updates) is None

    def test_handles_mixed_updates(self) -> None:
        from app.services.ai.agent_chat_command_service import _build_rejection_message

        updates = [
            {"kind": "other_kind", "rejected": True},
            {"kind": "pending_confirmation", "rejected": False},
            {"kind": "pending_confirmation", "rejected": True},
        ]
        result = _build_rejection_message(updates)
        assert result == "取消"

    def test_handles_non_dict_updates(self) -> None:
        from app.services.ai.agent_chat_command_service import _build_rejection_message

        updates: list = ["not_a_dict", {"kind": "pending_confirmation", "rejected": True}]
        result = _build_rejection_message(updates)
        assert result == "取消"


# ---------------------------------------------------------------------------
# Rejection shortcircuit in plan_execution_tools / 拒绝短路测试
# ---------------------------------------------------------------------------


class TestRejectionShortcircuit:
    """Verify plan_execution_tools returns a direct_reply plan when rejection is detected."""

    def _build_request_with_rejection(self):
        from app.ai.engine.types import ExecutionRequest

        return ExecutionRequest(
            agent_id=1,
            tenant_id=0,
            messages=[],
            interaction_updates=[
                {
                    "kind": "pending_confirmation",
                    "rejected": True,
                    "tool_name": "invoke_internal_operation",
                }
            ],
        )

    def test_rejection_returns_direct_reply_no_tools(self) -> None:
        from types import SimpleNamespace

        from app.ai.engine.prepare_execution_tool_helpers import plan_execution_tools

        request = self._build_request_with_rejection()
        tools = [
            SimpleNamespace(
                name="invoke_internal_operation",
                description="Internal ops tool",
                semantic_family="internal_ops",
                semantic_tags=[],
            )
        ]
        messages = [SimpleNamespace(role="user", content="取消")]
        diagnostics: dict = {"intent_plan": []}

        plan = plan_execution_tools(
            agent_id=1,
            conversation_id=100,
            request=request,
            messages=messages,  # type: ignore[arg-type]
            tools=list(tools),
            all_tools=list(tools),
            diagnostics=diagnostics,
        )

        assert plan.tools == []
        assert plan.candidate_tool_names == []
        assert plan.tool_planner["reason"] == "rejection_shortcircuit"
        assert plan.intent_plan[0].kind == "direct_reply"
        assert plan.intent_plan[0].requires_tools is False
        assert plan.tool_use_policy.reason == "confirmation_rejection"

    def test_no_rejection_does_not_shortcircuit(self) -> None:
        from types import SimpleNamespace

        from app.ai.engine.prepare_execution_tool_helpers import plan_execution_tools
        from app.ai.engine.types import ExecutionRequest

        request = ExecutionRequest(
            agent_id=1,
            tenant_id=0,
            messages=[],
            interaction_updates=[
                {"kind": "pending_confirmation", "rejected": False}
            ],
        )
        tools = [
            SimpleNamespace(
                name="invoke_internal_operation",
                description="Internal ops tool",
                semantic_family="internal_ops",
                semantic_tags=[],
            )
        ]
        messages = [SimpleNamespace(role="user", content="确认")]
        diagnostics: dict = {"intent_plan": []}

        plan = plan_execution_tools(
            agent_id=1,
            conversation_id=101,
            request=request,
            messages=messages,  # type: ignore[arg-type]
            tools=list(tools),
            all_tools=list(tools),
            diagnostics=diagnostics,
        )

        # Non-rejection should not trigger the rejection shortcircuit
        if plan.tool_planner is not None:
            assert plan.tool_planner.get("reason") != "rejection_shortcircuit"
