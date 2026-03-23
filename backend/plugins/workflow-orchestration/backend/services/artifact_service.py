from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select

from app.core.base_model import utc_now
from app.core.i18n import _
from app.core.logging import get_logger
from app.plugins.module_loader import load_plugin_module

PLUGIN_NAME = "workflow-orchestration"
logger = get_logger(__name__)
_MISSING = object()


def _runtime(name: str):
    module = load_plugin_module(PLUGIN_NAME, f"runtime.{name}")
    if module is None:
        raise RuntimeError(f"Missing runtime module: {name}")
    return module


class ArtifactService:
    def __init__(self, db: Any, tenant_id: int | None = None) -> None:
        self.db = db
        self.tenant_id = tenant_id

    async def list_artifacts(self, query_params: Any) -> dict[str, Any]:
        model_access = _runtime("model_access")
        query = _runtime("query")

        artifact_model = model_access.resolve_model("execution_artifact")
        page, page_size = query.parse_page(query_params)
        allowed_fields = model_access.model_field_names(artifact_model)

        list_stmt = select(artifact_model)
        count_stmt = select(func.count()).select_from(artifact_model)
        list_stmt, count_stmt = self._apply_tenant_scope(list_stmt, count_stmt, artifact_model)

        parsed_filters = query.parse_filters(query_params, allowed_fields)
        list_stmt = query.apply_filters(list_stmt, artifact_model, parsed_filters)
        count_stmt = query.apply_filters(count_stmt, artifact_model, parsed_filters)
        list_stmt = query.apply_sort(
            list_stmt,
            artifact_model,
            query.parse_sort(query_params, allowed_fields, default_sort="-updated_at"),
        )

        total = (await self.db.execute(count_stmt)).scalar() or 0
        list_stmt = list_stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(list_stmt)

        return {
            "items": [await self._serialize_artifact_payload(item) for item in result.scalars().all()],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_artifact_detail(self, artifact_id: int) -> dict[str, Any]:
        artifact = await self._get_artifact(artifact_id)
        payload = await self._serialize_artifact_payload(artifact)
        payload["download_available"] = bool(
            payload.get("storage_path") or payload.get("storage_uri") or payload.get("content_text") or payload.get("content_json")
        )
        return payload

    async def submit_feedback(self, artifact_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        executor = _runtime("executor")
        model_access = _runtime("model_access")
        artifact = await self._get_artifact(artifact_id)
        decision = str(payload.get("decision") or "").strip().lower()
        comments = str(payload.get("comments") or "").strip()
        if decision in {"adopted", "rejected"}:
            model_access.assign_model_values(artifact, {"status": decision})
        feedback_summary = {
            "decision": decision or None,
            "comments": comments or None,
            "rating": payload.get("rating"),
            "tags": payload.get("tags") or [],
            "submitted_at": _runtime("serializer").to_iso(utc_now()),
        }
        model_access.assign_model_values(
            artifact,
            {
                "feedback_summary": feedback_summary,
            },
        )

        event = executor.create_event_instance(
            "artifact_feedback_submitted",
            {
                "run_id": model_access.first_attr(artifact, ("run_id", "workflow_run_id")),
                "node_run_id": model_access.first_attr(artifact, ("node_run_id", "workflow_node_run_id")),
                "tenant_id": model_access.first_attr(artifact, ("tenant_id",)),
                "message": "artifact feedback submitted",
                "payload_json": feedback_summary,
                "event_level": "audit",
            },
        )
        if event is not None:
            self.db.add(event)
        await self.db.flush()
        return await self._serialize_artifact_payload(artifact)

    async def download_artifact(self, artifact_id: int) -> dict[str, Any]:
        errors = _runtime("errors")
        model_access = _runtime("model_access")
        artifact = await self._get_artifact(artifact_id)
        storage_path = model_access.first_attr(artifact, ("storage_path", "file_path"))
        storage_uri = model_access.first_attr(artifact, ("storage_uri",))
        mime_type = model_access.first_attr(artifact, ("mime_type",), "application/json")
        filename = model_access.first_attr(artifact, ("download_filename",))
        title = model_access.first_attr(artifact, ("name", "title"), f"artifact-{artifact_id}")

        if storage_path or storage_uri:
            path = str(storage_path or storage_uri or "")
            path = path.replace("artifact://", "").strip()
            tenant_id = await self._resolve_artifact_tenant_id(artifact)
            storage = await self._get_storage_for_artifact(artifact, tenant_id=tenant_id)
            content = await storage.get(path)
            if isinstance(content, str):
                content_bytes = content.encode("utf-8")
            elif isinstance(content, bytes):
                content_bytes = content
            else:
                content_bytes = content.read()
            return {
                "content": content_bytes,
                "filename": filename or f"{title}.bin",
                "mime_type": mime_type or "application/octet-stream",
            }

        content_text = model_access.first_attr(artifact, ("content_text",))
        if content_text:
            return {
                "content": str(content_text).encode("utf-8"),
                "filename": filename or f"{title}.txt",
                "mime_type": "text/plain; charset=utf-8",
            }

        content_json = model_access.first_attr(artifact, ("content_json",))
        if content_json is not None:
            return {
                "content": json.dumps(content_json, ensure_ascii=False, indent=2).encode("utf-8"),
                "filename": filename or f"{title}.json",
                "mime_type": "application/json",
            }

        raise errors.WorkflowNotFoundError(
            _("plugin.workflow-orchestration.error.artifact_content_missing"),
        )

    async def cleanup_expired_artifacts(self) -> dict[str, Any]:
        executor = _runtime("executor")
        model_access = _runtime("model_access")

        artifact_model = model_access.resolve_model("execution_artifact")
        expires_field = None
        for field_name in ("expires_at", "retention_until"):
            if hasattr(artifact_model, field_name):
                expires_field = getattr(artifact_model, field_name)
                break
        if expires_field is None:
            return {"processed_count": 0, "artifact_ids": []}

        stmt = select(artifact_model).where(expires_field.is_not(None), expires_field <= utc_now())
        stmt, _ = self._apply_tenant_scope(stmt, None, artifact_model)
        expired_artifacts = list((await self.db.execute(stmt)).scalars().all())

        deleted_ids: list[int] = []

        for artifact in expired_artifacts:
            artifact_id = int(model_access.first_attr(artifact, ("id",), 0) or 0)
            storage_path = model_access.first_attr(artifact, ("storage_path", "file_path"))
            storage_uri = model_access.first_attr(artifact, ("storage_uri",))
            storage_ref = storage_path or storage_uri

            tenant_id = await self._resolve_artifact_tenant_id(artifact)
            storage = await self._get_storage_for_artifact(artifact, tenant_id=tenant_id)

            if storage_ref:
                try:
                    await storage.delete(str(storage_ref).replace("artifact://", ""))
                except Exception as exc:
                    logger.warning("Failed to delete artifact {} payload (tenant {}): {}", artifact_id, tenant_id, exc)
            model_access.assign_model_values(
                artifact,
                {
                    "status": "expired",
                },
            )
            event = executor.create_event_instance(
                "artifact_retention_cleaned",
                {
                    "run_id": model_access.first_attr(artifact, ("run_id", "workflow_run_id")),
                    "node_run_id": model_access.first_attr(artifact, ("node_run_id", "workflow_node_run_id")),
                    "tenant_id": tenant_id,
                    "message": "artifact retention cleaned",
                    "payload_json": {"artifact_id": artifact_id},
                    "event_level": "audit",
                },
            )
            if event is not None:
                self.db.add(event)
            deleted_ids.append(artifact_id)
        await self.db.flush()
        return {
            "processed_count": len(deleted_ids),
            "artifact_ids": deleted_ids,
        }

    async def _get_artifact(self, artifact_id: int) -> Any:
        errors = _runtime("errors")
        model_access = _runtime("model_access")

        artifact_model = model_access.resolve_model("execution_artifact")
        stmt = select(artifact_model).where(artifact_model.id == artifact_id)
        run_model = model_access.try_resolve_model("workflow_run")
        if self.tenant_id is not None and run_model is not None and not hasattr(artifact_model, "tenant_id"):
            stmt = stmt.join(run_model, artifact_model.run_id == run_model.id).where(run_model.tenant_id == self.tenant_id)
        elif self.tenant_id is not None and hasattr(artifact_model, "tenant_id"):
            stmt = stmt.where(artifact_model.tenant_id == self.tenant_id)
        artifact = (await self.db.execute(stmt)).scalar_one_or_none()
        if artifact is None:
            raise errors.WorkflowNotFoundError(
                _("plugin.workflow-orchestration.error.artifact_not_found"),
            )
        return artifact

    def _apply_tenant_scope(self, list_stmt: Any, count_stmt: Any, artifact_model: Any) -> tuple[Any, Any]:
        if self.tenant_id is None:
            return list_stmt, count_stmt
        model_access = _runtime("model_access")
        if hasattr(artifact_model, "tenant_id"):
            list_stmt = list_stmt.where(artifact_model.tenant_id == self.tenant_id)
            if count_stmt is not None:
                count_stmt = count_stmt.where(artifact_model.tenant_id == self.tenant_id)
            return list_stmt, count_stmt

        run_model = model_access.try_resolve_model("workflow_run")
        if run_model is None:
            return list_stmt, count_stmt
        list_stmt = list_stmt.join(run_model, artifact_model.run_id == run_model.id).where(run_model.tenant_id == self.tenant_id)
        if count_stmt is not None:
            count_stmt = count_stmt.join(run_model, artifact_model.run_id == run_model.id).where(run_model.tenant_id == self.tenant_id)
        return list_stmt, count_stmt

    async def _serialize_artifact_payload(self, artifact: Any) -> dict[str, Any]:
        run_query_module = load_plugin_module(PLUGIN_NAME, "services.run_query_service")
        if run_query_module is None:
            return _runtime("serializer").serialize_artifact(artifact)
        query_service = run_query_module.RunQueryService(self.db, tenant_id=self.tenant_id)
        return await query_service._serialize_artifact_record(artifact)

    async def _resolve_artifact_tenant_id(self, artifact: Any) -> int | None:
        model_access = _runtime("model_access")
        artifact_tid = model_access.first_attr(artifact, ("tenant_id",), None)
        if artifact_tid is not None:
            return artifact_tid

        run_model = model_access.try_resolve_model("workflow_run")
        if run_model is None:
            return None

        run_id = model_access.first_attr(artifact, ("run_id", "workflow_run_id"))
        if not run_id:
            return None

        run_stmt = select(run_model).where(run_model.id == run_id)
        run_row = (await self.db.execute(run_stmt)).scalar_one_or_none()
        return model_access.first_attr(run_row, ("tenant_id",), None) if run_row is not None else None

    async def _get_storage_for_artifact(self, artifact: Any, *, tenant_id: Any = _MISSING) -> Any:
        storage_access = _runtime("storage_access")
        if tenant_id is _MISSING:
            tenant_id = await self._resolve_artifact_tenant_id(artifact)
        return await storage_access.get_plugin_storage(self.db, tenant_id=tenant_id)
