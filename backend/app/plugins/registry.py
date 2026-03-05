"""
扩展点注册中心

桥接插件扩展点声明到已有系统注册表，追踪注册记录用于反注册。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# 共享事件循环（Celery worker 中运行异步插件任务用）
_bg_loop = None
_bg_thread = None
_bg_lock = None  # 延迟初始化，避免模块导入时创建线程对象


def _get_bg_lock():
    """获取全局锁（懒初始化，线程安全）"""
    import threading

    global _bg_lock
    if _bg_lock is None:
        # 模块级初始化 — CPython GIL 保证此赋值原子，无需双重检查
        _bg_lock = threading.Lock()
    return _bg_lock


def _run_async(coro):
    """在共享后台事件循环中运行协程（避免每次创建/销毁循环）"""
    import asyncio
    import threading

    global _bg_loop, _bg_thread
    with _get_bg_lock():
        if _bg_loop is None or _bg_loop.is_closed():
            _bg_loop = asyncio.new_event_loop()
            _bg_thread = threading.Thread(
                target=_bg_loop.run_forever, daemon=True, name="plugin-task-loop",
            )
            _bg_thread.start()
        loop = _bg_loop
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


@dataclass
class RegisteredExtension:
    """已注册的扩展记录"""

    plugin_name: str
    ext_type: str
    key: str
    ref: Any = None


class ExtensionRegistry:
    """
    扩展点注册中心（单例）

    职责：
    - 桥接插件扩展到已有系统注册表（AdapterRegistry / HookRegistry / StorageManager 等）
    - 追踪每个插件注册的扩展，供 unregister_all 反注册使用
    - 提供插件技能解析器和执行器的查询接口
    """

    _instance: ExtensionRegistry | None = None

    def __init__(self) -> None:
        self._registry: dict[str, list[RegisteredExtension]] = {}
        self._plugin_skill_resolvers: dict[str, Callable] = {}
        self._plugin_executors: dict[str, Callable] = {}
        self._plugin_webhooks: dict[str, dict[str, Any]] = {}
        self._plugin_notifications: dict[str, dict[str, Any]] = {}
        self._plugin_permissions: dict[str, dict[str, Any]] = {}
        # slot_type 取値见 FrontendSlotTypeEnum
        self._plugin_frontend_slots: dict[str, list[dict[str, Any]]] = {}
        # consumer: plugin_name -> list of consumer info dicts
        self._plugin_consumers: dict[str, list[dict[str, Any]]] = {}
        # custom: plugin_name -> list of custom extension dicts
        self._plugin_custom_extensions: dict[str, list[dict[str, Any]]] = {}
        # middleware: plugin_name -> list of middleware class refs
        self._plugin_middlewares: dict[str, list[dict[str, Any]]] = {}
        # menu i18n fallback: plugin_name -> {i18n_key: {"zh-CN": "...", "en": "..."}}
        self._plugin_menu_titles: dict[str, dict[str, dict[str, str]]] = {}

    @classmethod
    def get_instance(cls) -> ExtensionRegistry:
        """获取单例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """重置单例（仅测试用）"""
        cls._instance = None

    # ── 追踪 ──

    def _track(
        self, plugin_name: str, ext_type: str, key: str, ref: Any = None
    ) -> None:
        """追踪已注册的扩展"""
        if plugin_name not in self._registry:
            self._registry[plugin_name] = []
        self._registry[plugin_name].append(
            RegisteredExtension(plugin_name, ext_type, key, ref)
        )

    # ── 1. Adapter ──

    def register_adapter(
        self, plugin_name: str, provider_type: str, adapter_class: type
    ) -> None:
        """注册 AI 适配器 → AdapterRegistry"""
        from app.ai.adapters import AdapterRegistry

        AdapterRegistry.register(provider_type, adapter_class)
        self._track(plugin_name, "adapter", provider_type)
        logger.info(
            "Plugin %s registered adapter: %s", plugin_name, provider_type
        )

    def _unregister_adapter(self, ext: RegisteredExtension) -> None:
        from app.ai.adapters import AdapterRegistry

        AdapterRegistry.unregister(ext.key)

    # ── 2. Hook ──

    def register_hook(
        self,
        plugin_name: str,
        hook_point: str,
        handler: Callable,
        priority: int = 50,
    ) -> None:
        """注册钩子 → HookRegistry"""
        from app.ai.events.hooks import HookRegistry

        HookRegistry.get_instance().register(hook_point, handler, priority)
        self._track(plugin_name, "hook", hook_point, handler)
        logger.info(
            "Plugin %s registered hook: %s (priority=%d)",
            plugin_name, hook_point, priority,
        )

    def _unregister_hook(self, ext: RegisteredExtension) -> None:
        from app.ai.events.hooks import HookRegistry

        HookRegistry.get_instance().unregister(ext.key, ext.ref)

    # ── 3. Storage Driver ──

    def register_storage_driver(
        self, plugin_name: str, driver_class: type
    ) -> None:
        """注册存储驱动 → StorageManager"""
        from app.storage.manager import storage_manager

        storage_manager.register_driver(driver_class)
        driver_name = getattr(driver_class, "name", "")
        self._track(plugin_name, "storage", driver_name, driver_class)
        logger.info(
            "Plugin %s registered storage driver: %s", plugin_name, driver_name
        )

    def _unregister_storage(self, ext: RegisteredExtension) -> None:
        from app.storage.manager import storage_manager

        storage_manager.unregister_driver(ext.key)

    # ── 4. Skill ──

    def register_skill(
        self,
        plugin_name: str,
        skill_type: str,
        resolver: Callable,
        executor: type | Callable | None = None,
    ) -> None:
        """
        注册插件技能

        以 plugin_name 为 key 注册 resolver 和 executor，
        使插件技能可以使用标准类型（如 toolkit）而不与内置 resolver 冲突。

        Args:
            plugin_name: 插件名（注册 key）
            skill_type: 技能类型标识（仅用于日志）
            resolver: 技能解析函数 (skill, config) -> list[ToolDefinition]
            executor: 工具执行器类或实例；类会在注册时实例化并缓存
        """
        self._plugin_skill_resolvers[plugin_name] = resolver
        if executor:
            # 类 → 实例化后缓存，避免每次工具调用都创建新实例
            if isinstance(executor, type):
                try:
                    executor = executor()
                except Exception as exc:
                    logger.warning(
                        "Failed to instantiate executor for plugin '%s': %s",
                        plugin_name, exc,
                    )
                    executor = None
            if executor:
                self._plugin_executors[plugin_name] = executor
        self._track(plugin_name, "skill", plugin_name)
        logger.info(
            "Plugin %s registered skill resolver (type=%s)", plugin_name, skill_type
        )

    def _unregister_skill(self, ext: RegisteredExtension) -> None:
        self._plugin_skill_resolvers.pop(ext.key, None)
        self._plugin_executors.pop(ext.key, None)

    def get_plugin_skill_resolver(self, plugin_name: str) -> Callable | None:
        """获取插件技能解析器（按插件名查找）"""
        return self._plugin_skill_resolvers.get(plugin_name)

    def get_plugin_executor(self, plugin_name: str) -> Any:
        """获取插件工具执行器实例（按插件名查找）"""
        return self._plugin_executors.get(plugin_name)

    # ── 5. Event ──

    def register_event(
        self, plugin_name: str, event_type_name: str, handler: Callable
    ) -> None:
        """注册事件订阅（支持 AI typed events 和 PluginEventBus 字符串事件）"""
        if event_type_name.startswith("plugin."):
            from app.plugins.event_bus import PluginEventBus

            bus = PluginEventBus.get_instance()
            bus.subscribe(event_type_name, handler, plugin_name=plugin_name)
            self._track(plugin_name, "event", event_type_name, (event_type_name, handler))
        else:
            from app.ai.events import get_event_bus

            event_cls = self._resolve_event_class(event_type_name)
            get_event_bus().subscribe(event_cls, handler)
            self._track(plugin_name, "event", event_type_name, (event_cls, handler))
        logger.info(
            "Plugin %s subscribed to event: %s", plugin_name, event_type_name
        )

    def _unregister_event(self, ext: RegisteredExtension) -> None:
        event_ref, handler = ext.ref
        if isinstance(event_ref, str) and event_ref.startswith("plugin."):
            from app.plugins.event_bus import PluginEventBus

            PluginEventBus.get_instance().unsubscribe(event_ref, handler=handler)
        else:
            from app.ai.events import get_event_bus

            get_event_bus().unsubscribe(event_ref, handler)

    @staticmethod
    def _resolve_event_class(name: str) -> type:
        """根据类名获取事件类"""
        from app.ai.events import types as event_types
        from app.plugins.exceptions import PluginError

        cls = getattr(event_types, name, None)
        if cls is None:
            raise PluginError(message=f"Unknown event type: {name}")
        return cls

    # ── 6. Webhook ──

    def register_webhook(
        self,
        plugin_name: str,
        path: str,
        handler: Callable,
        method: str = "POST",
        auth_config: dict | None = None,
    ) -> None:
        """注册 Webhook 端点

        路径规范化：path 不以 / 开头时自动补齐，确保生成的 full_path 与
        webhook_dispatcher.py 的 f"/plugins/{name}/{url_path}" 查找格式一致。
        """
        # 规范化：确保 path 以 / 开头（消除 /plugins/{name}path 的不一致风险）
        normalized_path = path if path.startswith("/") else f"/{path}"
        full_path = f"/plugins/{plugin_name}{normalized_path}"
        if plugin_name not in self._plugin_webhooks:
            self._plugin_webhooks[plugin_name] = {}
        self._plugin_webhooks[plugin_name][full_path] = {
            "handler": handler,
            "method": method,
            "auth": auth_config or {},
        }
        self._track(plugin_name, "webhook", full_path, handler)
        logger.info(
            "Plugin %s registered webhook: %s %s",
            plugin_name, method, full_path,
        )

    def _unregister_webhook(self, ext: RegisteredExtension) -> None:
        for plugin_webhooks in self._plugin_webhooks.values():
            plugin_webhooks.pop(ext.key, None)

    def get_plugin_webhooks(
        self, plugin_name: str | None = None
    ) -> dict[str, dict]:
        """获取插件 Webhook 注册（供路由层使用）"""
        if plugin_name:
            return self._plugin_webhooks.get(plugin_name, {})
        result: dict[str, dict] = {}
        for webhooks in self._plugin_webhooks.values():
            result.update(webhooks)
        return result

    # ── 7. Task ──

    def register_task(
        self,
        plugin_name: str,
        task_name: str,
        handler: Callable,
        schedule_type: str = "interval",
        cron_expression: str | None = None,
        interval_seconds: int | None = None,
        queue: str = "default",
    ) -> None:
        """
        注册定时任务到 Celery Beat。

        将插件声明的定时任务包装为 Celery task 并注入 beat_schedule。
        任务名约定: plugin.{plugin_name}.{task_name}
        """
        from app.celery_app import celery_app

        celery_task_name = f"plugin.{plugin_name}.{task_name}"

        # 将 handler 包装为 Celery task（如果尚未注册）
        if celery_task_name not in celery_app.tasks:
            import asyncio
            import functools

            if asyncio.iscoroutinefunction(handler):
                @functools.wraps(handler)
                def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                    return _run_async(handler(*args, **kwargs))
                celery_app.task(name=celery_task_name, queue=queue)(_sync_wrapper)
            else:
                celery_app.task(name=celery_task_name, queue=queue)(handler)

        # 注入 beat_schedule
        beat_key = f"plugin_{plugin_name}_{task_name}"
        schedule_entry: dict[str, Any] = {
            "task": celery_task_name,
            "options": {"queue": queue},
        }

        if schedule_type == "cron" and cron_expression:
            from celery.schedules import crontab
            parts = cron_expression.strip().split()
            if len(parts) == 5:
                schedule_entry["schedule"] = crontab(
                    minute=parts[0], hour=parts[1],
                    day_of_month=parts[2], month_of_year=parts[3],
                    day_of_week=parts[4],
                )
            else:
                logger.warning(
                    "Plugin %s task %s: invalid cron '%s', skipping schedule",
                    plugin_name, task_name, cron_expression,
                )
        elif interval_seconds and interval_seconds > 0:
            schedule_entry["schedule"] = float(interval_seconds)
        else:
            logger.warning(
                "Plugin %s task %s: no valid schedule, task registered but not scheduled",
                plugin_name, task_name,
            )

        if "schedule" in schedule_entry:
            if not celery_app.conf.beat_schedule:
                celery_app.conf.beat_schedule = {}
            celery_app.conf.beat_schedule[beat_key] = schedule_entry

        self._track(plugin_name, "task", beat_key, {
            "celery_task_name": celery_task_name,
            "handler": handler,
        })
        logger.info(
            "Plugin %s registered task: %s (%s)",
            plugin_name, task_name, schedule_type,
        )

    def _unregister_task(self, ext: RegisteredExtension) -> None:
        """从 Celery Beat 移除插件定时任务"""
        try:
            from app.celery_app import celery_app
            beat_key = ext.key  # plugin_{name}_{task_name}
            if celery_app.conf.beat_schedule and beat_key in celery_app.conf.beat_schedule:
                del celery_app.conf.beat_schedule[beat_key]
                logger.info("Removed beat schedule: %s", beat_key)
        except Exception as exc:
            logger.warning("Failed to unregister task %s: %s", ext.key, exc)

    # ── 8. Notification ──

    def register_notification(
        self,
        plugin_name: str,
        template_code: str,
        title: dict[str, str] | None = None,
        channels: list[str] | None = None,
        category: str = "biz",
    ) -> None:
        """
        注册通知模板。

        将插件声明的通知模板写入内存注册表，供通知服务在运行时查询。
        DB 持久化在 lifecycle.enable() 中通过独立逻辑处理（如有需要）。
        """
        full_code = f"plugin.{plugin_name}.{template_code}" if not template_code.startswith("plugin.") else template_code
        self._plugin_notifications[full_code] = {
            "plugin_name": plugin_name,
            "code": full_code,
            "title": title or {},
            "channels": channels or ["ws", "inbox"],
            "category": category,
        }
        self._track(plugin_name, "notification", full_code, {
            "title": title or {},
            "channels": channels or ["ws", "inbox"],
            "category": category,
        })
        logger.info(
            "Plugin %s registered notification: %s",
            plugin_name, full_code,
        )

    def _unregister_notification(self, ext: RegisteredExtension) -> None:
        """移除插件通知模板注册"""
        self._plugin_notifications.pop(ext.key, None)

    def get_plugin_notification(self, code: str) -> dict | None:
        """获取插件注册的通知模板（供通知服务查询）"""
        return self._plugin_notifications.get(code)

    # ── 9. Permission ──

    def register_permission(
        self,
        plugin_name: str,
        code: str,
        name: dict[str, str] | None = None,
        scope: str = "all_tenants",
        actions: list[str] | None = None,
    ) -> None:
        """
        注册插件权限。

        将插件声明的权限写入内存注册表，供 RBAC 中间件在运行时查询。
        """
        full_code = f"plugin.{plugin_name}.{code}" if not code.startswith("plugin.") else code
        self._plugin_permissions[full_code] = {
            "plugin_name": plugin_name,
            "code": full_code,
            "name": name or {},
            "scope": scope,
            "actions": actions or [],
        }
        self._track(plugin_name, "permission", full_code, {
            "name": name or {},
            "scope": scope,
            "actions": actions or [],
        })
        logger.info(
            "Plugin %s registered permission: %s", plugin_name, full_code
        )

    def _unregister_permission(self, ext: RegisteredExtension) -> None:
        """移除插件权限注册"""
        self._plugin_permissions.pop(ext.key, None)

    def get_plugin_permissions(self, plugin_name: str | None = None) -> list[dict]:
        """获取插件注册的权限列表（供 RBAC 查询）"""
        if plugin_name:
            return [
                v for v in self._plugin_permissions.values()
                if v["plugin_name"] == plugin_name
            ]
        return list(self._plugin_permissions.values())

    # ── 10. Menu ──

    def register_menu(
        self,
        plugin_name: str,
        name: str,
        path: str,
        icon: str = "",
        parent: str | None = None,
        sort_order: int = 100,
        scope: str = "admin_only",
        component: str = "",
        title: dict[str, str] | None = None,
        hidden: bool = False,
    ) -> None:
        """
        注册插件菜单到 RBAC 权限注册中心。

        将插件声明的菜单转换为 PermissionMeta 并注册到 permission_registry，
        下次 sync_permissions 时会写入 DB 并出现在侧边栏。

        Args:
            plugin_name: 插件名
            name: 菜单唯一标识
            path: 前端路由路径
            icon: 图标（lucide:xxx）
            parent: 父菜单资源名（如 system_mgmt）
            sort_order: 排序
            scope: 权限范围（admin_only / all_tenants）
            component: 前端组件路径
            title: i18n 标题 {"zh-CN": "存储迁移", "en": "Storage Migration"}
            hidden: 是否隐藏
        """
        from app.enums.rbac import PermissionScope, PermissionType
        from app.rbac.decorators import PermissionMeta
        from app.rbac.registry import permission_registry

        scope_enum = (
            PermissionScope.ADMIN_ONLY
            if scope == "admin_only"
            else PermissionScope.ALL_TENANTS
        )
        scope_prefix = "admin" if scope_enum == PermissionScope.ADMIN_ONLY else "tenant"
        safe_name = plugin_name.replace("-", "_")
        menu_code = f"menu:{scope_prefix}.plugin_{safe_name}_{name}"
        parent_code = f"menu:{scope_prefix}.{parent}" if parent else None

        # i18n key: 为每个菜单独立生成 key，避免多菜单插件标题冲突
        # 例如 plugin.novusdoc.menu.novusdoc_docs_admin.title
        i18n_key = f"plugin.{plugin_name}.menu.{name}.title"
        if title:
            self._plugin_menu_titles.setdefault(plugin_name, {})[i18n_key] = {
                k: str(v) for k, v in title.items() if isinstance(v, str)
            }

        perm = PermissionMeta(
            code=menu_code,
            name=i18n_key,
            type=PermissionType.MENU,
            scope=scope_enum,
            resource="menu",
            action=f"{scope_prefix}.plugin_{plugin_name.replace('-', '_')}_{name}",
            icon=icon,
            path=path,
            component=component,
            parent_code=parent_code,
            sort_order=sort_order,
            hidden=hidden,
        )

        permission_registry.register(perm)
        self._track(plugin_name, "menu", menu_code, {"i18n_key": i18n_key})
        logger.info(
            "Plugin %s registered menu: %s -> %s (parent=%s)",
            plugin_name, menu_code, path, parent,
        )

    def _unregister_menu(self, ext: RegisteredExtension) -> None:
        """从 RBAC 权限注册中心移除插件菜单"""
        from app.rbac.registry import permission_registry

        permission_registry.unregister(ext.key)
        i18n_key = (ext.ref or {}).get("i18n_key")
        if i18n_key:
            plugin_titles = self._plugin_menu_titles.get(ext.plugin_name)
            if plugin_titles:
                plugin_titles.pop(i18n_key, None)
                if not plugin_titles:
                    self._plugin_menu_titles.pop(ext.plugin_name, None)

    def resolve_plugin_menu_title(
        self,
        i18n_key: str,
        locale: str | None = None,
    ) -> str | None:
        """
        解析插件菜单 i18n key 的运行时标题（用于 i18n 缺失时回退）。

        Args:
            i18n_key: 例如 plugin.novusdoc.menu.docs_admin.title
            locale: 语言代码（zh_CN / zh-CN / en / en-US）
        """
        from app.core.i18n import get_locale

        if locale is None:
            locale = get_locale()
        normalized = (locale or "").replace("-", "_").lower()

        for plugin_titles in self._plugin_menu_titles.values():
            title_map = plugin_titles.get(i18n_key)
            if not title_map:
                continue

            # locale 优先级：精确 -> 前缀 -> zh-CN -> en -> 首个
            exact = (
                title_map.get(locale)
                or title_map.get(locale.replace("_", "-"))
                or title_map.get(normalized)
            )
            if exact:
                return exact
            if normalized.startswith("zh"):
                zh = title_map.get("zh-CN") or title_map.get("zh_CN") or title_map.get("zh")
                if zh:
                    return zh
            if normalized.startswith("en"):
                en = title_map.get("en") or title_map.get("en-US") or title_map.get("en_US")
                if en:
                    return en

            return (
                title_map.get("zh-CN")
                or title_map.get("zh_CN")
                or title_map.get("en")
                or next(iter(title_map.values()), None)
            )
        return None

    # ── 11. Socket.IO Namespace ──

    def register_socketio(
        self,
        plugin_name: str,
        namespace_path: str,
        handler_class: type,
        auth_required: bool = True,
        auth_scopes: list[str] | None = None,
    ) -> None:
        """
        注册插件 Socket.IO namespace 到全局 AsyncServer。

        namespace 路径自动添加 /plugin/{plugin_name}/ 前缀。
        如果 auth_required=True，自动用 PluginAuthNamespaceWrapper 包装
        handler_class，注入 JWT 校验和租户隔离。

        Args:
            plugin_name: 插件名
            namespace_path: 短路径（如 "collab"）
            handler_class: AsyncNamespace 子类
            auth_required: 是否需要 JWT 认证
            auth_scopes: 允许的 token scope 列表
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
            "Plugin %s registered Socket.IO namespace: %s (auth=%s scopes=%s)",
            plugin_name, full_ns, auth_required, auth_scopes,
        )

    def _unregister_socketio(self, ext: RegisteredExtension) -> None:
        """反注册插件 Socket.IO namespace"""
        try:
            from app.core.socketio_server import get_sio

            sio = get_sio()
            full_ns = ext.key
            # python-socketio 没有原生 unregister_namespace，
            # 手动从 namespace_handlers 移除
            if hasattr(sio, "namespace_handlers") and full_ns in sio.namespace_handlers:
                del sio.namespace_handlers[full_ns]
                logger.info("Removed Socket.IO namespace: %s", full_ns)
            else:
                logger.warning(
                    "Socket.IO namespace %s not found in handlers", full_ns
                )
        except Exception as exc:
            logger.warning(
                "Failed to unregister socketio namespace %s: %s", ext.key, exc
            )

    # ── 12. Frontend Slot ──

    def register_frontend_slot(
        self,
        plugin_name: str,
        slot_type: str,
        **data: object,
    ) -> None:
        """
        注册插件前端插槽。

        slot_type 取值:
          header_widget / dashboard_widget / settings_tab /
          floating_panel / standalone_page / notification_ui

        去重策略: 按 (slot_type, name) 唯一，重复注册时覆盖旧值。
        """
        slot_entry = {"slot_type": slot_type, "plugin_name": plugin_name, **data}
        dedup_key = f"{slot_type}:{data.get('name', '')}"

        slots = self._plugin_frontend_slots.setdefault(plugin_name, [])
        # 移除同 key 的旧条目，再追加新条目（upsert 语义）
        self._plugin_frontend_slots[plugin_name] = [
            s for s in slots
            if f"{s['slot_type']}:{s.get('name', '')}" != dedup_key
        ]
        self._plugin_frontend_slots[plugin_name].append(slot_entry)

        self._track(plugin_name, "frontend_slot", dedup_key, slot_entry)
        logger.info(
            "Plugin %s registered frontend slot: %s/%s",
            plugin_name, slot_type, data.get("name", ""),
        )

    def _unregister_frontend_slot(self, ext: RegisteredExtension) -> None:
        """移除插件前端插槽注册"""
        plugin_name = ext.plugin_name
        key = ext.key  # "slot_type:name"
        if plugin_name in self._plugin_frontend_slots:
            self._plugin_frontend_slots[plugin_name] = [
                s for s in self._plugin_frontend_slots[plugin_name]
                if f"{s['slot_type']}:{s.get('name', '')}" != key
            ]

    def get_frontend_slots(
        self,
        slot_type: str | None = None,
        scope: str | None = None,
        plugin_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取前端插槽数据，供 GET /plugins/slots API 使用。

        Args:
            slot_type: 过滤插槽类型（None = 全部）
            scope: 过滤适用端（"admin" / "tenant" / None = 全部）
            plugin_name: 过滤指定插件（None = 全部）
        """
        all_slots: list[dict[str, Any]] = []
        plugins_iter = (
            [plugin_name] if plugin_name
            else list(self._plugin_frontend_slots.keys())
        )
        for pname in plugins_iter:
            for slot in self._plugin_frontend_slots.get(pname, []):
                if slot_type and slot.get("slot_type") != slot_type:
                    continue
                if scope:
                    slot_scope = slot.get("scope", "")
                    # 按请求端过滤插槽可见性：
                    # - slot_scope="tenant"    → 仅 tenant 端可见
                    # - slot_scope="admin"/"admin_only" → 仅 admin 端可见
                    # - 其他（空/all_tenants/admin_and_all 等） → 两端都可见
                    from app.enums.common import ResourceScopeEnum
                    _ADMIN_ONLY = ResourceScopeEnum.ADMIN_ONLY.value
                    if scope == "admin" and slot_scope == "tenant":
                        continue
                    elif scope == "tenant" and slot_scope in (_ADMIN_ONLY, "admin"):
                        continue
                all_slots.append(slot)
        return all_slots

    # ── 通用 ──

    _DISPATCH: dict[str, str] = {
        "adapter": "_unregister_adapter",
        "hook": "_unregister_hook",
        "storage": "_unregister_storage",
        "skill": "_unregister_skill",
        "event": "_unregister_event",
        "webhook": "_unregister_webhook",
        "task": "_unregister_task",
        "notification": "_unregister_notification",
        "permission": "_unregister_permission",
        "menu": "_unregister_menu",
        "socketio": "_unregister_socketio",
        "frontend_slot": "_unregister_frontend_slot",
        "consumer": "_unregister_consumer",
        "custom": "_unregister_custom",
        "middleware": "_unregister_middleware",
    }

    def unregister_all(self, plugin_name: str) -> int:
        """
        反注册指定插件的所有扩展。

        Returns:
            反注册的扩展数量
        """
        extensions = self._registry.pop(plugin_name, [])
        count = 0
        for ext in extensions:
            method_name = self._DISPATCH.get(ext.ext_type)
            if method_name:
                try:
                    getattr(self, method_name)(ext)
                    count += 1
                except Exception as exc:
                    logger.warning(
                        "Failed to unregister %s/%s for plugin %s: %s",
                        ext.ext_type, ext.key, plugin_name, exc,
                    )
        # 清理 webhook 字典
        self._plugin_webhooks.pop(plugin_name, None)

        # 清理前端插槽
        self._plugin_frontend_slots.pop(plugin_name, None)
        # 清理消费者
        self._plugin_consumers.pop(plugin_name, None)
        # 清理自定义扩展
        self._plugin_custom_extensions.pop(plugin_name, None)
        # 清理中间件
        self._plugin_middlewares.pop(plugin_name, None)
        # 清理菜单 i18n 回退缓存
        self._plugin_menu_titles.pop(plugin_name, None)

        # 清理 PluginEventBus 订阅
        try:
            from app.plugins.event_bus import get_plugin_event_bus
            get_plugin_event_bus().unsubscribe_all(plugin_name)
        except Exception as exc:
            logger.warning(
                "Failed to cleanup PluginEventBus for %s: %s", plugin_name, exc,
            )

        logger.info(
            "Unregistered %d extensions for plugin %s", count, plugin_name
        )
        return count

    def get_conflicts(
        self, manifest: Any
    ) -> list[dict[str, str]]:
        """
        检测插件扩展与已注册扩展的冲突。

        Returns:
            冲突列表 [{"type": "adapter", "key": "xxx", "plugin": "yyy"}, ...]
        """
        conflicts: list[dict[str, str]] = []
        extensions = getattr(manifest, "extensions", None)
        if not extensions:
            return conflicts

        # 检查适配器冲突
        for adapter in getattr(extensions, "adapters", []):
            from app.ai.adapters import AdapterRegistry

            if AdapterRegistry.get_adapter(adapter.provider_code):
                # 找到是哪个插件注册的
                owner = self._find_owner("adapter", adapter.provider_code)
                conflicts.append({
                    "type": "adapter",
                    "key": adapter.provider_code,
                    "owner": owner or "system",
                })

        # 检查技能冲突（按 plugin_name 匹配，与 register_skill key 一致）
        plugin_name = getattr(manifest, "name", "")
        if plugin_name and plugin_name in self._plugin_skill_resolvers:
            owner = self._find_owner("skill", plugin_name)
            if owner and owner != plugin_name:
                conflicts.append({
                    "type": "skill",
                    "key": plugin_name,
                    "owner": owner,
                })

        # 检查存储驱动冲突
        for driver in getattr(extensions, "storage_drivers", []):
            from app.storage.manager import storage_manager

            if storage_manager.has_driver(driver.code):
                owner = self._find_owner("storage", driver.code)
                conflicts.append({
                    "type": "storage",
                    "key": driver.code,
                    "owner": owner or "system",
                })

        return conflicts

    def _find_owner(self, ext_type: str, key: str) -> str | None:
        """查找某个扩展的所属插件"""
        for plugin_name, extensions in self._registry.items():
            for ext in extensions:
                if ext.ext_type == ext_type and ext.key == key:
                    return plugin_name
        return None

    # ── 13. Consumer ──

    def register_consumer(
        self,
        plugin_name: str,
        consumer_name: str,
        handler: Callable,
        queue: str = "default",
        max_retries: int = 3,
        retry_delay: int = 60,
    ) -> None:
        """
        注册插件消息队列消费者（Celery task，无调度）。

        区别于 register_task（带 Celery Beat 调度），consumer 仅注册 Celery task，
        不加入 beat_schedule，由队列消息触发。
        """
        from app.celery_app import celery_app

        celery_task_name = f"plugin.{plugin_name}.{consumer_name}"

        if celery_task_name not in celery_app.tasks:
            import asyncio
            import functools

            if asyncio.iscoroutinefunction(handler):
                @functools.wraps(handler)
                def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                    return _run_async(handler(*args, **kwargs))
                celery_app.task(name=celery_task_name, queue=queue,
                                max_retries=max_retries, default_retry_delay=retry_delay)(_sync_wrapper)
            else:
                celery_app.task(name=celery_task_name, queue=queue,
                                max_retries=max_retries, default_retry_delay=retry_delay)(handler)

        consumer_info: dict[str, Any] = {
            "name": consumer_name,
            "celery_task_name": celery_task_name,
            "queue": queue,
        }
        self._plugin_consumers.setdefault(plugin_name, []).append(consumer_info)
        self._track(plugin_name, "consumer", celery_task_name, consumer_info)
        logger.info(
            "Plugin %s registered consumer: %s (queue=%s)",
            plugin_name, consumer_name, queue,
        )

    def _unregister_consumer(self, ext: RegisteredExtension) -> None:
        """消费者反注册（Celery task 无法热卸载，仅清理追踪记录）"""
        plugin_name = ext.plugin_name
        celery_task_name = ext.key
        if plugin_name in self._plugin_consumers:
            self._plugin_consumers[plugin_name] = [
                c for c in self._plugin_consumers[plugin_name]
                if c.get("celery_task_name") != celery_task_name
            ]
        logger.info(
            "Plugin consumer unregistered (Celery task remains until restart): %s",
            celery_task_name,
        )

    # ── 14. Middleware ──

    def register_middleware(
        self,
        plugin_name: str,
        name: str,
        middleware_cls: type,
        priority: int = 50,
    ) -> None:
        """
        注册插件 ASGI 中间件。

        应用启动时将优先级较高的中间件注入到请求链外层。
        禁用插件后标记为待移除，完全移除需重启。
        """
        entry: dict[str, Any] = {
            "plugin_name": plugin_name,
            "name": name,
            "cls": middleware_cls,
            "priority": priority,
        }
        self._plugin_middlewares.setdefault(plugin_name, []).append(entry)
        self._track(plugin_name, "middleware", f"{plugin_name}:{name}", middleware_cls)
        # 尝试注入到运行时 FastAPI 应用
        try:
            from app.main import app as fastapi_app
            fastapi_app.add_middleware(middleware_cls)
            logger.info(
                "Plugin %s registered middleware: %s (priority=%d)",
                plugin_name, name, priority,
            )
        except Exception as exc:
            logger.warning(
                "Plugin %s: failed to add middleware %s at runtime: %s",
                plugin_name, name, exc,
            )

    def _unregister_middleware(self, ext: RegisteredExtension) -> None:
        """移除中间件注册（内存清理，完全移除需重启服务）"""
        plugin_name = ext.plugin_name
        name = ext.key.split(":", 1)[-1]
        if plugin_name in self._plugin_middlewares:
            self._plugin_middlewares[plugin_name] = [
                m for m in self._plugin_middlewares[plugin_name]
                if m.get("name") != name
            ]
        logger.info(
            "Plugin middleware unregistered (full removal requires restart): %s",
            ext.key,
        )

    def get_plugin_middlewares(self, plugin_name: str | None = None) -> list[dict[str, Any]]:
        """获取插件中间件列表（按 priority 升序）"""
        result: list[dict[str, Any]] = []
        plugins_iter = [plugin_name] if plugin_name else list(self._plugin_middlewares.keys())
        for pname in plugins_iter:
            result.extend(self._plugin_middlewares.get(pname, []))
        result.sort(key=lambda x: x.get("priority", 50))
        return result

    # ── 15. Custom Extension ──

    def register_custom(
        self,
        plugin_name: str,
        ext_type: str,
        name: str,
        data: dict[str, Any] | None = None,
        description: str = "",
    ) -> None:
        """
        注册通用自定义扩展点。

        元数据存入内存注册表，其他插件或平台可通过
        `get_custom_extensions(ext_type)` 查询。
        """
        entry: dict[str, Any] = {
            "plugin_name": plugin_name,
            "type": ext_type,
            "name": name,
            "data": data or {},
            "description": description,
        }
        key = f"{ext_type}:{name}"
        customs = self._plugin_custom_extensions.setdefault(plugin_name, [])
        # upsert
        self._plugin_custom_extensions[plugin_name] = [
            c for c in customs if f"{c['type']}:{c['name']}" != key
        ]
        self._plugin_custom_extensions[plugin_name].append(entry)
        self._track(plugin_name, "custom", key, entry)
        logger.info(
            "Plugin %s registered custom extension: %s/%s",
            plugin_name, ext_type, name,
        )

    def _unregister_custom(self, ext: RegisteredExtension) -> None:
        """\u79fb\u9664\u81ea\u5b9a\u4e49\u6269\u5c55\u6ce8\u518c"""
        plugin_name = ext.plugin_name
        key = ext.key
        if plugin_name in self._plugin_custom_extensions:
            self._plugin_custom_extensions[plugin_name] = [
                c for c in self._plugin_custom_extensions[plugin_name]
                if f"{c['type']}:{c['name']}" != key
            ]

    def get_custom_extensions(
        self,
        ext_type: str | None = None,
        plugin_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """\u83b7\u53d6\u81ea\u5b9a\u4e49\u6269\u5c55列\u8868\u3002\n\n        Args:\n            ext_type: 过\u6ee4\u6269\u5c55\u7c7b\u578b\uff08None = 全\u90e8\uff09\n            plugin_name: 过\u6ee4\u63d2\u4ef6\uff08None = 全\u90e8\uff09\n        """
        result: list[dict[str, Any]] = []
        plugins_iter = [plugin_name] if plugin_name else list(self._plugin_custom_extensions.keys())
        for pname in plugins_iter:
            for ext in self._plugin_custom_extensions.get(pname, []):
                if ext_type and ext.get("type") != ext_type:
                    continue
                result.append(ext)
        return result

    def get_frontend_slots_grouped(
        self,
        scope: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        获取按类型分组的前端插槽数据。

        供 Controller 直接返回，避免 Controller 内写分组+排序逻辑。

        Args:
            scope: "admin" / "tenant" / None = 全部

        Returns:
            {"header_widgets": [...], "dashboard_widgets": [...], ...}
        """
        from app.enums.plugin import FrontendSlotTypeEnum

        _TYPE_TO_KEY: dict[str, str] = {
            FrontendSlotTypeEnum.HEADER_WIDGET.value: "header_widgets",
            FrontendSlotTypeEnum.DASHBOARD_WIDGET.value: "dashboard_widgets",
            FrontendSlotTypeEnum.SETTINGS_TAB.value: "settings_tabs",
            FrontendSlotTypeEnum.FLOATING_PANEL.value: "floating_panels",
            FrontendSlotTypeEnum.STANDALONE_PAGE.value: "standalone_pages",
            FrontendSlotTypeEnum.NOTIFICATION_UI.value: "notification_ui",
        }

        result: dict[str, list[dict[str, Any]]] = {k: [] for k in _TYPE_TO_KEY.values()}

        for slot in self.get_frontend_slots(scope=scope):
            key = _TYPE_TO_KEY.get(slot.get("slot_type", ""))
            if key:
                result[key].append(slot)

        # 所有插槽类型统一按 sort_order 升序排序，保证前端渲染顺序一致
        for slots in result.values():
            slots.sort(key=lambda x: x.get("sort_order", 100))
        return result

    def get_registered_count(self, plugin_name: str) -> int:
        """获取某插件已注册的扩展数量"""
        return len(self._registry.get(plugin_name, []))
