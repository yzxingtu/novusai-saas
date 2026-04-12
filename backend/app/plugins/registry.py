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
        self._plugin_permission_titles.pop(plugin_name, None)
        self._plugin_skill_resolvers.pop(plugin_name, None)
        self._plugin_executors.pop(plugin_name, None)

        if self._plugin_permissions:
            self._plugin_permissions = {
                key: value
                for key, value in self._plugin_permissions.items()
                if value.get("plugin_name") != plugin_name
            }

        if self._plugin_notifications:
            self._plugin_notifications = {
                key: value
                for key, value in self._plugin_notifications.items()
                if value.get("plugin_name") != plugin_name
            }

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
