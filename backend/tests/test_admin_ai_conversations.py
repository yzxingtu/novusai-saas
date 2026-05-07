"""Admin AI conversations helper tests."""

from __future__ import annotations

from types import SimpleNamespace

from app.api.admin.ai_conversations import (
    _build_admin_conversation_item,
    _resolve_conversation_usage,
)


def _make_conversation(**overrides):
    base = {
        "id": 448,
        "tenant_id": 0,
        "agent_id": 59,
        "user_id": 1,
        "title": "猫娘智能体对话",
        "status": "active",
        "token_count": 0,
        "cost": 0,
        "created_at": None,
        "updated_at": None,
        "agent": SimpleNamespace(name="猫娘智能体", avatar="avatar.png"),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_resolve_conversation_usage_prefers_available_call_log_cost() -> None:
    conversation = _make_conversation(token_count=120, cost=0)

    tokens, cost = _resolve_conversation_usage(
        conversation,
        {"total_tokens": 100, "total_cost": 0.42},
    )

    assert tokens == 120
    assert cost == 0.42


def test_build_admin_conversation_item_uses_call_log_aggregate_when_stats_missing() -> (
    None
):
    conversation = _make_conversation(token_count=0, cost=0)

    item = _build_admin_conversation_item(
        conversation,
        tenant_map={0: {"name": "平台管理端", "code": "platform"}},
        user_map={
            "0:1": {"username": "admin", "nickname": "超级管理员", "avatar": None}
        },
        usage_map={448: {"total_tokens": 200, "total_cost": 0.66}},
    )

    assert item["token_count"] == 200
    assert item["cost"] == 0.66
    assert item["tenant_name"] == "平台管理端"
    assert item["user_info"]["nickname"] == "超级管理员"
