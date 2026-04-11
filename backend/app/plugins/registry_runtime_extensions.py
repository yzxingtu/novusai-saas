"""Runtime extension families extracted from ExtensionRegistry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from starlette.middleware import Middleware

from app.core.logging import get_logger

logger = get_logger(__name__)


class RegistryRuntimeExtensionsMixin:
    """Consumer/middleware/custom extension families for ExtensionRegistry."""

    def register_consumer(
        self,
        plugin_name: str,
        consumer_name: str,
        handler: Callable,
        queue: str = "default",
        max_retries: int = 3,
        retry_delay: int = 60,
    ) -> None:
        from app.celery_app import celery_app
        from app.plugins.registry import _RegistryRuntimeBridge

        celery_task_name = f"plugin.{plugin_name}.{consumer_name}"

        if celery_task_name not in celery_app.tasks:
            import asyncio
            import functools

            if asyncio.iscoroutinefunction(handler):

                @functools.wraps(handler)
                def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                    return _RegistryRuntimeBridge.run_async(handler(*args, **kwargs))

                celery_app.task(
                    name=celery_task_name,
                    queue=queue,
                    max_retries=max_retries,
                    default_retry_delay=retry_delay,
                )(_sync_wrapper)
            else:
                celery_app.task(
                    name=celery_task_name,
                    queue=queue,
                    max_retries=max_retries,
                    default_retry_delay=retry_delay,
                )(handler)

        consumer_info: dict[str, Any] = {
            "name": consumer_name,
            "celery_task_name": celery_task_name,
            "queue": queue,
        }
        self._plugin_consumers.setdefault(plugin_name, []).append(consumer_info)
        self._track(plugin_name, "consumer", celery_task_name, consumer_info)
        logger.info(
            "Plugin {} registered consumer: {} (queue={})",
            plugin_name,
            consumer_name,
            queue,
        )

    def _unregister_consumer(self, ext: Any) -> None:
        plugin_name = ext.plugin_name
        celery_task_name = ext.key
        if plugin_name in self._plugin_consumers:
            self._plugin_consumers[plugin_name] = [
                c
                for c in self._plugin_consumers[plugin_name]
                if c.get("celery_task_name") != celery_task_name
            ]
        logger.info(
            "Plugin consumer unregistered (Celery task remains until restart): {}",
            celery_task_name,
        )

    def _iter_runtime_plugin_middlewares(self) -> list[dict[str, Any]]:
        from app.plugins.registry import _RegistryRuntimeBridge

        return _RegistryRuntimeBridge.iter_runtime_middlewares(self._plugin_middlewares)

    def _rebuild_runtime_middleware_stack(self, fastapi_app: Any) -> None:
        from app.plugins.registry import _RegistryRuntimeBridge

        _RegistryRuntimeBridge.rebuild_runtime_middleware_stack(fastapi_app)

    def _sync_runtime_plugin_middlewares(
        self,
        *,
        removed_runtime_middleware: Middleware | None = None,
    ) -> bool:
        from app.plugins.registry import _RegistryRuntimeBridge

        return _RegistryRuntimeBridge.sync_runtime_middlewares(
            self._plugin_middlewares,
            removed_runtime_middleware=removed_runtime_middleware,
        )

    def register_middleware(
        self,
        plugin_name: str,
        name: str,
        middleware_cls: type,
        priority: int = 50,
    ) -> None:
        entry: dict[str, Any] = {
            "plugin_name": plugin_name,
            "name": name,
            "cls": middleware_cls,
            "priority": priority,
            "runtime_middleware": Middleware(middleware_cls),
        }
        self._plugin_middlewares.setdefault(plugin_name, []).append(entry)
        self._track(plugin_name, "middleware", f"{plugin_name}:{name}", entry)

        if self._sync_runtime_plugin_middlewares():
            logger.info(
                "Plugin {} registered middleware: {} (priority={})",
                plugin_name,
                name,
                priority,
            )
        else:
            logger.warning(
                "Plugin {}: middleware {} registered in registry, but runtime sync skipped",
                plugin_name,
                name,
            )

    def _unregister_middleware(self, ext: Any) -> None:
        plugin_name = ext.plugin_name
        name = ext.key.split(":", 1)[-1]
        removed_runtime_middleware = (
            ext.ref.get("runtime_middleware") if isinstance(ext.ref, dict) else None
        )
        if plugin_name in self._plugin_middlewares:
            self._plugin_middlewares[plugin_name] = [
                m
                for m in self._plugin_middlewares[plugin_name]
                if m is not ext.ref and m.get("name") != name
            ]
            if not self._plugin_middlewares[plugin_name]:
                self._plugin_middlewares.pop(plugin_name, None)

        if self._sync_runtime_plugin_middlewares(
            removed_runtime_middleware=removed_runtime_middleware
        ):
            logger.info("Plugin middleware unregistered from runtime: {}", ext.key)
        else:
            logger.info(
                "Plugin middleware unregistered from registry only: {}", ext.key
            )

    def get_plugin_middlewares(
        self,
        plugin_name: str | None = None,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        plugins_iter = (
            [plugin_name] if plugin_name else list(self._plugin_middlewares.keys())
        )
        for pname in plugins_iter:
            result.extend(self._plugin_middlewares.get(pname, []))
        result.sort(key=lambda x: x.get("priority", 50))
        return result

    def register_custom(
        self,
        plugin_name: str,
        ext_type: str,
        name: str,
        data: dict[str, Any] | None = None,
        description: str = "",
    ) -> None:
        entry: dict[str, Any] = {
            "plugin_name": plugin_name,
            "type": ext_type,
            "name": name,
            "data": data or {},
            "description": description,
        }
        key = f"{ext_type}:{name}"
        customs = self._plugin_custom_extensions.setdefault(plugin_name, [])
        self._plugin_custom_extensions[plugin_name] = [
            c for c in customs if f"{c['type']}:{c['name']}" != key
        ]
        self._plugin_custom_extensions[plugin_name].append(entry)
        self._track(plugin_name, "custom", key, entry)
        logger.info(
            "Plugin {} registered custom extension: {}/{}",
            plugin_name,
            ext_type,
            name,
        )

    def _unregister_custom(self, ext: Any) -> None:
        plugin_name = ext.plugin_name
        key = ext.key
        if isinstance(ext.ref, dict) and ext.ref.get("type") == "captcha_provider":
            from app.captcha.registry import registry as captcha_registry

            provider_code = str(
                (ext.ref.get("data") or {}).get("provider_code")
                or ext.ref.get("name")
                or ""
            ).strip()
            if provider_code:
                captcha_registry.unregister(provider_code)

        if plugin_name in self._plugin_custom_extensions:
            self._plugin_custom_extensions[plugin_name] = [
                c
                for c in self._plugin_custom_extensions[plugin_name]
                if f"{c['type']}:{c['name']}" != key
            ]

    def get_custom_extensions(
        self,
        ext_type: str | None = None,
        plugin_name: str | None = None,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        plugins_iter = (
            [plugin_name] if plugin_name else list(self._plugin_custom_extensions.keys())
        )
        for pname in plugins_iter:
            for ext in self._plugin_custom_extensions.get(pname, []):
                if ext_type and ext.get("type") != ext_type:
                    continue
                result.append(ext)
        return result

    def get_plugin_tenant_menu_policy(self, plugin_name: str) -> dict[str, Any]:
        return self.read_layer.get_plugin_tenant_menu_policy(plugin_name)

    def get_frontend_slots_grouped(
        self,
        scope: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        return self.read_layer.get_frontend_slots_grouped(scope=scope)

    def get_registered_count(self, plugin_name: str) -> int:
        return len(self._registry.get(plugin_name, []))

    def register_notification(
        self,
        plugin_name: str,
        template_code: str,
        title: dict[str, str] | None = None,
        channels: list[str] | None = None,
        category: str = "biz",
    ) -> None:
        """
        Register notification template.
        / 注册通知模板。

        Writes plugin-declared notification templates to the in-memory registry for runtime query by notification service.
        / 将插件声明的通知模板写入内存注册表。
        """
        full_code = (
            f"plugin.{plugin_name}.{template_code}"
            if not template_code.startswith("plugin.")
            else template_code
        )
        self._plugin_notifications[full_code] = {
            "plugin_name": plugin_name,
            "code": full_code,
            "title": title or {},
            "channels": channels or ["ws", "inbox"],
            "category": category,
        }
        self._track(
            plugin_name,
            "notification",
            full_code,
            {
                "title": title or {},
                "channels": channels or ["ws", "inbox"],
                "category": category,
            },
        )
        logger.info(
            "Plugin {} registered notification: {}",
            plugin_name,
            full_code,
        )

    def _unregister_notification(self, ext: Any) -> None:
        """Remove plugin notification template registration / 移除插件通知模板注册"""
        self._plugin_notifications.pop(ext.key, None)

    def get_plugin_notification(self, code: str) -> dict | None:
        """Get plugin-registered notification template (for notification service query) / 获取插件注册的通知模板"""
        return self._plugin_notifications.get(code)

    def register_permission(
        self,
        plugin_name: str,
        code: str,
        name: dict[str, str] | None = None,
        scope: str = "all_tenants",
        actions: list[str] | None = None,
    ) -> None:
        """
        Register plugin permission.
        / 注册插件权限。

        Writes plugin-declared permissions to the in-memory registry for runtime query by RBAC middleware.
        / 将插件声明的权限写入内存注册表。
        """
        full_code = (
            f"plugin.{plugin_name}.{code}" if not code.startswith("plugin.") else code
        )
        self._plugin_permissions[full_code] = {
            "plugin_name": plugin_name,
            "code": full_code,
            "name": name or {},
            "scope": scope,
            "actions": actions or [],
        }
        self._track(
            plugin_name,
            "permission",
            full_code,
            {
                "name": name or {},
                "scope": scope,
                "actions": actions or [],
            },
        )
        normalized_name: dict[str, str] = {}
        if isinstance(name, dict):
            normalized_name = {
                str(k): str(v).strip() for k, v in name.items() if str(v or "").strip()
            }
        elif isinstance(name, str) and name.strip():
            normalized_name = {"zh-CN": name.strip(), "en": name.strip()}
        if normalized_name:
            titles = self._plugin_permission_titles.setdefault(plugin_name, {})
            safe_name = plugin_name.replace("-", "_")
            base_code_prefix = f"plugin.{plugin_name}."
            base_code = (
                full_code[len(base_code_prefix) :]
                if full_code.startswith(base_code_prefix)
                else code
            )
            titles[f"{safe_name}.permission.{base_code}"] = normalized_name
        logger.info("Plugin {} registered permission: {}", plugin_name, full_code)

    def _unregister_permission(self, ext: Any) -> None:
        """Remove plugin permission registration / 移除插件权限注册"""
        self._plugin_permissions.pop(ext.key, None)
        plugin_name = ext.plugin_name
        if plugin_name in self._plugin_permission_titles:
            safe_name = plugin_name.replace("-", "_")
            base_code_prefix = f"plugin.{plugin_name}."
            base_code = (
                ext.key[len(base_code_prefix) :]
                if ext.key.startswith(base_code_prefix)
                else ext.key
            )
            self._plugin_permission_titles[plugin_name].pop(
                f"{safe_name}.permission.{base_code}",
                None,
            )

    def get_plugin_permissions(self, plugin_name: str | None = None) -> list[dict]:
        """Get plugin-registered permission list (for RBAC query) / 获取插件注册的权限列表"""
        if plugin_name:
            return [
                value
                for value in self._plugin_permissions.values()
                if value["plugin_name"] == plugin_name
            ]
        return list(self._plugin_permissions.values())

    def register_menu(
        self,
        plugin_name: str,
        name: str,
        path: str,
        icon: str = "",
        parent: str = "",
        sort_order: int = 100,
        scope: str = "admin",
        component: str = "",
        title: dict[str, str] | None = None,
        hidden: bool = False,
    ) -> None:
        """
        Register plugin menu entry (stored in-memory, synced to permission system on enable).
        / 注册插件菜单条目（内存存储，enable 时同步到权限系统）。

        scope 须为权限端别字面量：admin / tenant（与 PermissionScope 一致）。
        """
        from app.enums.rbac import PermissionScope as _PS

        allowed_menu_scopes = {_PS.ADMIN.value, _PS.TENANT.value}
        if scope not in allowed_menu_scopes:
            raise ValueError(
                f"Invalid plugin menu scope {scope!r}; expected one of {sorted(allowed_menu_scopes)}"
            )

        menu_entry: dict[str, Any] = {
            "plugin_name": plugin_name,
            "name": name,
            "path": path,
            "icon": icon,
            "parent": parent,
            "sort_order": sort_order,
            "scope": scope,
            "component": component,
            "title": title or {},
            "hidden": hidden,
        }
        menus = self._plugin_menus.setdefault(plugin_name, [])
        self._plugin_menus[plugin_name] = [menu for menu in menus if menu.get("name") != name]
        self._plugin_menus[plugin_name].append(menu_entry)

        if title:
            titles = self._plugin_menu_titles.setdefault(plugin_name, {})
            safe_name = plugin_name.replace("-", "_")
            i18n_key = f"{safe_name}.{name}.title"
            titles[i18n_key] = title

        self._track(plugin_name, "menu", name, menu_entry)
        self._register_menu_permission(
            plugin_name,
            name,
            path,
            icon,
            parent,
            sort_order,
            scope,
            component,
            hidden,
        )

        logger.info(
            "Plugin {} registered menu: {} (parent={}, scope={})",
            plugin_name,
            name,
            parent,
            scope,
        )

    def _register_menu_permission(
        self,
        plugin_name: str,
        name: str,
        path: str,
        icon: str,
        parent: str,
        sort_order: int,
        scope: str,
        component: str,
        hidden: bool,
    ) -> None:
        """
        Bridge plugin menu entry to permission_registry as PermissionMeta.
        / 将插件菜单条目桥接到 permission_registry，生成 PermissionMeta。

        Permission code format: menu:{admin|tenant}.plugin_{safe_name}_{menu_name}
        Must match the prefix pattern used by sync_plugin_permissions() and
        _set_plugin_permissions_enabled() in lifecycle.py.
        """
        from app.enums.rbac import PermissionScope, PermissionType
        from app.plugins.registry import _build_plugin_menu_action
        from app.rbac.decorators import PermissionMeta
        from app.rbac.registry import permission_registry

        safe_name = plugin_name.replace("-", "_")

        if scope == PermissionScope.ADMIN.value:
            scope_prefix = "admin"
            perm_scope = PermissionScope.ADMIN
        elif scope == PermissionScope.TENANT.value:
            scope_prefix = "tenant"
            perm_scope = PermissionScope.TENANT
        else:
            raise ValueError(
                f"Invalid plugin menu scope {scope!r}; expected "
                f"{PermissionScope.ADMIN.value!r} or {PermissionScope.TENANT.value!r}"
            )

        perm_code = f"menu:{scope_prefix}.plugin_{safe_name}_{name}"
        parent_code = f"menu:{scope_prefix}.{parent}" if parent else None
        i18n_key = f"{safe_name}.{name}.title"

        perm_meta = PermissionMeta(
            code=perm_code,
            name=i18n_key,
            type=PermissionType.MENU,
            scope=perm_scope,
            resource="menu",
            action=_build_plugin_menu_action(scope_prefix, safe_name, name),
            icon=icon,
            path=path,
            component=component,
            parent_code=parent_code,
            sort_order=sort_order,
            hidden=hidden,
        )
        permission_registry.register(perm_meta)

    def _unregister_menu(self, ext: Any) -> None:
        """Remove plugin menu registration / 移除插件菜单注册"""
        plugin_name = ext.plugin_name
        name = ext.key
        if plugin_name in self._plugin_menus:
            self._plugin_menus[plugin_name] = [
                menu for menu in self._plugin_menus[plugin_name] if menu.get("name") != name
            ]
        if plugin_name in self._plugin_menu_titles:
            safe_name = plugin_name.replace("-", "_")
            i18n_key = f"{safe_name}.{name}.title"
            self._plugin_menu_titles[plugin_name].pop(i18n_key, None)

        from app.rbac.registry import permission_registry

        safe_name = plugin_name.replace("-", "_")
        permission_registry.unregister(f"menu:admin.plugin_{safe_name}_{name}")
        permission_registry.unregister(f"menu:tenant.plugin_{safe_name}_{name}")

    def get_plugin_menus(
        self,
        plugin_name: str | None = None,
        scope: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get plugin menu list (for frontend navigation building) / 获取插件菜单列表"""
        result: list[dict[str, Any]] = []
        plugins_iter = [plugin_name] if plugin_name else list(self._plugin_menus.keys())
        for pname in plugins_iter:
            for menu in self._plugin_menus.get(pname, []):
                if scope and menu.get("scope") != scope:
                    continue
                result.append(menu)
        result.sort(key=lambda item: item.get("sort_order", 100))
        return result

    def resolve_plugin_menu_title(self, i18n_key: str) -> str | None:
        return self.read_layer.resolve_plugin_menu_title(i18n_key)

    def resolve_plugin_permission_title(self, i18n_key: str) -> str | None:
        return self.read_layer.resolve_plugin_permission_title(i18n_key)

    def register_socketio(
        self,
        plugin_name: str,
        namespace_path: str,
        handler_class: type,
        auth_required: bool = True,
        auth_scopes: list[str] | None = None,
    ) -> None:
        """
        Register plugin Socket.IO namespace to global AsyncServer.
        / 注册插件 Socket.IO namespace 到全局 AsyncServer。

        Namespace path is auto-prefixed with /plugin/{plugin_name}/.
        If auth_required=True, automatically wraps handler_class with
        PluginAuthNamespaceWrapper for JWT validation and tenant isolation.
        / namespace 路径自动添加前缀，auth_required=True 时自动包装认证。
        """
        from app.core.socketio_server import get_sio

        full_ns = f"/plugin/{plugin_name}/{namespace_path.strip('/')}"
        sio = get_sio()

        if auth_required:
            from app.plugins.sio_auth import PluginAuthNamespaceWrapper

            wrapped = PluginAuthNamespaceWrapper(
                delegate=handler_class(full_ns),
                plugin_name=plugin_name,
                auth_scopes=auth_scopes or ["tenant_admin"],
            )
            sio.register_namespace(wrapped)
        else:
            sio.register_namespace(handler_class(full_ns))

        self._track(plugin_name, "socketio", full_ns, handler_class)
        logger.info(
            "Plugin {} registered Socket.IO namespace: {} (auth={} scopes={})",
            plugin_name,
            full_ns,
            auth_required,
            auth_scopes,
        )

    def _unregister_socketio(self, ext: Any) -> None:
        """Unregister plugin Socket.IO namespace / 反注册插件 Socket.IO namespace"""
        try:
            from app.core.socketio_server import get_sio

            sio = get_sio()
            full_ns = ext.key
            if hasattr(sio, "namespace_handlers") and full_ns in sio.namespace_handlers:
                del sio.namespace_handlers[full_ns]
                logger.info("Removed Socket.IO namespace: {}", full_ns)
            else:
                logger.warning("Socket.IO namespace {} not found in handlers", full_ns)
        except Exception as exc:
            logger.warning(
                "Failed to unregister socketio namespace {}: {}", ext.key, exc
            )

    def register_frontend_slot(
        self,
        plugin_name: str,
        slot_type: str,
        **data: object,
    ) -> None:
        """
        Register plugin frontend slot.
        / 注册插件前端插槽。

        Dedup strategy: unique by (slot_type, name), overwrites old value on re-registration.
        / 去重策略：按 (slot_type, name) 唯一，重复注册时覆盖旧值。
        """
        slot_entry = {"slot_type": slot_type, "plugin_name": plugin_name, **data}
        dedup_key = f"{slot_type}:{data.get('name', '')}"

        slots = self._plugin_frontend_slots.setdefault(plugin_name, [])
        self._plugin_frontend_slots[plugin_name] = [
            slot for slot in slots if f"{slot['slot_type']}:{slot.get('name', '')}" != dedup_key
        ]
        self._plugin_frontend_slots[plugin_name].append(slot_entry)

        self._track(plugin_name, "frontend_slot", dedup_key, slot_entry)
        logger.info(
            "Plugin {} registered frontend slot: {}/{}",
            plugin_name,
            slot_type,
            data.get("name", ""),
        )

    def _unregister_frontend_slot(self, ext: Any) -> None:
        """Remove plugin frontend slot registration / 移除插件前端插槽注册"""
        plugin_name = ext.plugin_name
        key = ext.key
        if plugin_name in self._plugin_frontend_slots:
            self._plugin_frontend_slots[plugin_name] = [
                slot
                for slot in self._plugin_frontend_slots[plugin_name]
                if f"{slot['slot_type']}:{slot.get('name', '')}" != key
            ]

    def get_frontend_slots(
        self,
        slot_type: str | None = None,
        scope: str | None = None,
        plugin_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get frontend slot data for GET /plugins/slots API.
        / 获取前端插槽数据。
        """
        all_slots: list[dict[str, Any]] = []
        plugins_iter = (
            [plugin_name] if plugin_name else list(self._plugin_frontend_slots.keys())
        )
        for pname in plugins_iter:
            for slot in self._plugin_frontend_slots.get(pname, []):
                if slot_type and slot.get("slot_type") != slot_type:
                    continue
                if scope:
                    slot_scope = slot.get("scope", "")
                    if (
                        scope == "admin"
                        and slot_scope == "tenant"
                        or scope == "tenant"
                        and slot_scope == "admin"
                    ):
                        continue
                all_slots.append(slot)
        return all_slots
