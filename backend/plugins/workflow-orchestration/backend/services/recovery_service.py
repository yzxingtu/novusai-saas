from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select

from app.core.base_model import utc_now
from app.core.i18n import _
from app.core.logging import get_logger
from app.plugins.module_loader import load_plugin_module

PLUGIN_NAME = "workflow-orchestration"
logger = get_logger(__name__)
WAITING_NODE_STATUSES = {"waiting_human", "waiting_approval", "waiting_input"}
WAITING_INPUT_PAYLOAD_FIELDS = (
    "input_payload",
    "inputs",
    "input_envelope_json",
    "human_input",
    "manual_input",
)


def _runtime(name: str):
    module = load_plugin_module(PLUGIN_NAME, f"runtime.{name}")
    if module is None:
        raise RuntimeError(f"Missing runtime module: {name}")
    return module


def _service(name: str):
    module = load_plugin_module(PLUGIN_NAME, f"services.{name}")
    if module is None:
        raise RuntimeError(f"Missing service module: {name}")
    return module


class RecoveryService:
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

    async def retry_run(self, run_id: int) -> dict[str, Any]:
        errors = _runtime("errors")
        executor = _runtime("executor")
        model_access = _runtime("model_access")
        serializer = _runtime("serializer")

        run = await self._get_run(run_id)
        current_status = str(model_access.first_attr(run, ("status",), "queued"))
        if current_status not in {"failed", "partially_completed", "recovering"}:
            raise errors.WorkflowConflictError(
                _("plugin.workflow-orchestration.error.run_not_retryable"),
            )

        node_runs = await self._list_node_runs(run_id)
        changed = False
        for node in node_runs:
            node_status = str(model_access.first_attr(node, ("status",), ""))
            if node_status in {"failed_retryable", "failed_terminal", "cancelled", "retry_scheduled"}:
                next_attempt = int(model_access.first_attr(node, ("attempt_no",), 0) or 0) + 1
                model_access.assign_model_values(
                    node,
                    {
                        "status": "ready",
                        "attempt_no": next_attempt,
                        "error_summary": None,
                        "duration_ms": None,
                        "output_envelope_json": None,
                        "started_at": None,
                        "ended_at": None,
                    },
                )
                changed = True
        if not changed:
            raise errors.WorkflowConflictError(
                _("plugin.workflow-orchestration.error.run_no_failed_nodes"),
            )

        model_access.assign_model_values(
            run,
            {
                "status": "recovering",
                "error_summary": None,
                "retry_count": int(model_access.first_attr(run, ("retry_count",), 0) or 0) + 1,
                "ended_at": None,
                "last_heartbeat_at": utc_now(),
            },
        )
        requested_event = executor.create_event_instance(
            "recovery_requested",
            {
                "run": run,
                "message": "manual retry requested",
                "payload_json": {"actor_type": self.actor_type, "actor_id": self.actor_id},
            },
        )
        if requested_event is not None:
            self.db.add(requested_event)
        final_status = executor.synchronize_run_status(run, node_runs)
        completed_event = executor.create_event_instance(
            "recovery_completed",
            {
                "run": run,
                "status_from": current_status,
                "status_to": final_status,
                "message": "manual retry prepared",
            },
        )
        if completed_event is not None:
            self.db.add(completed_event)
        await self.db.flush()
        return serializer.serialize_run(run, node_runs=node_runs)

    async def resume_run(self, run_id: int, checkpoint_id: int | None = None) -> dict[str, Any]:
        errors = _runtime("errors")
        executor = _runtime("executor")
        model_access = _runtime("model_access")
        serializer = _runtime("serializer")

        run = await self._get_run(run_id)
        current_status = str(model_access.first_attr(run, ("status",), "queued"))
        if current_status not in {"paused", "waiting_human", "waiting_approval", "waiting_input"}:
            raise errors.WorkflowConflictError(
                _("plugin.workflow-orchestration.error.run_not_resumable"),
            )

        node_runs = await self._list_node_runs(run_id)
        for node in node_runs:
            node_status = str(model_access.first_attr(node, ("status",), ""))
            if node_status in {"waiting_human", "waiting_approval", "waiting_input"}:
                model_access.assign_model_values(
                    node,
                    {
                        "status": "ready",
                        "started_at": None,
                        "ended_at": None,
                    },
                )

        resume_node_key = await self._resolve_checkpoint_node_key(checkpoint_id)
        model_access.assign_model_values(
            run,
            {
                "status": "running",
                "current_node_key": resume_node_key or model_access.first_attr(run, ("current_node_key",)),
                "ended_at": None,
                "last_heartbeat_at": utc_now(),
            },
        )
        event = executor.create_event_instance(
            "recovery_completed",
            {
                "run": run,
                "status_from": current_status,
                "status_to": "running",
                "message": "run resumed",
                "payload_json": {"checkpoint_id": checkpoint_id},
            },
        )
        if event is not None:
            self.db.add(event)
        await self.db.flush()
        return serializer.serialize_run(run, node_runs=node_runs)

    async def submit_waiting_action(self, run_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        errors = _runtime("errors")
        executor = _runtime("executor")
        model_access = _runtime("model_access")
        serializer = _runtime("serializer")

        run = await self._get_run(run_id)
        current_status = str(model_access.first_attr(run, ("status",), "queued"))
        if current_status not in WAITING_NODE_STATUSES:
            raise errors.WorkflowConflictError(
                _("plugin.workflow-orchestration.error.run_not_resumable"),
            )

        node_runs = await self._list_node_runs(run_id)
        target_node = await self._resolve_waiting_node(run, node_runs, payload)
        target_status = str(model_access.first_attr(target_node, ("status",), ""))
        normalized_payload = self._normalize_waiting_action_payload(payload)
        self._validate_waiting_action(errors, target_status, normalized_payload)

        model_access.assign_model_values(
            target_node,
            {
                "status": "ready",
                "input_envelope_json": self._apply_waiting_action_to_input_envelope(
                    model_access.first_attr(target_node, ("input_envelope_json", "input_payload"), {}) or {},
                    target_status,
                    normalized_payload,
                ),
                "metrics_json": self._apply_waiting_action_to_metrics(
                    model_access.first_attr(target_node, ("metrics_json",), {}) or {},
                    target_status,
                    normalized_payload,
                ),
                "error_summary": None,
                "started_at": None,
                "ended_at": None,
            },
        )

        next_status = self._next_run_status_after_waiting_action(node_runs)
        model_access.assign_model_values(
            run,
            {
                "status": next_status,
                "current_node_key": self._next_current_node_key(
                    node_runs,
                    next_status,
                    fallback=model_access.first_attr(run, ("current_node_key",)),
                ),
                "ended_at": None,
                "last_heartbeat_at": utc_now(),
            },
        )

        event = executor.create_event_instance(
            "recovery_completed",
            {
                "run": run,
                "node_run_id": model_access.first_attr(target_node, ("id",)),
                "status_from": current_status,
                "status_to": next_status,
                "message": "waiting action submitted",
                "payload_json": self._waiting_action_event_payload(
                    target_node,
                    target_status,
                    normalized_payload,
                ),
            },
        )
        if event is not None:
            self.db.add(event)
        await self.db.flush()
        return serializer.serialize_run(run, node_runs=node_runs)

    async def recover_run(self, run_id: int, checkpoint_id: int | None = None) -> dict[str, Any]:
        run = await self._get_run(run_id)
        status = str(_runtime("model_access").first_attr(run, ("status",), "queued"))
        if status in {"failed", "partially_completed"}:
            return await self.retry_run(run_id)
        return await self.resume_run(run_id, checkpoint_id=checkpoint_id)

    async def replay_run(self, run_id: int) -> dict[str, Any]:
        errors = _runtime("errors")
        model_access = _runtime("model_access")

        run = await self._get_run(run_id)
        workflow_id = model_access.first_attr(run, ("workflow_id", "tenant_workflow_id"))
        if not workflow_id:
            raise errors.WorkflowConflictError(
                _("plugin.workflow-orchestration.error.run_not_replayable"),
            )

        run_service = _service("run_service").RunService(
            self.db,
            self.tenant_id,
            actor_type=self.actor_type,
            actor_id=self.actor_id,
        )
        control_envelope = model_access.first_attr(run, ("control_envelope_json", "control_envelope"), {}) or {}
        return await run_service.create_run_from_workflow(
            int(workflow_id),
            {
                "trigger_source": "manual",
                "input_payload": model_access.first_attr(run, ("input_payload_json", "input_payload"), {}) or {},
                "parent_run_id": model_access.first_attr(run, ("id",)),
                "entrypoint": model_access.first_attr(run, ("entrypoint",)),
                "workflow_version_id": model_access.first_attr(run, ("workflow_version_id", "tenant_workflow_version_id")),
                "workflow_snapshot": control_envelope.get("workflow_snapshot"),
            },
        )

    async def sweep_timeout_runs(self, timeout_minutes: int = 30) -> dict[str, Any]:
        executor = _runtime("executor")
        model_access = _runtime("model_access")

        run_model = model_access.resolve_model("workflow_run")
        cutoff = utc_now() - timedelta(minutes=timeout_minutes)
        stmt = select(run_model).where(
            run_model.status.in_(["running", "recovering", "compensating"]),
        )
        if hasattr(run_model, "last_heartbeat_at"):
            stmt = stmt.where(
                run_model.last_heartbeat_at.is_not(None),
                run_model.last_heartbeat_at <= cutoff,
            )
        elif hasattr(run_model, "started_at"):
            stmt = stmt.where(run_model.started_at <= cutoff)
        elif hasattr(run_model, "updated_at"):
            stmt = stmt.where(run_model.updated_at <= cutoff)
        timed_out_runs = list((await self.db.execute(stmt)).scalars().all())

        affected_ids: list[int] = []
        for run in timed_out_runs:
            run_id = int(model_access.first_attr(run, ("id",), 0) or 0)
            if run_id <= 0:
                continue
            node_runs = await self._list_node_runs(run_id)
            for node in node_runs:
                if model_access.first_attr(node, ("status",)) == "running":
                    model_access.assign_model_values(
                        node,
                        {
                            "status": "failed_terminal",
                            "error_summary": _("plugin.workflow-orchestration.error.run_timeout"),
                            "ended_at": utc_now(),
                        },
                    )
            model_access.assign_model_values(
                run,
                {
                    "status": "failed",
                    "error_summary": _("plugin.workflow-orchestration.error.run_timeout"),
                    "ended_at": utc_now(),
                    "last_heartbeat_at": utc_now(),
                },
            )
            event = executor.create_event_instance(
                "run_timed_out",
                {
                    "run": run,
                    "status_from": "running",
                    "status_to": "failed",
                    "message": "run timed out",
                    "payload_json": {"timeout_minutes": timeout_minutes},
                },
            )
            if event is not None:
                self.db.add(event)
            affected_ids.append(run_id)
        await self.db.flush()
        return {
            "timeout_minutes": timeout_minutes,
            "processed_count": len(affected_ids),
            "run_ids": affected_ids,
        }

    async def dispatch_retryable_runs(self, limit: int = 20) -> dict[str, Any]:
        model_access = _runtime("model_access")

        run_model = model_access.resolve_model("workflow_run")
        stmt = (
            select(run_model)
            .where(run_model.status.in_(["failed", "partially_completed", "recovering"]))
            .order_by(getattr(run_model, "updated_at", run_model.id))
            .limit(limit)
        )
        if self.tenant_id is not None:
            stmt = stmt.where(run_model.tenant_id == self.tenant_id)

        processed_ids: list[int] = []
        for run in (await self.db.execute(stmt)).scalars().all():
            run_id = int(model_access.first_attr(run, ("id",), 0) or 0)
            if run_id <= 0:
                continue
            node_runs = await self._list_node_runs(run_id)
            if not any(
                model_access.first_attr(node, ("status",)) in {"failed_retryable", "retry_scheduled"}
                for node in node_runs
            ):
                continue
            try:
                await self.retry_run(run_id)
                processed_ids.append(run_id)
            except Exception as exc:
                logger.warning("Failed to auto-retry run {}: {}", run_id, exc)
        return {
            "processed_count": len(processed_ids),
            "run_ids": processed_ids,
        }

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

    async def _resolve_checkpoint_node_key(self, checkpoint_id: int | None) -> str | None:
        if checkpoint_id is None:
            return None
        model_access = _runtime("model_access")
        checkpoint_model = model_access.try_resolve_model("execution_checkpoint")
        if checkpoint_model is None:
            return None
        stmt = select(checkpoint_model).where(checkpoint_model.id == checkpoint_id)
        if self.tenant_id is not None and hasattr(checkpoint_model, "tenant_id"):
            stmt = stmt.where(checkpoint_model.tenant_id == self.tenant_id)
        checkpoint = (await self.db.execute(stmt)).scalar_one_or_none()
        if checkpoint is None:
            return None
        payload = model_access.first_attr(checkpoint, ("snapshot_json", "snapshot_payload"), {}) or {}
        if isinstance(payload, dict):
            node_key = payload.get("current_node_key") or payload.get("resume_node_key") or payload.get("node_key")
            if isinstance(node_key, str) and node_key.strip():
                return node_key.strip()
        node_run_id = model_access.first_attr(checkpoint, ("node_run_id", "workflow_node_run_id"))
        node_model = model_access.try_resolve_model("workflow_node_run")
        if node_model is None or node_run_id is None:
            return None
        node_stmt = select(node_model).where(node_model.id == node_run_id)
        node = (await self.db.execute(node_stmt)).scalar_one_or_none()
        if node is None:
            return None
        return model_access.first_attr(node, ("node_key",))

    async def _resolve_waiting_node(self, run: Any, node_runs: list[Any], payload: dict[str, Any]) -> Any:
        errors = _runtime("errors")
        model_access = _runtime("model_access")

        waiting_nodes = [
            node
            for node in node_runs
            if str(model_access.first_attr(node, ("status",), "")) in WAITING_NODE_STATUSES
        ]
        if not waiting_nodes:
            raise errors.WorkflowConflictError(
                _("plugin.workflow-orchestration.error.invalid_state"),
            )

        node_run_id = self._safe_int(payload.get("node_run_id"))
        node_key = self._clean_text(payload.get("node_key"))
        checkpoint_node_key = await self._resolve_checkpoint_node_key(self._safe_int(payload.get("checkpoint_id")))

        if node_run_id is not None:
            matched = [
                node
                for node in waiting_nodes
                if self._safe_int(model_access.first_attr(node, ("id",), 0)) == node_run_id
            ]
            if len(matched) == 1:
                return matched[0]
            raise errors.WorkflowConflictError(
                _("plugin.workflow-orchestration.error.invalid_state"),
            )

        selector_key = node_key or checkpoint_node_key
        if selector_key:
            matched = [
                node
                for node in waiting_nodes
                if str(model_access.first_attr(node, ("node_key",), "")).strip() == selector_key
            ]
            if len(matched) == 1:
                return matched[0]
            raise errors.WorkflowConflictError(
                _("plugin.workflow-orchestration.error.invalid_state"),
            )

        current_node_key = self._clean_text(model_access.first_attr(run, ("current_node_key",)))
        if current_node_key:
            matched = [
                node
                for node in waiting_nodes
                if str(model_access.first_attr(node, ("node_key",), "")).strip() == current_node_key
            ]
            if len(matched) == 1:
                return matched[0]

        if len(waiting_nodes) == 1:
            return waiting_nodes[0]

        raise errors.WorkflowConflictError(
            _("plugin.workflow-orchestration.error.invalid_state"),
        )

    def _normalize_waiting_action_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = self._clean_text(payload.get("action"))
        decision = payload.get("decision")
        approved = payload.get("approved")
        raw_input_payload = None
        for field_name in WAITING_INPUT_PAYLOAD_FIELDS:
            if field_name in payload:
                raw_input_payload = payload.get(field_name)
                break

        if action in {"approved", "accept"}:
            action = "approve"
        elif action in {"rejected", "deny"}:
            action = "reject"
        elif action in {"submit_input", "manual_submit"}:
            action = "submit"

        if isinstance(approved, bool):
            decision = "approved" if approved else "rejected"
            action = action or ("approve" if approved else "reject")
        elif isinstance(decision, bool):
            decision = "approved" if decision else "rejected"
            action = action or ("approve" if decision else "reject")
        elif isinstance(decision, str):
            decision = decision.strip() or None
            if decision and action is None:
                action = decision.lower()
        elif decision is not None:
            decision = str(decision)

        if action == "approve" and decision is None:
            decision = "approved"
        elif action == "reject" and decision is None:
            decision = "rejected"

        return {
            "action": action,
            "decision": decision,
            "comment": self._clean_text(payload.get("comment") or payload.get("note") or payload.get("reason")),
            "node_run_id": self._safe_int(payload.get("node_run_id")),
            "node_key": self._clean_text(payload.get("node_key")),
            "checkpoint_id": self._safe_int(payload.get("checkpoint_id")),
            "input_payload_present": raw_input_payload is not None,
            "input_payload_valid": raw_input_payload is None or isinstance(raw_input_payload, dict),
            "input_payload": self._normalize_dict(raw_input_payload),
            "submitted_at": utc_now().isoformat(),
        }

    def _validate_waiting_action(self, errors: Any, node_status: str, payload: dict[str, Any]) -> None:
        if node_status not in WAITING_NODE_STATUSES:
            raise errors.WorkflowConflictError(
                _("plugin.workflow-orchestration.error.invalid_state"),
            )
        if not payload["input_payload_valid"]:
            raise errors.WorkflowValidationError()
        if node_status == "waiting_input":
            if not payload["input_payload_present"]:
                raise errors.WorkflowValidationError()
            return
        if node_status == "waiting_approval":
            if payload["decision"] is None:
                raise errors.WorkflowValidationError()
            return
        if (
            payload["action"] is None
            and payload["decision"] is None
            and not payload["input_payload_present"]
            and payload["comment"] is None
        ):
            raise errors.WorkflowValidationError()

    def _apply_waiting_action_to_input_envelope(
        self,
        current_input: dict[str, Any],
        node_status: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        envelope = self._normalize_dict(current_input)
        action_record = self._waiting_action_record(payload)
        if node_status == "waiting_input":
            envelope.update(payload["input_payload"])
        elif payload["input_payload_present"]:
            envelope["submitted_input"] = payload["input_payload"]
        if payload["decision"] is not None and node_status in {"waiting_human", "waiting_approval"}:
            envelope["decision"] = payload["decision"]
        envelope["waiting_action"] = action_record
        return envelope

    def _apply_waiting_action_to_metrics(
        self,
        current_metrics: dict[str, Any],
        node_status: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        metrics = self._normalize_dict(current_metrics)
        metrics["waiting_action"] = {
            "node_status": node_status,
            "action": payload["action"],
            "decision": payload["decision"],
            "comment": payload["comment"],
            "submitted_at": payload["submitted_at"],
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
        }
        return metrics

    def _waiting_action_event_payload(self, node: Any, node_status: str, payload: dict[str, Any]) -> dict[str, Any]:
        model_access = _runtime("model_access")
        return {
            "node_run_id": model_access.first_attr(node, ("id",)),
            "node_key": model_access.first_attr(node, ("node_key",)),
            "node_status": node_status,
            "action": payload["action"],
            "decision": payload["decision"],
            "comment": payload["comment"],
            "checkpoint_id": payload["checkpoint_id"],
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
        }

    def _waiting_action_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        record = {
            "action": payload["action"],
            "decision": payload["decision"],
            "comment": payload["comment"],
            "submitted_at": payload["submitted_at"],
            "submitted_by": {
                "actor_type": self.actor_type,
                "actor_id": self.actor_id,
            },
        }
        if payload["checkpoint_id"] is not None:
            record["checkpoint_id"] = payload["checkpoint_id"]
        if payload["input_payload_present"]:
            record["input_payload"] = payload["input_payload"]
        return record

    def _next_run_status_after_waiting_action(self, node_runs: list[Any]) -> str:
        model_access = _runtime("model_access")
        statuses = [str(model_access.first_attr(node, ("status",), "")) for node in node_runs]
        for waiting_status in ("waiting_human", "waiting_approval", "waiting_input"):
            if waiting_status in statuses:
                return waiting_status
        return "running"

    def _next_current_node_key(self, node_runs: list[Any], next_status: str, *, fallback: Any = None) -> str | None:
        model_access = _runtime("model_access")
        if next_status in WAITING_NODE_STATUSES:
            for node in node_runs:
                if str(model_access.first_attr(node, ("status",), "")) == next_status:
                    return model_access.first_attr(node, ("node_key",))
            for waiting_status in ("waiting_human", "waiting_approval", "waiting_input"):
                for node in node_runs:
                    if str(model_access.first_attr(node, ("status",), "")) == waiting_status:
                        return model_access.first_attr(node, ("node_key",))
        for active_status in ("running", "ready", "pending", "waiting_human", "waiting_approval", "waiting_input"):
            for node in node_runs:
                if str(model_access.first_attr(node, ("status",), "")) == active_status:
                    return model_access.first_attr(node, ("node_key",))
        return self._clean_text(fallback)

    def _normalize_dict(self, value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    def _clean_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _safe_int(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
