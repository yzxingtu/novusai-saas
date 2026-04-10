"""Permission menu query domain."""

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.enums.rbac import PermissionScope
from app.models import Admin, Permission, TenantAdmin, TenantUser
from app.schemas.common import MenuResponse
from app.services.system.plugin_service import PluginService

if TYPE_CHECKING:
    from app.rbac.services.permission_service import PermissionService


class PermissionMenuDomain:
    """Menu query/composition domain that keeps service facade thin."""

    def __init__(self, service: "PermissionService") -> None:
        self._service = service

    async def get_admin_menus(self, admin: Admin) -> list[MenuResponse]:
        all_permissions = await self._service.get_enabled_permissions_by_scope(
            PermissionScope.ADMIN.value
        )

        if admin.is_super:
            return self._service._build_menu_tree(
                all_permissions,
                user_permission_codes=None,
            )

        effective_ids = await self._service.get_admin_effective_permission_ids(admin)
        if not effective_ids:
            return []

        result = await self._service.db.execute(
            select(Permission).where(
                Permission.id.in_(effective_ids),
                Permission.is_enabled.is_(True),
                Permission.is_deleted.is_(False),
            )
        )
        user_permissions = list(result.scalars().all())
        return self._build_user_menu_tree(
            all_permissions=all_permissions,
            user_permissions=user_permissions,
        )

    async def get_tenant_admin_menus(
        self,
        tenant_admin: TenantAdmin,
    ) -> list[MenuResponse]:
        all_permissions = await self._service.get_enabled_permissions_by_scope(
            PermissionScope.TENANT.value
        )
        visible_plugin_safe_names = {
            name.replace("-", "_")
            for name in await PluginService(self._service.db).get_tenant_visible_plugin_names(
                tenant_admin.tenant_id,
            )
        }

        def _menu_visible_for_tenant(permission: Permission) -> bool:
            if not self._service._is_plugin_menu(permission.code):
                return True
            name_key = str(permission.name or "")
            safe_name = name_key.split(".", 1)[0].strip()
            if not safe_name:
                return False
            return safe_name in visible_plugin_safe_names

        all_permissions = [
            permission
            for permission in all_permissions
            if permission.type != "menu" or _menu_visible_for_tenant(permission)
        ]

        effective_ids = await self._service.get_tenant_admin_effective_permission_ids(
            tenant_admin
        )
        if not effective_ids:
            return []

        result = await self._service.db.execute(
            select(Permission).where(
                Permission.id.in_(effective_ids),
                Permission.is_enabled.is_(True),
                Permission.is_deleted.is_(False),
            )
        )
        user_permissions = list(result.scalars().all())
        user_permissions = [
            permission
            for permission in user_permissions
            if permission.type != "menu" or _menu_visible_for_tenant(permission)
        ]
        return self._build_user_menu_tree(
            all_permissions=all_permissions,
            user_permissions=user_permissions,
        )

    async def get_tenant_user_menus(
        self,
        tenant_user: TenantUser,
    ) -> list[MenuResponse]:
        all_permissions = await self._service.get_enabled_permissions_by_scope(
            PermissionScope.USER.value
        )
        effective_ids = await self._service.get_tenant_user_effective_permission_ids(
            tenant_user
        )
        if not effective_ids:
            return []

        result = await self._service.db.execute(
            select(Permission).where(
                Permission.id.in_(effective_ids),
                Permission.is_enabled.is_(True),
                Permission.is_deleted.is_(False),
            )
        )
        user_permissions = list(result.scalars().all())
        return self._build_user_menu_tree(
            all_permissions=all_permissions,
            user_permissions=user_permissions,
        )

    def _build_user_menu_tree(
        self,
        *,
        all_permissions: list[Permission],
        user_permissions: list[Permission],
    ) -> list[MenuResponse]:
        user_permission_codes = {permission.code for permission in user_permissions}

        menu_ids: set[int] = set()
        for permission in user_permissions:
            if permission.type == "menu":
                menu_ids.add(permission.id)
            elif permission.type == "operation" and permission.parent_id:
                menu_ids.add(permission.parent_id)

        menu_by_id = {
            permission.id: permission
            for permission in all_permissions
            if permission.type == "menu"
        }

        ids_to_process = list(menu_ids)
        while ids_to_process:
            menu_id = ids_to_process.pop()
            menu = menu_by_id.get(menu_id)
            if menu and menu.parent_id and menu.parent_id not in menu_ids:
                menu_ids.add(menu.parent_id)
                ids_to_process.append(menu.parent_id)

        permissions_for_tree = []
        for permission in all_permissions:
            if (
                permission.type == "menu"
                and permission.id in menu_ids
                or permission.type == "operation"
            ):
                permissions_for_tree.append(permission)

        return self._service._build_menu_tree(
            permissions_for_tree,
            user_permission_codes,
        )

