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
