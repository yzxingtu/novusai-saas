"""Unit tests for _build_rejection_message helper.

验证用户取消授权确认卡片时，后端正确注入拒绝消息。
"""

from __future__ import annotations


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


class TestBuildRejectionChatMessage:
    """Test the _build_rejection_chat_message helper.

    The synthetic cancellation message must be ``internal_only`` so it reaches
    the LLM but is never persisted as a real user message or written to memory.
    """

    def test_returns_none_when_message_present(self) -> None:
        from app.services.ai.agent_chat_command_service import (
            _build_rejection_chat_message,
        )

        updates = [{"kind": "pending_confirmation", "rejected": True}]
        # A real user message means no synthetic injection.
        assert _build_rejection_chat_message("你好", updates) is None

    def test_returns_none_when_no_rejection(self) -> None:
        from app.services.ai.agent_chat_command_service import (
            _build_rejection_chat_message,
        )

        updates = [{"kind": "pending_confirmation", "rejected": False}]
        assert _build_rejection_chat_message("", updates) is None

    def test_returns_none_when_updates_empty(self) -> None:
        from app.services.ai.agent_chat_command_service import (
            _build_rejection_chat_message,
        )

        assert _build_rejection_chat_message("", None) is None
        assert _build_rejection_chat_message("", []) is None

    def test_returns_internal_only_message_on_rejection(self) -> None:
        from app.ai.types import ChatMessage
        from app.services.ai.agent_chat_command_service import (
            _build_rejection_chat_message,
        )

        updates = [{"kind": "pending_confirmation", "rejected": True}]
        msg = _build_rejection_chat_message("", updates)

        assert isinstance(msg, ChatMessage)
        assert msg.role == "user"
        assert msg.content == "取消"
        # Critical: must be internal_only so persistence layer skips it.
        assert msg.internal_only is True

    def test_synthetic_message_is_filtered_by_persistence(self) -> None:
        """An internal_only synthetic user message is dropped by persistence."""
        from app.services.ai.agent_chat_command_service import (
            _build_rejection_chat_message,
        )
        from app.services.ai.conversation_message_persistence_service import (
            ConversationMessagePersistenceService,
        )

        updates = [{"kind": "pending_confirmation", "rejected": True}]
        synthetic = _build_rejection_chat_message("", updates)
        assert synthetic is not None

        # Simulate engine echoing the synthetic message back in result.messages
        # (asdict-style dict carrying the internal_only flag).
        result_messages = [
            {"role": "user", "content": "之前的真实消息"},
            {"role": "user", "content": synthetic.content, "internal_only": True},
            {"role": "assistant", "content": "好的，已取消该操作。"},
        ]
        new_start = ConversationMessagePersistenceService.resolve_new_message_start(
            result_messages=result_messages,
            history_count=1,
        )
        new_messages_raw = result_messages[new_start:]
        # The synthetic (internal_only) user message must not survive into the
        # persisted user content.
        persisted_user_contents = [
            m.get("content")
            for m in new_messages_raw
            if m.get("role") == "user" and not m.get("internal_only")
        ]
        assert "取消" not in persisted_user_contents


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
