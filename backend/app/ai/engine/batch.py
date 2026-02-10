"""
批量执行引擎

串行处理多个 BatchItem，每个 item 独立执行，单个失败不影响其他
"""

import time

from app.core.logging import LogManager
from app.enums.agent import AgentExecutionModeEnum, BatchRunStatusEnum
from app.models.ai.agent import Agent

from .base import BaseEngine
from .task import TaskEngine
from .types import BatchItem, BatchResult, ExecutionRequest, ExecutionResult

logger = LogManager.get_logger("ai.engine.batch")


class BatchEngine(BaseEngine):
    """
    批量执行引擎

    内部复用 TaskEngine 逐项处理，每项独立：
    1. 遍历所有 BatchItem
    2. 为每项构造独立的 ExecutionRequest
    3. 通过 TaskEngine 执行
    4. 记录每项状态，汇总结果
    """

    async def execute(self, agent: Agent, request: ExecutionRequest) -> ExecutionResult:
        """
        execute 仅用于满足 BaseEngine 接口。
        批量执行应使用 execute_batch()。
        """
        from app.core.i18n import _

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
        批量执行

        Args:
            agent: 智能体
            request: 基础执行请求（含 tenant_id, user_id 等公共参数）
            items: 批量项目列表

        Returns:
            BatchResult 汇总结果
        """
        start = time.perf_counter()

        # 复用 TaskEngine
        task_engine = TaskEngine(
            db=self.db,
            gateway=self.gateway,
            sandbox=self.sandbox,
        )

        succeeded = 0
        failed = 0

        for item in items:
            try:
                # 构造独立请求
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
                    "Batch item %s failed: %s",
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
