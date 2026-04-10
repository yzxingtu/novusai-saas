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
