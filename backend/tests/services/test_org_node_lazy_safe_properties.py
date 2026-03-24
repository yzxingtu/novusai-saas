from types import SimpleNamespace

from app.models.org.admin_org_node import AdminOrgNode
from app.models.org.tenant_org_node import TenantOrgNode


def test_admin_org_node_uses_cached_counts_when_relations_are_unloaded():
    node = AdminOrgNode.__new__(AdminOrgNode)
    node._children_count = 3
    node._has_children = True
    node._member_count = 2
    node._permissions_count = 4
    node._scope_mode = "custom"
    node._custom_org_node_ids = [10, 11]

    assert node.children_count == 3
    assert node.has_children is True
    assert node.member_count == 2
    assert node.permissions_count == 4
    assert node.scope_mode == "custom"
    assert node.custom_org_node_ids == [10, 11]


def test_admin_org_node_computes_permission_count_from_loaded_relations():
    node = AdminOrgNode.__new__(AdminOrgNode)
    node.__dict__["permissions"] = [
        SimpleNamespace(is_deleted=False, is_enabled=True),
        SimpleNamespace(is_deleted=False, is_enabled=False),
        SimpleNamespace(is_deleted=True, is_enabled=True),
    ]

    assert node.permissions_count == 1


def test_tenant_org_node_computes_counts_from_loaded_relations_without_lazy_loading():
    node = TenantOrgNode.__new__(TenantOrgNode)
    node.__dict__["children"] = [
        SimpleNamespace(is_deleted=False),
        SimpleNamespace(is_deleted=True),
    ]
    node.__dict__["admins"] = [
        SimpleNamespace(is_deleted=False),
        SimpleNamespace(is_deleted=True),
    ]
    node.__dict__["users"] = [
        SimpleNamespace(is_deleted=False),
        SimpleNamespace(is_deleted=False),
    ]

    assert node.children_count == 1
    assert node.has_children is True
    assert node.member_count == 3
