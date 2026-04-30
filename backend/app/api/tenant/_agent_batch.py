"""
企业端智能体批处理路由 / Tenant Agent Batch Processing Routes

提供批处理任务提交、进度查询、取消等接口
Provides batch task submission, progress query, and cancellation endpoints
"""

from fastapi import APIRouter, Request

from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.exceptions import NotFoundException
from app.rbac.decorators import action_create, action_read, action_update
from app.schemas.ai.batch_run import BatchRunCreate, BatchRunResponse

router = APIRouter()


def _sanitize_batch_input_variables(item_data: dict) -> dict:
    sanitized = dict(item_data or {})
    sanitized.pop("page_context", None)
    sanitized.pop("page_session_id", None)
    return sanitized


@router.post("/{agent_id}/batch", summary="提交批处理任务", status_code=202)
@action_create("action.agent.batch_submit")
async def submit_batch(
    request: Request,
    db: DbSession,
    agent_id: int,
    data: BatchRunCreate,
    tenant_admin: ActiveTenantAdmin,
):
    """
    提交智能体批处理任务 / Submit agent batch processing task

    立即返回 batch_run_id，实际执行由 Celery Worker 异步完成。
    Returns batch_run_id immediately, actual execution is done asynchronously by Celery Worker.
    通过 GET /{agent_id}/batch/{run_id} 查询进度。
    Query progress via GET /{agent_id}/batch/{run_id}.

    权限 / Permission: agent:batch_submit
    """
    from app.api.tenant.agents import _ensure_tenant_owned_agent

    await _ensure_tenant_owned_agent(db, tenant_admin.tenant_id, agent_id)

    from app.ai.engine.dispatcher import ExecutionDispatcher
    from app.ai.engine.types import BatchItem, ExecutionRequest
    from app.enums.agent import AgentExecutionModeEnum

    # 构建 BatchItem 列表 / Build BatchItem list
    items = [
        BatchItem(
            item_id=str(idx),
            input_variables=_sanitize_batch_input_variables(item_data),
        )
        for idx, item_data in enumerate(data.items)
    ]

    exec_request = ExecutionRequest(
        agent_id=agent_id,
        tenant_id=tenant_admin.tenant_id,
        user_id=tenant_admin.id,
        execution_mode=AgentExecutionModeEnum.BATCH.value,
    )

    dispatcher = ExecutionDispatcher(db)
    result = await dispatcher.dispatch_batch(
        request=exec_request,
        items=items,
        max_workers=data.max_workers,
        created_by=tenant_admin.id,
    )

    return success(
        data={
            "batch_run_id": result.batch_run_id,
            "total": result.total,
            "status": "pending",
        }
    )


@router.get("/{agent_id}/batch/{run_id}", summary="查询批处理进度")
@action_read("action.agent.batch_progress")
async def get_batch_progress(
    request: Request,
    db: DbSession,
    agent_id: int,
    run_id: int,
    tenant_admin: ActiveTenantAdmin,
):
    """
    查询批处理进度和结果 / Query batch processing progress and results

    权限 / Permission: agent:batch_progress
    """
    from app.services.ai.batch_run_service import BatchRunService

    batch_svc = BatchRunService(db, tenant_admin.tenant_id)
    batch_run = await batch_svc.get_agent_batch_run(agent_id, run_id)
    if not batch_run:
        raise NotFoundException(
            message=_("agent.error.batch_run_not_found"),
        )

    return success(
        data=BatchRunResponse.model_validate(
            batch_run,
            from_attributes=True,
        ).model_dump()
    )


@router.post(
    "/{agent_id}/batch/{run_id}/cancel",
    summary="取消批处理任务",
)
@action_update("action.agent.batch_cancel")
async def cancel_batch(
    request: Request,
    db: DbSession,
    agent_id: int,
    run_id: int,
    tenant_admin: ActiveTenantAdmin,
):
    """
    取消批处理任务 / Cancel batch processing task

    将 BatchRun 状态设为 cancelled，worker 会在下一项开始前检测并停止。
    Sets BatchRun status to cancelled, worker will detect and stop before starting next item.
    权限 / Permission: agent:batch_cancel
    """
    from app.api.tenant.agents import _ensure_tenant_owned_agent

    await _ensure_tenant_owned_agent(db, tenant_admin.tenant_id, agent_id)

    from app.services.ai.batch_run_service import BatchRunService

    batch_svc = BatchRunService(db, tenant_admin.tenant_id)
    await batch_svc.cancel_batch_run(agent_id, run_id)
    await db.commit()

    return success(message=_("agent.batch.cancelled"))
