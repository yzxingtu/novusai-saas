from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.auth.tenant_admin_role import TenantAdminRole
from app.services.ai.action_log_service import (
    AdminAIActionLogService,
    AIActionLogService,
    _normalize_audit_payload,
    write_ai_action_log,
)


@dataclass
class _NestedPayload:
    value: str


def test_normalize_audit_payload_serializes_models_and_nested_values():
    role = TenantAdminRole(
        id=1,
        tenant_id=9,
        name="Tenant Root",
        code="tenant_root",
        level=1,
    )

    payload = {
        "result": [role],
        "cost": Decimal("12.50"),
        "created_at": datetime(2026, 2, 13, 0, 42, 39),
        "nested": _NestedPayload(value="ok"),
    }

    normalized = _normalize_audit_payload(payload)

    assert normalized == {
        "result": [
            {
                "id": 1,
                "created_at": None,
                "updated_at": None,
                "is_deleted": None,
                "deleted_at": None,
                "delete_level": None,
                "tenant_id": 9,
                "name": "Tenant Root",
                "code": "tenant_root",
                "description": None,
                "is_system": None,
                "is_active": None,
                "sort_order": None,
                "parent_id": None,
                "path": None,
                "level": 1,
                "type": None,
                "allow_members": None,
                "leader_id": None,
                "data_scope": None,
                "custom_dept_ids": None,
                "recycle_stage": None,
                "promoted_to_global_at": None,
            }
        ],
        "cost": "12.50",
        "created_at": "2026-02-13T00:42:39+00:00",
        "nested": {"value": "ok"},
    }


def test_normalize_audit_payload_wraps_non_dict_top_level_values():
    normalized = _normalize_audit_payload(["a", "b"])

    assert normalized == {"value": ["a", "b"]}


def test_normalize_audit_payload_does_not_call_async_mock_serializers():
    payload = {"result": SimpleNamespace(model_dump=AsyncMock(), to_dict=AsyncMock())}

    normalized = _normalize_audit_payload(payload)

    assert normalized == {"result": str(payload["result"])}


async def _fake_empty_async(*_args, **_kwargs):
    return {}


def test_tenant_action_log_serialize_log_enriches_agent_and_operator_metadata():
    service = AIActionLogService.__new__(AIActionLogService)
    service.tenant_id = 9
    service._load_agent_meta_map = _fake_empty_async  # type: ignore[method-assign]
    service._load_operator_meta_map = _fake_empty_async  # type: ignore[method-assign]

    async def _agent_meta(_agent_ids):
        return {7: {"agent_name": "Order Copilot", "agent_avatar": "18"}}

    async def _operator_meta(_operator_ids):
        return {
            ("tenant_admin", 12): {
                "operator_name": "alice",
                "operator_nickname": "Alice",
                "operator_avatar": "22",
                "operator_display_name": "Alice",
                "operator_org_node_id": 5,
                "operator_org_node_name": "Ops",
                "operator_role_name": "Owner",
                "operator_is_active": True,
                "operator_is_leader": True,
                "operator_is_owner": True,
                "operator_type": "tenant_admin",
            }
        }

    service._load_agent_meta_map = _agent_meta  # type: ignore[method-assign]
    service._load_operator_meta_map = _operator_meta  # type: ignore[method-assign]

    log = SimpleNamespace(
        agent_id=7,
        operator_id=12,
        to_dict=lambda: {
            "id": 1,
            "tenant_id": 9,
            "agent_id": 7,
            "operator_id": 12,
        },
    )

    import asyncio

    payload = asyncio.run(service.serialize_log(log))

    assert payload["agent_name"] == "Order Copilot"
    assert payload["agent_avatar"] == "18"
    assert payload["operator_name"] == "alice"
    assert payload["operator_nickname"] == "Alice"
    assert payload["operator_avatar"] == "22"
    assert payload["operator_display_name"] == "Alice"
    assert payload["operator_org_node_id"] == 5
    assert payload["operator_org_node_name"] == "Ops"
    assert payload["operator_role_name"] == "Owner"
    assert payload["operator_is_active"] is True
    assert payload["operator_is_leader"] is True
    assert payload["operator_is_owner"] is True
    assert payload["operator_type"] == "tenant_admin"


def test_tenant_action_log_serialize_log_prefers_operator_snapshot_over_live_meta():
    service = AIActionLogService.__new__(AIActionLogService)
    service.tenant_id = 9

    async def _agent_meta(_agent_ids):
        return {}

    async def _operator_meta(_operator_ids):
        return {
            ("tenant_admin", 12): {
                "operator_name": "alice_live",
                "operator_nickname": "Alice Live",
                "operator_avatar": "live-avatar",
                "operator_display_name": "Alice Live",
                "operator_display_role_name": "当前角色",
                "operator_org_node_id": 99,
                "operator_org_node_name": "当前组织",
                "operator_role_name": "当前角色",
                "operator_is_active": False,
                "operator_is_leader": False,
                "operator_is_owner": False,
                "operator_type": "tenant_admin",
            }
        }

    service._load_agent_meta_map = _agent_meta  # type: ignore[method-assign]
    service._load_operator_meta_map = _operator_meta  # type: ignore[method-assign]

    log = SimpleNamespace(
        agent_id=7,
        operator_id=12,
        operator_type="tenant_admin",
        to_dict=lambda: {
            "id": 1,
            "tenant_id": 9,
            "agent_id": 7,
            "operator_id": 12,
            "operator_type": "tenant_admin",
            "operator_snapshot": {
                "display_name": "历史 Alice",
                "username": "alice_old",
                "nickname": "Alice Old",
                "avatar": "snapshot-avatar",
                "org_node_id": 5,
                "org_node_name": "历史组织",
                "role_name": "历史角色",
                "display_role_name": None,
                "is_active": True,
                "is_leader": True,
                "is_owner": True,
                "user_type": "tenant_admin",
            },
            "operator_name_snapshot": "alice_old",
            "operator_nickname_snapshot": "Alice Old",
            "operator_avatar_snapshot": "snapshot-avatar",
        },
    )

    import asyncio

    payload = asyncio.run(service.serialize_log(log))

    assert payload["operator_display_name"] == "历史 Alice"
    assert payload["operator_name"] == "alice_old"
    assert payload["operator_avatar"] == "snapshot-avatar"
    assert payload["operator_org_node_name"] == "历史组织"
    assert payload["operator_role_name"] is None
    assert payload["operator_is_active"] is True
    assert payload["operator_is_leader"] is True
    assert payload["operator_is_owner"] is True


def test_admin_action_log_serialize_log_merges_tenant_agent_and_operator_metadata():
    service = AdminAIActionLogService.__new__(AdminAIActionLogService)
    service._load_tenant_meta_map = _fake_empty_async  # type: ignore[method-assign]
    service._load_agent_meta_map = _fake_empty_async  # type: ignore[method-assign]
    service._load_operator_meta_map = _fake_empty_async  # type: ignore[method-assign]

    async def _tenant_meta(_tenant_ids):
        return {9: {"tenant_name": "Acme", "tenant_code": "acme"}}

    async def _agent_meta(_agent_ids):
        return {7: {"agent_name": "Order Copilot", "agent_avatar": "18"}}

    async def _operator_meta(_logs):
        return {
            (9, "tenant_admin", 12): {
                "operator_name": "alice",
                "operator_nickname": "Alice",
                "operator_avatar": "22",
                "operator_display_name": "Alice",
                "operator_org_node_id": 5,
                "operator_org_node_name": "Ops",
                "operator_role_name": "Owner",
                "operator_is_active": True,
                "operator_is_leader": True,
                "operator_is_owner": True,
                "operator_type": "tenant_admin",
            }
        }

    service._load_tenant_meta_map = _tenant_meta  # type: ignore[method-assign]
    service._load_agent_meta_map = _agent_meta  # type: ignore[method-assign]
    service._load_operator_meta_map = _operator_meta  # type: ignore[method-assign]

    log = SimpleNamespace(
        tenant_id=9,
        agent_id=7,
        operator_id=12,
        to_dict=lambda: {
            "id": 1,
            "tenant_id": 9,
            "agent_id": 7,
            "operator_id": 12,
        },
    )

    import asyncio

    payload = asyncio.run(service.serialize_log(log))

    assert payload["tenant_name"] == "Acme"
    assert payload["tenant_code"] == "acme"
    assert payload["agent_name"] == "Order Copilot"
    assert payload["operator_name"] == "alice"
    assert payload["operator_avatar"] == "22"
    assert payload["operator_display_name"] == "Alice"
    assert payload["operator_org_node_name"] == "Ops"
    assert payload["operator_role_name"] == "Owner"
    assert payload["operator_is_active"] is True
    assert payload["operator_is_leader"] is True
    assert payload["operator_is_owner"] is True
    assert payload["operator_type"] == "tenant_admin"


@pytest.mark.asyncio
async def test_write_ai_action_log_persists_trace_id_and_tool_call_id(mock_db):
    async def _empty_agent(*_args, **_kwargs):
        return {}

    async def _empty_operator(*_args, **_kwargs):
        return {"operator_type": "tenant_admin"}

    from unittest.mock import patch

    with (
        patch(
            "app.services.ai.action_log_service._load_agent_snapshot",
            new=_empty_agent,
        ),
        patch(
            "app.services.ai.action_log_service._load_operator_snapshot",
            new=_empty_operator,
        ),
    ):
        log = await write_ai_action_log(
            mock_db,
            tenant_id=9,
            agent_id=7,
            conversation_id=100,
            operator_id=12,
            operator_type="tenant_admin",
            action_name="email_send",
            action_level="dangerous",
            trace_id="trace-123",
            tool_call_id="tc_email_1",
            request_data={"to": ["alice@example.com"]},
        )

    assert log.trace_id == "trace-123"
    assert log.tool_call_id == "tc_email_1"


@pytest.mark.asyncio
async def test_write_ai_action_log_persists_operator_snapshot(mock_db):
    async def _empty_agent(*_args, **_kwargs):
        return {}

    async def _snapshot_operator(*_args, **_kwargs):
        return {
            "operator_type": "tenant_admin",
            "operator_name_snapshot": "alice_old",
            "operator_nickname_snapshot": "Alice Old",
            "operator_avatar_snapshot": "snapshot-avatar",
            "operator_snapshot": {
                "display_name": "历史 Alice",
                "username": "alice_old",
                "nickname": "Alice Old",
                "avatar": "snapshot-avatar",
                "org_node_id": 5,
                "org_node_name": "历史组织",
                "role_name": "历史角色",
                "display_role_name": None,
                "is_active": True,
                "is_leader": True,
                "is_owner": True,
                "user_type": "tenant_admin",
            },
        }

    from unittest.mock import patch

    with (
        patch(
            "app.services.ai.action_log_service._load_agent_snapshot",
            new=_empty_agent,
        ),
        patch(
            "app.services.ai.action_log_service._load_operator_snapshot",
            new=_snapshot_operator,
        ),
    ):
        log = await write_ai_action_log(
            mock_db,
            tenant_id=9,
            agent_id=7,
            conversation_id=100,
            operator_id=12,
            operator_type="tenant_admin",
            action_name="email_send",
            action_level="dangerous",
            request_data={"to": ["alice@example.com"]},
        )

    assert log.operator_name_snapshot == "alice_old"
    assert log.operator_snapshot["display_name"] == "历史 Alice"
    assert log.operator_snapshot["org_node_name"] == "历史组织"
