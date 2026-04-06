"""
Thin bridge for AI runtime CLI commands.

This module intentionally avoids owning business logic. It only routes CLI
requests to unified runtime services when those services are available.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from importlib import import_module
from typing import Any


@dataclass(slots=True, frozen=True)
class RuntimeCliScope:
    tenant_id: int | None = None
    agent_id: int | None = None
    agent_code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "agent_id": self.agent_id,
            "agent_code": self.agent_code,
        }


class RuntimeCliDependencyMissing(RuntimeError):
    """Raised when the runtime unified service layer is unavailable."""

    def __init__(
        self,
        operation: str,
        candidates: list[str],
    ) -> None:
        joined = ", ".join(candidates)
        super().__init__(
            f"Runtime CLI operation '{operation}' is not available yet. "
            f"Expected one of: {joined}"
        )
        self.operation = operation
        self.candidates = candidates


class AIRuntimeCliBridge:
    """Dispatches CLI operations to unified services when present."""

    def __init__(self, db: Any) -> None:
        self.db = db

    async def get_capabilities(self, scope: RuntimeCliScope) -> dict[str, Any]:
        return await self._dispatch(
            operation="capabilities",
            scope=scope,
            candidates=[
                (
                    "app.services.ai.runtime_inventory_service",
                    "RuntimeInventoryService",
                    "build_manifest",
                ),
                (
                    "app.services.ai.runtime_inventory_service",
                    "RuntimeInventoryService",
                    "get_manifest",
                ),
            ],
            fallback={"status": "not_available", "scope": scope.as_dict()},
        )

    async def run_doctor(self, scope: RuntimeCliScope) -> dict[str, Any]:
        return await self._dispatch(
            operation="doctor",
            scope=scope,
            candidates=[
                (
                    "app.services.ai.runtime_diagnostics_service",
                    "RuntimeDiagnosticsService",
                    "run_doctor",
                ),
            ],
            fallback={"status": "not_available", "scope": scope.as_dict()},
        )

    async def run_smoke(self, scope: RuntimeCliScope) -> dict[str, Any]:
        return await self._dispatch(
            operation="smoke",
            scope=scope,
            candidates=[
                (
                    "app.services.ai.runtime_diagnostics_service",
                    "RuntimeDiagnosticsService",
                    "run_smoke",
                ),
            ],
            fallback={"status": "not_available", "scope": scope.as_dict()},
        )

    async def run_root_cause(
        self,
        *,
        trace_id: str | None = None,
        call_log_id: int | None = None,
        conversation_id: int | None = None,
        turn: int | None = None,
    ) -> dict[str, Any]:
        request_payload = {
            "trace_id": trace_id,
            "call_log_id": call_log_id,
            "conversation_id": conversation_id,
            "turn": turn,
        }
        return await self._dispatch(
            operation="root-cause",
            payload=request_payload,
            candidates=[
                (
                    "app.services.ai.runtime_diagnostics_service",
                    "RuntimeDiagnosticsService",
                    "run_root_cause",
                ),
            ],
            fallback={"status": "not_available", "request": request_payload},
        )

    async def sync_starter_pack(self) -> dict[str, Any]:
        return await self._dispatch(
            operation="starter-pack-sync",
            candidates=[
                (
                    "app.services.ai.runtime_diagnostics_service",
                    "RuntimeDiagnosticsService",
                    "sync_official_starter_pack",
                ),
            ],
            fallback={
                "status": "not_available",
                "message": "starter-pack service is not wired yet",
            },
        )

    async def _dispatch(
        self,
        *,
        operation: str,
        candidates: list[tuple[str, str, str]],
        scope: RuntimeCliScope | None = None,
        payload: dict[str, Any] | None = None,
        fallback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        for module_name, class_name, method_name in candidates:
            service_cls = self._load_class(module_name, class_name)
            if service_cls is None:
                continue

            service_obj = self._instantiate_service(service_cls)
            if service_obj is None:
                continue

            method = getattr(service_obj, method_name, None)
            if not callable(method):
                continue

            kwargs = self._build_call_kwargs(method, scope=scope, payload=payload)
            result = method(**kwargs)
            if inspect.isawaitable(result):
                result = await result
            if isinstance(result, dict):
                return result
            return {"result": result}

        if fallback is not None:
            return fallback

        available = [f"{m}.{c}.{fn}" for m, c, fn in candidates]
        raise RuntimeCliDependencyMissing(operation, available)

    @staticmethod
    def _load_class(module_name: str, class_name: str) -> type | None:
        try:
            module = import_module(module_name)
        except Exception:
            return None
        value = getattr(module, class_name, None)
        return value if isinstance(value, type) else None

    def _instantiate_service(self, service_cls: type) -> Any | None:
        try:
            return service_cls(self.db)
        except TypeError:
            try:
                return service_cls(db=self.db)
            except Exception:
                return None
        except Exception:
            return None

    @staticmethod
    def _build_call_kwargs(
        method: Any,
        *,
        scope: RuntimeCliScope | None,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        signature = inspect.signature(method)
        allowed = set(signature.parameters.keys())
        kwargs: dict[str, Any] = {}

        if scope is not None:
            if "scope" in allowed:
                kwargs["scope"] = scope
            if "tenant_id" in allowed:
                kwargs["tenant_id"] = scope.tenant_id
            if "agent_id" in allowed:
                kwargs["agent_id"] = scope.agent_id
            if "agent_code" in allowed:
                kwargs["agent_code"] = scope.agent_code

        for key, value in (payload or {}).items():
            if key in allowed:
                kwargs[key] = value
        return kwargs
