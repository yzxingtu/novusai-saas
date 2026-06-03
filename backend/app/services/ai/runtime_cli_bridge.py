"""
Thin bridge for AI runtime CLI commands.

This module intentionally avoids owning business logic. It only routes CLI
requests to unified runtime services and fails closed when a required service
cannot be loaded.
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
        detail: str | None = None,
    ) -> None:
        joined = ", ".join(candidates)
        message = (
            f"Runtime CLI operation '{operation}' is not available yet. "
            f"Expected one of: {joined}"
        )
        if detail:
            message = f"{message}. Detail: {detail}"
        super().__init__(message)
        self.operation = operation
        self.candidates = candidates
        self.detail = detail


class AIRuntimeCliBridge:
    """Dispatches CLI operations to required unified services."""

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
        )

    async def run_real_dialogue_smoke(
        self,
        scope: RuntimeCliScope,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._dispatch(
            operation="real-dialogue-smoke",
            scope=scope,
            payload=payload,
            candidates=[
                (
                    "app.services.ai.runtime_diagnostics_service",
                    "RuntimeDiagnosticsService",
                    "run_real_dialogue_smoke",
                ),
            ],
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
        )

    async def _dispatch(
        self,
        *,
        operation: str,
        candidates: list[tuple[str, str, str]],
        scope: RuntimeCliScope | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        available = [f"{m}.{c}.{fn}" for m, c, fn in candidates]
        for module_name, class_name, method_name in candidates:
            try:
                service_cls = self._load_class(module_name, class_name)
            except Exception as exc:
                raise RuntimeCliDependencyMissing(
                    operation,
                    available,
                    detail=f"failed to load {module_name}.{class_name}: {exc}",
                ) from exc
            if service_cls is None:
                continue

            try:
                service_obj = service_cls(self.db)
            except Exception as exc:
                raise RuntimeCliDependencyMissing(
                    operation,
                    available,
                    detail=f"failed to initialize {module_name}.{class_name}: {exc}",
                ) from exc

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

        raise RuntimeCliDependencyMissing(operation, available)

    @staticmethod
    def _load_class(module_name: str, class_name: str) -> type | None:
        module = import_module(module_name)
        value = getattr(module, class_name, None)
        return value if isinstance(value, type) else None

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
