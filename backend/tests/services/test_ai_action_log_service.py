from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from app.models.auth.tenant_admin_role import TenantAdminRole
from app.services.ai.action_log_service import (
    AIActionLogService,
    AdminAIActionLogService,
    _normalize_audit_payload,
)


@dataclass
class _NestedPayload:
    value: str


def test_normalize_audit_payload_serializes_models_and_nested_values():
    role = TenantAdminRole(
        id=1,
        tenant_id=9,
        name='Tenant Root',
        code='tenant_root',
        level=1,
    )

    payload = {
        'result': [role],
        'cost': Decimal('12.50'),
        'created_at': datetime(2026, 2, 13, 0, 42, 39),
        'nested': _NestedPayload(value='ok'),
    }

    normalized = _normalize_audit_payload(payload)

    assert normalized == {
        'result': [
            {
                'id': 1,
                'created_at': None,
                'updated_at': None,
                'is_deleted': None,
                'deleted_at': None,
                'delete_level': None,
                'tenant_id': 9,
                'name': 'Tenant Root',
                'code': 'tenant_root',
                'description': None,
                'is_system': None,
                'is_active': None,
                'sort_order': None,
                'parent_id': None,
                'path': None,
                'level': 1,
                'type': None,
                'allow_members': None,
                'leader_id': None,
                'data_scope': None,
                'custom_dept_ids': None,
                'recycle_stage': None,
                'promoted_to_global_at': None,
            }
        ],
        'cost': '12.50',
        'created_at': '2026-02-13T00:42:39',
        'nested': {'value': 'ok'},
    }


def test_normalize_audit_payload_wraps_non_dict_top_level_values():
    normalized = _normalize_audit_payload(['a', 'b'])

    assert normalized == {'value': ['a', 'b']}


async def _fake_empty_async(*_args, **_kwargs):
    return {}


def test_tenant_action_log_serialize_log_enriches_agent_and_operator_metadata():
    service = AIActionLogService.__new__(AIActionLogService)
    service.tenant_id = 9
    service._load_agent_meta_map = _fake_empty_async  # type: ignore[method-assign]
    service._load_operator_meta_map = _fake_empty_async  # type: ignore[method-assign]

    async def _agent_meta(_agent_ids):
        return {7: {'agent_name': 'Order Copilot', 'agent_avatar': '18'}}

    async def _operator_meta(_operator_ids):
        return {
            12: {
                'operator_name': 'alice',
                'operator_nickname': 'Alice',
                'operator_avatar': '22',
                'operator_type': 'tenant_admin',
            }
        }

    service._load_agent_meta_map = _agent_meta  # type: ignore[method-assign]
    service._load_operator_meta_map = _operator_meta  # type: ignore[method-assign]

    log = SimpleNamespace(
        agent_id=7,
        operator_id=12,
        to_dict=lambda: {
            'id': 1,
            'tenant_id': 9,
            'agent_id': 7,
            'operator_id': 12,
        },
    )

    import asyncio

    payload = asyncio.run(service.serialize_log(log))

    assert payload['agent_name'] == 'Order Copilot'
    assert payload['agent_avatar'] == '18'
    assert payload['operator_name'] == 'alice'
    assert payload['operator_nickname'] == 'Alice'
    assert payload['operator_avatar'] == '22'
    assert payload['operator_type'] == 'tenant_admin'


def test_admin_action_log_serialize_log_merges_tenant_agent_and_operator_metadata():
    service = AdminAIActionLogService.__new__(AdminAIActionLogService)
    service._load_tenant_meta_map = _fake_empty_async  # type: ignore[method-assign]
    service._load_agent_meta_map = _fake_empty_async  # type: ignore[method-assign]
    service._load_operator_meta_map = _fake_empty_async  # type: ignore[method-assign]

    async def _tenant_meta(_tenant_ids):
        return {9: {'tenant_name': 'Acme', 'tenant_code': 'acme'}}

    async def _agent_meta(_agent_ids):
        return {7: {'agent_name': 'Order Copilot', 'agent_avatar': '18'}}

    async def _operator_meta(_logs):
        return {
            (9, 12): {
                'operator_name': 'alice',
                'operator_nickname': 'Alice',
                'operator_avatar': '22',
                'operator_type': 'tenant_admin',
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
            'id': 1,
            'tenant_id': 9,
            'agent_id': 7,
            'operator_id': 12,
        },
    )

    import asyncio

    payload = asyncio.run(service.serialize_log(log))

    assert payload['tenant_name'] == 'Acme'
    assert payload['tenant_code'] == 'acme'
    assert payload['agent_name'] == 'Order Copilot'
    assert payload['operator_name'] == 'alice'
    assert payload['operator_avatar'] == '22'
    assert payload['operator_type'] == 'tenant_admin'
