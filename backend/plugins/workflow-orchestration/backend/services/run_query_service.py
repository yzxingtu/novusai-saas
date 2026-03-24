from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.core.i18n import _
from app.core.logging import get_logger
from app.plugins.module_loader import load_plugin_module
from ._data_scope import (
    apply_artifact_data_scope,
    apply_model_scope,
    apply_run_data_scope,
    apply_run_related_scope,
    apply_tenant_workflow_scope,
)

PLUGIN_NAME = "workflow-orchestration"
logger = get_logger(__name__)


def _runtime(name: str):
    module = load_plugin_module(PLUGIN_NAME, f"runtime.{name}")
    if module is None:
        raise RuntimeError(f"Missing runtime module: {name}")
    return module


class RunQueryService:
    def __init__(self, db: Any, tenant_id: int | None = None) -> None:
        self.db = db
        self.tenant_id = tenant_id

    def _apply_run_scope(self, stmt: Any, run_model: Any, model_access: Any) -> Any:
        workflow_model = model_access.try_resolve_model("tenant_workflow")
        return apply_run_data_scope(
            stmt,
            run_model,
            tenant_id=self.tenant_id,
            workflow_model=workflow_model,
        )

    def _apply_artifact_scope(self, stmt: Any, artifact_model: Any, model_access: Any) -> Any:
        workflow_model = model_access.try_resolve_model("tenant_workflow")
        run_model = model_access.try_resolve_model("workflow_run")
        return apply_artifact_data_scope(
            stmt,
            artifact_model,
            run_model,
            tenant_id=self.tenant_id,
            workflow_model=workflow_model,
        )

    async def list_runs(self, query_params: Any) -> dict[str, Any]:
        model_access = _runtime("model_access")
        query = _runtime("query")

        run_model = model_access.resolve_model("workflow_run")
        base_filters = []
        if self.tenant_id is not None:
            base_filters.append(run_model.tenant_id == self.tenant_id)

        page, page_size = query.parse_page(query_params)
        allowed_fields = model_access.model_field_names(run_model)

        list_stmt = self._apply_run_scope(
            select(run_model).where(*base_filters),
            run_model,
            model_access,
        )
        count_stmt = self._apply_run_scope(
            select(func.count()).select_from(run_model).where(*base_filters),
            run_model,
            model_access,
        )

        parsed_filters = query.parse_filters(query_params, allowed_fields)
        list_stmt = query.apply_filters(list_stmt, run_model, parsed_filters)
        count_stmt = query.apply_filters(count_stmt, run_model, parsed_filters)
        list_stmt = query.apply_sort(
            list_stmt,
            run_model,
            query.parse_sort(query_params, allowed_fields, default_sort="-updated_at"),
        )

        total = (await self.db.execute(count_stmt)).scalar() or 0
        list_stmt = list_stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(list_stmt)
        runs = result.scalars().all()

        items = []
        for run in runs:
            run_id = model_access.first_attr(run, ("id",))
            items.append(
                await self._serialize_run_record(
                    run,
                    node_runs=await self._list_node_runs(run_id),
                )
            )

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_run_detail(self, run_id: int) -> dict[str, Any]:
        errors = _runtime("errors")
        graph = _runtime("graph")
        model_access = _runtime("model_access")
        serializer = _runtime("serializer")

        run_model = model_access.resolve_model("workflow_run")
        stmt = self._apply_run_scope(
            select(run_model).where(run_model.id == run_id),
            run_model,
            model_access,
        )
        run = (await self.db.execute(stmt)).scalar_one_or_none()
        if run is None:
            raise errors.WorkflowNotFoundError(
                _("plugin.workflow-orchestration.error.run_not_found"),
            )

        node_runs = await self._list_node_runs(run_id)
        checkpoints = await self._list_checkpoints(run_id)
        events = await self._list_events(run_id)
        artifacts = await self._list_artifacts(run_id)

        workflow_snapshot = await self._resolve_run_snapshot(run)
        execution_graph = graph.build_graph(workflow_snapshot) if workflow_snapshot else {
            "nodes": [],
            "edges": [],
            "root_node_keys": [],
        }

        return {
            "run": await self._serialize_run_record(run, node_runs=node_runs, artifacts=artifacts),
            "node_runs": [serializer.serialize_node_run(item) for item in node_runs],
            "checkpoints": [serializer.serialize_checkpoint(item) for item in checkpoints],
            "events": [serializer.serialize_event(item) for item in events],
            "artifacts": [await self._serialize_artifact_record(item) for item in artifacts],
            "execution_graph": execution_graph,
        }

    async def get_tenant_run_detail(self, run_id: int) -> dict[str, Any]:
        detail = await self.get_run_detail(run_id)
        run_payload = dict(detail["run"])
        run_payload["node_runs"] = detail["node_runs"]
        run_payload["artifacts"] = detail["artifacts"]
        run_payload["approvals"] = self._build_approvals_from_node_runs(detail["node_runs"])
        run_payload["recovery_events"] = detail["events"]
        run_payload["events"] = detail["events"]
        run_payload["checkpoints"] = detail["checkpoints"]
        run_payload["execution_graph"] = detail["execution_graph"]
        run_payload["contract_summary"] = self._build_run_contract_summary(run_payload)
        run_payload["snapshot_version"] = (
            run_payload.get("snapshot_version")
            or run_payload.get("mode")
            or "1.0.0"
        )
        run_payload["host_approval_path"] = None
        return run_payload

    async def get_tenant_home(self, builder_capabilities: dict[str, Any]) -> dict[str, Any]:
        stats = {
            "total_runs": await self._count_runs(),
            "running_runs": await self._count_runs({"status": ["running", "recovering", "compensating"]}),
            "waiting_approval_runs": await self._count_runs({"status": ["waiting_human", "waiting_approval", "waiting_input", "paused"]}),
            "failed_runs": await self._count_runs({"status": ["failed", "partially_completed"]}),
            "published_workflows": await self._count_workflows({"status": ["published"]}),
            "ready_artifacts": await self._count_artifacts({"status": ["ready"]}),
            "approval_todo": await self._count_runs({"status": ["waiting_human", "waiting_approval"]}),
            "recovery_todo": await self._count_runs({"status": ["failed", "partially_completed"]}),
            "artifact_review_todo": await self._count_artifacts({"status": ["ready"]}),
            "context_fix_todo": 0,
            "activation_todo": 0,
            "quota_warning_todo": 0,
        }

        recent_runs = []
        for run in await self._recent_runs():
            recent_runs.append(await self._serialize_run_record(run))

        recent_artifacts = [
            await self._serialize_artifact_record(artifact)
            for artifact in await self._recent_artifacts()
        ]

        return {
            "summary": {
                "pending_approvals": stats["approval_todo"],
                "failed_runs": stats["failed_runs"],
                "pending_artifacts": stats["artifact_review_todo"],
                "active_workflows": stats["published_workflows"],
                "running_now": stats["running_runs"],
                "quota_warnings": stats["quota_warning_todo"],
            },
            "stats": [],
            "todos": self._build_home_todos(stats),
            "alerts": self._build_home_alerts(stats),
            "builder_capabilities": list(builder_capabilities.get("items") or []),
            "highlighted_workflows": await self._highlighted_workflows(limit=4),
            "latest_runs": recent_runs,
            "latest_artifacts": recent_artifacts,
        }

    async def _list_node_runs(self, run_id: int) -> list[Any]:
        model_access = _runtime("model_access")
        node_model = model_access.try_resolve_model("workflow_node_run")
        if node_model is None:
            return []
        stmt = (
            select(node_model)
            .where(node_model.run_id == run_id)
            .order_by(getattr(node_model, "created_at", node_model.id))
        )
        run_model = model_access.try_resolve_model("workflow_run")
        workflow_model = model_access.try_resolve_model("tenant_workflow")
        if run_model is not None:
            stmt = apply_run_related_scope(
                stmt,
                node_model.run_id,
                run_model,
                tenant_id=self.tenant_id,
                workflow_model=workflow_model,
            )
        return list((await self.db.execute(stmt)).scalars().all())

    async def _list_checkpoints(self, run_id: int) -> list[Any]:
        model_access = _runtime("model_access")
        checkpoint_model = model_access.try_resolve_model("execution_checkpoint")
        if checkpoint_model is None:
            return []
        stmt = (
            select(checkpoint_model)
            .where(checkpoint_model.run_id == run_id)
            .order_by(getattr(checkpoint_model, "created_at", checkpoint_model.id).desc())
        )
        run_model = model_access.try_resolve_model("workflow_run")
        workflow_model = model_access.try_resolve_model("tenant_workflow")
        if run_model is not None:
            stmt = apply_run_related_scope(
                stmt,
                checkpoint_model.run_id,
                run_model,
                tenant_id=self.tenant_id,
                workflow_model=workflow_model,
            )
        return list((await self.db.execute(stmt)).scalars().all())

    async def _list_events(self, run_id: int) -> list[Any]:
        model_access = _runtime("model_access")
        event_model = model_access.try_resolve_model("execution_event")
        if event_model is None:
            return []
        stmt = (
            select(event_model)
            .where(event_model.run_id == run_id)
            .order_by(getattr(event_model, "occurred_at", getattr(event_model, "created_at", event_model.id)), event_model.id)
        )
        run_model = model_access.try_resolve_model("workflow_run")
        workflow_model = model_access.try_resolve_model("tenant_workflow")
        if run_model is not None:
            stmt = apply_run_related_scope(
                stmt,
                event_model.run_id,
                run_model,
                tenant_id=self.tenant_id,
                workflow_model=workflow_model,
            )
        return list((await self.db.execute(stmt)).scalars().all())

    async def _list_artifacts(self, run_id: int) -> list[Any]:
        model_access = _runtime("model_access")
        artifact_model = model_access.try_resolve_model("execution_artifact")
        if artifact_model is None:
            return []
        stmt = (
            select(artifact_model)
            .where(artifact_model.run_id == run_id)
            .order_by(
                getattr(
                    artifact_model,
                    "ready_at",
                    getattr(artifact_model, "created_at", artifact_model.id),
                ).desc(),
                artifact_model.id.desc(),
            )
        )
        stmt = self._apply_artifact_scope(stmt, artifact_model, model_access)
        return list((await self.db.execute(stmt)).scalars().all())

    async def _resolve_run_snapshot(self, run: Any) -> dict[str, Any]:
        graph = _runtime("graph")
        model_access = _runtime("model_access")

        direct_snapshot = graph.extract_snapshot(run)
        if direct_snapshot:
            return direct_snapshot

        workflow_version_id = model_access.first_attr(run, ("workflow_version_id",))
        version_model = model_access.try_resolve_model("tenant_workflow_version")
        workflow_model = model_access.try_resolve_model("tenant_workflow")
        if workflow_version_id and version_model is not None and workflow_model is not None:
            stmt = apply_tenant_workflow_scope(
                select(version_model).where(version_model.id == workflow_version_id),
                workflow_model,
                self.tenant_id,
                workflow_id_column=version_model.workflow_id,
            )
            version = (await self.db.execute(stmt)).scalar_one_or_none()
            if version is not None:
                snapshot = graph.extract_snapshot(version)
                if snapshot:
                    return snapshot

        workflow_id = model_access.first_attr(run, ("workflow_id", "tenant_workflow_id"))
        if workflow_id:
            workflow_model = model_access.try_resolve_model("tenant_workflow")
            if workflow_model is not None:
                stmt = select(workflow_model).where(workflow_model.id == workflow_id)
                stmt = apply_tenant_workflow_scope(stmt, workflow_model, self.tenant_id)
                workflow = (await self.db.execute(stmt)).scalar_one_or_none()
                if workflow is not None:
                    active_version_id = model_access.first_attr(
                        workflow,
                        ("active_version_id", "latest_version_id"),
                    )
                    if active_version_id and version_model is not None:
                        version_stmt = apply_tenant_workflow_scope(
                            select(version_model).where(version_model.id == active_version_id),
                            workflow_model,
                            self.tenant_id,
                            workflow_id_column=version_model.workflow_id,
                        )
                        version = (await self.db.execute(version_stmt)).scalar_one_or_none()
                        if version is not None:
                            snapshot = graph.extract_snapshot(version)
                            if snapshot:
                                return snapshot
                    return graph.extract_snapshot(workflow)
        return {}

    async def _count_runs(self, criteria: dict[str, list[str]] | None = None) -> int:
        model_access = _runtime("model_access")
        run_model = model_access.try_resolve_model("workflow_run")
        if run_model is None:
            return 0
        stmt = self._apply_run_scope(
            select(func.count()).select_from(run_model),
            run_model,
            model_access,
        )
        for field, values in (criteria or {}).items():
            if hasattr(run_model, field):
                stmt = stmt.where(getattr(run_model, field).in_(values))
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def _count_workflows(self, criteria: dict[str, list[str]] | None = None) -> int:
        model_access = _runtime("model_access")
        workflow_model = model_access.try_resolve_model("tenant_workflow")
        if workflow_model is None or self.tenant_id is None:
            return 0
        stmt = apply_tenant_workflow_scope(
            select(func.count()).select_from(workflow_model).where(workflow_model.tenant_id == self.tenant_id),
            workflow_model,
            self.tenant_id,
        )
        for field, values in (criteria or {}).items():
            if hasattr(workflow_model, field):
                stmt = stmt.where(getattr(workflow_model, field).in_(values))
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def _count_artifacts(self, criteria: dict[str, list[str]] | None = None) -> int:
        model_access = _runtime("model_access")
        artifact_model = model_access.try_resolve_model("execution_artifact")
        if artifact_model is None:
            return 0
        stmt = self._apply_artifact_scope(
            select(func.count()).select_from(artifact_model),
            artifact_model,
            model_access,
        )
        for field, values in (criteria or {}).items():
            if hasattr(artifact_model, field):
                stmt = stmt.where(getattr(artifact_model, field).in_(values))
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def _recent_runs(self) -> list[Any]:
        model_access = _runtime("model_access")
        run_model = model_access.try_resolve_model("workflow_run")
        if run_model is None:
            return []
        stmt = self._apply_run_scope(select(run_model), run_model, model_access)
        stmt = stmt.order_by(getattr(run_model, "updated_at", run_model.id).desc()).limit(5)
        return list((await self.db.execute(stmt)).scalars().all())

    async def _recent_artifacts(self) -> list[Any]:
        model_access = _runtime("model_access")
        artifact_model = model_access.try_resolve_model("execution_artifact")
        if artifact_model is None:
            return []
        stmt = select(artifact_model)
        stmt = self._apply_artifact_scope(stmt, artifact_model, model_access)
        stmt = stmt.order_by(
            getattr(
                artifact_model,
                "ready_at",
                getattr(artifact_model, "updated_at", artifact_model.id),
            ).desc(),
        ).limit(5)
        return list((await self.db.execute(stmt)).scalars().all())

    async def _serialize_run_record(
        self,
        run: Any,
        *,
        node_runs: list[Any] | None = None,
        artifacts: list[Any] | None = None,
    ) -> dict[str, Any]:
        model_access = _runtime("model_access")
        serializer = _runtime("serializer")

        run_id = model_access.first_attr(run, ("id",))
        node_runs = node_runs or []
        artifacts = artifacts if artifacts is not None else await self._list_artifacts(run_id)
        payload = serializer.serialize_run(run, node_runs=node_runs)
        workflow_name = await self._resolve_workflow_name(
            model_access.first_attr(run, ("workflow_id", "tenant_workflow_id")),
        )
        workflow_name = workflow_name or model_access.first_attr(run, ("workflow_name", "template_name"))
        payload.update(
            {
                "workflow_name": workflow_name,
                "template_name": workflow_name,
                "artifact_count": len(artifacts),
                "current_node_name": self._resolve_current_node_name(payload.get("current_node_key"), node_runs),
                "risk_level": self._derive_run_risk_level(run, node_runs),
            }
        )
        return payload

    async def _serialize_artifact_record(self, artifact: Any) -> dict[str, Any]:
        model_access = _runtime("model_access")
        serializer = _runtime("serializer")

        payload = serializer.serialize_artifact(artifact)
        run_id = model_access.first_attr(artifact, ("run_id", "workflow_run_id"))
        node_run_id = model_access.first_attr(artifact, ("node_run_id", "workflow_node_run_id"))
        workflow_name = None
        run_name = None
        source_node_name = None

        run_model = model_access.try_resolve_model("workflow_run")
        workflow_model = model_access.try_resolve_model("tenant_workflow")
        if run_model is not None and run_id is not None:
            run_stmt = apply_run_data_scope(
                select(run_model).where(run_model.id == run_id),
                run_model,
                tenant_id=self.tenant_id,
                workflow_model=workflow_model,
            )
            run = (await self.db.execute(run_stmt)).scalar_one_or_none()
            if run is not None:
                workflow_name = await self._resolve_workflow_name(
                    model_access.first_attr(run, ("workflow_id", "tenant_workflow_id")),
                )
                run_name = serializer.serialize_run(run).get("name")

        node_model = model_access.try_resolve_model("workflow_node_run")
        if node_model is not None and node_run_id is not None and run_model is not None:
            node_stmt = select(node_model).where(node_model.id == node_run_id)
            node_stmt = apply_run_related_scope(
                node_stmt,
                node_model.run_id,
                run_model,
                tenant_id=self.tenant_id,
                workflow_model=workflow_model,
            )
            node_run = (await self.db.execute(node_stmt)).scalar_one_or_none()
            if node_run is not None:
                source_node_name = model_access.first_attr(
                    node_run,
                    ("node_label", "node_name", "node_key"),
                )

        payload.update(
            {
                "workflow_name": workflow_name,
                "run_name": run_name,
                "source_node_name": source_node_name,
                "download_filename": payload.get("download_filename") or f"{payload.get('name') or payload.get('title') or 'artifact'}.bin",
                "feedback": [payload["feedback_summary"]] if payload.get("feedback_summary") else [],
            }
        )
        return payload

    async def _resolve_workflow_name(self, workflow_id: Any) -> str | None:
        if workflow_id is None:
            return None
        model_access = _runtime("model_access")
        workflow_model = model_access.try_resolve_model("tenant_workflow")
        if workflow_model is None:
            return None
        stmt = apply_tenant_workflow_scope(
            select(workflow_model).where(workflow_model.id == workflow_id),
            workflow_model,
            self.tenant_id,
        )
        workflow = (await self.db.execute(stmt)).scalar_one_or_none()
        if workflow is None:
            return None
        return model_access.first_attr(workflow, ("name",))

    def _resolve_current_node_name(self, current_node_key: Any, node_runs: list[Any]) -> str | None:
        model_access = _runtime("model_access")
        for node_run in node_runs:
            if model_access.first_attr(node_run, ("node_key",)) == current_node_key:
                return model_access.first_attr(node_run, ("node_label", "node_name", "node_key"))
        return current_node_key if isinstance(current_node_key, str) else None

    def _derive_run_risk_level(self, run: Any, node_runs: list[Any]) -> str | None:
        model_access = _runtime("model_access")
        risk_snapshot = model_access.first_attr(run, ("risk_snapshot_json", "risk_snapshot"), {}) or {}
        explicit = None
        if isinstance(risk_snapshot, dict):
            explicit = risk_snapshot.get("level") or risk_snapshot.get("risk_level")
        explicit = explicit or model_access.first_attr(run, ("risk_level",))
        if explicit:
            return explicit
        if any(model_access.first_attr(node, ("status",)) == "failed_terminal" for node in node_runs):
            return "high"
        if any(
            model_access.first_attr(node, ("status",)) in {"waiting_human", "waiting_approval", "waiting_input"}
            for node in node_runs
        ):
            return "medium"
        return "low" if node_runs else None

    def _build_approvals_from_node_runs(self, node_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        approvals = []
        for node_run in node_runs:
            status = node_run.get("status")
            if status not in {"waiting_human", "waiting_approval", "waiting_input"}:
                continue
            approvals.append(
                {
                    "id": node_run.get("id"),
                    "title": node_run.get("node_name") or node_run.get("node_key") or "approval",
                    "status": status,
                    "approver_name": None,
                    "due_at": None,
                    "detail_path": None,
                }
            )
        return approvals

    def _build_run_contract_summary(self, run_payload: dict[str, Any]) -> str:
        pieces = []
        if run_payload.get("workflow_name"):
            pieces.append(str(run_payload["workflow_name"]))
        if run_payload.get("trigger_source"):
            pieces.append(str(run_payload["trigger_source"]))
        if run_payload.get("mode"):
            pieces.append(str(run_payload["mode"]))
        return " / ".join(pieces) if pieces else "workflow execution"

    def _build_home_todos(self, stats: dict[str, Any]) -> list[dict[str, Any]]:
        todos = []
        todo_specs = (
            ("approval_todo", "approval_todo", "high", "runs"),
            ("recovery_todo", "recovery_todo", "high", "runs"),
            ("artifact_review_todo", "artifact_review_todo", "medium", "artifacts"),
            ("context_fix_todo", "context_fix_todo", "medium", "workflows"),
            ("activation_todo", "activation_todo", "medium", "workflows"),
            ("quota_warning_todo", "quota_warning_todo", "medium", "home"),
        )
        for code, category, severity, path in todo_specs:
            count = int(stats.get(code, 0) or 0)
            if count <= 0:
                continue
            todos.append(
                {
                    "id": code,
                    "category": category,
                    "title": f"{count} {category.replace('_', ' ')}",
                    "summary": f"{count} items require attention.",
                    "severity": severity,
                    "action_label": "Open",
                    "target_path": path,
                }
            )
        return todos

    def _build_home_alerts(self, stats: dict[str, Any]) -> list[dict[str, Any]]:
        alerts = []
        failed_runs = int(stats.get("failed_runs", 0) or 0)
        if failed_runs > 0:
            alerts.append(
                {
                    "id": "failed_runs",
                    "level": "high",
                    "title": "Failed runs detected",
                    "summary": f"{failed_runs} runs need recovery.",
                    "target_path": "runs",
                }
            )
        waiting_runs = int(stats.get("waiting_approval_runs", 0) or 0)
        if waiting_runs > 0:
            alerts.append(
                {
                    "id": "waiting_approval_runs",
                    "level": "medium",
                    "title": "Approvals are waiting",
                    "summary": f"{waiting_runs} runs are blocked by human actions.",
                    "target_path": "runs",
                }
            )
        return alerts

    async def _highlighted_workflows(self, limit: int = 4) -> list[dict[str, Any]]:
        model_access = _runtime("model_access")
        workflow_model = model_access.try_resolve_model("tenant_workflow")
        if workflow_model is None or self.tenant_id is None:
            return []
        stmt = (
            select(workflow_model)
            .where(workflow_model.tenant_id == self.tenant_id)
            .order_by(getattr(workflow_model, "updated_at", workflow_model.id).desc())
            .limit(limit)
        )
        stmt = apply_tenant_workflow_scope(stmt, workflow_model, self.tenant_id)
        workflows = (await self.db.execute(stmt)).scalars().all()
        workflow_service_module = load_plugin_module(PLUGIN_NAME, "services.tenant_workflow_service")
        if workflow_service_module is None:
            return []
        workflow_service = workflow_service_module.TenantWorkflowService(self.db, self.tenant_id)
        items = []
        for workflow in workflows:
            items.append(await workflow_service.serialize_workflow_summary(workflow))
        return items
