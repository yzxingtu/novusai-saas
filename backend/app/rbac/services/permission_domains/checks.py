"""Pure permission predicate helpers."""


class PermissionCheckDomain:
    """Pure permission predicate helpers."""

    @staticmethod
    def check_permission(user_permissions: set[str], required: str) -> bool:
        if "*" in user_permissions:
            return True
        if required in user_permissions:
            return True
        if ":" in required:
            resource = required.split(":")[0]
            if f"{resource}:*" in user_permissions:
                return True
        return False

    @classmethod
    def check_any_permission(
        cls,
        user_permissions: set[str],
        required_permissions: list[str],
    ) -> bool:
        return any(
            cls.check_permission(user_permissions, perm)
            for perm in required_permissions
        )

    @classmethod
    def check_all_permissions(
        cls,
        user_permissions: set[str],
        required_permissions: list[str],
    ) -> bool:
        return all(
            cls.check_permission(user_permissions, perm)
            for perm in required_permissions
        )
