"""
智能体批处理 Celery 任务

异步执行批量请求，逐项处理并实时更新 BatchRun 进度
"""

import asyncio

from app.core.logging import LogManager
from app.tasks.base import register_task, BaseTask
from app.core.base_model import utc_now

logger = LogManager.get_logger("task")


@register_task(
    queue="ai_gateway",
    description="执行智能体批处理",
    max_retries=1,
)
def execute_batch_run(self: BaseTask, batch_run_id: int, tenant_id: int) -> dict:
    """
    Celery 异步执行批处理

    1. 从 DB 加载 BatchRun + Agent
    2. 遍历 items，逐项调用 TaskEngine.execute()
    3. 实时更新 BatchRun.completed_items / failed_items
    4. 全部完成后更新 status 和 completed_at

    Args:
        batch_run_id: 批量运行 ID
        tenant_id: 租户 ID

    Returns:
        执行摘要
    """

    async def _execute() -> dict:
        from app.core.database import async_session_factory
        from app.ai.engine.types import ExecutionRequest
        from app.ai.engine.task import TaskEngine
        from app.ai.gateway import AIGateway
        from app.ai.tools.sandbox import SandboxConfig, ToolSandbox
        from app.enums.agent import AgentExecutionModeEnum, BatchRunStatusEnum
        from app.models.ai.batch_run import BatchRun
        from app.repositories.ai.agent_repository import AgentRepository

        async with async_session_factory() as db:
            try:
                # 1. 加载 BatchRun
                from sqlalchemy import select
                stmt = select(BatchRun).where(BatchRun.id == batch_run_id)
                result = await db.execute(stmt)
                batch_run = result.scalar_one_or_none()

                if not batch_run:
                    logger.error("BatchRun %d not found", batch_run_id)
                    return {"error": "BatchRun not found"}

                # 检查是否已取消
                if batch_run.status == BatchRunStatusEnum.CANCELLED.value:
                    return {"status": "cancelled"}

                # 2. 加载 Agent
                agent_repo = AgentRepository(db, tenant_id)
                agent = await agent_repo.get_by_id(batch_run.agent_id)
                if not agent:
                    batch_run.status = BatchRunStatusEnum.FAILED.value
                    batch_run.completed_at = utc_now()
                    await db.commit()
                    return {"error": "Agent not found"}

                # 3. 标记为运行中
                batch_run.status = BatchRunStatusEnum.RUNNING.value
                batch_run.started_at = utc_now()
                await db.commit()

                # 4. 创建引擎
                gateway = AIGateway(db)
                sandbox = ToolSandbox(
                    tenant_id=tenant_id,
                    agent_id=agent.id,
                    config=SandboxConfig(),
                )
                task_engine = TaskEngine(
                    db=db,
                    gateway=gateway,
                    sandbox=sandbox,
                )

                # 5. 逐项执行
                items = batch_run.input_items or []
                succeeded = 0
                failed = 0
                all_results: list[dict] = []
                all_errors: list[dict] = []

                for idx, item_data in enumerate(items):
                    # 检查取消标志
                    await db.refresh(batch_run, ["status"])
                    if batch_run.status == BatchRunStatusEnum.CANCELLED.value:
                        logger.info(
                            "Batch %d cancelled at item %d/%d",
                            batch_run_id, idx, len(items),
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
                        )

                        exec_result = await task_engine.execute(
                            agent, item_request,
                        )

                        if exec_result.success:
                            succeeded += 1
                            all_results.append({
                                "item_id": item_id,
                                "output": exec_result.output,
                                "total_tokens": exec_result.total_tokens,
                            })
                        else:
                            failed += 1
                            all_errors.append({
                                "item_id": item_id,
                                "error": exec_result.error,
                            })

                    except Exception as exc:
                        failed += 1
                        all_errors.append({
                            "item_id": item_id,
                            "error": str(exc),
                        })
                        logger.error(
                            "Batch item %s failed: %s",
                            item_id, str(exc),
                            exc_info=True,
                        )

                    # 实时更新进度
                    batch_run.completed_items = succeeded
                    batch_run.failed_items = failed
                    await db.commit()

                # 6. 最终状态更新
                if batch_run.status != BatchRunStatusEnum.CANCELLED.value:
                    if failed == 0:
                        batch_run.status = BatchRunStatusEnum.COMPLETED.value
                    elif succeeded == 0:
                        batch_run.status = BatchRunStatusEnum.FAILED.value
                    else:
                        batch_run.status = (
                            BatchRunStatusEnum.PARTIAL_FAILED.value
                        )

                batch_run.completed_items = succeeded
                batch_run.failed_items = failed
                batch_run.results = all_results
                batch_run.errors = all_errors if all_errors else None
                batch_run.completed_at = utc_now()
                await db.commit()

                logger.info(
                    "Batch %d done: %d/%d succeeded, %d failed",
                    batch_run_id, succeeded, len(items), failed,
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
                    "Batch %d execution error: %s",
                    batch_run_id, str(exc),
                    exc_info=True,
                )
                # 更新为失败
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
