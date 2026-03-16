"""
Batch Execution Engine / 批量执行引擎

Serially processes multiple BatchItems, each item executes independently,
single failure does not affect others.
串行处理多个 BatchItem，每个 item 独立执行，单个失败不影响其他。
"""

import time

from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import AgentExecutionModeEnum, BatchRunStatusEnum
from app.models.ai.agent import Agent

from .base import BaseEngine
from .task import TaskEngine
from .types import BatchItem, BatchResult, ExecutionRequest, ExecutionResult

logger = LogManager.get_logger("ai.engine.batch")


class BatchEngine(BaseEngine):
    """
    Batch Execution Engine / 批量执行引擎

    Internally reuses TaskEngine to process items one by one, each independent:
    内部复用 TaskEngine 逐项处理，每项独立：
    1. Iterate all BatchItems / 遍历所有 BatchItem
    2. Construct independent ExecutionRequest for each / 为每项构造独立的 ExecutionRequest
    3. Execute via TaskEngine / 通过 TaskEngine 执行
    4. Record status per item, aggregate results / 记录每项状态，汇总结果
    """

    async def execute(self, agent: Agent, request: ExecutionRequest) -> ExecutionResult:
        """
        execute is only for satisfying BaseEngine interface. / execute 仅用于满足 BaseEngine 接口；批量执行应使用 execute_batch()。
        """
        logger.debug(
            "BatchEngine.execute is not supported: agent_id={} request_agent_id={}",
            getattr(agent, "id", None),
            getattr(request, "agent_id", None),
        )
        return ExecutionResult(
            success=False,
            error=_("agent.error.use_execute_batch"),
        )

    async def execute_batch(
        self,
        agent: Agent,
        request: ExecutionRequest,
        items: list[BatchItem],
    ) -> BatchResult:
        """
        Batch execution.
        批量执行。

        Args:
            agent: Agent / 智能体
            request: Base execution request (with tenant_id, user_id etc.) / 基础执行请求
            items: Batch item list / 批量项目列表

        Returns:
            BatchResult aggregated result / BatchResult 汇总结果
        """
        start = time.perf_counter()

        # Reuse TaskEngine / 复用 TaskEngine
        task_engine = TaskEngine(
            db=self.db,
            gateway=self.gateway,
            sandbox=self.sandbox,
        )

        succeeded = 0
        failed = 0

        for item in items:
            try:
                # Construct independent request / 构造独立请求
                item_request = ExecutionRequest(
                    agent_id=request.agent_id,
                    tenant_id=request.tenant_id,
                    user_id=request.user_id,
                    input_variables=item.input_variables,
                    execution_mode=AgentExecutionModeEnum.TASK.value,
                    stream=False,
                )

                result = await task_engine.execute(agent, item_request)
                item.result = result

                if result.success:
                    item.status = BatchRunStatusEnum.COMPLETED.value
                    succeeded += 1
                else:
                    item.status = BatchRunStatusEnum.FAILED.value
                    failed += 1

            except Exception as exc:
                logger.error(
                    "Batch item {} failed: {}",
                    item.item_id,
                    str(exc),
                    exc_info=True,
                )
                item.status = BatchRunStatusEnum.FAILED.value
                item.result = ExecutionResult(
                    success=False,
                    error=str(exc),
                )
                failed += 1

        duration_ms = int((time.perf_counter() - start) * 1000)

        return BatchResult(
            items=items,
            total=len(items),
            succeeded=succeeded,
            failed=failed,
            duration_ms=duration_ms,
        )


__all__ = ["BatchEngine"]
