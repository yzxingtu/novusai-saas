"""
执行分发器

根据 execution_mode 路由到对应引擎，编排并发控制、配额检查和钩子触发
"""

import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent_quota import (
    AgentConcurrencyExceeded,
    AgentConcurrencyLimiter,
    AgentQuotaConfig,
    AgentQuotaExceeded,
    AgentQuotaManager,
)
from app.ai.events.hooks import HookPoint, get_hook_registry
from app.ai.tools.sandbox import SandboxConfig, ToolSandbox
from app.ai.utils.token_estimator import estimate_tokens
from app.core.logging import LogManager
from app.enums.agent import AgentExecutionModeEnum, AgentStatusEnum
from app.exceptions import BusinessException, NotFoundException
from app.core.i18n import _
from app.models.ai.agent import Agent
from app.repositories.ai.agent_repository import AgentRepository

from .base import BaseEngine
from .batch import BatchEngine
from .conversation import ConversationEngine
from .task import TaskEngine
from .types import BatchItem, BatchResult, ExecutionRequest, ExecutionResult

logger = LogManager.get_logger("ai.engine.dispatcher")


class ExecutionDispatcher:
    """
    执行分发器

    完整执行编排：
    1. 加载并校验 Agent
    2. 并发控制 (acquire)
    3. 配额检查
    4. BEFORE_EXECUTE 钩子
    5. 路由到对应 Engine
    6. AFTER_EXECUTE 钩子
    7. 记录配额使用
    8. 释放并发 (release)
    9. 发布事件

    使用示例:
        dispatcher = ExecutionDispatcher(db)
        result = await dispatcher.dispatch(request)
    """

    def __init__(
        self,
        db: AsyncSession,
        sandbox_config: SandboxConfig | None = None,
    ):
        """
        Args:
            db: 数据库会话
            sandbox_config: 沙箱配置
        """
        self.db = db
        self.sandbox_config = sandbox_config or SandboxConfig()

    async def dispatch(
        self,
        request: ExecutionRequest,
    ) -> ExecutionResult:
        """
        分发执行请求

        Args:
            request: 执行请求

        Returns:
            ExecutionResult
        """
        start = time.perf_counter()
        agent: Agent | None = None
        lock_token: str = ""
        quota_config = AgentQuotaConfig()

        try:
            # 1. 加载 Agent
            agent_repo = AgentRepository(self.db, request.tenant_id)
            agent = await agent_repo.get_by_id(request.agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            if agent.status != AgentStatusEnum.PUBLISHED.value:
                raise BusinessException(
                    message=_("agent.error.not_published")
                )

            # 从 agent 加载配额配置
            quota_config = AgentQuotaConfig.from_dict(agent.quota_config)

            # 2. 并发控制
            if quota_config.max_concurrent > 0 or quota_config.tenant_max_concurrent > 0:
                lock_token = await AgentConcurrencyLimiter.acquire(
                    tenant_id=request.tenant_id,
                    agent_id=agent.id,
                    max_concurrent=quota_config.max_concurrent,
                    tenant_max_concurrent=quota_config.tenant_max_concurrent,
                )

            # 3. 配额检查（API 模式跳过，由调用方负责）
            if not request.skip_quota:
                # 估算输入 Token 以启用原子预扣减，防止高并发下超限
                estimated = 0
                if request.messages:
                    estimated = sum(
                        estimate_tokens(m.content or "")
                        for m in request.messages
                    )
                # 至少预估 100 tokens（system prompt + 生成开销）
                estimated = max(estimated, 100)

                await AgentQuotaManager.check_quota(
                    tenant_id=request.tenant_id,
                    agent_id=agent.id,
                    config=quota_config,
                    estimated_tokens=estimated,
                )

                # 3.5 用户级配额检查
                if request.user_id:
                    await AgentQuotaManager.check_user_quota(
                        tenant_id=request.tenant_id,
                        agent_id=agent.id,
                        user_id=request.user_id,
                        config=quota_config,
                    )

            # 4. BEFORE_EXECUTE 钩子
            hook_registry = get_hook_registry()
            hook_context = await hook_registry.trigger(
                HookPoint.BEFORE_EXECUTE,
                tenant_id=request.tenant_id,
                agent_id=agent.id,
                execution_mode=request.execution_mode,
                request=request,
            )

            # 钩子可阻止执行
            if hook_context.get("blocked"):
                reason = hook_context.get("block_reason", _("agent.error.blocked_by_hook"))
                return ExecutionResult(success=False, error=reason)

            # 4.5 发布 ExecutionStarted 事件
            await BaseEngine._publish_execution_started(request, agent)

            # 5. 创建 Engine 并执行
            engine = self._create_engine(agent, request)
            result = await engine.execute(agent, request)

            # 6. AFTER_EXECUTE 钩子
            await hook_registry.trigger(
                HookPoint.AFTER_EXECUTE,
                tenant_id=request.tenant_id,
                agent_id=agent.id,
                result=result,
            )

            # 7. 调整配额用量：从预估调整为实际（API 模式跳过）
            if not request.skip_quota:
                actual_tokens = result.total_tokens or 0
                await AgentQuotaManager.adjust_usage(
                    tenant_id=request.tenant_id,
                    agent_id=agent.id,
                    estimated_tokens=estimated,
                    actual_tokens=actual_tokens,
                    config=quota_config,
                )
                # 记录用户级用量
                if request.user_id:
                    await AgentQuotaManager.record_user_usage(
                        tenant_id=request.tenant_id,
                        agent_id=agent.id,
                        user_id=request.user_id,
                        tokens=result.total_tokens,
                    )

            # 8. 发布事件
            if result.success:
                await BaseEngine._publish_execution_completed(request, agent, result)
            else:
                await BaseEngine._publish_execution_failed(
                    request, agent, result.error,
                )

            return result

        except (NotFoundException, BusinessException):
            raise

        except (AgentQuotaExceeded, AgentConcurrencyExceeded):
            raise

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "Execution dispatch failed: agent=%s error=%s",
                request.agent_id,
                str(exc),
                exc_info=True,
            )

            if agent:
                await BaseEngine._publish_execution_failed(
                    request, agent, str(exc), type(exc).__name__,
                )

            return ExecutionResult(
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
            )

        finally:
            # 9. 释放并发
            if lock_token and agent:
                await AgentConcurrencyLimiter.release(
                    tenant_id=request.tenant_id,
                    agent_id=agent.id,
                    lock_token=lock_token,
                )

    async def dispatch_batch(
        self,
        request: ExecutionRequest,
        items: list[BatchItem],
        max_workers: int = 5,
        created_by: int | None = None,
    ) -> BatchResult:
        """
        分发批量执行请求（异步提交到 Celery）

        创建 BatchRun 记录后立即返回 batch_run_id，
        实际执行由 Celery Worker 异步完成。

        Args:
            request: 基础请求
            items: 批量项目列表
            max_workers: 最大并行度
            created_by: 创建者 ID

        Returns:
            BatchResult（含 batch_run_id，status=pending）
        """
        from app.enums.agent import BatchRunStatusEnum
        from app.repositories.ai.batch_run_repository import BatchRunRepository

        # 1. 校验 Agent
        agent_repo = AgentRepository(self.db, request.tenant_id)
        agent = await agent_repo.get_by_id(request.agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        if agent.status != AgentStatusEnum.PUBLISHED.value:
            raise BusinessException(
                message=_("agent.error.not_published"))

        # 2. 配额检查（批处理提交时检查一次）
        quota_config = AgentQuotaConfig.from_dict(agent.quota_config)
        await AgentQuotaManager.check_quota(
            tenant_id=request.tenant_id,
            agent_id=agent.id,
            config=quota_config,
        )

        # 3. 通过 Repository 创建 BatchRun 记录
        batch_repo = BatchRunRepository(self.db, request.tenant_id)
        input_snapshot = [
            {"item_id": item.item_id, "input_variables": item.input_variables}
            for item in items
        ]
        batch_run = await batch_repo.create({
            "agent_id": agent.id,
            "status": BatchRunStatusEnum.PENDING.value,
            "total_items": len(items),
            "completed_items": 0,
            "failed_items": 0,
            "max_workers": max_workers,
            "input_items": input_snapshot,
            "created_by": created_by,
        })

        # 4. 提交 Celery 异步任务
        from app.tasks.agent_batch import execute_batch_run
        celery_result = execute_batch_run.delay(
            batch_run_id=batch_run.id,
            tenant_id=request.tenant_id,
        )

        # 通过 Repository 保存 celery_task_id
        await batch_repo.update(batch_run.id, {
            "celery_task_id": celery_result.id,
        })
        await self.db.commit()

        logger.info(
            "Batch submitted: batch_run_id=%d agent=%d items=%d celery_task=%s",
            batch_run.id, agent.id, len(items), celery_result.id,
        )

        # 5. 立即返回（非阻塞）
        return BatchResult(
            batch_run_id=batch_run.id,
            items=items,
            total=len(items),
            succeeded=0,
            failed=0,
        )

    def _create_engine(
        self,
        agent: Agent,
        request: ExecutionRequest,
    ) -> BaseEngine:
        """根据执行模式创建对应引擎"""
        from app.ai.gateway import AIGateway

        gateway = AIGateway(self.db)
        sandbox = ToolSandbox(
            tenant_id=request.tenant_id,
            agent_id=agent.id,
            config=self.sandbox_config,
            user_id=request.user_id,
            user_role=request.user_role,
            permissions=request.permissions,
            gateway=gateway,
            db=self.db,
            agent=agent,
        )
        # 传递前端会话级授权
        if request.consented_actions:
            sandbox.consented_actions = set(request.consented_actions)

        mode = request.execution_mode

        # API 模式自动设置控制标志
        if mode == AgentExecutionModeEnum.API.value:
            request.skip_quota = True
            request.skip_persistence = True
            request.skip_logging = True

        if mode in (
            AgentExecutionModeEnum.CONVERSATION.value,
            AgentExecutionModeEnum.API.value,
        ):
            return ConversationEngine(
                db=self.db,
                gateway=gateway,
                sandbox=sandbox,
            )

        if mode == AgentExecutionModeEnum.TASK.value:
            return TaskEngine(
                db=self.db,
                gateway=gateway,
                sandbox=sandbox,
            )

        # batch 模式由 dispatch_batch() 处理
        # fallback 默认 conversation
        return ConversationEngine(
            db=self.db,
            gateway=gateway,
            sandbox=sandbox,
        )


__all__ = ["ExecutionDispatcher"]
