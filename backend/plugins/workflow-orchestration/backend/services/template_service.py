from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import Select, asc, delete, desc, func, select

from app.core.base_model import utc_now
from app.core.i18n import _
from app.exceptions.base import BusinessException, NotFoundException, ValidationException
from app.schemas.common.query import FilterOp, QuerySpec

from ..models.enums import BuilderSurfaceEnum, ReleaseScopeEnum, TemplateStatusEnum
from ..models.release import WorkflowRelease
from ..models.runtime import WorkflowArtifact, WorkflowRun
from ..models.template import (
    WorkflowTemplate,
    WorkflowTemplateEdge,
    WorkflowTemplateNode,
    WorkflowTemplateVersion,
)
from ..schemas.release import WorkflowReleaseSchema
from ..schemas.template import (
    CreateTemplateRequestSchema,
    UpdateTemplateRequestSchema,
    WorkflowSnapshotSchema,
    WorkflowTemplateDetailSchema,
    WorkflowTemplateEdgeResponseSchema,
    WorkflowTemplateListItemSchema,
    WorkflowTemplateNodeResponseSchema,
    WorkflowTemplateVersionSchema,
)

_TEMPLATE_FILTERS = {
    "code": WorkflowTemplate.code,
    "name": WorkflowTemplate.name,
    "status": WorkflowTemplate.status,
    "category": WorkflowTemplate.category,
    "builder_surface": WorkflowTemplate.builder_surface,
    "release_scope": WorkflowTemplate.release_scope,
    "created_by": WorkflowTemplate.created_by,
}

_TEMPLATE_SORTS = {
    "created_at": WorkflowTemplate.created_at,
    "updated_at": WorkflowTemplate.updated_at,
    "name": WorkflowTemplate.name,
    "code": WorkflowTemplate.code,
    "published_at": WorkflowTemplate.published_at,
}

_VERSION_FILTERS = {
    "status": WorkflowTemplateVersion.status,
    "version_no": WorkflowTemplateVersion.version_no,
    "is_latest": WorkflowTemplateVersion.is_latest,
    "is_published": WorkflowTemplateVersion.is_published,
}

_VERSION_SORTS = {
    "created_at": WorkflowTemplateVersion.created_at,
    "updated_at": WorkflowTemplateVersion.updated_at,
    "published_at": WorkflowTemplateVersion.published_at,
    "version_no": WorkflowTemplateVersion.version_no,
}


def _apply_filters(
    stmt: Select,
    query_spec: QuerySpec,
    filter_map: dict[str, Any],
) -> Select:
    for rule in query_spec.filters:
        column = filter_map.get(rule.field)
        if column is None:
            continue
        value = rule.value
        if rule.op == FilterOp.eq:
            stmt = stmt.where(column == value)
        elif rule.op == FilterOp.ne:
            stmt = stmt.where(column != value)
        elif rule.op == FilterOp.ilike:
            stmt = stmt.where(column.ilike(f"%{value}%"))
        elif rule.op == FilterOp.like:
            stmt = stmt.where(column.like(f"%{value}%"))
        elif rule.op == FilterOp.in_:
            items = [item.strip() for item in str(value).split(",") if item.strip()]
            if items:
                stmt = stmt.where(column.in_(items))
        elif rule.op == FilterOp.gte:
            stmt = stmt.where(column >= value)
        elif rule.op == FilterOp.lte:
            stmt = stmt.where(column <= value)
    return stmt


def _apply_sorts(
    stmt: Select,
    query_spec: QuerySpec,
    sort_map: dict[str, Any],
    *,
    default_sort: Any,
) -> Select:
    if not query_spec.sort:
        return stmt.order_by(default_sort)

    order_clauses = []
    for sort_field in query_spec.sort:
        is_desc = sort_field.startswith("-")
        field_name = sort_field[1:] if is_desc else sort_field
        column = sort_map.get(field_name)
        if column is None:
            continue
        order_clauses.append(desc(column) if is_desc else asc(column))

    if not order_clauses:
        return stmt.order_by(default_sort)
    return stmt.order_by(*order_clauses)


def _snapshot_to_dict(
    snapshot: WorkflowSnapshotSchema | dict[str, Any],
    *,
    builder_surface: str,
    compiled_by: int | None,
) -> dict[str, Any]:
    if isinstance(snapshot, WorkflowSnapshotSchema):
        data = snapshot.model_dump()
    else:
        data = dict(snapshot)

    data["builder_surface"] = builder_surface
    data["compiled_by"] = compiled_by
    data["compiled_at"] = data.get("compiled_at") or utc_now().isoformat()
    return data


def _hash_snapshot(snapshot: dict[str, Any]) -> str:
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _serialize_template(template: WorkflowTemplate) -> dict[str, Any]:
    return WorkflowTemplateListItemSchema.model_validate(template).model_dump()


def _serialize_template_version(version: WorkflowTemplateVersion) -> dict[str, Any]:
    return WorkflowTemplateVersionSchema.model_validate(version).model_dump()


def _serialize_template_node(node: WorkflowTemplateNode) -> dict[str, Any]:
    return WorkflowTemplateNodeResponseSchema.model_validate(node).model_dump()


def _serialize_template_edge(edge: WorkflowTemplateEdge) -> dict[str, Any]:
    return WorkflowTemplateEdgeResponseSchema.model_validate(edge).model_dump()


def _validate_template_payload(
    *,
    status: str,
    builder_surface: str,
    release_scope: str,
) -> None:
    if status == TemplateStatusEnum.PUBLISHED.value:
        raise ValidationException(
            message=_("Published status requires the publish endpoint."),
        )
    if not TemplateStatusEnum.has_value(status):
        raise ValidationException(message=_("Invalid template status."))
    if not BuilderSurfaceEnum.has_value(builder_surface):
        raise ValidationException(message=_("Invalid builder surface."))
    if not ReleaseScopeEnum.has_value(release_scope):
        raise ValidationException(message=_("Invalid release scope."))


async def _get_template_or_raise(db, template_id: int) -> WorkflowTemplate:
    template = await db.get(WorkflowTemplate, template_id)
    if not template or template.is_deleted:
        raise NotFoundException(message=_("Workflow template not found."))
    return template


async def _get_template_version_or_raise(
    db,
    *,
    template_id: int,
    version_id: int,
) -> WorkflowTemplateVersion:
    version = await db.get(WorkflowTemplateVersion, version_id)
    if not version or version.is_deleted or version.template_id != template_id:
        raise NotFoundException(message=_("Workflow template version not found."))
    return version


async def _upsert_template_graph(
    db,
    *,
    template_id: int,
    snapshot_json: dict[str, Any],
) -> None:
    graph = snapshot_json.get("graph") or {}
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []

    await db.execute(
        delete(WorkflowTemplateEdge).where(WorkflowTemplateEdge.template_id == template_id)
    )
    await db.execute(
        delete(WorkflowTemplateNode).where(WorkflowTemplateNode.template_id == template_id)
    )

    node_instances = []
    for item in nodes:
        node_instances.append(
            WorkflowTemplateNode(
                template_id=template_id,
                node_key=item["node_key"],
                node_type=item["node_type"],
                title=item["title"],
                description=item.get("description"),
                sort_order=item.get("sort_order", 0),
                timeout_minutes=item.get("timeout_minutes"),
                retry_limit=item.get("retry_limit"),
                config_json=item.get("config_json") or {},
                position_json=item.get("position_json") or {},
                input_contract_json=item.get("input_contract_json") or {},
                output_contract_json=item.get("output_contract_json") or {},
                policy_json=item.get("policy_json") or {},
                metadata_json=item.get("metadata_json") or {},
            )
        )

    edge_instances = []
    for item in edges:
        edge_instances.append(
            WorkflowTemplateEdge(
                template_id=template_id,
                edge_key=item["edge_key"],
                from_node_key=item["from_node_key"],
                from_port=item.get("from_port"),
                to_node_key=item["to_node_key"],
                to_port=item.get("to_port"),
                sort_order=item.get("sort_order", 0),
                condition_json=item.get("condition_json") or {},
                metadata_json=item.get("metadata_json") or {},
            )
        )

    if node_instances:
        db.add_all(node_instances)
    if edge_instances:
        db.add_all(edge_instances)
    await db.flush()


async def _create_template_version(
    db,
    *,
    template: WorkflowTemplate,
    snapshot_json: dict[str, Any],
    change_summary: str | None,
    release_notes: str | None,
    user_id: int | None,
) -> WorkflowTemplateVersion:
    existing_versions = (
        await db.execute(
            select(WorkflowTemplateVersion).where(
                WorkflowTemplateVersion.template_id == template.id,
                WorkflowTemplateVersion.is_deleted.is_(False),
                WorkflowTemplateVersion.is_latest.is_(True),
            )
        )
    ).scalars().all()
    for existing in existing_versions:
        existing.is_latest = False
        existing.updated_by = user_id

    current_time = utc_now()
    version = WorkflowTemplateVersion(
        template_id=template.id,
        version_no=template.latest_version_no + 1,
        status=TemplateStatusEnum.DRAFT.value,
        snapshot_version=str(snapshot_json.get("snapshot_version") or "1.0.0"),
        workflow_schema_version=str(snapshot_json.get("workflow_schema_version") or "1.0.0"),
        snapshot_hash=_hash_snapshot(snapshot_json),
        snapshot_json=snapshot_json,
        change_summary=change_summary,
        release_notes=release_notes,
        compiled_at=current_time,
        compiled_by=user_id,
        is_latest=True,
        is_published=False,
        created_by=user_id,
        updated_by=user_id,
    )

    db.add(version)
    await db.flush()
    await db.refresh(version)
    return version


async def _ensure_template_code_available(db, code: str, *, exclude_id: int | None = None) -> None:
    stmt = select(WorkflowTemplate).where(
        WorkflowTemplate.code == code,
        WorkflowTemplate.is_deleted.is_(False),
    )
    if exclude_id is not None:
        stmt = stmt.where(WorkflowTemplate.id != exclude_id)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise BusinessException(message=_("Workflow template code already exists."))


async def list_templates(db, query_spec: QuerySpec | None = None) -> dict[str, Any]:
    query = query_spec or QuerySpec()
    stmt = select(WorkflowTemplate).where(WorkflowTemplate.is_deleted.is_(False))
    stmt = _apply_filters(stmt, query, _TEMPLATE_FILTERS)
    total_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int((await db.execute(total_stmt)).scalar_one() or 0)

    stmt = _apply_sorts(
        stmt,
        query,
        _TEMPLATE_SORTS,
        default_sort=desc(WorkflowTemplate.updated_at),
    )
    stmt = stmt.offset(query.offset).limit(query.limit)
    items = (await db.execute(stmt)).scalars().all()

    return {
        "items": [_serialize_template(item) for item in items],
        "total": total,
        "page": query.page,
        "page_size": query.size,
    }


async def create_template(
    db,
    payload: CreateTemplateRequestSchema,
    *,
    user_id: int | None,
) -> dict[str, Any]:
    _validate_template_payload(
        status=payload.status,
        builder_surface=payload.builder_surface,
        release_scope=payload.release_scope,
    )
    await _ensure_template_code_available(db, payload.code)

    snapshot_json = _snapshot_to_dict(
        payload.snapshot,
        builder_surface=payload.builder_surface,
        compiled_by=user_id,
    )
    template = WorkflowTemplate(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        status=payload.status,
        builder_surface=payload.builder_surface,
        release_scope=payload.release_scope,
        tags_json=payload.tags_json,
        metadata_json=payload.metadata_json,
        risk_policy_json=payload.risk_policy_json,
        contract_summary_json=payload.contract_summary_json,
        default_trigger_json=payload.default_trigger_json,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)

    version = await _create_template_version(
        db,
        template=template,
        snapshot_json=snapshot_json,
        change_summary=payload.change_summary,
        release_notes=payload.release_notes,
        user_id=user_id,
    )
    template.latest_version_no = version.version_no
    template.latest_version_id = version.id
    template.updated_by = user_id
    await _upsert_template_graph(db, template_id=template.id, snapshot_json=snapshot_json)
    await db.flush()
    await db.refresh(template)

    return await get_template_detail(db, template.id)


async def get_template_detail(db, template_id: int) -> dict[str, Any]:
    template = await _get_template_or_raise(db, template_id)

    node_items = (
        await db.execute(
            select(WorkflowTemplateNode)
            .where(
                WorkflowTemplateNode.template_id == template_id,
                WorkflowTemplateNode.is_deleted.is_(False),
            )
            .order_by(asc(WorkflowTemplateNode.sort_order), asc(WorkflowTemplateNode.id))
        )
    ).scalars().all()
    edge_items = (
        await db.execute(
            select(WorkflowTemplateEdge)
            .where(
                WorkflowTemplateEdge.template_id == template_id,
                WorkflowTemplateEdge.is_deleted.is_(False),
            )
            .order_by(asc(WorkflowTemplateEdge.sort_order), asc(WorkflowTemplateEdge.id))
        )
    ).scalars().all()

    latest_version = None
    if template.latest_version_id:
        version = await db.get(WorkflowTemplateVersion, template.latest_version_id)
        if version and not version.is_deleted:
            latest_version = _serialize_template_version(version)

    published_version = None
    if template.current_published_version_id:
        version = await db.get(WorkflowTemplateVersion, template.current_published_version_id)
        if version and not version.is_deleted:
            published_version = _serialize_template_version(version)

    latest_release = None
    if template.latest_release_id:
        release = await db.get(WorkflowRelease, template.latest_release_id)
        if release and not release.is_deleted:
            latest_release = WorkflowReleaseSchema.model_validate(release).model_dump()

    version_count = int(
        (
            await db.execute(
                select(func.count(WorkflowTemplateVersion.id)).where(
                    WorkflowTemplateVersion.template_id == template_id,
                    WorkflowTemplateVersion.is_deleted.is_(False),
                )
            )
        ).scalar_one()
        or 0
    )

    payload = WorkflowTemplateDetailSchema(
        **_serialize_template(template),
        nodes=[_serialize_template_node(item) for item in node_items],
        edges=[_serialize_template_edge(item) for item in edge_items],
        latest_version=latest_version,
        published_version=published_version,
        latest_release=latest_release,
        version_count=version_count,
    )
    return payload.model_dump()


async def update_template(
    db,
    template_id: int,
    payload: UpdateTemplateRequestSchema,
    *,
    user_id: int | None,
) -> dict[str, Any]:
    template = await _get_template_or_raise(db, template_id)

    next_status = payload.status or template.status
    next_builder_surface = payload.builder_surface or template.builder_surface
    next_release_scope = payload.release_scope or template.release_scope
    _validate_template_payload(
        status=next_status,
        builder_surface=next_builder_surface,
        release_scope=next_release_scope,
    )

    if payload.name is not None:
        template.name = payload.name
    if payload.description is not None:
        template.description = payload.description
    if payload.category is not None:
        template.category = payload.category
    if payload.status is not None:
        template.status = payload.status
    if payload.builder_surface is not None:
        template.builder_surface = payload.builder_surface
    if payload.release_scope is not None:
        template.release_scope = payload.release_scope
    if payload.tags_json is not None:
        template.tags_json = payload.tags_json
    if payload.metadata_json is not None:
        template.metadata_json = payload.metadata_json
    if payload.risk_policy_json is not None:
        template.risk_policy_json = payload.risk_policy_json
    if payload.contract_summary_json is not None:
        template.contract_summary_json = payload.contract_summary_json
    if payload.default_trigger_json is not None:
        template.default_trigger_json = payload.default_trigger_json
    template.updated_by = user_id

    if payload.snapshot is not None:
        snapshot_json = _snapshot_to_dict(
            payload.snapshot,
            builder_surface=template.builder_surface,
            compiled_by=user_id,
        )
        await _upsert_template_graph(db, template_id=template.id, snapshot_json=snapshot_json)
        if payload.create_version:
            version = await _create_template_version(
                db,
                template=template,
                snapshot_json=snapshot_json,
                change_summary=payload.change_summary,
                release_notes=payload.release_notes,
                user_id=user_id,
            )
            template.latest_version_no = version.version_no
            template.latest_version_id = version.id

    await db.flush()
    await db.refresh(template)
    return await get_template_detail(db, template.id)


async def list_template_versions(
    db,
    template_id: int,
    query_spec: QuerySpec | None = None,
) -> dict[str, Any]:
    await _get_template_or_raise(db, template_id)
    query = query_spec or QuerySpec()

    stmt = select(WorkflowTemplateVersion).where(
        WorkflowTemplateVersion.template_id == template_id,
        WorkflowTemplateVersion.is_deleted.is_(False),
    )
    stmt = _apply_filters(stmt, query, _VERSION_FILTERS)
    total_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int((await db.execute(total_stmt)).scalar_one() or 0)

    stmt = _apply_sorts(
        stmt,
        query,
        _VERSION_SORTS,
        default_sort=desc(WorkflowTemplateVersion.version_no),
    )
    stmt = stmt.offset(query.offset).limit(query.limit)
    items = (await db.execute(stmt)).scalars().all()

    return {
        "items": [_serialize_template_version(item) for item in items],
        "total": total,
        "page": query.page,
        "page_size": query.size,
    }


async def get_template_overview_stats(db) -> dict[str, Any]:
    total_templates = int(
        (
            await db.execute(
                select(func.count(WorkflowTemplate.id)).where(
                    WorkflowTemplate.is_deleted.is_(False)
                )
            )
        ).scalar_one()
        or 0
    )

    status_rows = (
        await db.execute(
            select(
                WorkflowTemplate.status,
                func.count(WorkflowTemplate.id),
            )
            .where(WorkflowTemplate.is_deleted.is_(False))
            .group_by(WorkflowTemplate.status)
        )
    ).all()
    status_counts = {row[0]: int(row[1]) for row in status_rows}

    version_count = int(
        (
            await db.execute(
                select(func.count(WorkflowTemplateVersion.id)).where(
                    WorkflowTemplateVersion.is_deleted.is_(False)
                )
            )
        ).scalar_one()
        or 0
    )
    run_count = int(
        (
            await db.execute(
                select(func.count(WorkflowRun.id)).where(WorkflowRun.is_deleted.is_(False))
            )
        ).scalar_one()
        or 0
    )
    artifact_count = int(
        (
            await db.execute(
                select(func.count(WorkflowArtifact.id)).where(
                    WorkflowArtifact.is_deleted.is_(False)
                )
            )
        ).scalar_one()
        or 0
    )

    return {
        "total_templates": total_templates,
        "status_counts": status_counts,
        "total_versions": version_count,
        "total_runs": run_count,
        "total_artifacts": artifact_count,
    }
