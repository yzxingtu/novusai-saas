from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.models.auth.tenant_admin_role import TenantAdminRole
from app.services.ai.action_log_service import _normalize_audit_payload


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
            }
        ],
        'cost': '12.50',
        'created_at': '2026-02-13T00:42:39',
        'nested': {'value': 'ok'},
    }


def test_normalize_audit_payload_wraps_non_dict_top_level_values():
    normalized = _normalize_audit_payload(['a', 'b'])

    assert normalized == {'value': ['a', 'b']}
