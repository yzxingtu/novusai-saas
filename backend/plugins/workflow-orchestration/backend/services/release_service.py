from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select, asc, desc, func, select

from app.core.base_model import utc_now
from app.core.data_permission import apply_data_permission_if_needed
from app.core.i18n import _
from app.exceptions.base import BusinessException, NotFoundException, ValidationException
from app.schemas.common.query import FilterOp, QuerySpec

from ..models.enums import (
    ChangeSetStatusEnum,
    ReleaseChannelEnum,
    ReleaseScopeEnum,
    ReleaseStatusEnum,
    TemplateStatusEnum,
    WorkflowKindEnum,
)
from ..models.release import WorkflowChangeSet, WorkflowEnvironment, WorkflowRelease
from ..models.runtime import WorkflowArtifact, WorkflowRun
from ..models.template import WorkflowTemplate, WorkflowTemplateVersion
from ..schemas.release import (
    PublishTemplateRequestSchema,
    RollbackReleaseRequestSchema,
    WorkflowReleaseSchema,
)

_RELEASE_FILTERS = {
    "workflow_kind": WorkflowRelease.workflow_kind,
    "workflow_id": WorkflowRelease.workflow_id,
    "status": WorkflowRelease.status,
    "release_scope": WorkflowRelease.release_scope,
    "channel": WorkflowRelease.channel,
    "environment_code": WorkflowRelease.environment_code,
}

_RELEASE_SORTS = {
    "created_at": WorkflowRelease.created_at,
    "updated_at": WorkflowRelease.updated_at,
    "published_at": WorkflowRelease.published_at,
    "code": WorkflowRelease.code,
}


def apply_model_scope(stmt: Any, model: type) -> Any:
    return apply_data_permission_if_needed(stmt, model)


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
        elif rule.op == FilterOp.in_:
            items = [item.strip() for item in str(value).split(",") if item.strip()]
            if items:
                stmt = stmt.where(column.in_(items))
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
    return stmt.order_by(*order_clauses) if order_clauses else stmt.order_by(default_sort)


def _now_stamp() -> str:
    return utc_now().strftime("%Y%m%d%H%M%S")


def _generate_release_code(template_id: int) -> str:
    return f"REL-TPL-{template_id}-{_now_stamp()}"


def _generate_change_set_code(template_id: int) -> str:
    return f"CS-TPL-{template_id}-{_now_stamp()}"


async def _get_template_or_raise(db, template_id: int) -> WorkflowTemplate:
    template = (
        await db.execute(
            apply_model_scope(
                select(WorkflowTemplate).where(WorkflowTemplate.id == template_id),
                WorkflowTemplate,
            )
        )
    ).scalar_one_or_none()
    if not template or template.is_deleted:
        raise NotFoundException(message=_("Workflow template not found."))
    return template


async def _get_template_version_or_raise(
    db,
    *,
    template_id: int,
    version_id: int,
) -> WorkflowTemplateVersion:
    version = (
        await db.execute(
            apply_model_scope(
                select(WorkflowTemplateVersion).where(WorkflowTemplateVersion.id == version_id),
                WorkflowTemplateVersion,
            )
        )
    ).scalar_one_or_none()
    if not version or version.is_deleted or version.template_id != template_id:
        raise NotFoundException(message=_("Workflow template version not found."))
    return version


async def _get_environment_by_code(db, code: str) -> WorkflowEnvironment:
    environment = (
        await db.execute(
            apply_model_scope(
                select(WorkflowEnvironment).where(
                    WorkflowEnvironment.code == code,
                    WorkflowEnvironment.is_deleted.is_(False),
                ),
                WorkflowEnvironment,
            )
        )
    ).scalar_one_or_none()
    if not environment:
        raise NotFoundException(message=_("Workflow environment not found."))
    return environment


def _serialize_release(release: WorkflowRelease) -> dict[str, Any]:
    return WorkflowReleaseSchema.model_validate(release).model_dump()


async def _mark_previous_published_releases_deprecated(
    db,
    *,
    workflow_kind: str,
    workflow_id: int,
    user_id: int | None,
) -> None:
    rows = (
        await db.execute(
            apply_model_scope(
                select(WorkflowRelease).where(
                    WorkflowRelease.workflow_kind == workflow_kind,
                    WorkflowRelease.workflow_id == workflow_id,
                    WorkflowRelease.status == ReleaseStatusEnum.PUBLISHED.value,
                    WorkflowRelease.is_deleted.is_(False),
                ),
                WorkflowRelease,
            )
        )
    ).scalars().all()
    for row in rows:
        row.status = ReleaseStatusEnum.DEPRECATED.value
        row.updated_by = user_id


async def _mark_previous_published_versions_deprecated(
    db,
    *,
    template_id: int,
    user_id: int | None,
) -> None:
    rows = (
        await db.execute(
            apply_model_scope(
                select(WorkflowTemplateVersion).where(
                    WorkflowTemplateVersion.template_id == template_id,
                    WorkflowTemplateVersion.is_deleted.is_(False),
                    WorkflowTemplateVersion.is_published.is_(True),
                ),
                WorkflowTemplateVersion,
            )
        )
    ).scalars().all()
    for row in rows:
        row.is_published = False
        if row.status == TemplateStatusEnum.PUBLISHED.value:
            row.status = TemplateStatusEnum.DEPRECATED.value
        row.updated_by = user_id


async def _create_change_set(
    db,
    *,
    template_id: int,
    environment_id: int | None,
    payload: PublishTemplateRequestSchema,
    user_id: int | None,
) -> WorkflowChangeSet:
    change_set = WorkflowChangeSet(
        code=_generate_change_set_code(template_id),
        workflow_kind=WorkflowKindEnum.TEMPLATE.value,
        workflow_id=template_id,
        environment_id=environment_id,
        status=ChangeSetStatusEnum.PUBLISHED.value,
        risk_level=payload.risk_level,
        change_types_json=payload.change_types_json,
        validation_result_json=payload.validation_result_json,
        rollback_plan_json={},
        notes=payload.notes,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(change_set)
    await db.flush()
    await db.refresh(change_set)
    return change_set


async def list_releases(db, query_spec: QuerySpec | None = None) -> dict[str, Any]:
    query = query_spec or QuerySpec()
    stmt = apply_model_scope(
        select(WorkflowRelease).where(WorkflowRelease.is_deleted.is_(False)),
        WorkflowRelease,
    )
    stmt = _apply_filters(stmt, query, _RELEASE_FILTERS)
    total_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int((await db.execute(total_stmt)).scalar_one() or 0)

    stmt = _apply_sorts(
        stmt,
        query,
        _RELEASE_SORTS,
        default_sort=desc(WorkflowRelease.created_at),
    )
    stmt = stmt.offset(query.offset).limit(query.limit)
    rows = (await db.execute(stmt)).scalars().all()

    workflow_ids = [row.workflow_id for row in rows if row.workflow_kind == WorkflowKindEnum.TEMPLATE.value]
    workflow_map: dict[int, WorkflowTemplate] = {}
    if workflow_ids:
        template_rows = (
            await db.execute(
                apply_model_scope(
                    select(WorkflowTemplate).where(
                        WorkflowTemplate.id.in_(workflow_ids),
                        WorkflowTemplate.is_deleted.is_(False),
                    ),
                    WorkflowTemplate,
                )
            )
        ).scalars().all()
        workflow_map = {row.id: row for row in template_rows}

    items = []
    for row in rows:
        payload = _serialize_release(row)
        template = workflow_map.get(row.workflow_id)
        if template:
            payload["workflow_code"] = template.code
            payload["workflow_name"] = template.name
        items.append(payload)

    return {
        "items": items,
        "total": total,
        "page": query.page,
        "page_size": query.size,
    }


async def publish_template(
    db,
    template_id: int,
    payload: PublishTemplateRequestSchema,
    *,
    user_id: int | None,
) -> dict[str, Any]:
    if not ReleaseScopeEnum.has_value(payload.release_scope):
        raise ValidationException(message=_("Invalid release scope."))
    if not ReleaseChannelEnum.has_value(payload.channel):
        raise ValidationException(message=_("Invalid release channel."))

    template = await _get_template_or_raise(db, template_id)
    version_id = payload.version_id or template.latest_version_id
    if version_id is None:
        raise BusinessException(message=_("No template version is available for publishing."))
    version = await _get_template_version_or_raise(db, template_id=template_id, version_id=version_id)
    environment = await _get_environment_by_code(db, payload.environment_code)

    await _mark_previous_published_releases_deprecated(
        db,
        workflow_kind=WorkflowKindEnum.TEMPLATE.value,
        workflow_id=template.id,
        user_id=user_id,
    )
    await _mark_previous_published_versions_deprecated(db, template_id=template.id, user_id=user_id)

    change_set = await _create_change_set(
        db,
        template_id=template.id,
        environment_id=environment.id,
        payload=payload,
        user_id=user_id,
    )
    change_set.rollback_plan_json = {
        "previous_release_id": template.latest_release_id,
        "previous_version_id": template.current_published_version_id,
    }

    now = utc_now()
    release = WorkflowRelease(
        code=_generate_release_code(template.id),
        workflow_kind=WorkflowKindEnum.TEMPLATE.value,
        workflow_id=template.id,
        workflow_version_id=version.id,
        change_set_id=change_set.id,
        environment_id=environment.id,
        environment_code=environment.code,
        release_scope=payload.release_scope,
        channel=payload.channel,
        status=ReleaseStatusEnum.PUBLISHED.value,
        rollout_json=payload.rollout_json,
        notes=payload.notes,
        published_by=user_id,
        reviewed_by=user_id,
        published_at=now,
        reviewed_at=now,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(release)
    await db.flush()
    await db.refresh(release)

    version.status = TemplateStatusEnum.PUBLISHED.value
    version.is_published = True
    version.is_latest = True
    version.published_at = now
    version.published_by = user_id
    version.updated_by = user_id

    template.status = TemplateStatusEnum.PUBLISHED.value
    template.current_published_version_id = version.id
    template.latest_release_id = release.id
    template.published_at = now
    template.published_by = user_id
    template.updated_by = user_id

    await db.flush()
    await db.refresh(release)
    return _serialize_release(release)


async def rollback_release(
    db,
    release_id: int,
    payload: RollbackReleaseRequestSchema,
    *,
    user_id: int | None,
) -> dict[str, Any]:
    release = (
        await db.execute(
            apply_model_scope(
                select(WorkflowRelease).where(WorkflowRelease.id == release_id),
                WorkflowRelease,
            )
        )
    ).scalar_one_or_none()
    if not release or release.is_deleted:
        raise NotFoundException(message=_("Workflow release not found."))
    if release.workflow_kind != WorkflowKindEnum.TEMPLATE.value:
        raise BusinessException(message=_("Only template releases can be rolled back in this delivery."))

    template = await _get_template_or_raise(db, release.workflow_id)

    target_release: WorkflowRelease | None = None
    if payload.target_release_id is not None:
        candidate = (
            await db.execute(
                apply_model_scope(
                    select(WorkflowRelease).where(WorkflowRelease.id == payload.target_release_id),
                    WorkflowRelease,
                )
            )
        ).scalar_one_or_none()
        if (
            candidate
            and not candidate.is_deleted
            and candidate.workflow_id == release.workflow_id
            and candidate.workflow_kind == release.workflow_kind
        ):
            target_release = candidate
    else:
        target_release = (
            await db.execute(
                apply_model_scope(
                    select(WorkflowRelease)
                    .where(
                        WorkflowRelease.workflow_id == release.workflow_id,
                        WorkflowRelease.workflow_kind == release.workflow_kind,
                        WorkflowRelease.id != release.id,
                        WorkflowRelease.is_deleted.is_(False),
                        WorkflowRelease.workflow_version_id.is_not(None),
                    )
                    .order_by(desc(WorkflowRelease.published_at), desc(WorkflowRelease.id))
                    .limit(1),
                    WorkflowRelease,
                )
            )
        ).scalar_one_or_none()

    if not target_release:
        raise BusinessException(message=_("No rollback target release is available."))

    target_version = await _get_template_version_or_raise(
        db,
        template_id=template.id,
        version_id=target_release.workflow_version_id,
    )
    environment = (
        await _get_environment_by_code(db, target_release.environment_code)
        if target_release.environment_code
        else None
    )

    await _mark_previous_published_releases_deprecated(
        db,
        workflow_kind=WorkflowKindEnum.TEMPLATE.value,
        workflow_id=template.id,
        user_id=user_id,
    )
    await _mark_previous_published_versions_deprecated(db, template_id=template.id, user_id=user_id)

    release.status = ReleaseStatusEnum.ROLLED_BACK.value
    release.updated_by = user_id

    now = utc_now()
    rollback_release_row = WorkflowRelease(
        code=_generate_release_code(template.id),
        workflow_kind=WorkflowKindEnum.TEMPLATE.value,
        workflow_id=template.id,
        workflow_version_id=target_version.id,
        change_set_id=None,
        environment_id=environment.id if environment else target_release.environment_id,
        environment_code=environment.code if environment else target_release.environment_code,
        release_scope=target_release.release_scope,
        channel=target_release.channel,
        status=ReleaseStatusEnum.PUBLISHED.value,
        rollout_json=target_release.rollout_json,
        notes=payload.notes or target_release.notes,
        rollback_of_release_id=release.id,
        rollback_target_release_id=target_release.id,
        published_by=user_id,
        reviewed_by=user_id,
        published_at=now,
        reviewed_at=now,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(rollback_release_row)
    await db.flush()
    await db.refresh(rollback_release_row)

    target_version.status = TemplateStatusEnum.PUBLISHED.value
    target_version.is_published = True
    target_version.updated_by = user_id
    target_version.published_at = now
    target_version.published_by = user_id

    template.status = TemplateStatusEnum.PUBLISHED.value
    template.current_published_version_id = target_version.id
    template.latest_release_id = rollback_release_row.id
    template.published_at = now
    template.published_by = user_id
    template.updated_by = user_id

    await db.flush()
    await db.refresh(rollback_release_row)
    return _serialize_release(rollback_release_row)


async def get_release_overview_stats(db) -> dict[str, Any]:
    total_releases = int(
        (
            await db.execute(
                apply_model_scope(
                    select(func.count(WorkflowRelease.id)).where(
                        WorkflowRelease.is_deleted.is_(False)
                    ),
                    WorkflowRelease,
                )
            )
        ).scalar_one()
        or 0
    )

    status_rows = (
        await db.execute(
            apply_model_scope(
                select(WorkflowRelease.status, func.count(WorkflowRelease.id))
                .where(WorkflowRelease.is_deleted.is_(False))
                .group_by(WorkflowRelease.status),
                WorkflowRelease,
            )
        )
    ).all()
    status_counts = {row[0]: int(row[1]) for row in status_rows}

    published_at = (
        await db.execute(
            apply_model_scope(
                select(func.max(WorkflowRelease.published_at)).where(
                    WorkflowRelease.is_deleted.is_(False)
                ),
                WorkflowRelease,
            )
        )
    ).scalar_one_or_none()

    return {
        "total_releases": total_releases,
        "status_counts": status_counts,
        "latest_published_at": published_at.isoformat() if isinstance(published_at, datetime) else None,
    }


async def get_runtime_status_metrics(db) -> dict[str, Any]:
    run_rows = (
        await db.execute(
            apply_model_scope(
                select(WorkflowRun.status, func.count(WorkflowRun.id))
                .where(WorkflowRun.is_deleted.is_(False))
                .group_by(WorkflowRun.status),
                WorkflowRun,
            )
        )
    ).all()
    artifact_rows = (
        await db.execute(
            apply_model_scope(
                select(WorkflowArtifact.status, func.count(WorkflowArtifact.id))
                .join(WorkflowRun, WorkflowArtifact.run_id == WorkflowRun.id)
                .where(
                    WorkflowArtifact.is_deleted.is_(False),
                    WorkflowRun.is_deleted.is_(False),
                )
                .group_by(WorkflowArtifact.status),
                WorkflowRun,
            )
        )
    ).all()

    return {
        "run_status_counts": {row[0]: int(row[1]) for row in run_rows},
        "artifact_status_counts": {row[0]: int(row[1]) for row in artifact_rows},
    }
