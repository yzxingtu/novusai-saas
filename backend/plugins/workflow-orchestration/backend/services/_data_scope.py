from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.core.data_permission import apply_data_permission_if_needed


def apply_model_scope(stmt: Any, model: type) -> Any:
    """对单模型查询应用组织数据范围 / Apply org data scope to a single-model statement."""
    return apply_data_permission_if_needed(stmt, model)


def _build_scoped_parent_ids(parent_model: type, tenant_id: int | None = None) -> Any:
    stmt = select(parent_model.id)
    if hasattr(parent_model, "is_deleted"):
        stmt = stmt.where(parent_model.is_deleted.is_(False))
    if tenant_id is not None:
        if hasattr(parent_model, "tenant_id"):
            stmt = stmt.where(parent_model.tenant_id == tenant_id)
        elif hasattr(parent_model, "owner_tenant_id"):
            stmt = stmt.where(parent_model.owner_tenant_id == tenant_id)
    return apply_data_permission_if_needed(stmt, parent_model)


def apply_parent_model_scope(
    stmt: Any,
    parent_model: type,
    relation_column: Any,
    *,
    tenant_id: int | None = None,
) -> Any:
    """按父模型可见范围过滤子记录 / Filter child rows by parent-model visibility."""
    if (
        parent_model is None
        or relation_column is None
        or not hasattr(parent_model, "id")
        or not hasattr(relation_column, "in_")
    ):
        return stmt
    return stmt.where(relation_column.in_(_build_scoped_parent_ids(parent_model, tenant_id)))


def apply_template_scope(stmt: Any, template_model: type, template_id_column: Any) -> Any:
    """按模板可见范围过滤 / Filter by workflow-template visibility."""
    return apply_parent_model_scope(stmt, template_model, template_id_column)


def apply_release_data_scope(stmt: Any, release_model: type, template_model: type) -> Any:
    """按模板范围过滤发布记录 / Filter releases by template visibility."""
    workflow_id_column = getattr(release_model, "workflow_id", None)
    if workflow_id_column is None:
        return apply_data_permission_if_needed(stmt, release_model)
    return apply_template_scope(stmt, template_model, workflow_id_column)


def apply_run_data_scope(
    stmt: Any,
    run_model: type,
    *,
    tenant_id: int | None = None,
    workflow_model: type | None = None,
    workflow_id_column: Any | None = None,
    template_model: type | None = None,
    template_id_column: Any | None = None,
) -> Any:
    """对运行记录查询应用数据范围 / Apply data scope to workflow-run statements."""
    if tenant_id is not None and hasattr(run_model, "tenant_id"):
        stmt = stmt.where(run_model.tenant_id == tenant_id)

    if template_model is not None:
        template_column = template_id_column or getattr(run_model, "workflow_template_id", None)
        if template_column is not None:
            return apply_template_scope(stmt, template_model, template_column)

    if workflow_model is not None:
        workflow_column = workflow_id_column or getattr(run_model, "workflow_id", None)
        if workflow_column is not None:
            return apply_parent_model_scope(
                stmt,
                workflow_model,
                workflow_column,
                tenant_id=tenant_id,
            )

    return apply_data_permission_if_needed(stmt, run_model)


def apply_run_related_scope(
    stmt: Any,
    run_id_column: Any,
    run_model: type,
    *,
    tenant_id: int | None = None,
    workflow_model: type | None = None,
    template_model: type | None = None,
) -> Any:
    """按运行记录可见范围过滤子表 / Filter run-related child rows by visible runs."""
    if (
        run_model is None
        or run_id_column is None
        or not hasattr(run_model, "id")
        or not hasattr(run_id_column, "in_")
    ):
        return stmt
    run_ids_stmt = select(run_model.id)
    if hasattr(run_model, "is_deleted"):
        run_ids_stmt = run_ids_stmt.where(run_model.is_deleted.is_(False))
    run_ids_stmt = apply_run_data_scope(
        run_ids_stmt,
        run_model,
        tenant_id=tenant_id,
        workflow_model=workflow_model,
        template_model=template_model,
    )
    return stmt.where(run_id_column.in_(run_ids_stmt))


def apply_artifact_data_scope(
    stmt: Any,
    artifact_model: type,
    run_model: type | None = None,
    *,
    tenant_id: int | None = None,
    workflow_model: type | None = None,
    template_model: type | None = None,
) -> Any:
    """
    对产物查询应用数据范围 / Apply data scope to artifact statements.

    优先按 workflow/template 父级链过滤；若无法判定，再回退到模型自身声明。
    Prefer workflow/template parent-chain scoping; otherwise fallback to model metadata.
    """
    if tenant_id is not None and hasattr(artifact_model, "tenant_id"):
        stmt = stmt.where(artifact_model.tenant_id == tenant_id)

    if workflow_model is not None and hasattr(artifact_model, "workflow_id"):
        return apply_parent_model_scope(
            stmt,
            workflow_model,
            artifact_model.workflow_id,
            tenant_id=tenant_id,
        )

    if (
        run_model is not None
        and hasattr(artifact_model, "run_id")
        and (workflow_model is not None or template_model is not None)
    ):
        return apply_run_related_scope(
            stmt,
            artifact_model.run_id,
            run_model,
            tenant_id=tenant_id,
            workflow_model=workflow_model,
            template_model=template_model,
        )

    scoped_stmt = apply_data_permission_if_needed(stmt, artifact_model)
    if scoped_stmt is not stmt or run_model is None:
        return scoped_stmt
    return apply_run_data_scope(
        stmt,
        run_model,
        tenant_id=tenant_id,
        workflow_model=workflow_model,
        template_model=template_model,
    )


def apply_tenant_workflow_scope(
    stmt: Any,
    workflow_model: type,
    tenant_id: int | None,
    *,
    workflow_id_column: Any | None = None,
) -> Any:
    """
    按租户流程所有权应用数据范围 / Apply tenant-workflow based scope.

    `workflow_model` 应为租户流程模型，`workflow_id_column` 为运行态记录上的 workflow_id 列。
    `workflow_model` should be the tenant workflow model, and `workflow_id_column`
    should be the runtime record's workflow_id column when filtering related tables.
    """
    if tenant_id is None:
        return stmt

    if workflow_id_column is None:
        if hasattr(workflow_model, "tenant_id"):
            stmt = stmt.where(workflow_model.tenant_id == tenant_id)
        return apply_data_permission_if_needed(stmt, workflow_model)

    return apply_parent_model_scope(
        stmt,
        workflow_model,
        workflow_id_column,
        tenant_id=tenant_id,
    )
