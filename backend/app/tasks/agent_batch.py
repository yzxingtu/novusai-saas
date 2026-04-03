"""
Agent batch processing Celery task / 智能体批处理 Celery 任务

Asynchronously executes batch requests, processing items one by one
and updating BatchRun progress in real time.
异步执行批量请求，逐项处理并实时更新 BatchRun 进度

Note: In Celery Worker (Windows --pool=solo), asyncio.new_event_loop()
between retries invalidates the module-level async_session_factory's event loop.
Therefore, an independent async engine + session must be created on each task call.
注意：Celery Worker (Windows --pool=solo) 中，asyncio.new_event_loop() 在 retries 之间
会导致模块级 async_session_factory 绑定的 event loop 失效。
因此必须在每次任务调用时创建独立的 async engine + session。
"""

import asyncio

from app.core.base_model import utc_now
from app.core.logging import LogManager
from app.tasks.async_db import task_async_session as _task_async_session
from app.tasks.base import BaseTask, register_task

logger = LogManager.get_logger("task")


@register_task(
    queue="ai_gateway",
    description="Execute agent batch processing / 执行智能体批处理",
    max_retries=1,
)
def execute_batch_run(self: BaseTask, batch_run_id: int, tenant_id: int) -> dict:
    """
    Celery async batch execution / Celery 异步执行批处理

    1. Load BatchRun + Agent from DB / 从 DB 加载 BatchRun + Agent
    2. Iterate items, call TaskEngine.execute() for each / 遍历 items，逐项调用 TaskEngine.execute()
    3. Update BatchRun.completed_items / failed_items in real time / 实时更新 BatchRun.completed_items / failed_items
    4. Update status and completed_at after all done / 全部完成后更新 status 和 completed_at

    Args:
        batch_run_id: Batch run ID / 批量运行 ID
        tenant_id: Tenant ID / 企业 ID

    Returns:
        Execution summary / 执行摘要
    """

    async def _execute() -> dict:
        from app.ai.engine.task import TaskEngine
        from app.ai.engine.types import ExecutionRequest
        from app.ai.gateway import AIGateway
        from app.ai.tools.sandbox import SandboxConfig, ToolSandbox
        from app.enums.agent import AgentExecutionModeEnum, BatchRunStatusEnum
        from app.models.ai.batch_run import BatchRun
        from app.repositories.ai.agent_repository import AgentRepository

        async with _task_async_session() as db:
            try:
                # 1. Load BatchRun / 加载 BatchRun
                from sqlalchemy import select

                stmt = select(BatchRun).where(BatchRun.id == batch_run_id)
                result = await db.execute(stmt)
                batch_run = result.scalar_one_or_none()

                if not batch_run:
                    logger.error("BatchRun {} not found", batch_run_id)
                    return {"error": "BatchRun not found"}

                # Check if already cancelled / 检查是否已取消
                if batch_run.status == BatchRunStatusEnum.CANCELLED.value:
                    return {"status": "cancelled"}

                # 2. Load Agent / 加载 Agent
                agent_repo = AgentRepository(db, tenant_id)
                agent = await agent_repo.get_by_id(batch_run.agent_id)
                if not agent:
                    batch_run.status = BatchRunStatusEnum.FAILED.value
                    batch_run.completed_at = utc_now()
                    await db.commit()
                    return {"error": "Agent not found"}

                # 3. Mark as running / 标记为运行中
                batch_run.status = BatchRunStatusEnum.RUNNING.value
                batch_run.started_at = utc_now()
                await db.commit()

                # 4. Resolve skill bindings + read platform security config / 解析技能绑定 + 读取平台安全配置
                gateway = AIGateway(db)

                # Immutable billing context for batch (tenant admin–initiated) / 批处理计费归属快照
                from app.enums.common import UserRoleEnum
                from app.services.ai.agent_service import AgentService

                _batch_user_role = UserRoleEnum.TENANT_ADMIN.value
                _batch_billing_ctx = await AgentService(
                    db,
                    tenant_id,
                ).build_usage_attribution_context(
                    agent=agent,
                    user_id=batch_run.created_by,
                    user_role=_batch_user_role,
                    user_role_id=None,
                )

                # Resolve skills bound to Agent / 解析 Agent 绑定的技能
                try:
                    from app.ai.skills.resolver import resolve_for_agent

                    await resolve_for_agent(
                        db,
                        agent,
                        tenant_id=tenant_id,
                        user_role=_batch_user_role,
                    )
                except Exception as skill_exc:
                    logger.warning(
                        "Batch {}: skill resolution failed: {}",
                        batch_run_id,
                        str(skill_exc),
                    )

                # Read platform Toolkit security config / 读取平台 Toolkit 安全配置
                from app.configs.service import ConfigService

                _cfg = ConfigService(db)
                _toolkit_security_level = str(
                    await _cfg.get_platform_config(
                        "toolkit_security_level", default="normal"
                    )
                )
                _toolkit_memory_limit_mb = int(
                    await _cfg.get_platform_config(
                        "toolkit_memory_limit_mb", default=256
                    )
                )

                sandbox = ToolSandbox(
                    tenant_id=tenant_id,
                    agent_id=agent.id,
                    config=SandboxConfig(),
                    gateway=gateway,
                    db=db,
                    agent=agent,
                    toolkit_security_level=_toolkit_security_level,
                    toolkit_memory_limit_mb=_toolkit_memory_limit_mb,
                )
                task_engine = TaskEngine(
                    db=db,
                    gateway=gateway,
                    sandbox=sandbox,
                )

                # 5. Execute items one by one / 逐项执行
                items = batch_run.input_items or []
                succeeded = 0
                failed = 0
                all_results: list[dict] = []
                all_errors: list[dict] = []

                for idx, item_data in enumerate(items):
                    # Check cancellation flag / 检查取消标志
                    await db.refresh(batch_run, ["status"])
                    if batch_run.status == BatchRunStatusEnum.CANCELLED.value:
                        logger.info(
                            "Batch {} cancelled at item {}/{}",
                            batch_run_id,
                            idx,
                            len(items),
                        )
                        break

                    item_id = item_data.get("item_id", str(idx))
                    input_vars = item_data.get("input_variables", {})

                    try:
                        item_request = ExecutionRequest(
                            agent_id=agent.id,
                            tenant_id=tenant_id,
                            input_variables=input_vars,
                            execution_mode=AgentExecutionModeEnum.TASK.value,
                            stream=False,
                            skip_quota=True,
                            skip_persistence=True,
                            user_role=_batch_user_role,
                            billing_context=_batch_billing_ctx,
                        )

                        exec_result = await task_engine.execute(
                            agent,
                            item_request,
                        )

                        if exec_result.success:
                            succeeded += 1
                            all_results.append(
                                {
                                    "item_id": item_id,
                                    "output": exec_result.output,
                                    "total_tokens": exec_result.total_tokens,
                                }
                            )
                        else:
                            failed += 1
                            all_errors.append(
                                {
                                    "item_id": item_id,
                                    "error": exec_result.error,
                                }
                            )

                    except Exception as exc:
                        failed += 1
                        all_errors.append(
                            {
                                "item_id": item_id,
                                "error": str(exc),
                            }
                        )
                        logger.error(
                            "Batch item {} failed: {}",
                            item_id,
                            str(exc),
                            exc_info=True,
                        )

                    # Update progress in real time / 实时更新进度
                    batch_run.completed_items = succeeded
                    batch_run.failed_items = failed
                    await db.commit()

                    # Socket.IO real-time progress push / Socket.IO 实时进度推送
                    try:
                        from app.core.sio_bridge import notify_user_sync

                        if batch_run.created_by:
                            percent = int((idx + 1) / len(items) * 100)
                            notify_user_sync(
                                "tenant_admin",
                                batch_run.created_by,
                                {
                                    "type": "ai.batch_progress",
                                    "category": "ai",
                                    "title": f"Batch {batch_run_id}: {idx + 1}/{len(items)}",
                                    "data": {
                                        "batch_id": batch_run_id,
                                        "current": idx + 1,
                                        "total": len(items),
                                        "percent": percent,
                                        "succeeded": succeeded,
                                        "failed": failed,
                                    },
                                    "priority": "normal",
                                },
                            )
                    except Exception:
                        pass

                # 6. Final status update / 最终状态更新
                if batch_run.status != BatchRunStatusEnum.CANCELLED.value:
                    if failed == 0:
                        batch_run.status = BatchRunStatusEnum.COMPLETED.value
                    elif succeeded == 0:
                        batch_run.status = BatchRunStatusEnum.FAILED.value
                    else:
                        batch_run.status = BatchRunStatusEnum.PARTIAL_FAILED.value

                batch_run.completed_items = succeeded
                batch_run.failed_items = failed
                batch_run.results = all_results
                batch_run.errors = all_errors if all_errors else None
                batch_run.completed_at = utc_now()
                await db.commit()

                # Socket.IO completion/failure notification / Socket.IO 完成/失败通知
                try:
                    from app.core.sio_bridge import notify_user_sync

                    if batch_run.created_by:
                        event_type = (
                            "ai.batch_complete" if failed == 0 else "ai.batch_failed"
                        )
                        priority = "normal" if failed == 0 else "high"
                        notify_user_sync(
                            "tenant_admin",
                            batch_run.created_by,
                            {
                                "type": event_type,
                                "category": "ai",
                                "title": f"Batch {batch_run_id}: {succeeded}/{len(items)} succeeded",
                                "data": {
                                    "batch_id": batch_run_id,
                                    "total": len(items),
                                    "succeeded": succeeded,
                                    "failed": failed,
                                    "status": batch_run.status,
                                },
                                "priority": priority,
                            },
                        )
                except Exception:
                    pass

                logger.info(
                    "Batch {} done: {}/{} succeeded, {} failed",
                    batch_run_id,
                    succeeded,
                    len(items),
                    failed,
                )

                return {
                    "batch_run_id": batch_run_id,
                    "total": len(items),
                    "succeeded": succeeded,
                    "failed": failed,
                    "status": batch_run.status,
                }

            except Exception as exc:
                logger.error(
                    "Batch {} execution error: {}",
                    batch_run_id,
                    str(exc),
                    exc_info=True,
                )
                # Update to failed / 更新为失败
                try:
                    batch_run.status = BatchRunStatusEnum.FAILED.value
                    batch_run.completed_at = utc_now()
                    await db.commit()
                except Exception:
                    pass
                return {"error": str(exc)}

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_execute())
    finally:
        loop.close()


__all__ = ["execute_batch_run"]
