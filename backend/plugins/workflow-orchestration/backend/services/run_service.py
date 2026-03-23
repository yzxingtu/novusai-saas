from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.core.base_model import utc_now
from app.core.i18n import _
from app.core.logging import get_logger
from app.middleware.trace import trace_id_var
from app.plugins.module_loader import load_plugin_module

PLUGIN_NAME = "workflow-orchestration"
logger = get_logger(__name__)


def _runtime(name: str):
    module = load_plugin_module(PLUGIN_NAME, f"runtime.{name}")
    if module is None:
        raise RuntimeError(f"Missing runtime module: {name}")
    return module


class RunService:
    def __init__(
        self,
        db: Any,
        tenant_id: int | None = None,
        *,
        actor_type: str = "tenant_admin",
        actor_id: int | None = None,
    ) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.actor_type = actor_type
        self.actor_id = actor_id

    async def create_run_from_workflow(self, workflow_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        errors = _runtime("errors")
        executor = _runtime("executor")
        graph = _runtime("graph")
        model_access = _runtime("model_access")
        serializer = _runtime("serializer")

        workflow_model = model_access.resolve_model("tenant_workflow")
        run_model = model_access.resolve_model("workflow_run")

        stmt = select(workflow_model).where(workflow_model.id == workflow_id)
        if self.tenant_id is not None:
            stmt = stmt.where(workflow_model.tenant_id == self.tenant_id)
        workflow = (await self.db.execute(stmt)).scalar_one_or_none()
        if workflow is None:
            raise errors.WorkflowNotFoundError(
                _("plugin.workflow-orchestration.error.workflow_not_found"),
            )

        workflow_status = str(model_access.first_attr(workflow, ("status",), "draft"))
        if workflow_status != "published":
            raise errors.WorkflowConflictError(
                _("plugin.workflow-orchestration.error.workflow_not_published"),
            )

        preferred_version_id = self._safe_int(payload.get("workflow_version_id"))
        explicit_snapshot = self._normalize_payload_dict(payload.get("workflow_snapshot"))
        workflow_version, resolved_version_id = await self._resolve_executable_version(
            workflow,
            preferred_version_id=preferred_version_id,
            allow_snapshot_fallback=bool(preferred_version_id and explicit_snapshot),
        )
        if resolved_version_id is None:
            raise errors.WorkflowConflictError(
                _("plugin.workflow-orchestration.error.workflow_not_published"),
            )

        if preferred_version_id is not None and workflow_version is None and not explicit_snapshot:
            raise errors.WorkflowConflictError(
                _("plugin.workflow-orchestration.error.workflow_not_published"),
            )

        snapshot = explicit_snapshot
        if not snapshot and workflow_version is not None:
            snapshot = graph.extract_snapshot(workflow_version)
        if not snapshot:
            snapshot = graph.extract_snapshot(workflow)
        if not snapshot:
            raise errors.WorkflowValidationError(
                _("plugin.workflow-orchestration.error.workflow_snapshot_missing"),
            )
        compiled_graph = graph.build_graph(snapshot)
        if not compiled_graph["nodes"]:
            raise errors.WorkflowValidationError(
                _("plugin.workflow-orchestration.error.workflow_snapshot_missing"),
            )

        input_payload = self._normalize_payload_dict(payload.get("input_payload") or payload.get("inputs") or {})
        initiated_from = str(
            payload.get("initiated_from") or payload.get("trigger_source") or "manual"
        ).strip() or "manual"
        control_envelope = self._normalize_payload_dict(payload.get("control_envelope_json") or payload.get("control_envelope") or {})
        control_envelope.setdefault("workflow_snapshot", snapshot)
        control_envelope.setdefault("workflow_version_id", resolved_version_id)
        control_envelope.setdefault("workflow_id", model_access.first_attr(workflow, ("id",)))
        control_envelope.setdefault("builder_surface", model_access.first_attr(workflow, ("builder_surface",)))
        risk_snapshot = self._normalize_payload_dict(payload.get("risk_snapshot_json") or payload.get("risk_snapshot"))
        if not risk_snapshot:
            risk_snapshot = self._normalize_payload_dict(model_access.first_attr(workflow, ("summary_json",), {}) or {})

        run = model_access.instantiate_model(
            run_model,
            {
                "tenant_id": model_access.first_attr(workflow, ("tenant_id",)),
                "workflow_template_id": model_access.first_attr(workflow, ("source_template_id",)),
                "workflow_id": model_access.first_attr(workflow, ("id",)),
                "workflow_version_id": resolved_version_id,
                "release_id": model_access.first_attr(workflow, ("current_release_id", "source_release_id")),
                "trigger_id": payload.get("trigger_id"),
                "environment_id": payload.get("environment_id"),
                "parent_run_id": payload.get("parent_run_id"),
                "initiated_from": initiated_from,
                "initiated_by": self.actor_id,
                "started_by_type": self.actor_type,
                "entrypoint": payload.get("entrypoint") or "workflow_run",
                "mode": payload.get("mode") or model_access.first_attr(workflow, ("mode",), "deterministic"),
                "status": "queued",
                "trace_id": trace_id_var.get() or payload.get("trace_id"),
                "idempotency_key": payload.get("idempotency_key"),
                "retry_count": int(payload.get("retry_count") or 0),
                "input_payload_json": input_payload,
                "output_payload_json": None,
                "cost_summary_json": {},
                "control_envelope_json": control_envelope,
                "budget_snapshot_json": self._normalize_payload_dict(
                    payload.get("budget_snapshot_json") or payload.get("budget_snapshot") or {}
                ),
                "risk_snapshot_json": risk_snapshot,
                "metrics_json": {
                    "node_count": len(compiled_graph["nodes"]),
                    "edge_count": len(compiled_graph["edges"]),
                    "root_node_count": len(compiled_graph["root_node_keys"]),
                },
                "current_node_key": None,
                "last_heartbeat_at": utc_now(),
            },
        )
        self.db.add(run)
        await self.db.flush()

        bootstrapped = await executor.bootstrap_run_graph(self.db, run, snapshot)
        advanced = await executor.advance_run_execution(
            self.db,
            run,
            snapshot,
            node_runs=bootstrapped["node_runs"],
            graph=bootstrapped["graph"],
        )
        status_event = executor.create_event_instance(
            "run_status_changed",
            {
                "run": run,
                "status_from": "queued",
                "status_to": model_access.first_attr(run, ("status",), "queued"),
                "message": "run entered active state",
                "payload_json": {
                    "entrypoint": model_access.first_attr(run, ("entrypoint",)),
                    "workflow_version_id": resolved_version_id,
                },
            },
        )
        if status_event is not None:
            self.db.add(status_event)
        await self.db.flush()
        return serializer.serialize_run(run, node_runs=advanced["node_runs"])

    async def pause_run(self, run_id: int) -> dict[str, Any]:
        errors = _runtime("errors")
        executor = _runtime("executor")
        model_access = _runtime("model_access")
        serializer = _runtime("serializer")

        run = await self._get_run(run_id)
        current_status = str(model_access.first_attr(run, ("status",), "queued"))
        if current_status not in {"running", "waiting_human", "waiting_approval", "waiting_input", "recovering", "compensating"}:
            raise errors.WorkflowConflictError(
                _("plugin.workflow-orchestration.error.run_not_paused_state"),
            )

        executor.mark_run_status(run, status="paused", current_node_key=model_access.first_attr(run, ("current_node_key",)))
        event = executor.create_event_instance(
            "run_status_changed",
            {
                "run": run,
                "status_from": current_status,
                "status_to": "paused",
                "message": "run paused",
            },
        )
        if event is not None:
            self.db.add(event)
        await self.db.flush()
        return serializer.serialize_run(run, node_runs=await self._list_node_runs(run_id))

    async def terminate_run(self, run_id: int) -> dict[str, Any]:
        errors = _runtime("errors")
        executor = _runtime("executor")
        model_access = _runtime("model_access")
        serializer = _runtime("serializer")

        run = await self._get_run(run_id)
        current_status = str(model_access.first_attr(run, ("status",), "queued"))
        if current_status in {"completed", "failed", "cancelled", "partially_completed"}:
            raise errors.WorkflowConflictError(
                _("plugin.workflow-orchestration.error.run_already_terminal"),
            )

        node_runs = await self._list_node_runs(run_id)
        for node in node_runs:
            if model_access.first_attr(node, ("status",)) in {"pending", "ready", "running", "waiting_human", "waiting_approval", "waiting_input"}:
                model_access.assign_model_values(node, {"status": "cancelled", "ended_at": utc_now()})

        executor.mark_run_status(run, status="cancelled", current_node_key=None)
        event = executor.create_event_instance(
            "run_status_changed",
            {
                "run": run,
                "status_from": current_status,
                "status_to": "cancelled",
                "message": "run terminated",
            },
        )
        if event is not None:
            self.db.add(event)
        await self.db.flush()
        return serializer.serialize_run(run, node_runs=node_runs)

    async def _get_run(self, run_id: int) -> Any:
        errors = _runtime("errors")
        run_model = _runtime("model_access").resolve_model("workflow_run")
        stmt = select(run_model).where(run_model.id == run_id)
        if self.tenant_id is not None:
            stmt = stmt.where(run_model.tenant_id == self.tenant_id)
        run = (await self.db.execute(stmt)).scalar_one_or_none()
        if run is None:
            raise errors.WorkflowNotFoundError(
                _("plugin.workflow-orchestration.error.run_not_found"),
            )
        return run

    async def _list_node_runs(self, run_id: int) -> list[Any]:
        model_access = _runtime("model_access")
        node_model = model_access.try_resolve_model("workflow_node_run")
        if node_model is None:
            return []
        stmt = select(node_model).where(node_model.run_id == run_id)
        stmt = stmt.order_by(getattr(node_model, "created_at", node_model.id))
        return list((await self.db.execute(stmt)).scalars().all())

    async def _resolve_executable_version(
        self,
        workflow: Any,
        *,
        preferred_version_id: int | None = None,
        allow_snapshot_fallback: bool = False,
    ) -> tuple[Any | None, int | None]:
        model_access = _runtime("model_access")
        version_model = model_access.try_resolve_model("tenant_workflow_version")
        if version_model is None:
            return None, None

        if preferred_version_id:
            workflow_id = model_access.first_attr(workflow, ("id",))
            stmt = select(version_model).where(
                version_model.id == preferred_version_id,
                version_model.workflow_id == workflow_id,
            )
            preferred = (await self.db.execute(stmt)).scalar_one_or_none()
            if preferred is not None:
                return preferred, preferred_version_id
            if allow_snapshot_fallback:
                return None, preferred_version_id
            return None, None

        version_id = model_access.first_attr(workflow, ("active_version_id", "latest_version_id"))
        if version_id:
            stmt = select(version_model).where(version_model.id == version_id)
            version = (await self.db.execute(stmt)).scalar_one_or_none()
            if version is not None:
                return version, model_access.first_attr(version, ("id",))

        workflow_id = model_access.first_attr(workflow, ("id",))
        if workflow_id is None:
            return None, None

        stmt = select(version_model).where(version_model.workflow_id == workflow_id)
        if hasattr(version_model, "is_published"):
            stmt = stmt.where(version_model.is_published.is_(True))
        stmt = stmt.order_by(
            getattr(version_model, "version_no", version_model.id).desc(),
        ).limit(1)
        version = (await self.db.execute(stmt)).scalar_one_or_none()
        if version is None:
            return None, None
        return version, model_access.first_attr(version, ("id",))

    def _normalize_payload_dict(self, value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    def _safe_int(self, value: Any) -> int | None:
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            return None
        return numeric if numeric > 0 else None
