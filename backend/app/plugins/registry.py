"""
Extension point registry. / 扩展点注册中心。

Bridges plugin extension declarations to existing system registries,
tracks registration records for unregistration.
/ 桥接插件扩展点声明到已有系统注册表，追踪注册记录用于反注册。
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from starlette.middleware import Middleware

from app.core.logging import get_logger
from app.plugins.registry_read_layer import RegistryReadLayer
from app.plugins.registry_runtime_extensions import RegistryRuntimeExtensionsMixin

logger = get_logger(__name__)

_PLUGIN_MENU_ACTION_MAX_LEN = 50

class _RegistryRuntimeBridge:
    """Runtime-only bridge: async consumer execution + middleware projection."""

    _bg_loop = None
    _bg_thread = None
    _bg_lock: threading.Lock | None = None

    @classmethod
    def _get_lock(cls) -> threading.Lock:
        if cls._bg_lock is None:
            cls._bg_lock = threading.Lock()
        return cls._bg_lock

    @classmethod
    def run_async(cls, coro):
        import asyncio

        with cls._get_lock():
            if cls._bg_loop is None or cls._bg_loop.is_closed():
                cls._bg_loop = asyncio.new_event_loop()
                cls._bg_thread = threading.Thread(
                    target=cls._bg_loop.run_forever,
                    daemon=True,
                    name="plugin-task-loop",
                )
                cls._bg_thread.start()
            loop = cls._bg_loop
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=300)

    @staticmethod
    def iter_runtime_middlewares(
        plugin_middlewares: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for middlewares in plugin_middlewares.values():
            entries.extend(middlewares)
        entries.sort(key=lambda item: -int(item.get("priority", 50)))
        return entries

    @staticmethod
    def rebuild_runtime_middleware_stack(fastapi_app: Any) -> None:
        build_stack = getattr(fastapi_app, "build_middleware_stack", None)
        if callable(build_stack):
            fastapi_app.middleware_stack = build_stack()

    @classmethod
    def sync_runtime_middlewares(
        cls,
        plugin_middlewares: dict[str, list[dict[str, Any]]],
        *,
        removed_runtime_middleware: Middleware | None = None,
    ) -> bool:
        try:
            from app.main import app as fastapi_app
        except Exception as exc:
            logger.warning(
                "Plugin middleware runtime sync skipped: failed to import app: {}",
                exc,
            )
            return False

        user_middleware = getattr(fastapi_app, "user_middleware", None)
        if not isinstance(user_middleware, list):
            logger.warning(
                "Plugin middleware runtime sync skipped: app.user_middleware unavailable"
            )
            return False

        managed_ids = {
            id(runtime_middleware)
            for entry in cls.iter_runtime_middlewares(plugin_middlewares)
            if (runtime_middleware := entry.get("runtime_middleware")) is not None
        }
        if removed_runtime_middleware is not None:
            managed_ids.add(id(removed_runtime_middleware))

        preserved = [
            middleware
            for middleware in list(user_middleware)
            if id(middleware) not in managed_ids
        ]
        runtime_middlewares = [
            entry["runtime_middleware"]
            for entry in cls.iter_runtime_middlewares(plugin_middlewares)
            if entry.get("runtime_middleware") is not None
        ]
        fastapi_app.user_middleware = runtime_middlewares + preserved
        cls.rebuild_runtime_middleware_stack(fastapi_app)
        return True


def _build_plugin_menu_action(scope_prefix: str, safe_name: str, name: str) -> str:
    """Build a menu action string that stays within Permission.action limits.
    / 构造满足 Permission.action 长度限制的插件菜单 action。"""
    raw_action = f"{scope_prefix}.plugin_{safe_name}_{name}"
    if len(raw_action) <= _PLUGIN_MENU_ACTION_MAX_LEN:
        return raw_action

    digest = hashlib.sha1(raw_action.encode("utf-8")).hexdigest()[:10]
    compact_source = f"{safe_name}_{name}".replace("-", "_")
    reserved = len(scope_prefix) + len(".plugin.") + len(digest) + 1
    budget = max(1, _PLUGIN_MENU_ACTION_MAX_LEN - reserved)
    compact = compact_source[:budget].rstrip("._") or "menu"
    return f"{scope_prefix}.plugin.{compact}.{digest}"


def _select_i18n_value(locale_titles: dict[str, str], locale: str) -> str | None:
    """Select best-matching i18n value for current locale. / 按当前语言选择最佳匹配文案。"""
    if locale in locale_titles:
        return locale_titles[locale]
    normalized = locale.replace("_", "-")
    if normalized in locale_titles:
        return locale_titles[normalized]
    short = normalized.split("-")[0]
    if short in locale_titles:
        return locale_titles[short]
    if locale_titles:
        return next(iter(locale_titles.values()))
    return None


@dataclass
class RegisteredExtension:
    """Registered extension record / 已注册的扩展记录"""

    plugin_name: str
    ext_type: str
    key: str
    ref: Any = None


class ExtensionRegistry(RegistryRuntimeExtensionsMixin):
    """
    Extension point registry (singleton).
    / 扩展点注册中心（单例）

    Responsibilities:
    - Bridge plugin extensions to existing system registries (AdapterRegistry / HookRegistry / StorageManager etc.)
    - Track extensions registered by each plugin for unregister_all
    - Provide query interfaces for plugin skill resolvers and executors
    / 职责：桥接插件扩展、追踪注册记录、提供查询接口
    """

    _instance: ExtensionRegistry | None = None
    _instance_lock: threading.Lock = threading.Lock()

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
        "socketio": "_unregister_socketio",
        "frontend_slot": "_unregister_frontend_slot",
        "consumer": "_unregister_consumer",
        "middleware": "_unregister_middleware",
        "custom": "_unregister_custom",
        "menu": "_unregister_menu",
    }

    def __init__(self) -> None:
        self._registry: dict[str, list[RegisteredExtension]] = {}
        self._plugin_skill_resolvers: dict[str, Callable] = {}
        self._plugin_executors: dict[str, Callable] = {}
        self._plugin_webhooks: dict[str, dict[str, Any]] = {}
        self._plugin_notifications: dict[str, dict[str, Any]] = {}
        self._plugin_permissions: dict[str, dict[str, Any]] = {}
        # slot_type 取値见 FrontendSlotTypeEnum / slot_type values: see FrontendSlotTypeEnum
        self._plugin_frontend_slots: dict[str, list[dict[str, Any]]] = {}
        # consumer: plugin_name -> list of consumer info dicts / 消费者：插件名 -> 消费者信息列表
        self._plugin_consumers: dict[str, list[dict[str, Any]]] = {}
        # custom: plugin_name -> list of custom extension dicts / 自定义：插件名 -> 扩展列表
        self._plugin_custom_extensions: dict[str, list[dict[str, Any]]] = {}
        # middleware: plugin_name -> list of middleware class refs / 中间件：插件名 -> 中间件类引用列表
        self._plugin_middlewares: dict[str, list[dict[str, Any]]] = {}
        # menu: plugin_name -> list of menu registration dicts / 菜单：插件名 -> 菜单注册列表
        self._plugin_menus: dict[str, list[dict[str, Any]]] = {}
        # menu i18n fallback: plugin_name -> {i18n_key: {"zh-CN": "...", "en": "..."}} / 菜单 i18n 回退
        self._plugin_menu_titles: dict[str, dict[str, dict[str, str]]] = {}
        # permission i18n fallback: plugin_name -> {i18n_key: {"zh-CN": "...", "en": "..."}} / 权限 i18n 回退
        self._plugin_permission_titles: dict[str, dict[str, dict[str, str]]] = {}
        self.read_layer = RegistryReadLayer(
            self,
            select_i18n_value=_select_i18n_value,
        )

    @classmethod
    def get_instance(cls) -> ExtensionRegistry:
        """Get singleton instance (thread-safe, double-checked locking) / 获取单例（线程安全，双检锁）"""
        if cls._instance is not None:
            return cls._instance
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (testing only) / 重置单例（仅测试用）"""
        cls._instance = None

    # ── Tracking / 追踪 ──

    def _track(
        self, plugin_name: str, ext_type: str, key: str, ref: Any = None
    ) -> None:
        """Track registered extension / 追踪已注册的扩展"""
        if plugin_name not in self._registry:
            self._registry[plugin_name] = []
        self._registry[plugin_name].append(
            RegisteredExtension(plugin_name, ext_type, key, ref)
        )

    def _cleanup_plugin_runtime_state(self, plugin_name: str) -> None:
        """Cleanup plugin-scoped in-memory extension families."""
        self._plugin_webhooks.pop(plugin_name, None)
        self._plugin_frontend_slots.pop(plugin_name, None)
        self._plugin_consumers.pop(plugin_name, None)
        self._plugin_custom_extensions.pop(plugin_name, None)
        self._plugin_middlewares.pop(plugin_name, None)
        self._plugin_menus.pop(plugin_name, None)
        self._plugin_menu_titles.pop(plugin_name, None)

    @staticmethod
    def _cleanup_plugin_event_bus(plugin_name: str) -> None:
        """Cleanup plugin event-bus subscriptions with safe fallback."""
        try:
            from app.plugins.event_bus import get_plugin_event_bus

            get_plugin_event_bus().unsubscribe_all(plugin_name)
        except Exception as exc:
            logger.warning(
                "Failed to cleanup PluginEventBus for {}: {}",
                plugin_name,
                exc,
            )

    # ── 1. Adapter / 适配器 ──

    def register_adapter(
        self, plugin_name: str, provider_type: str, adapter_class: type
    ) -> None:
        """Register AI adapter → AdapterRegistry / 注册 AI 适配器"""
        from app.ai.adapters import AdapterRegistry

        AdapterRegistry.register(provider_type, adapter_class)
        self._track(plugin_name, "adapter", provider_type)
        logger.info("Plugin {} registered adapter: {}", plugin_name, provider_type)

    def _unregister_adapter(self, ext: RegisteredExtension) -> None:
        from app.ai.adapters import AdapterRegistry

        AdapterRegistry.unregister(ext.key)

    # ── 2. Hook / 钩子 ──

    def register_hook(
        self,
        plugin_name: str,
        hook_point: str,
        handler: Callable,
        priority: int = 50,
    ) -> None:
        """Register hook → HookRegistry / 注册钩子"""
        from app.ai.events.hooks import HookRegistry

        HookRegistry.get_instance().register(hook_point, handler, priority)
        self._track(plugin_name, "hook", hook_point, handler)
        logger.info(
            "Plugin {} registered hook: {} (priority={})",
            plugin_name,
            hook_point,
            priority,
        )

    def _unregister_hook(self, ext: RegisteredExtension) -> None:
        from app.ai.events.hooks import HookRegistry

        HookRegistry.get_instance().unregister(ext.key, ext.ref)

    # ── 3. Storage Driver / 存储驱动 ──

    def register_storage_driver(self, plugin_name: str, driver_class: type) -> None:
        """Register storage driver → StorageManager / 注册存储驱动"""
        from app.storage.manager import storage_manager

        storage_manager.register_driver(driver_class)
        driver_name = getattr(driver_class, "name", "")
        self._track(plugin_name, "storage", driver_name, driver_class)
        logger.info("Plugin {} registered storage driver: {}", plugin_name, driver_name)

    def _unregister_storage(self, ext: RegisteredExtension) -> None:
        from app.storage.manager import storage_manager

        storage_manager.unregister_driver(ext.key)

    # ── 4. Skill / 技能 ──

    def register_skill(
        self,
        plugin_name: str,
        skill_type: str,
        resolver: Callable,
        executor: type | Callable | None = None,
    ) -> None:
        """
        Register plugin skill.
        / 注册插件技能

        Registers resolver and executor keyed by plugin_name,
        allowing plugin skills to use standard types (e.g. toolkit) without conflicting with built-in resolvers.
        / 以 plugin_name 为 key 注册 resolver 和 executor。

        Args:
            plugin_name: Plugin name (registration key) / 插件名（注册 key）
            skill_type: Skill type identifier (for logging only) / 技能类型标识
            resolver: Skill resolver function (skill, config) -> list[ToolDefinition] / 技能解析函数
            executor: Tool executor class or instance; class is instantiated and cached at registration
                      / 工具执行器类或实例
        """
        self._plugin_skill_resolvers[plugin_name] = resolver
        if executor:
            # Class → instantiate and cache, avoid creating new instance on every tool call / 类→实例化并缓存，避免每次调用新建
            # / 类 → 实例化后缓存
            if isinstance(executor, type):
                try:
                    executor = executor()
                except Exception as exc:
                    logger.warning(
                        "Failed to instantiate executor for plugin '{}': {}",
                        plugin_name,
                        exc,
                    )
                    executor = None
            if executor:
                self._plugin_executors[plugin_name] = executor
        self._track(plugin_name, "skill", plugin_name)
        logger.info(
            "Plugin {} registered skill resolver (type={})", plugin_name, skill_type
        )

    def _unregister_skill(self, ext: RegisteredExtension) -> None:
        self._plugin_skill_resolvers.pop(ext.key, None)
        self._plugin_executors.pop(ext.key, None)

    def get_plugin_skill_resolver(self, plugin_name: str) -> Callable | None:
        """Get plugin skill resolver (lookup by plugin name) / 获取插件技能解析器"""
        return self._plugin_skill_resolvers.get(plugin_name)

    def get_plugin_executor(self, plugin_name: str) -> Any:
        """Get plugin tool executor instance (lookup by plugin name) / 获取插件工具执行器实例"""
        return self._plugin_executors.get(plugin_name)

    # ── 5. Event / 事件 ──

    def register_event(
        self, plugin_name: str, event_type_name: str, handler: Callable
    ) -> None:
        """Register event subscription (supports AI typed events and PluginEventBus string events)
        / 注册事件订阅"""
        if event_type_name.startswith("plugin."):
            from app.plugins.event_bus import PluginEventBus

            bus = PluginEventBus.get_instance()
            bus.subscribe(event_type_name, handler, plugin_name=plugin_name)
            self._track(
                plugin_name, "event", event_type_name, (event_type_name, handler)
            )
        else:
            from app.ai.events import get_event_bus

            event_cls = self._resolve_event_class(event_type_name)
            get_event_bus().subscribe(event_cls, handler)
            self._track(plugin_name, "event", event_type_name, (event_cls, handler))
        logger.info("Plugin {} subscribed to event: {}", plugin_name, event_type_name)

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
        """Get event class by class name / 根据类名获取事件类"""
        from app.ai.events import types as event_types
        from app.plugins.exceptions import PluginError

        cls = getattr(event_types, name, None)
        if cls is None:
            raise PluginError(message=f"Unknown event type: {name}")
        return cls

    # ── 6. Webhook / Webhook 回调 ──

    def register_webhook(
        self,
        plugin_name: str,
        path: str,
        handler: Callable,
        method: str = "POST",
        auth_config: dict | None = None,
    ) -> None:
        """Register Webhook endpoint.
        / 注册 Webhook 端点

        Path normalization: auto-prefix / if path doesn't start with /,
        ensuring generated full_path matches webhook_dispatcher.py lookup format.
        / 路径规范化：自动补齐 /。
        """
        # Normalize: ensure path starts with / (eliminate /plugins/{name}path inconsistency risk) / 规范化路径，确保以 / 开头
        # / 规范化
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
            "Plugin {} registered webhook: {} {}",
            plugin_name,
            method,
            full_path,
        )

    def _unregister_webhook(self, ext: RegisteredExtension) -> None:
        self._plugin_webhooks.get(ext.plugin_name, {}).pop(ext.key, None)

    def get_plugin_webhooks(self, plugin_name: str | None = None) -> dict[str, dict]:
        """Get plugin Webhook registrations (for routing layer) / 获取插件 Webhook 注册"""
        if plugin_name:
            return self._plugin_webhooks.get(plugin_name, {})
        result: dict[str, dict] = {}
        for webhooks in self._plugin_webhooks.values():
            result.update(webhooks)
        return result

    # ── 7. Task / 异步任务 ──

    def register_task(
        self,
        plugin_name: str,
        task_name: str,
        handler: Callable,
        schedule_type: str = "interval",
        cron_expression: str | None = None,
        interval_seconds: int | None = None,
        queue: str = "default",
        *,
        register_schedule: bool = True,
    ) -> None:
        """
        Register scheduled task to Celery Beat.
        / 注册定时任务到 Celery Beat。

        Wraps plugin-declared scheduled tasks as Celery tasks and injects into beat_schedule.
        Task name convention: plugin.{plugin_name}.{task_name}
        / 将插件声明的定时任务包装为 Celery task 并注入 beat_schedule。
        """
        from app.celery_app import celery_app

        celery_task_name = f"plugin.{plugin_name}.{task_name}"

        # Wrap handler as Celery task (if not yet registered) / 将 handler 包装为 Celery task
        if celery_task_name not in celery_app.tasks:
            import asyncio
            import functools

            if asyncio.iscoroutinefunction(handler):

                @functools.wraps(handler)
                def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                    return _RegistryRuntimeBridge.run_async(handler(*args, **kwargs))

                celery_app.task(name=celery_task_name, queue=queue)(_sync_wrapper)
            else:
                celery_app.task(name=celery_task_name, queue=queue)(handler)

        beat_key = f"plugin_{plugin_name}_{task_name}"

        if register_schedule:
            # Inject into beat_schedule / 注入 beat_schedule
            schedule_entry: dict[str, Any] = {
                "task": celery_task_name,
                "options": {"queue": queue},
            }

            if schedule_type == "cron" and cron_expression:
                from celery.schedules import crontab

                parts = cron_expression.strip().split()
                if len(parts) == 5:
                    schedule_entry["schedule"] = crontab(
                        minute=parts[0],
                        hour=parts[1],
                        day_of_month=parts[2],
                        month_of_year=parts[3],
                        day_of_week=parts[4],
                    )
                else:
                    logger.warning(
                        "Plugin {} task {}: invalid cron '{}', skipping schedule",
                        plugin_name,
                        task_name,
                        cron_expression,
                    )
            elif interval_seconds and interval_seconds > 0:
                schedule_entry["schedule"] = float(interval_seconds)
            else:
                logger.warning(
                    "Plugin {} task {}: no valid schedule, task registered but not scheduled",
                    plugin_name,
                    task_name,
                )

            if "schedule" in schedule_entry:
                if not celery_app.conf.beat_schedule:
                    celery_app.conf.beat_schedule = {}
                celery_app.conf.beat_schedule[beat_key] = schedule_entry

        self._track(
            plugin_name,
            "task",
            beat_key,
            {
                "celery_task_name": celery_task_name,
                "handler": handler,
            },
        )
        logger.info(
            "Plugin {} registered task: {} ({})",
            plugin_name,
            task_name,
            schedule_type,
        )

    def _unregister_task(self, ext: RegisteredExtension) -> None:
        """Remove plugin scheduled task from Celery Beat / 从 Celery Beat 移除插件定时任务"""
        try:
            from app.celery_app import celery_app

            beat_key = ext.key  # plugin_{name}_{task_name} / Celery Beat 调度键
            if (
                celery_app.conf.beat_schedule
                and beat_key in celery_app.conf.beat_schedule
            ):
                del celery_app.conf.beat_schedule[beat_key]
                logger.info("Removed beat schedule: {}", beat_key)
        except Exception as exc:
            logger.warning("Failed to unregister task {}: {}", ext.key, exc)

    # ── 8. Notification / 通知 ──

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
        DB persistence is handled by separate logic in lifecycle.enable() if needed.
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

    def _unregister_notification(self, ext: RegisteredExtension) -> None:
        """Remove plugin notification template registration / 移除插件通知模板注册"""
        self._plugin_notifications.pop(ext.key, None)

    def get_plugin_notification(self, code: str) -> dict | None:
        """Get plugin-registered notification template (for notification service query) / 获取插件注册的通知模板"""
        return self._plugin_notifications.get(code)

    # ── 9. Permission / 权限 ──

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

    def _unregister_permission(self, ext: RegisteredExtension) -> None:
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
                v
                for v in self._plugin_permissions.values()
                if v["plugin_name"] == plugin_name
            ]
        return list(self._plugin_permissions.values())

    # ── 10. Menu / 菜单 ──

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

        _allowed_menu_scopes = {_PS.ADMIN.value, _PS.TENANT.value}
        if scope not in _allowed_menu_scopes:
            raise ValueError(
                f"Invalid plugin menu scope {scope!r}; expected one of {sorted(_allowed_menu_scopes)}"
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
        self._plugin_menus[plugin_name] = [m for m in menus if m.get("name") != name]
        self._plugin_menus[plugin_name].append(menu_entry)

        if title:
            titles = self._plugin_menu_titles.setdefault(plugin_name, {})
            safe_name = plugin_name.replace("-", "_")
            i18n_key = f"{safe_name}.{name}.title"
            titles[i18n_key] = title

        self._track(plugin_name, "menu", name, menu_entry)

        # Bridge to permission_registry so sync_plugin_permissions() can write to DB / 桥接到 permission_registry 以便写入 DB
        self._register_menu_permission(
            plugin_name, name, path, icon, parent, sort_order, scope, component, hidden
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

    def _unregister_menu(self, ext: RegisteredExtension) -> None:
        """Remove plugin menu registration / 移除插件菜单注册"""
        plugin_name = ext.plugin_name
        name = ext.key
        if plugin_name in self._plugin_menus:
            self._plugin_menus[plugin_name] = [
                m for m in self._plugin_menus[plugin_name] if m.get("name") != name
            ]
        if plugin_name in self._plugin_menu_titles:
            safe_name = plugin_name.replace("-", "_")
            i18n_key = f"{safe_name}.{name}.title"
            self._plugin_menu_titles[plugin_name].pop(i18n_key, None)

        # Unregister from permission_registry (try both scope prefixes) / 从 permission_registry 反注册
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
        result.sort(key=lambda x: x.get("sort_order", 100))
        return result

    def resolve_plugin_menu_title(self, i18n_key: str) -> str | None:
        return self.read_layer.resolve_plugin_menu_title(i18n_key)

    def resolve_plugin_permission_title(self, i18n_key: str) -> str | None:
        return self.read_layer.resolve_plugin_permission_title(i18n_key)

    # ── 11. Socket.IO Namespace / Socket.IO 命名空间 ──

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

        Args:
            plugin_name: Plugin name / 插件名
            namespace_path: Short path (e.g. "collab") / 短路径
            handler_class: AsyncNamespace subclass / AsyncNamespace 子类
            auth_required: Whether JWT auth is needed / 是否需要 JWT 认证
            auth_scopes: Allowed token scope list / 允许的 token scope 列表
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

    def _unregister_socketio(self, ext: RegisteredExtension) -> None:
        """Unregister plugin Socket.IO namespace / 反注册插件 Socket.IO namespace"""
        try:
            from app.core.socketio_server import get_sio

            sio = get_sio()
            full_ns = ext.key
            # python-socketio has no native unregister_namespace, manually remove from namespace_handlers / 手动从 namespace_handlers 移除
            # / 手动从 namespace_handlers 移除
            if hasattr(sio, "namespace_handlers") and full_ns in sio.namespace_handlers:
                del sio.namespace_handlers[full_ns]
                logger.info("Removed Socket.IO namespace: {}", full_ns)
            else:
                logger.warning("Socket.IO namespace {} not found in handlers", full_ns)
        except Exception as exc:
            logger.warning(
                "Failed to unregister socketio namespace {}: {}", ext.key, exc
            )

    # ── 12. Frontend Slot / 前端插槽 ──

    def register_frontend_slot(
        self,
        plugin_name: str,
        slot_type: str,
        **data: object,
    ) -> None:
        """
        Register plugin frontend slot.
        / 注册插件前端插槽。

        slot_type values:
          header_widget / dashboard_widget / settings_tab /
          floating_panel / standalone_page / notification_ui

        Dedup strategy: unique by (slot_type, name), overwrites old value on re-registration.
        / 去重策略：按 (slot_type, name) 唯一，重复注册时覆盖旧值。
        """
        slot_entry = {"slot_type": slot_type, "plugin_name": plugin_name, **data}
        dedup_key = f"{slot_type}:{data.get('name', '')}"

        slots = self._plugin_frontend_slots.setdefault(plugin_name, [])
        # Remove old entry with same key, then append new entry (upsert semantics) / 移除同 key 旧条目再追加（upsert）
        # / 移除同 key 的旧条目，再追加新条目
        self._plugin_frontend_slots[plugin_name] = [
            s for s in slots if f"{s['slot_type']}:{s.get('name', '')}" != dedup_key
        ]
        self._plugin_frontend_slots[plugin_name].append(slot_entry)

        self._track(plugin_name, "frontend_slot", dedup_key, slot_entry)
        logger.info(
            "Plugin {} registered frontend slot: {}/{}",
            plugin_name,
            slot_type,
            data.get("name", ""),
        )

    def _unregister_frontend_slot(self, ext: RegisteredExtension) -> None:
        """Remove plugin frontend slot registration / 移除插件前端插槽注册"""
        plugin_name = ext.plugin_name
        key = ext.key  # "slot_type:name" / 插槽去重键
        if plugin_name in self._plugin_frontend_slots:
            self._plugin_frontend_slots[plugin_name] = [
                s
                for s in self._plugin_frontend_slots[plugin_name]
                if f"{s['slot_type']}:{s.get('name', '')}" != key
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

        Args:
            slot_type: Filter slot type (None = all) / 过滤插槽类型
            scope: Filter applicable side ("admin" / "tenant" / None = all) / 过滤适用端
            plugin_name: Filter specific plugin (None = all) / 过滤指定插件
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
                    # Filter by endpoint side (admin / tenant / user / both / empty) / 按管理端/企业端等过滤插槽
                    if (
                        scope == "admin"
                        and slot_scope == "tenant"
                        or scope == "tenant"
                        and slot_scope == "admin"
                    ):
                        continue
                all_slots.append(slot)
        return all_slots

    # ── General / 通用 ──

    def unregister_all(self, plugin_name: str) -> int:
        """
        Unregister all extensions of the specified plugin.
        / 反注册指定插件的所有扩展。

        Returns:
            Number of unregistered extensions / 反注册的扩展数量
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
                        "Failed to unregister {}/{} for plugin {}: {}",
                        ext.ext_type,
                        ext.key,
                        plugin_name,
                        exc,
                    )
        self._cleanup_plugin_runtime_state(plugin_name)
        self._cleanup_plugin_event_bus(plugin_name)

        logger.info("Unregistered {} extensions for plugin {}", count, plugin_name)
        return count

    def unregister_by_type(self, plugin_name: str, ext_type: str) -> int:
        """Unregister a single extension type for a plugin. / 反注册插件的单一扩展类型。"""
        tracked = self._registry.get(plugin_name, [])
        if not tracked:
            return 0

        remaining: list[RegisteredExtension] = []
        removed = 0
        for ext in tracked:
            if ext.ext_type != ext_type:
                remaining.append(ext)
                continue
            method_name = self._DISPATCH.get(ext.ext_type)
            if method_name:
                getattr(self, method_name)(ext)
                removed += 1

        if remaining:
            self._registry[plugin_name] = remaining
        else:
            self._registry.pop(plugin_name, None)
        return removed

    def get_conflicts(self, manifest: Any) -> list[dict[str, str]]:
        return self.read_layer.get_conflicts(manifest)

    def _find_owner(self, ext_type: str, key: str) -> str | None:
        return self.read_layer.find_owner(ext_type, key)
