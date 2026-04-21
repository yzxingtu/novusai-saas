"""Permission presentation and tree/menu composition helpers."""

import re

from app.core.i18n import _
from app.enums.rbac import PermissionScope
from app.models import Permission
from app.rbac.registry import permission_registry
from app.schemas.common import (
    MenuAIResponse,
    MenuMetaResponse,
    MenuResponse,
    PermissionResponse,
    PermissionTreeResponse,
)

_MENU_AI_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+")


class PermissionPresentationDomain:
    """Shared name translation and tree composition domain."""

    @staticmethod
    def _translate_name(name: str) -> str:
        if name and "." in name:
            translated = _(name)
            if translated == name:
                runtime_title = PermissionPresentationDomain._resolve_plugin_menu_title(
                    name
                )
                if runtime_title:
                    return runtime_title
                runtime_permission_title = (
                    PermissionPresentationDomain._resolve_plugin_permission_title(name)
                )
                if runtime_permission_title:
                    return runtime_permission_title
                return PermissionPresentationDomain._fallback_permission_name(name)
            return translated
        return name or ""

    @classmethod
    def translate_name(cls, name: str) -> str:
        return cls._translate_name(name)

    @staticmethod
    def _resolve_plugin_menu_title(name: str) -> str | None:
        from app.plugins.registry import ExtensionRegistry

        registry = ExtensionRegistry.get_instance()
        runtime_title = registry.resolve_plugin_menu_title(name)
        if runtime_title:
            return runtime_title

        parts = name.split(".")
        if len(parts) < 3 or parts[-1] != "title":
            return None

        plugin_key = parts[0]
        menu_key = ".".join(parts[1:-1])
        candidate_menu_keys = {
            menu_key,
            menu_key.replace("-", "_"),
            menu_key.replace("_", "-"),
        }

        for candidate_menu_key in candidate_menu_keys:
            candidate_key = f"{plugin_key}.{candidate_menu_key}.title"
            if candidate_key == name:
                continue
            runtime_title = registry.resolve_plugin_menu_title(candidate_key)
            if runtime_title:
                return runtime_title

        return None

    @staticmethod
    def _resolve_plugin_permission_title(name: str) -> str | None:
        from app.plugins.registry import ExtensionRegistry

        registry = ExtensionRegistry.get_instance()
        return registry.resolve_plugin_permission_title(name)

    @staticmethod
    def _fallback_permission_name(name: str) -> str:
        parts = name.split(".")
        fallback = parts[-1] if parts else name
        if fallback == "title" and len(parts) >= 2:
            menu_name = parts[-2].replace("-", " ").replace("_", " ").strip()
            if menu_name:
                return menu_name
        return fallback

    @staticmethod
    def _is_plugin_menu(code: str | None) -> bool:
        return bool(code and ".plugin_" in code)

    @classmethod
    def _build_permission_tree(
        cls,
        permissions: list[Permission],
        parent_id: int | None = None,
    ) -> list[PermissionTreeResponse]:
        tree = []
        for perm in permissions:
            if perm.parent_id == parent_id:
                children = cls._build_permission_tree(permissions, perm.id)
                tree.append(
                    PermissionTreeResponse(
                        id=perm.id,
                        code=perm.code,
                        name=cls._translate_name(perm.name),
                        description=perm.description,
                        type=perm.type,
                        scope=perm.scope,
                        resource=perm.resource,
                        action=perm.action,
                        parent_id=perm.parent_id,
                        sort_order=perm.sort_order,
                        icon=perm.icon,
                        path=perm.path,
                        component=perm.component,
                        hidden=perm.hidden,
                        children=children,
                    )
                )
        return sorted(tree, key=lambda x: x.sort_order)

    @classmethod
    def serialize_permission(cls, permission: Permission) -> PermissionResponse:
        """Project a Permission ORM object into the shared API response shape."""

        return PermissionResponse(
            id=permission.id,
            code=permission.code,
            name=cls._translate_name(permission.name),
            description=permission.description,
            type=permission.type,
            scope=permission.scope,
            resource=permission.resource,
            action=permission.action,
            parent_id=permission.parent_id,
            sort_order=permission.sort_order,
            icon=permission.icon,
            path=permission.path,
            component=permission.component,
            hidden=permission.hidden,
        )

    @classmethod
    def build_simple_permission_tree(
        cls,
        permissions: list[Permission],
        parent_id: int | None = None,
    ) -> list:
        """Build the simplified plan-assignment permission tree with shared titles."""

        from app.schemas.tenant.plan import PermissionTreeSimpleResponse

        tree: list[PermissionTreeSimpleResponse] = []
        for permission in permissions:
            if permission.parent_id != parent_id:
                continue

            children = cls.build_simple_permission_tree(permissions, permission.id)
            tree.append(
                PermissionTreeSimpleResponse(
                    id=permission.id,
                    code=permission.code,
                    name=cls._translate_name(permission.name),
                    type=permission.type,
                    resource=permission.resource,
                    parent_id=permission.parent_id,
                    sort_order=permission.sort_order,
                    children=children,
                )
            )

        return sorted(tree, key=lambda item: item.sort_order)

    @staticmethod
    def _normalize_menu_ai_strings(values: list[str] | None) -> list[str]:
        normalized: list[str] = []
        for value in values or []:
            text = str(value or "").strip()
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    @staticmethod
    def _scope_enum_from_value(scope: str | None) -> PermissionScope | None:
        try:
            if scope:
                return PermissionScope(scope)
        except ValueError:
            return None
        return None

    @classmethod
    def _infer_menu_ai_category(cls, permission: Permission) -> str | None:
        path = str(permission.path or "").strip("/")
        if path:
            first_segment = path.split("/", 1)[0].strip()
            if first_segment and first_segment not in {"admin", "tenant", "user"}:
                return first_segment

        action = str(getattr(permission, "action", "") or "").strip()
        if action:
            parts = [part for part in action.split(".") if part]
            if len(parts) >= 2:
                return parts[1]
        return None

    @classmethod
    def _build_generic_menu_ai_keywords(
        cls,
        permission: Permission,
        *,
        translated_name: str,
    ) -> list[str]:
        keywords: list[str] = []

        def _add(value: str | None) -> None:
            text = str(value or "").strip()
            if not text or text in keywords:
                return
            keywords.append(text)

        _add(translated_name)

        path = str(permission.path or "").strip()
        if path:
            for segment in path.strip("/").split("/"):
                cleaned = segment.strip()
                if not cleaned or cleaned in {"admin", "tenant", "user"}:
                    continue
                _add(cleaned)
                for token in _MENU_AI_TOKEN_RE.findall(cleaned.replace("-", " ")):
                    _add(token)

        action = str(getattr(permission, "action", "") or "").strip()
        if action:
            for part in action.split("."):
                cleaned = part.strip()
                if not cleaned or cleaned in {"admin", "tenant", "user"}:
                    continue
                _add(cleaned)
                for token in _MENU_AI_TOKEN_RE.findall(cleaned.replace("_", " ")):
                    _add(token)

        code = str(permission.code or "").strip()
        if code.startswith("menu:"):
            tail = code.split(":", 1)[1]
            for part in tail.split("."):
                cleaned = part.strip()
                if not cleaned or cleaned in {"admin", "tenant", "user", "menu"}:
                    continue
                _add(cleaned)
                for token in _MENU_AI_TOKEN_RE.findall(cleaned.replace("_", " ")):
                    _add(token)

        return keywords

    @classmethod
    def _build_menu_ai_meta(cls, permission: Permission) -> MenuMetaResponse | None:
        scope_enum = cls._scope_enum_from_value(getattr(permission, "scope", None))
        registry_meta = (
            permission_registry.get(permission.code, scope_enum)
            if scope_enum is not None
            else None
        )
        ai_config = getattr(registry_meta, "ai", None)

        translated_name = cls._translate_name(permission.name)
        keywords = cls._build_generic_menu_ai_keywords(
            permission,
            translated_name=translated_name,
        )
        if ai_config is not None:
            keywords = cls._normalize_menu_ai_strings(
                [*(ai_config.keywords or []), *keywords]
            )
            capabilities = cls._normalize_menu_ai_strings(ai_config.capabilities or [])
            category = str(
                ai_config.category or ""
            ).strip() or cls._infer_menu_ai_category(permission)
            description = (
                str(ai_config.description or "").strip()
                or str(getattr(permission, "description", "") or "").strip()
                or None
            )
            mode = str(ai_config.mode or "").strip() or None
            page_context_key = str(ai_config.page_context_key or "").strip() or None
            disabled_capabilities = ai_config.disabled_capabilities
            disabled_operations = ai_config.disabled_operations
        else:
            capabilities = []
            category = cls._infer_menu_ai_category(permission)
            description = (
                str(getattr(permission, "description", "") or "").strip() or None
            )
            mode = None
            page_context_key = None
            disabled_capabilities = None
            disabled_operations = None

        if not any(
            [
                description,
                keywords,
                capabilities,
                category,
                mode,
                page_context_key,
                disabled_capabilities,
                disabled_operations,
            ]
        ):
            return None

        return MenuMetaResponse(
            ai=MenuAIResponse(
                description=description,
                keywords=keywords,
                capabilities=capabilities,
                category=category,
                mode=mode,
                page_context_key=page_context_key,
                disabled_capabilities=disabled_capabilities,
                disabled_operations=disabled_operations,
            )
        )

    @classmethod
    def _build_menu_tree(
        cls,
        permissions: list[Permission],
        user_permission_codes: set[str] | None = None,
        parent_id: int | None = None,
    ) -> list[MenuResponse]:
        tree = []
        seen_plugin_paths: set[str] = set()
        for perm in permissions:
            if perm.parent_id == parent_id and perm.type == "menu":
                children = cls._build_menu_tree(
                    permissions, user_permission_codes, perm.id
                )

                menu_permissions = []
                for permission in permissions:
                    if (
                        permission.type == "operation"
                        and permission.parent_id == perm.id
                        and (
                            user_permission_codes is None
                            or permission.code in user_permission_codes
                        )
                    ):
                        menu_permissions.append(permission.code)

                is_plugin_menu = cls._is_plugin_menu(perm.code)
                if is_plugin_menu and perm.path and perm.path in seen_plugin_paths:
                    continue
                menu_component = None if is_plugin_menu else perm.component
                if (
                    not perm.component
                    and not children
                    and not menu_permissions
                    and not is_plugin_menu
                ):
                    continue

                tree.append(
                    MenuResponse(
                        id=perm.id,
                        code=perm.code,
                        name=cls._translate_name(perm.name),
                        icon=perm.icon,
                        path=perm.path,
                        component=menu_component,
                        hidden=perm.hidden,
                        sort_order=perm.sort_order,
                        permissions=sorted(menu_permissions),
                        meta=cls._build_menu_ai_meta(perm),
                        children=children,
                    )
                )
                if is_plugin_menu and perm.path:
                    seen_plugin_paths.add(perm.path)
        return sorted(tree, key=lambda x: x.sort_order)
