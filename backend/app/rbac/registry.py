"""
Permission Registry. / 权限注册中心。

Collects all permissions defined via decorators, synced to database on app startup.
收集所有通过装饰器定义的权限，应用启动时同步到数据库。
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.enums.rbac import PermissionScope, PermissionType
    from app.rbac.decorators import PermissionMeta


class PermissionRegistry:
    """
    Permission Registry (singleton). / 权限注册中心（单例）。

    Collects all permissions defined via decorators, synced to database on app startup.
    收集所有通过装饰器定义的权限，应用启动时同步到数据库。
    """

    _instance: "PermissionRegistry | None" = None
    _permissions: dict[str, "PermissionMeta"]  # key = "code:scope" / 权限字典键格式

    def __new__(cls) -> "PermissionRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._permissions = {}
        return cls._instance

    def _make_key(self, code: str, scope: "PermissionScope") -> str:
        """Generate permission unique key / 生成权限唯一标识"""
        return f"{code}:{scope.value}"

    def register(self, permission: "PermissionMeta") -> None:
        """
        Register a permission.
        注册权限。

        Args:
            permission: Permission metadata / 权限元信息
        """
        key = self._make_key(permission.code, permission.scope)
        if key not in self._permissions:
            self._permissions[key] = permission

    def get(
        self, code: str, scope: "PermissionScope | None" = None
    ) -> "PermissionMeta | None":
        """
        Get a permission.
        获取权限。

        Args:
            code: Permission code / 权限代码
            scope: Permission scope (optional, iterates to match if not provided) /
                权限作用域（可选，若不提供则逐一匹配）

        Returns:
            Permission metadata or None / 权限元信息或 None
        """
        if scope:
            return self._permissions.get(self._make_key(code, scope))
        # Iterate to find when no scope provided / 无 scope 时遍历查找
        for perm in self._permissions.values():
            if perm.code == code:
                return perm
        return None

    def get_all(self) -> list["PermissionMeta"]:
        """Get all permissions / 获取所有权限"""
        return list(self._permissions.values())

    def get_by_scope(self, scope: "PermissionScope") -> list["PermissionMeta"]:
        """
        Get permissions by scope.
        按作用域获取权限。

        Args:
            scope: Permission scope / 权限作用域

        Returns:
            Permission list / 权限列表
        """
        return [p for p in self._permissions.values() if p.scope == scope]

    def get_by_type(self, perm_type: "PermissionType") -> list["PermissionMeta"]:
        """
        Get permissions by type.
        按类型获取权限。

        Args:
            perm_type: Permission type / 权限类型

        Returns:
            Permission list / 权限列表
        """
        return [p for p in self._permissions.values() if p.type == perm_type]

    def get_menus(self) -> list["PermissionMeta"]:
        """Get all menu permissions / 获取所有菜单权限"""
        from app.enums.rbac import PermissionType

        return self.get_by_type(PermissionType.MENU)

    def get_operations(self) -> list["PermissionMeta"]:
        """Get all operation permissions / 获取所有操作权限"""
        from app.enums.rbac import PermissionType

        return self.get_by_type(PermissionType.OPERATION)

    def unregister(self, code: str) -> bool:
        """
        Remove permissions with specified code (all scopes).
        移除指定 code 的权限（所有 scope）。

        Used to remove dynamically registered menus/permissions when plugins are disabled.
        用于插件禁用时移除动态注册的菜单/权限。

        Returns:
            Whether removal was successful / 是否成功移除
        """
        keys_to_remove = [k for k, p in self._permissions.items() if p.code == code]
        for k in keys_to_remove:
            del self._permissions[k]
        return len(keys_to_remove) > 0

    def clear(self) -> None:
        """Clear all (for testing) / 清空（测试用）"""
        self._permissions.clear()

    def __len__(self) -> int:
        return len(self._permissions)

    def __contains__(self, code: str) -> bool:
        """Check if permission code exists (regardless of scope) / 检查权限代码是否存在（不区分 scope）"""
        return any(p.code == code for p in self._permissions.values())


# Global instance / 全局实例
permission_registry = PermissionRegistry()


__all__ = ["PermissionRegistry", "permission_registry"]
