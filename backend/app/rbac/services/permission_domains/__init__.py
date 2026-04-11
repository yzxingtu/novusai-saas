"""Permission service internal domains."""

from app.rbac.services.permission_domains.aggregation import PermissionAggregationDomain
from app.rbac.services.permission_domains.checks import PermissionCheckDomain
from app.rbac.services.permission_domains.menu_query import PermissionMenuDomain
from app.rbac.services.permission_domains.presentation import (
    PermissionPresentationDomain,
)
from app.rbac.services.permission_domains.query import PermissionQueryDomain
from app.rbac.services.permission_domains.tenant_admin import (
    TenantAdminPermissionDomain,
)

__all__ = [
    "PermissionCheckDomain",
    "PermissionAggregationDomain",
    "PermissionMenuDomain",
    "PermissionPresentationDomain",
    "PermissionQueryDomain",
    "TenantAdminPermissionDomain",
]
