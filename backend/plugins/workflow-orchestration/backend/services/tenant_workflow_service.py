from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any

from sqlalchemy import func, or_, select

from app.core.base_model import utc_now
from app.core.i18n import _
from app.core.logging import get_logger
from app.plugins.module_loader import load_plugin_module

PLUGIN_NAME = "workflow-orchestration"
logger = get_logger(__name__)


def _runtime(name: str):
    module = load_plugin_module(PLUGIN_NAME, f"runtime.{name}")
    if module is None:
        raise RuntimeError(f"Missing runtime module: {name}")
    return module


class TenantWorkflowService:
    def __init__(self, db: Any, tenant_id: int, ctx: Any | None = None) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.ctx = ctx

    async def get_builder_capabilities(self) -> dict[str, Any]:
        tenant_config: dict[str, Any] = {}
        plugin_config: dict[str, Any] = {}
        if self.ctx is not None:
            try:
                tenant_config = await self.ctx.get_tenant_config(self.tenant_id)
            except Exception as exc:
                logger.warning("Failed to load tenant builder config: {}", exc)
            try:
                plugin_config = await self.ctx.get_config()
            except Exception as exc:
                logger.warning("Failed to load plugin builder config: {}", exc)

        simple_builder_enabled = bool(tenant_config.get("simple_builder_enabled", True))
        template_editor_enabled = bool(tenant_config.get("template_editor_enabled", True))
        agentic_builder_enabled = bool(
            tenant_config.get(
                "agentic_builder_enabled",
                plugin_config.get("tenant_agentic_enabled_default", False),
            )
        )
        max_agentic_steps = int(tenant_config.get("max_agentic_steps") or 8)
        allowed_modes = ["deterministic", "hybrid"]
        if agentic_builder_enabled:
            allowed_modes.append("agentic")

        payload = {
            "simple_builder_enabled": simple_builder_enabled,
            "template_editor_enabled": template_editor_enabled,
            "agentic_builder_enabled": agentic_builder_enabled,
            "max_agentic_steps": max_agentic_steps,
            "allowed_modes": allowed_modes,
            "can_copy_from_template": True,
            "can_create_workflow": simple_builder_enabled or template_editor_enabled,
            "can_publish_workflow": True,
        }
        payload["items"] = self._build_builder_capability_items(payload)
        return payload

    async def list_workflows(self, query_params: Any) -> dict[str, Any]:
        model_access = _runtime("model_access")
        query = _runtime("query")

        workflow_model = model_access.resolve_model("tenant_workflow")
        base_filters = [workflow_model.tenant_id == self.tenant_id]
        page, page_size = query.parse_page(query_params)
        allowed_fields = model_access.model_field_names(workflow_model)

        list_stmt = select(workflow_model).where(*base_filters)
        count_stmt = select(func.count()).select_from(workflow_model).where(*base_filters)

        parsed_filters = query.parse_filters(query_params, allowed_fields)
        list_stmt = query.apply_filters(list_stmt, workflow_model, parsed_filters)
        count_stmt = query.apply_filters(count_stmt, workflow_model, parsed_filters)
        list_stmt, count_stmt = self._apply_builder_mode_filter(
            list_stmt,
            count_stmt,
            workflow_model,
            query_params,
        )
        list_stmt = query.apply_sort(
            list_stmt,
            workflow_model,
            query.parse_sort(query_params, allowed_fields, default_sort="-updated_at"),
        )

        total = (await self.db.execute(count_stmt)).scalar() or 0
        list_stmt = list_stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(list_stmt)
        items = [await self.serialize_workflow_summary(item) for item in result.scalars().all()]
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_workflow_detail(self, workflow_id: int) -> dict[str, Any]:
        workflow = await self._get_workflow(workflow_id)
        graph = _runtime("graph")
        model_access = _runtime("model_access")

        payload = await self.serialize_workflow_summary(workflow)
        versions = await self.list_workflow_versions(workflow_id)
        draft_snapshot = graph.extract_snapshot(workflow)
        published_snapshot = await self._resolve_published_snapshot(workflow)
        payload.update(
            {
                "builder_capabilities": (await self.get_builder_capabilities()).get("items", []),
                "versions": versions,
                "workflow_json": draft_snapshot,
                "draft_snapshot": draft_snapshot,
                "published_snapshot": published_snapshot,
                "input_variables": self._extract_input_variables(draft_snapshot),
                "output_contracts": self._extract_output_contracts(draft_snapshot),
                "nodes": self._extract_nodes(draft_snapshot),
                "edges": self._extract_edges(draft_snapshot),
                "related_runs": await self._list_related_runs(workflow_id),
                "related_artifacts": await self._list_related_artifacts(workflow_id),
                "entrypoint": f"/tenant/plugins/{PLUGIN_NAME}/api/workflows/{workflow_id}/run",
                "published_version": self._pick_published_version(versions),
                "latest_version": versions[0]["version"] if versions else None,
                "activation_summary": self._build_activation_summary(workflow),
                "context_health_summary": self._build_context_health_summary(draft_snapshot),
                "policy_summary": self._build_policy_summary(draft_snapshot),
                "approval_summary": self._build_approval_summary(draft_snapshot),
                "notes": model_access.first_attr(workflow, ("description",)),
            }
        )
        return payload

    async def create_workflow(self, payload: dict[str, Any]) -> dict[str, Any]:
        errors = _runtime("errors")
        graph = _runtime("graph")
        model_access = _runtime("model_access")

        builder_capabilities = await self.get_builder_capabilities()
        if not builder_capabilities["can_create_workflow"]:
            raise errors.WorkflowPermissionError(
                _("plugin.workflow-orchestration.error.builder_disabled"),
            )

        name = str(payload.get("name") or "").strip()
        if not name:
            raise errors.WorkflowValidationError(
                _("plugin.workflow-orchestration.error.workflow_name_required"),
            )

        mode = str(payload.get("mode") or builder_capabilities["allowed_modes"][0]).strip()
        if mode not in builder_capabilities["allowed_modes"]:
            raise errors.WorkflowValidationError(
                _("plugin.workflow-orchestration.error.workflow_mode_not_allowed"),
            )

        workflow_model = model_access.resolve_model("tenant_workflow")
        source_template_id = self._safe_int(payload.get("source_template_id"))
        source_release_id = self._safe_int(payload.get("source_release_id"))
        is_simple_builder = bool(payload.get("is_simple_builder", source_template_id is None))
        snapshot = self._normalize_snapshot(payload.get("workflow_json") or payload.get("snapshot_json"))
        summary = graph.summarize_snapshot(snapshot)
        editable_level = (
            str(payload.get("editable_level") or "").strip()
            or ("managed_partial" if source_template_id else "tenant_simple")
        )

        instance = model_access.instantiate_model(
            workflow_model,
            {
                "tenant_id": self.tenant_id,
                "source_template_id": source_template_id,
                "source_release_id": source_release_id,
                "name": name,
                "description": payload.get("description"),
                "mode": mode,
                "status": payload.get("status") or "draft",
                "editable_level": editable_level,
                "is_simple_builder": is_simple_builder,
                "builder_surface": self._resolve_builder_surface(is_simple_builder),
                "workflow_json": snapshot,
                "summary_json": summary,
                "settings_json": self._normalize_mapping(payload.get("settings_json")),
                "metadata_json": self._normalize_mapping(payload.get("metadata_json")),
                "created_by": self._current_user_id(),
                "updated_by": self._current_user_id(),
            },
        )
        self.db.add(instance)
        await self.db.flush()
        return await self.serialize_workflow_summary(instance)

    async def copy_from_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        errors = _runtime("errors")
        model_access = _runtime("model_access")

        template_id = int(payload.get("template_id") or 0)
        if template_id <= 0:
            raise errors.WorkflowValidationError(
                _("plugin.workflow-orchestration.error.template_id_required"),
            )

        template_model = model_access.resolve_model("workflow_template")
        template_stmt = select(template_model).where(template_model.id == template_id)
        template = (await self.db.execute(template_stmt)).scalar_one_or_none()
        if template is None:
            raise errors.WorkflowNotFoundError(
                _("plugin.workflow-orchestration.error.template_not_found"),
            )

        snapshot = await self._resolve_template_snapshot(template)
        template_name = model_access.first_attr(template, ("name",), "workflow")
        name = str(payload.get("name") or f"{template_name} copy").strip()
        return await self.create_workflow(
            {
                "name": name,
                "description": payload.get("description") or model_access.first_attr(template, ("description",)),
                "mode": payload.get("mode") or model_access.first_attr(template, ("mode",), "deterministic"),
                "workflow_json": snapshot,
                "source_template_id": template_id,
                "source_release_id": model_access.first_attr(template, ("latest_release_id",)),
                "is_simple_builder": payload.get("is_simple_builder", True),
                "editable_level": payload.get("editable_level") or "managed_partial",
                "settings_json": payload.get("settings_json") or {},
                "metadata_json": payload.get("metadata_json") or {},
            }
        )

    async def update_workflow(self, workflow_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        errors = _runtime("errors")
        graph = _runtime("graph")
        model_access = _runtime("model_access")

        workflow = await self._get_workflow(workflow_id)
        editable_level = str(model_access.first_attr(workflow, ("editable_level",), "tenant_simple"))
        restricted_fields = {"workflow_json", "mode", "is_simple_builder"}
        if editable_level == "managed_locked" and restricted_fields.intersection(payload.keys()):
            raise errors.WorkflowConflictError(
                _("plugin.workflow-orchestration.error.workflow_locked"),
            )

        if "mode" in payload:
            builder_capabilities = await self.get_builder_capabilities()
            if str(payload["mode"]) not in builder_capabilities["allowed_modes"]:
                raise errors.WorkflowValidationError(
                    _("plugin.workflow-orchestration.error.workflow_mode_not_allowed"),
                )

        updates: dict[str, Any] = {}
        for key in ("name", "description", "mode", "status", "editable_level"):
            if key in payload:
                updates[key] = payload[key]
        if "workflow_json" in payload:
            snapshot = self._normalize_snapshot(payload.get("workflow_json"))
            updates["workflow_json"] = snapshot
            updates["summary_json"] = graph.summarize_snapshot(snapshot)
        if "settings_json" in payload:
            updates["settings_json"] = self._normalize_mapping(payload.get("settings_json"))
        if "metadata_json" in payload:
            updates["metadata_json"] = self._normalize_mapping(payload.get("metadata_json"))
        if "is_simple_builder" in payload:
            updates["is_simple_builder"] = bool(payload.get("is_simple_builder"))
            updates["builder_surface"] = self._resolve_builder_surface(bool(payload.get("is_simple_builder")))
        updates["updated_by"] = self._current_user_id()
        model_access.assign_model_values(workflow, updates)
        await self.db.flush()
        return await self.serialize_workflow_summary(workflow)

    async def publish_workflow(self, workflow_id: int) -> dict[str, Any]:
        errors = _runtime("errors")
        graph = _runtime("graph")
        model_access = _runtime("model_access")

        workflow = await self._get_workflow(workflow_id)
        snapshot = graph.extract_snapshot(workflow)
        if not snapshot:
            raise errors.WorkflowValidationError(
                _("plugin.workflow-orchestration.error.workflow_snapshot_missing"),
            )

        version = await self._create_workflow_version(workflow, snapshot)
        now = utc_now()
        model_access.assign_model_values(
            workflow,
            {
                "status": "published",
                "summary_json": graph.summarize_snapshot(snapshot),
                "latest_version_no": model_access.first_attr(version, ("version_no",), 0),
                "latest_version_id": model_access.first_attr(version, ("id",)),
                "active_version_id": model_access.first_attr(version, ("id",)),
                "published_at": now,
                "published_by": self._current_user_id(),
                "updated_by": self._current_user_id(),
            },
        )
        await self.db.flush()
        return await self.get_workflow_detail(workflow_id)

    async def list_workflow_versions(self, workflow_id: int) -> list[dict[str, Any]]:
        model_access = _runtime("model_access")
        serializer = _runtime("serializer")
        graph = _runtime("graph")

        version_model = model_access.try_resolve_model("tenant_workflow_version")
        if version_model is None:
            return []

        workflow = await self._get_workflow(workflow_id)
        active_version_id = model_access.first_attr(workflow, ("active_version_id",))
        stmt = (
            select(version_model)
            .where(version_model.workflow_id == workflow_id)
            .order_by(getattr(version_model, "version_no", version_model.id).desc())
        )
        result = await self.db.execute(stmt)
        versions: list[dict[str, Any]] = []
        for item in result.scalars().all():
            version_no = int(model_access.first_attr(item, ("version_no",), 0) or 0)
            snapshot = self._normalize_snapshot(model_access.first_attr(item, ("snapshot_json",), {}) or {})
            versions.append(
                {
                    "id": model_access.first_attr(item, ("id",)),
                    "workflow_id": model_access.first_attr(item, ("workflow_id", "tenant_workflow_id")),
                    "tenant_workflow_id": model_access.first_attr(item, ("workflow_id", "tenant_workflow_id")),
                    "version_no": version_no,
                    "version": f"v{version_no}",
                    "status": model_access.first_attr(item, ("status",), "published"),
                    "snapshot_version": model_access.first_attr(item, ("snapshot_version",), "1.0.0"),
                    "workflow_schema_version": model_access.first_attr(item, ("workflow_schema_version",), "1.0.0"),
                    "snapshot_hash": model_access.first_attr(item, ("snapshot_hash",)),
                    "snapshot_summary": graph.summarize_snapshot(snapshot),
                    "created_at": serializer.to_iso(model_access.first_attr(item, ("created_at",))),
                    "created_by": (
                        str(model_access.first_attr(item, ("created_by",)))
                        if model_access.first_attr(item, ("created_by",)) is not None
                        else None
                    ),
                    "published_at": serializer.to_iso(model_access.first_attr(item, ("published_at",))),
                    "published_by": model_access.first_attr(item, ("published_by",)),
                    "is_current": model_access.first_attr(item, ("id",)) == active_version_id,
                    "is_latest": bool(model_access.first_attr(item, ("is_latest",), False)),
                    "is_published": bool(model_access.first_attr(item, ("is_published",), False)),
                    "change_log": model_access.first_attr(item, ("change_summary", "release_notes")),
                }
            )
        return versions

    async def serialize_workflow_summary(self, workflow: Any) -> dict[str, Any]:
        model_access = _runtime("model_access")
        serializer = _runtime("serializer")

        payload = serializer.serialize_tenant_workflow(workflow)
        workflow_id = model_access.first_attr(workflow, ("id",))
        versions = await self.list_workflow_versions(int(workflow_id)) if workflow_id is not None else []
        run_metrics = await self._workflow_run_metrics(workflow_id)
        payload.update(
            {
                "source_template_name": await self._source_template_name(model_access.first_attr(workflow, ("source_template_id",))),
                "current_version": self._pick_published_version(versions),
                "latest_run_status": run_metrics["latest_run_status"],
                "last_run_at": run_metrics["last_run_at"],
                "risk_level": run_metrics["risk_level"] or payload.get("risk_level"),
                "pending_approvals": run_metrics["pending_approvals"],
                "run_count_7d": run_metrics["run_count_7d"],
                "success_rate_7d": run_metrics["success_rate_7d"],
                "owner_name": None,
                "can_edit": str(payload.get("editable_level") or "") != "managed_locked",
                "can_publish": True,
                "can_execute": payload.get("status") == "published" and payload.get("active_version_id") is not None,
            }
        )
        return payload

    async def _get_workflow(self, workflow_id: int) -> Any:
        errors = _runtime("errors")
        workflow_model = _runtime("model_access").resolve_model("tenant_workflow")
        stmt = select(workflow_model).where(
            workflow_model.id == workflow_id,
            workflow_model.tenant_id == self.tenant_id,
        )
        workflow = (await self.db.execute(stmt)).scalar_one_or_none()
        if workflow is None:
            raise errors.WorkflowNotFoundError(
                _("plugin.workflow-orchestration.error.workflow_not_found"),
            )
        return workflow

    async def _resolve_template_snapshot(self, template: Any) -> dict[str, Any]:
        model_access = _runtime("model_access")
        graph = _runtime("graph")

        version_model = model_access.try_resolve_model("workflow_template_version")
        if version_model is not None:
            template_id = model_access.first_attr(template, ("id",))
            template_field = None
            if hasattr(version_model, "workflow_template_id"):
                template_field = version_model.workflow_template_id
            elif hasattr(version_model, "template_id"):
                template_field = version_model.template_id
            if template_field is not None:
                stmt = select(version_model).where(template_field == template_id)
                if hasattr(version_model, "is_published"):
                    stmt = stmt.where(version_model.is_published.is_(True))
                elif hasattr(version_model, "status"):
                    stmt = stmt.where(version_model.status == "published")
                order_field = getattr(version_model, "version_no", getattr(version_model, "id"))
                stmt = stmt.order_by(order_field.desc()).limit(1)
                latest = (await self.db.execute(stmt)).scalar_one_or_none()
                if latest is not None:
                    snapshot = graph.extract_snapshot(latest)
                    if snapshot:
                        return snapshot
        return graph.extract_snapshot(template)

    async def _resolve_published_snapshot(self, workflow: Any) -> dict[str, Any]:
        model_access = _runtime("model_access")
        graph = _runtime("graph")
        version_model = model_access.try_resolve_model("tenant_workflow_version")
        if version_model is None:
            return {}
        version_id = model_access.first_attr(workflow, ("active_version_id", "latest_version_id"))
        if not version_id:
            return {}
        stmt = select(version_model).where(version_model.id == version_id)
        version = (await self.db.execute(stmt)).scalar_one_or_none()
        if version is None:
            return {}
        return graph.extract_snapshot(version)

    async def _create_workflow_version(self, workflow: Any, snapshot: dict[str, Any]) -> Any:
        model_access = _runtime("model_access")
        version_model = model_access.try_resolve_model("tenant_workflow_version")
        if version_model is None:
            raise _runtime("errors").WorkflowDependencyError(
                _("plugin.workflow-orchestration.error.runtime_dependency_missing"),
            )

        workflow_id = model_access.first_attr(workflow, ("id",))
        if workflow_id is None:
            raise _runtime("errors").WorkflowValidationError(
                _("plugin.workflow-orchestration.error.workflow_not_found"),
            )

        stmt = select(version_model).where(version_model.workflow_id == workflow_id)
        existing_versions = list((await self.db.execute(stmt)).scalars().all())
        for item in existing_versions:
            model_access.assign_model_values(item, {"is_latest": False, "is_published": False})

        next_version_no = await self._next_workflow_version_no(version_model, workflow_id)
        now = utc_now()
        instance = model_access.instantiate_model(
            version_model,
            {
                "workflow_id": workflow_id,
                "version_no": next_version_no,
                "status": "published",
                "source_template_version_id": None,
                "snapshot_version": str(snapshot.get("snapshot_version") or "1.0.0"),
                "workflow_schema_version": str(snapshot.get("workflow_schema_version") or "1.0.0"),
                "snapshot_hash": self._snapshot_hash(snapshot),
                "snapshot_json": snapshot,
                "change_summary": self._build_change_summary(workflow, next_version_no),
                "compiled_at": now,
                "compiled_by": self._current_user_id(),
                "published_at": now,
                "published_by": self._current_user_id(),
                "is_latest": True,
                "is_published": True,
                "created_by": self._current_user_id(),
                "updated_by": self._current_user_id(),
            },
        )
        self.db.add(instance)
        await self.db.flush()
        return instance

    async def _next_workflow_version_no(self, version_model: Any, workflow_id: int) -> int:
        if not hasattr(version_model, "version_no"):
            return 1
        stmt = select(func.max(version_model.version_no)).where(
            version_model.workflow_id == workflow_id,
        )
        current = (await self.db.execute(stmt)).scalar()
        return int(current or 0) + 1

    def _build_builder_capability_items(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "code": "tenant_simple_builder",
                "enabled": bool(payload.get("simple_builder_enabled")),
            },
            {
                "code": "tenant_template_editor",
                "enabled": bool(payload.get("template_editor_enabled")),
            },
            {
                "code": "agentic_builder",
                "enabled": bool(payload.get("agentic_builder_enabled")),
                "limit": int(payload.get("max_agentic_steps") or 0) or None,
            },
        ]

    async def _workflow_run_metrics(self, workflow_id: Any) -> dict[str, Any]:
        model_access = _runtime("model_access")
        run_model = model_access.try_resolve_model("workflow_run")
        if run_model is None or workflow_id is None:
            return {
                "latest_run_status": None,
                "last_run_at": None,
                "pending_approvals": 0,
                "run_count_7d": 0,
                "success_rate_7d": None,
                "risk_level": None,
            }

        stmt = select(run_model).where(run_model.workflow_id == workflow_id)
        runs = list((await self.db.execute(stmt)).scalars().all())
        if not runs:
            return {
                "latest_run_status": None,
                "last_run_at": None,
                "pending_approvals": 0,
                "run_count_7d": 0,
                "success_rate_7d": None,
                "risk_level": None,
            }

        latest_run = max(
            runs,
            key=lambda item: model_access.first_attr(item, ("updated_at", "started_at", "created_at")) or utc_now(),
        )
        cutoff = utc_now() - timedelta(days=7)
        recent_runs = [
            item
            for item in runs
            if (model_access.first_attr(item, ("created_at", "started_at", "updated_at")) or utc_now()) >= cutoff
        ]
        successful = sum(
            1
            for item in recent_runs
            if model_access.first_attr(item, ("status",)) in {"completed", "succeeded"}
        )
        pending_approvals = sum(
            1
            for item in runs
            if model_access.first_attr(item, ("status",)) in {"waiting_human", "waiting_approval", "waiting_input"}
        )
        latest_status = model_access.first_attr(latest_run, ("status",))
        risk_level = "high" if latest_status in {"failed", "partially_completed"} else "medium" if pending_approvals else "low"
        return {
            "latest_run_status": latest_status,
            "last_run_at": _runtime("serializer").to_iso(model_access.first_attr(latest_run, ("updated_at", "started_at", "created_at"))),
            "pending_approvals": pending_approvals,
            "run_count_7d": len(recent_runs),
            "success_rate_7d": round((successful / len(recent_runs)) * 100, 1) if recent_runs else None,
            "risk_level": risk_level,
        }

    async def _source_template_name(self, template_id: Any) -> str | None:
        if template_id is None:
            return None
        model_access = _runtime("model_access")
        template_model = model_access.try_resolve_model("workflow_template")
        if template_model is None:
            return None
        stmt = select(template_model).where(template_model.id == template_id)
        template = (await self.db.execute(stmt)).scalar_one_or_none()
        if template is None:
            return None
        return model_access.first_attr(template, ("name",))

    async def _list_related_runs(self, workflow_id: int, limit: int = 5) -> list[dict[str, Any]]:
        run_query_module = load_plugin_module(PLUGIN_NAME, "services.run_query_service")
        if run_query_module is None:
            return []
        model_access = _runtime("model_access")
        run_model = model_access.try_resolve_model("workflow_run")
        if run_model is None:
            return []
        stmt = (
            select(run_model)
            .where(run_model.workflow_id == workflow_id)
            .order_by(getattr(run_model, "updated_at", run_model.id).desc())
            .limit(limit)
        )
        runs = (await self.db.execute(stmt)).scalars().all()
        query_service = run_query_module.RunQueryService(self.db, self.tenant_id)
        items = []
        for run in runs:
            run_id = model_access.first_attr(run, ("id",))
            items.append(
                await query_service._serialize_run_record(
                    run,
                    node_runs=await query_service._list_node_runs(run_id),
                )
            )
        return items

    async def _list_related_artifacts(self, workflow_id: int, limit: int = 5) -> list[dict[str, Any]]:
        run_query_module = load_plugin_module(PLUGIN_NAME, "services.run_query_service")
        if run_query_module is None:
            return []
        model_access = _runtime("model_access")
        artifact_model = model_access.try_resolve_model("execution_artifact")
        if artifact_model is None:
            return []
        stmt = (
            select(artifact_model)
            .where(artifact_model.workflow_id == workflow_id)
            .order_by(getattr(artifact_model, "ready_at", getattr(artifact_model, "updated_at", artifact_model.id)).desc())
            .limit(limit)
        )
        if hasattr(artifact_model, "tenant_id"):
            stmt = stmt.where(artifact_model.tenant_id == self.tenant_id)
        artifacts = (await self.db.execute(stmt)).scalars().all()
        query_service = run_query_module.RunQueryService(self.db, self.tenant_id)
        return [await query_service._serialize_artifact_record(item) for item in artifacts]

    def _extract_input_variables(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        raw = snapshot.get("input_variables") or snapshot.get("inputs") or []
        return [item for item in raw if isinstance(item, dict)]

    def _extract_output_contracts(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        raw = snapshot.get("output_contracts") or snapshot.get("outputs") or []
        return [item for item in raw if isinstance(item, dict)]

    def _extract_nodes(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        raw_nodes = snapshot.get("nodes") or snapshot.get("workflow_nodes") or []
        nodes = []
        for item in raw_nodes:
            if not isinstance(item, dict):
                continue
            nodes.append(
                {
                    "id": str(item.get("node_key") or item.get("id") or item.get("key") or ""),
                    "name": item.get("title") or item.get("name") or item.get("node_key") or item.get("id") or "",
                    "type": item.get("node_type") or item.get("type") or "unknown",
                    "status": item.get("status"),
                }
            )
        return nodes

    def _extract_edges(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        raw_edges = snapshot.get("edges") or snapshot.get("workflow_edges") or []
        edges = []
        for item in raw_edges:
            if not isinstance(item, dict):
                continue
            edges.append(
                {
                    "source": item.get("source_node_key") or item.get("from") or item.get("source") or "",
                    "target": item.get("target_node_key") or item.get("to") or item.get("target") or "",
                    "label": item.get("label"),
                }
            )
        return edges

    def _pick_published_version(self, versions: list[dict[str, Any]]) -> str | None:
        for version in versions:
            if version.get("is_published") or version.get("status") == "published":
                return version.get("version")
        return versions[0]["version"] if versions else None

    def _build_activation_summary(self, workflow: Any) -> str:
        model_access = _runtime("model_access")
        status = model_access.first_attr(workflow, ("status",), "draft")
        active_version_id = model_access.first_attr(workflow, ("active_version_id",))
        if active_version_id:
            return f"Workflow is currently {status} with active version {active_version_id}."
        return f"Workflow is currently {status}."

    def _build_context_health_summary(self, snapshot: dict[str, Any]) -> str:
        node_count = len(snapshot.get("nodes") or snapshot.get("workflow_nodes") or [])
        edge_count = len(snapshot.get("edges") or snapshot.get("workflow_edges") or [])
        return f"{node_count} nodes and {edge_count} edges are available in the current snapshot."

    def _build_policy_summary(self, snapshot: dict[str, Any]) -> str:
        policies = snapshot.get("policy_summary") or snapshot.get("policy_json") or {}
        if isinstance(policies, dict) and policies:
            return ", ".join(str(key) for key in policies.keys())
        return "No explicit policy summary is available."

    def _build_approval_summary(self, snapshot: dict[str, Any]) -> str:
        approvals = [
            item
            for item in (snapshot.get("nodes") or snapshot.get("workflow_nodes") or [])
            if isinstance(item, dict) and (item.get("node_type") or item.get("type")) in {"approval", "human_review"}
        ]
        if not approvals:
            return "No approval node is declared."
        return f"{len(approvals)} approval-related nodes are configured."

    def _apply_builder_mode_filter(
        self,
        list_stmt: Any,
        count_stmt: Any,
        workflow_model: Any,
        query_params: Any,
    ) -> tuple[Any, Any]:
        raw = query_params.get("filter[type][in]") or query_params.get("filter[builder_mode][in]")
        if not raw:
            return list_stmt, count_stmt

        values = [item.strip() for item in str(raw).split(",") if item.strip()]
        clauses = []
        source_template_field = getattr(workflow_model, "source_template_id", None)
        simple_builder_field = getattr(workflow_model, "is_simple_builder", None)

        for value in values:
            if value == "copied_from_template" and source_template_field is not None:
                clauses.append(source_template_field.is_not(None))
            elif value == "tenant_simple_builder" and source_template_field is not None and simple_builder_field is not None:
                clauses.append(source_template_field.is_(None) & simple_builder_field.is_(True))
            elif value == "tenant_template_editor" and source_template_field is not None and simple_builder_field is not None:
                clauses.append(source_template_field.is_(None) & simple_builder_field.is_(False))

        if not clauses:
            return list_stmt, count_stmt

        predicate = or_(*clauses)
        list_stmt = list_stmt.where(predicate)
        count_stmt = count_stmt.where(predicate)
        return list_stmt, count_stmt

    def _current_user_id(self) -> int | None:
        if self.ctx is None or not hasattr(self.ctx, "get_current_user_id"):
            return None
        try:
            return self.ctx.get_current_user_id()
        except Exception:
            return None

    def _normalize_mapping(self, value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    def _normalize_snapshot(self, value: Any) -> dict[str, Any]:
        snapshot = dict(value) if isinstance(value, dict) else {}
        snapshot.setdefault("nodes", list(snapshot.get("nodes") or []))
        snapshot.setdefault("edges", list(snapshot.get("edges") or []))
        return snapshot

    def _resolve_builder_surface(self, is_simple_builder: bool) -> str:
        return "tenant_simple_builder" if is_simple_builder else "tenant_template_editor"

    def _snapshot_hash(self, snapshot: dict[str, Any]) -> str:
        rendered = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(rendered.encode("utf-8")).hexdigest()

    def _build_change_summary(self, workflow: Any, version_no: int) -> str:
        name = _runtime("model_access").first_attr(workflow, ("name",), "workflow")
        return f"Published {name} as v{version_no}"

    def _safe_int(self, value: Any) -> int | None:
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            return None
        return numeric if numeric > 0 else None
