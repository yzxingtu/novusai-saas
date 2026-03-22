"""
Batch extension point registration / 扩展点批量注册

Shared function used by lifecycle.enable() and startup.restore_enabled_plugins().
Eliminates ~80 lines of duplicated registration loops.
/
公共函数，供 lifecycle.enable() 和 startup.restore_enabled_plugins() 共用。
消除两处 ~80 行的重复注册循环。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.enums.plugin import FrontendSlotTypeEnum

if TYPE_CHECKING:
    from app.plugins.manifest import ExtensionsSchema, PluginManifest
    from app.plugins.registry import ExtensionRegistry

logger = get_logger(__name__)


def _build_frontend_runtime_payload(manifest: PluginManifest) -> dict[str, str]:
    """Project frontend runtime contract into slot metadata. / 将前端运行时契约投影到插槽元数据。"""
    frontend = manifest.extensions.frontend
    payload: dict[str, str] = {}

    dev_entry = str(getattr(frontend.dev, "entry", "") or "").strip()
    if dev_entry:
        payload["dev_entry"] = dev_entry

    release_manifest = str(getattr(frontend.release, "manifest", "") or "").strip()
    if release_manifest:
        payload["release_manifest"] = release_manifest

    return payload


def _load_handler(plugin_name: str, handler_path: str) -> Callable | None:
    """Load plugin handler function — delegates to unified loader / 加载插件处理函数 — 委托给统一加载器"""
    from app.plugins.module_loader import load_plugin_handler

    return load_plugin_handler(plugin_name, handler_path)


def _load_executor(plugin_name: str, skill_type: str) -> type | None:
    """Load plugin executor class — delegates to unified loader / 加载插件 executor 类 — 委托给统一加载器"""
    from app.plugins.module_loader import load_plugin_executor

    return load_plugin_executor(plugin_name, skill_type)


def _normalize_public_captcha_endpoints(value: object) -> list[str]:
    """Normalize public captcha endpoints / 规范化公开验证码端点列表"""
    allowed = {"admin", "tenant", "user"}
    if not isinstance(value, list):
        return []

    normalized: list[str] = []
    for item in value:
        endpoint = str(item or "").strip().lower()
        if endpoint in allowed and endpoint not in normalized:
            normalized.append(endpoint)
    return normalized


def _register_custom_captcha_provider(
    manifest: PluginManifest,
    plugin_name: str,
    custom_ext,
) -> bool:
    """Register captcha provider declared via custom extension / 注册通过 custom 声明的验证码提供者"""
    entry_point = str((custom_ext.data or {}).get("entry_point") or "").strip()
    if not entry_point:
        return False

    provider_ref = _load_handler(plugin_name, entry_point)
    if provider_ref is None:
        return False

    try:
        provider = provider_ref() if isinstance(provider_ref, type) else provider_ref
    except Exception:
        logger.warning(
            "Plugin {} captcha provider '{}' failed to instantiate",
            plugin_name,
            entry_point,
            exc_info=True,
        )
        return False

    from app.captcha.provider import CaptchaProviderMetadata
    from app.captcha.registry import registry as captcha_registry

    captcha_registry.register(
        custom_ext.name,
        provider,
        metadata=CaptchaProviderMetadata(
            plugin_name=plugin_name,
            public_endpoints=_normalize_public_captcha_endpoints(
                (custom_ext.data or {}).get("public_endpoints"),
            ),
            frontend_runtime=_build_frontend_runtime_payload(manifest),
        ),
    )
    return True


def register_all_extensions(
    registry: ExtensionRegistry,
    manifest: PluginManifest,
    plugin_name: str,
    menu_overrides: dict[str, dict] | None = None,
) -> int:
    """
    Register all extension points declared in manifest to ExtensionRegistry.
    / 将 manifest 中声明的所有扩展点注册到 ExtensionRegistry。

    Failed extensions are recorded in failed_extensions list with warning logs.
    Callers can use get_failed_extensions() for fail-close decisions.
    / 加载失败的扩展会记入 failed_extensions 列表并输出警告日志。
    调用方可通过 get_failed_extensions() 获取失败列表进行 fail-close 决策。

    Args:
        registry: Extension registry instance / 扩展点注册中心实例
        manifest: Plugin manifest (parsed PluginManifest) / 插件清单（已解析的 PluginManifest）
        plugin_name: Plugin name / 插件名称
        menu_overrides: Admin-customized menu position overrides / 管理员自定义的菜单位置覆盖
            Format / 格式: {"menu_name": {"parent": "system_maintenance"}}

    Returns:
        Number of successfully registered extension points / 注册成功的扩展点数量（registry.get_registered_count）
    """
    # ── T13: Idempotency guarantee (clean-slate strategy) / 幂等性保证（clean-slate 策略）──
    # Clear old registrations first, then re-register all extension points.
    # Ensures no duplicate injections when enable/restore is executed repeatedly.
    # unregister_all is a no-op when plugin_name has no registrations, safely idempotent.
    # / 先清除旧注册，再重新注册所有扩展点。
    # 确保 enable/restore 重复执行时不会产生重复注入。
    # unregister_all 在 plugin_name 无注册时为 no-op，安全幂等。
    registry.unregister_all(plugin_name)

    ext: ExtensionsSchema = manifest.extensions
    _failed_extensions[plugin_name] = []

    # Skills（resolver + executor）
    for skill_ext in ext.skills:
        resolver_func = (
            _load_handler(plugin_name, skill_ext.entry_point + ".resolve")
            if skill_ext.entry_point
            else None
        )
        executor_cls = _load_executor(plugin_name, skill_ext.type)
        if resolver_func:
            registry.register_skill(
                plugin_name, skill_ext.type, resolver_func, executor_cls,
            )
        elif skill_ext.entry_point:
            _record_failure(plugin_name, "skill", skill_ext.entry_point)

    # Adapters
    for adapter_ext in ext.adapters:
        adapter_cls = _load_handler(plugin_name, adapter_ext.entry_point)
        if adapter_cls:
            registry.register_adapter(
                plugin_name, adapter_ext.provider_code, adapter_cls,
            )
        else:
            _record_failure(plugin_name, "adapter", adapter_ext.entry_point)

    # Storage Drivers
    for storage_ext in ext.storage_drivers:
        driver_cls = _load_handler(plugin_name, storage_ext.entry_point)
        if driver_cls:
            registry.register_storage_driver(plugin_name, driver_cls)
        else:
            _record_failure(plugin_name, "storage_driver", storage_ext.entry_point)

    # Hooks
    for hook in ext.hooks:
        handler = _load_handler(plugin_name, hook.handler)
        if handler:
            registry.register_hook(
                plugin_name, hook.point, handler, hook.priority,
            )
        else:
            _record_failure(plugin_name, "hook", hook.handler)

    # Events
    for event in ext.events:
        handler = _load_handler(plugin_name, event.handler)
        if handler:
            registry.register_event(plugin_name, event.event, handler)
        else:
            _record_failure(plugin_name, "event", event.handler)

    # Webhooks
    for webhook in ext.webhooks:
        handler = _load_handler(plugin_name, webhook.handler)
        if handler:
            registry.register_webhook(
                plugin_name, webhook.path, handler,
                webhook.method, webhook.auth.model_dump(),
            )
        else:
            _record_failure(plugin_name, "webhook", webhook.handler)

    # Tasks
    for task_ext in ext.tasks:
        handler = _load_handler(plugin_name, task_ext.handler)
        if handler:
            registry.register_task(
                plugin_name, task_ext.name, handler,
                task_ext.schedule_type,
                task_ext.cron_expression,
                task_ext.interval_seconds,
                task_ext.queue,
            )
        else:
            _record_failure(plugin_name, "task", task_ext.handler)

    # Notifications
    for notif_ext in ext.notifications:
        registry.register_notification(
            plugin_name, notif_ext.code,
            notif_ext.title, notif_ext.channels, notif_ext.category,
        )

    # Permissions
    for perm_ext in ext.permissions:
        registry.register_permission(
            plugin_name, perm_ext.code,
            perm_ext.name, perm_ext.scope, perm_ext.actions,
        )

    # Socket.IO Namespaces
    for sio_ext in ext.socketio:
        handler_class = _load_handler(plugin_name, sio_ext.handler)
        if handler_class:
            registry.register_socketio(
                plugin_name, sio_ext.path, handler_class,
                sio_ext.auth_required, sio_ext.auth_scopes,
            )
        else:
            _record_failure(plugin_name, "socketio", sio_ext.handler)

    register_navigation_extensions(
        registry,
        manifest,
        plugin_name,
        menu_overrides=menu_overrides,
    )

    # ── T9: Frontend Slots (6 types, registered by slot_type) / （6 种前端插槽，按 slot_type 分类注册）──
    frontend_runtime = _build_frontend_runtime_payload(manifest)
    slot_common = {"frontend_runtime": frontend_runtime} if frontend_runtime else {}

    # header_widgets — Top-right navigation bar components / 右上角导航栏组件
    for widget in ext.frontend.header_widgets:
        registry.register_frontend_slot(
            plugin_name, FrontendSlotTypeEnum.HEADER_WIDGET.value,
            name=widget.name,
            component=widget.component,
            sort_order=widget.sort_order,
            scope=widget.scope,
            **slot_common,
        )

    # floating_panels — Page floating panels (bottom-right, etc.) / 页面浮动面板（右下角等）
    for panel in ext.frontend.floating_panels:
        registry.register_frontend_slot(
            plugin_name, FrontendSlotTypeEnum.FLOATING_PANEL.value,
            name=panel.name,
            component=panel.component,
            icon=panel.icon,
            position=panel.position,
            **slot_common,
        )

    register_frontend_page_extensions(
        registry,
        manifest,
        plugin_name,
        frontend_runtime=frontend_runtime,
    )

    # notification_ui — Notification center custom UI components / 通知中心自定义 UI 组件
    for notif_ui in ext.frontend.notification_ui:
        registry.register_frontend_slot(
            plugin_name, FrontendSlotTypeEnum.NOTIFICATION_UI.value,
            name=notif_ui.event,
            event=notif_ui.event,
            component=notif_ui.component,
            **slot_common,
        )

    # dashboard_widgets — Dashboard widget cards / 仪表板卡片
    for widget in ext.frontend.dashboard_widgets:
        registry.register_frontend_slot(
            plugin_name, FrontendSlotTypeEnum.DASHBOARD_WIDGET.value,
            name=widget.name,
            component=widget.component,
            title=widget.title,
            grid=widget.grid,
            scope=widget.scope,
            **slot_common,
        )

    # settings_tabs — System settings tabs / 系统设置页签
    for tab in ext.frontend.settings_tabs:
        registry.register_frontend_slot(
            plugin_name, FrontendSlotTypeEnum.SETTINGS_TAB.value,
            name=tab.name,
            component=tab.component,
            title=tab.title,
            scope=tab.scope,
            **slot_common,
        )

    # Middleware — ASGI middleware (injected into request chain) / ASGI 中间件（注入请求链）
    for mw_ext in ext.middleware:
        mw_cls = _load_handler(plugin_name, mw_ext.handler)
        if mw_cls:
            registry.register_middleware(
                plugin_name, mw_ext.name, mw_cls,
                priority=mw_ext.priority,
            )
        else:
            _record_failure(plugin_name, "middleware", mw_ext.handler)

    # Custom Extensions — Generic custom extension points (metadata injection) / 通用自定义扩展点（元数据注入）
    for custom_ext in ext.custom:
        if custom_ext.type == "captcha_provider":
            if not _register_custom_captcha_provider(manifest, plugin_name, custom_ext):
                entry_point = str((custom_ext.data or {}).get("entry_point") or custom_ext.name)
                _record_failure(plugin_name, "custom", entry_point)
        registry.register_custom(
            plugin_name, custom_ext.type, custom_ext.name,
            data=custom_ext.data,
            description=custom_ext.description,
        )

    # Consumers — Message queue consumers (no scheduling, triggered by queue messages) / 消息队列消费者（无调度，由队列消息触发）
    for consumer_ext in ext.consumers:
        handler = _load_handler(plugin_name, consumer_ext.handler)
        if handler:
            registry.register_consumer(
                plugin_name, consumer_ext.name, handler,
                queue=consumer_ext.queue,
                max_retries=consumer_ext.max_retries,
                retry_delay=consumer_ext.retry_delay,
            )
        else:
            _record_failure(plugin_name, "consumer", consumer_ext.handler)

    # Clean up empty failure list / 清理空失败列表
    if not _failed_extensions[plugin_name]:
        del _failed_extensions[plugin_name]

    return registry.get_registered_count(plugin_name)


def register_navigation_extensions(
    registry: ExtensionRegistry,
    manifest: PluginManifest,
    plugin_name: str,
    menu_overrides: dict[str, dict] | None = None,
) -> None:
    """Register page-derived navigation only. / 仅注册页面派生导航。"""
    overrides = menu_overrides or {}
    for page in manifest.extensions.frontend.pages:
        if page.menu is None:
            continue
        override = overrides.get(page.name, {})
        effective_parent = override.get("parent", page.menu.parent)
        registry.register_menu(
            plugin_name,
            name=page.name,
            path=page.path,
            icon=page.menu.icon or page.icon,
            parent=effective_parent or "",
            sort_order=page.menu.sort_order,
            scope=page.scope,
            component=page.component,
            title=page.menu.title or page.title,
            hidden=page.menu.hidden,
        )


def register_frontend_page_extensions(
    registry: ExtensionRegistry,
    manifest: PluginManifest,
    plugin_name: str,
    *,
    frontend_runtime: dict[str, str] | None = None,
) -> None:
    """Register page slots from frontend.pages. / 根据 frontend.pages 注册页面插槽。"""
    for page in manifest.extensions.frontend.pages:
        slot_kwargs: dict[str, object] = {
            "name": page.name,
            "path": page.path,
            "component": page.component,
            "title": page.title,
            "scope": page.scope,
        }
        if page.icon:
            slot_kwargs["icon"] = page.icon
        if page.ai is not None:
            slot_kwargs["ai"] = page.ai.model_dump(exclude_none=True)
        if frontend_runtime:
            slot_kwargs["frontend_runtime"] = frontend_runtime
        registry.register_frontend_slot(
            plugin_name,
            FrontendSlotTypeEnum.STANDALONE_PAGE.value,
            **slot_kwargs,
        )


def get_failed_extensions(plugin_name: str) -> list[dict[str, str]]:
    """Get the list of failed extensions from the latest registration for a plugin. / 获取指定插件最近一次注册中失败的扩展列表。"""
    return list(_failed_extensions.get(plugin_name, []))


def _record_failure(plugin_name: str, ext_type: str, entry_point: str) -> None:
    """Record extension load failure and output warning. / 记录扩展加载失败并输出警告。"""
    _failed_extensions.setdefault(plugin_name, []).append(
        {"type": ext_type, "entry_point": entry_point},
    )
    logger.warning(
        "Plugin {}: failed to load {} extension '{}'",
        plugin_name, ext_type, entry_point,
    )


# Plugin name → list of failed extensions from the latest registration / 插件名 → 最近一次注册中失败的扩展列表
_failed_extensions: dict[str, list[dict[str, str]]] = {}
