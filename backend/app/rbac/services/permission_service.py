"""Permission check service."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.rbac import PermissionScope
from app.models import Admin, Permission, TenantAdmin, TenantUser
from app.rbac.registry import permission_registry
from app.rbac.services.permission_domains import (
    PermissionAggregationDomain,
    PermissionCheckDomain,
    PermissionMenuDomain,
    PermissionPresentationDomain,
    PermissionQueryDomain,
    TenantAdminPermissionDomain,
)
from app.schemas.common import (
    MenuMetaResponse,
    MenuResponse,
    PermissionResponse,
    PermissionTreeResponse,
)


class _PermissionAggregationFacade:
    """Permission aggregation by identity domain."""

    def __init__(self, service: "PermissionService") -> None:
        self._service = service

    async def get_admin_permissions(self, admin: Admin) -> set[str]:
        return await self._service.get_admin_permissions(admin)

    async def get_admin_effective_permission_ids(self, admin: Admin) -> set[int]:
        return await self._service.get_admin_effective_permission_ids(admin)

    async def get_tenant_admin_permissions(self, tenant_admin: TenantAdmin) -> set[str]:
        return await self._service.get_tenant_admin_permissions(tenant_admin)

    async def get_tenant_admin_effective_permission_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        return await self._service.get_tenant_admin_effective_permission_ids(
            tenant_admin
        )

    async def get_tenant_user_permissions(self, tenant_user: TenantUser) -> set[str]:
        return await self._service.get_tenant_user_permissions(tenant_user)

    async def get_tenant_user_effective_permission_ids(
        self,
        tenant_user: TenantUser,
    ) -> set[int]:
        return await self._service.get_tenant_user_effective_permission_ids(tenant_user)

    async def get_enabled_permissions_by_scope(self, scope: str) -> list[Permission]:
        return await self._service.get_enabled_permissions_by_scope(scope)


class _PermissionTreeFacade:
    """Permission list/tree composition facade."""

    def __init__(self, service: "PermissionService") -> None:
        self._service = service

    async def get_admin_tree(self, admin: Admin) -> list[PermissionTreeResponse]:
        return await self._service.get_admin_permission_tree(admin)

    async def get_tenant_tree(
        self,
        tenant_admin: TenantAdmin,
    ) -> list[PermissionTreeResponse]:
        return await self._service.get_tenant_permission_tree(tenant_admin)

    async def get_admin_list(self, admin: Admin) -> list[PermissionResponse]:
        return await self._service.get_admin_permission_list(admin)

    async def get_tenant_list(
        self,
        tenant_admin: TenantAdmin,
    ) -> list[PermissionResponse]:
        return await self._service.get_tenant_permission_list(tenant_admin)

    async def fill_parent_permissions_for_tree(
        self,
        permissions: list[Permission],
    ) -> list[Permission]:
        return await self._service.fill_parent_permissions_for_tree(permissions)


class _MenuFacade:
    """Menu tree facade."""

    def __init__(self, service: "PermissionService") -> None:
        self._service = service

    async def get_admin_menus(self, admin: Admin) -> list[MenuResponse]:
        return await self._service.get_admin_menus(admin)

    async def get_tenant_admin_menus(
        self,
        tenant_admin: TenantAdmin,
    ) -> list[MenuResponse]:
        return await self._service.get_tenant_admin_menus(tenant_admin)

    async def get_tenant_user_menus(
        self,
        tenant_user: TenantUser,
    ) -> list[MenuResponse]:
        return await self._service.get_tenant_user_menus(tenant_user)


class _OrgAuthorityFacade:
    """Role visibility/manageability facade."""

    def __init__(self, service: "PermissionService") -> None:
        self._service = service

    async def get_admin_manageable_role_ids(self, admin: Admin) -> set[int]:
        return await self._service.get_admin_manageable_role_ids(admin)

    async def get_admin_visible_role_ids(self, admin: Admin) -> set[int]:
        return await self._service.get_admin_visible_role_ids(admin)

    async def get_tenant_admin_manageable_role_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        return await self._service.get_tenant_admin_manageable_role_ids(tenant_admin)

    async def get_tenant_admin_visible_role_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        return await self._service.get_tenant_admin_visible_role_ids(tenant_admin)


class PermissionService:
    """Permission check service facade."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.permission_aggregation = _PermissionAggregationFacade(self)
        self.permission_tree = _PermissionTreeFacade(self)
        self.menu_tree = _MenuFacade(self)
        self.org_authority = _OrgAuthorityFacade(self)
        self._check_domain = PermissionCheckDomain()
        self._tenant_admin_permission_domain = TenantAdminPermissionDomain(self)
        self._query_domain = PermissionQueryDomain(self)
        self._aggregation_domain = PermissionAggregationDomain(db)
        self._menu_domain = PermissionMenuDomain(self)

    async def _get_admin_org_node(self, admin: Admin):
        return await self._aggregation_domain.get_admin_org_node(admin)

    async def _get_tenant_org_node(self, tenant_admin: TenantAdmin):
        return await self._aggregation_domain.get_tenant_org_node(tenant_admin)

    async def get_admin_permissions(self, admin: Admin) -> set[str]:
        return await self._aggregation_domain.get_admin_permissions(admin)

    async def get_admin_effective_permission_ids(self, admin: Admin) -> set[int]:
        return await self._aggregation_domain.get_admin_effective_permission_ids(admin)

    async def get_admin_manageable_role_ids(self, admin: Admin) -> set[int]:
        return await self._aggregation_domain.get_admin_manageable_role_ids(admin)

    async def get_admin_visible_role_ids(self, admin: Admin) -> set[int]:
        return await self._aggregation_domain.get_admin_visible_role_ids(admin)

    async def _get_tenant_plan_permissions(
        self,
        tenant_id: int,
    ) -> tuple[set[str], set[int]] | None:
        return await self._aggregation_domain.get_tenant_plan_permissions(tenant_id)

    async def get_tenant_admin_permissions(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[str]:
        return await self._tenant_admin_permission_domain.get_permissions(tenant_admin)

    async def get_tenant_admin_effective_permission_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        return await self._tenant_admin_permission_domain.get_effective_permission_ids(
            tenant_admin
        )

    async def get_tenant_admin_manageable_role_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        return await self._aggregation_domain.get_tenant_admin_manageable_role_ids(
            tenant_admin
        )

    async def get_tenant_admin_visible_role_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        return await self._aggregation_domain.get_tenant_admin_visible_role_ids(
            tenant_admin
        )

    def check_permission(
        self,
        user_permissions: set[str],
        required: str,
    ) -> bool:
        return self._check_domain.check_permission(user_permissions, required)

    def check_any_permission(
        self,
        user_permissions: set[str],
        required_permissions: list[str],
    ) -> bool:
        return self._check_domain.check_any_permission(
            user_permissions,
            required_permissions,
        )

    def check_all_permissions(
        self,
        user_permissions: set[str],
        required_permissions: list[str],
    ) -> bool:
        return self._check_domain.check_all_permissions(
            user_permissions,
            required_permissions,
        )

    async def get_enabled_permissions_by_scope(self, scope: str) -> list[Permission]:
        return await self._aggregation_domain.get_enabled_permissions_by_scope(scope)

    @staticmethod
    def _translate_name(name: str) -> str:
        return PermissionPresentationDomain._translate_name(name)

    @classmethod
    def translate_name(cls, name: str) -> str:
        return PermissionPresentationDomain.translate_name(name)

    @staticmethod
    def _resolve_plugin_menu_title(name: str) -> str | None:
        return PermissionPresentationDomain._resolve_plugin_menu_title(name)

    @staticmethod
    def _resolve_plugin_permission_title(name: str) -> str | None:
        return PermissionPresentationDomain._resolve_plugin_permission_title(name)

    @staticmethod
    def _fallback_permission_name(name: str) -> str:
        return PermissionPresentationDomain._fallback_permission_name(name)

    @staticmethod
    def _is_plugin_menu(code: str | None) -> bool:
        return PermissionPresentationDomain._is_plugin_menu(code)

    @classmethod
    def _build_permission_tree(
        cls,
        permissions: list[Permission],
        parent_id: int | None = None,
    ) -> list[PermissionTreeResponse]:
        return PermissionPresentationDomain._build_permission_tree(
            permissions,
            parent_id=parent_id,
        )

    async def get_admin_permission_tree(
        self,
        admin: Admin,
    ) -> list[PermissionTreeResponse]:
        return await self._query_domain.get_admin_tree(admin)

    async def get_tenant_permission_tree(
        self,
        tenant_admin: TenantAdmin,
    ) -> list[PermissionTreeResponse]:
        return await self._query_domain.get_tenant_tree(tenant_admin)

    async def get_admin_permission_list(
        self,
        admin: Admin,
        perm_type: str | None = None,
    ) -> list[PermissionResponse]:
        return await self._query_domain.get_admin_list(admin, perm_type=perm_type)

    async def get_tenant_permission_list(
        self,
        tenant_admin: TenantAdmin,
        perm_type: str | None = None,
    ) -> list[PermissionResponse]:
        return await self._query_domain.get_tenant_list(
            tenant_admin,
            perm_type=perm_type,
        )

    async def _fill_parent_permissions(
        self,
        permissions: list[Permission],
    ) -> list[Permission]:
        return await self._query_domain.fill_parent_permissions(permissions)

    async def fill_parent_permissions_for_tree(
        self,
        permissions: list[Permission],
    ) -> list[Permission]:
        return await self._query_domain.fill_parent_permissions_for_tree(permissions)

    @staticmethod
    def _normalize_menu_ai_strings(values: list[str] | None) -> list[str]:
        return PermissionPresentationDomain._normalize_menu_ai_strings(values)

    @staticmethod
    def _scope_enum_from_value(scope: str | None) -> PermissionScope | None:
        return PermissionPresentationDomain._scope_enum_from_value(scope)

    @classmethod
    def _infer_menu_ai_category(cls, permission: Permission) -> str | None:
        return PermissionPresentationDomain._infer_menu_ai_category(permission)

    @classmethod
    def _build_generic_menu_ai_keywords(
        cls,
        permission: Permission,
        *,
        translated_name: str,
    ) -> list[str]:
        return PermissionPresentationDomain._build_generic_menu_ai_keywords(
            permission,
            translated_name=translated_name,
        )

    @classmethod
    def _build_menu_ai_meta(cls, permission: Permission) -> MenuMetaResponse | None:
        return PermissionPresentationDomain._build_menu_ai_meta(permission)

    @classmethod
    def _build_menu_tree(
        cls,
        permissions: list[Permission],
        user_permission_codes: set[str] | None = None,
        parent_id: int | None = None,
    ) -> list[MenuResponse]:
        return PermissionPresentationDomain._build_menu_tree(
            permissions,
            user_permission_codes=user_permission_codes,
            parent_id=parent_id,
        )

    async def get_admin_menus(self, admin: Admin) -> list[MenuResponse]:
        return await self._menu_domain.get_admin_menus(admin)

    async def get_tenant_admin_menus(
        self,
        tenant_admin: TenantAdmin,
    ) -> list[MenuResponse]:
        return await self._menu_domain.get_tenant_admin_menus(tenant_admin)

    async def get_tenant_user_permissions(
        self,
        tenant_user: TenantUser,
    ) -> set[str]:
        return await self._aggregation_domain.get_tenant_user_permissions(tenant_user)

    async def get_tenant_user_effective_permission_ids(
        self,
        tenant_user: TenantUser,
    ) -> set[int]:
        return await self._aggregation_domain.get_tenant_user_effective_permission_ids(
            tenant_user
        )

    async def get_tenant_user_menus(
        self,
        tenant_user: TenantUser,
    ) -> list[MenuResponse]:
        return await self._menu_domain.get_tenant_user_menus(tenant_user)


__all__ = ["PermissionService", "permission_registry"]
