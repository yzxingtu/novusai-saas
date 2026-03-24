"""
Organization models / 组织架构模型

Dedicated organization authority models, separated from permission roles.
独立的组织权限模型，与权限角色分离。
"""

from app.models.org.admin_org_node import (
    AdminOrgNode,
    AdminOrgScopePolicy,
    AdminOrgScopeTarget,
    admin_org_node_permissions,
)
from app.models.org.tenant_org_node import (
    TenantOrgNode,
    TenantOrgScopePolicy,
    TenantOrgScopeTarget,
)

__all__ = [
    "AdminOrgNode",
    "AdminOrgScopePolicy",
    "AdminOrgScopeTarget",
    "admin_org_node_permissions",
    "TenantOrgNode",
    "TenantOrgScopePolicy",
    "TenantOrgScopeTarget",
]
