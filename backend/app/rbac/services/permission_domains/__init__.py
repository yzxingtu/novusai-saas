"""Permission service internal domains."""

from app.rbac.services.permission_domains.aggregation import PermissionAggregationDomain
from app.rbac.services.permission_domains.menu_query import PermissionMenuDomain
from app.rbac.services.permission_domains.presentation import (
    PermissionPresentationDomain,
)

__all__ = [
    "PermissionAggregationDomain",
    "PermissionMenuDomain",
    "PermissionPresentationDomain",
]

