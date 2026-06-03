"""
Execution Dispatcher / 执行分发器

Routes to corresponding engine based on execution_mode,
orchestrates concurrency control, quota checks, and hook triggers.
根据 execution_mode 路由到对应引擎，编排并发控制、配额检查和钩子触发。
"""

import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent_quota_config import AgentQuotaConfig
from app.ai.agent_quota_exceptions import (
    AgentConcurrencyExceeded,
    AgentQuotaExceeded,
)
from app.ai.agent_quota_manager import AgentQuotaManager
from app.ai.tools.sandbox import SandboxConfig
from app.configs.service import PLATFORM_TENANT_ID
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import build_public_error_text
from app.enums.agent import AgentStatusEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent import Agent
from app.repositories.ai.agent_repository import AgentRepository

from .base import BaseEngine
from .engine_bootstrap_support import build_engine_bootstrap_bundle
from .execution_postflight_support import (
    apply_execution_result_postflight,
    default_execution_postflight_dependencies,
    publish_failed_execution_postflight,
    release_execution_postflight_lock,
    rollback_execution_postflight_usage,
)
from .execution_preflight_support import (
    acquire_preflight_lock,
    apply_execution_mode_runtime_flags,
    check_preflight_quota,
    estimate_preflight_tokens,
    trigger_before_execute_preflight,
)
from .types import BatchItem, BatchResult, ExecutionRequest, ExecutionResult

logger = LogManager.get_logger("ai.engine.dispatcher")


class ExecutionDispatcher:
    """
    Execution Dispatcher / 执行分发器

    Full execution orchestration / 完整执行编排：
    1. Load and validate Agent / 加载并校验 Agent
    2. Concurrency control (acquire) / 并发控制 (acquire)
    3. Quota check / 配额检查
    4. BEFORE_EXECUTE hook / BEFORE_EXECUTE 钩子
    5. Route to corresponding Engine / 路由到对应 Engine
    6. AFTER_EXECUTE hook / AFTER_EXECUTE 钩子
    7. Record quota usage / 记录配额使用
    8. Release concurrency (release) / 释放并发 (release)
    9. Publish events / 发布事件

    Usage / 使用示例::

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
            db: Database session / 数据库会话
            sandbox_config: Sandbox config / 沙箱配置
        """
        self.db = db
        self.sandbox_config = sandbox_config or SandboxConfig()

    async def dispatch(
        self,
        request: ExecutionRequest,
        pre_loaded_agent: Agent | None = None,
    ) -> ExecutionResult:
        """
        Dispatch execution request.
        分发执行请求。

        Args:
            request: Execution request / 执行请求
            pre_loaded_agent: Pre-validated Agent instance from caller (optional).
                If provided, skips DB load to avoid double query;
                caller must ensure existence + published status validation.
                调用方已校验的 Agent 实例（可选）。
                若提供则跳过 DB 加载，避免双重查询；
                调用方须保证已做存在性 + 发布状态校验。

        Returns:
            ExecutionResult
        """
        start = time.perf_counter()
        agent: Agent | None = None
        lock_token: str = ""
        estimated: int = 0
        quota_config = AgentQuotaConfig()
        postflight_dependencies = default_execution_postflight_dependencies()

        try:
            # 1. Load Agent (use pre-loaded if provided, avoid double DB query) / 加载 Agent（若调用方已预加载则直接使用，避免双重 DB 查询）
            if pre_loaded_agent is not None:
                agent = pre_loaded_agent
            else:
                if request.tenant_id == PLATFORM_TENANT_ID:
                    from app.repositories.ai.agent_repository import (
                        AdminAgentRepository,
                    )

                    agent_repo = AdminAgentRepository(self.db)
                else:
                    agent_repo = AgentRepository(self.db, request.tenant_id)
                agent = await agent_repo.get_by_id(request.agent_id)
                if not agent:
                    raise NotFoundException(message=_("agent.error.not_found"))

                if agent.status != AgentStatusEnum.PUBLISHED.value:
                    raise BusinessException(message=_("agent.error.not_published"))

            # Load quota config from agent / 从 agent 加载配额配置
            quota_config = AgentQuotaConfig.from_dict(agent.quota_config)
            apply_execution_mode_runtime_flags(request)

            # 2. Concurrency control / 并发控制
            lock_token = await acquire_preflight_lock(
                tenant_id=request.tenant_id,
                agent_id=agent.id,
                quota_config=quota_config,
            )

            # 3. Quota check (API mode skipped, caller responsible) / 配额检查（API 模式跳过，由调用方负责）
            estimated = (
                estimate_preflight_tokens(request.messages)
                if not request.skip_quota
                else 0
            )
            await check_preflight_quota(
                db=self.db,
                request=request,
                agent_id=agent.id,
                quota_config=quota_config,
                estimated_tokens=estimated,
            )

            # 4. BEFORE_EXECUTE hook / BEFORE_EXECUTE 钩子
            hook_registry, hook_context = await trigger_before_execute_preflight(
                request=request,
                agent_id=agent.id,
            )

            # Hook can block execution / 钩子可阻止执行
            if hook_context.get("blocked"):
                reason = hook_context.get(
                    "block_reason", _("agent.error.blocked_by_hook")
                )
                return ExecutionResult(success=False, error=reason)

            # 4.5 Publish ExecutionStarted event / 发布 ExecutionStarted 事件
            await BaseEngine._publish_execution_started(request, agent)

            # 5. Build canonical runtime engine bundle / 构建 canonical runtime engine bundle
            engine_bundle = await build_engine_bootstrap_bundle(
                db=self.db,
                agent=agent,
                request=request,
                sandbox_config=self.sandbox_config,
                log=logger,
            )
            result = await engine_bundle.engine.execute(
                agent,
                request,
                skill_result=engine_bundle.skill_result,
            )
            await apply_execution_result_postflight(
                request=request,
                agent=agent,
                agent_id=agent.id,
                result=result,
                hook_registry=hook_registry,
                estimated_tokens=estimated,
                quota_config=quota_config,
                user_id=request.user_id,
                dependencies=postflight_dependencies,
            )

            return result

        except (NotFoundException, BusinessException):
            raise

        except (AgentQuotaExceeded, AgentConcurrencyExceeded):
            raise

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "Execution dispatch failed: agent={} error={}",
                request.agent_id,
                str(exc),
                exc_info=True,
            )

            # Rollback pre-deducted quota (release pre-deducted estimated_tokens on failure) / 回滚预扣配额（执行失败时释放已预扣的 estimated_tokens）
            try:
                await rollback_execution_postflight_usage(
                    request=request,
                    agent_id=request.agent_id,
                    estimated_tokens=estimated,
                    quota_config=quota_config,
                    dependencies=postflight_dependencies,
                )
            except Exception as rollback_exc:
                logger.warning(
                    "Quota rollback failed: agent={} error={}",
                    request.agent_id,
                    rollback_exc,
                )

            if agent:
                public_error = build_public_error_text(
                    message=_("common.server_error"),
                    exc=exc,
                )
                await publish_failed_execution_postflight(
                    request=request,
                    agent=agent,
                    error=public_error,
                    error_type=type(exc).__name__,
                    dependencies=postflight_dependencies,
                )

            return ExecutionResult(
                success=False,
                error=build_public_error_text(
                    message=_("common.server_error"),
                    exc=exc,
                ),
                duration_ms=duration_ms,
            )

        finally:
            # 9. Release concurrency / 释放并发
            if lock_token and agent:
                await release_execution_postflight_lock(
                    request=request,
                    agent_id=agent.id,
                    lock_token=lock_token,
                    dependencies=postflight_dependencies,
                )

    async def dispatch_batch(
        self,
        request: ExecutionRequest,
        items: list[BatchItem],
        max_workers: int = 5,
        created_by: int | None = None,
    ) -> BatchResult:
        """
        Dispatch batch execution request (async submit to Celery).
        分发批量执行请求（异步提交到 Celery）。

        Creates BatchRun record and returns batch_run_id immediately,
        actual execution done asynchronously by Celery Worker.
        创建 BatchRun 记录后立即返回 batch_run_id，
        实际执行由 Celery Worker 异步完成。

        Args:
            request: Base request / 基础请求
            items: Batch item list / 批量项目列表
            max_workers: Max parallelism / 最大并行度
            created_by: Creator ID / 创建者 ID

        Returns:
            BatchResult (with batch_run_id, status=pending) / BatchResult（含 batch_run_id，status=pending）
        """
        from app.enums.agent import BatchRunStatusEnum
        from app.repositories.ai.batch_run_repository import BatchRunRepository

        # 1. Validate Agent / 校验 Agent
        if request.tenant_id == PLATFORM_TENANT_ID:
            from app.repositories.ai.agent_repository import (
                AdminAgentRepository,
            )

            agent_repo = AdminAgentRepository(self.db)
        else:
            agent_repo = AgentRepository(self.db, request.tenant_id)
        agent = await agent_repo.get_by_id(request.agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))

        if agent.status != AgentStatusEnum.PUBLISHED.value:
            raise BusinessException(message=_("agent.error.not_published"))

        # 2. Quota check (checked once at batch submission) / 配额检查（批处理提交时检查一次）
        quota_config = AgentQuotaConfig.from_dict(agent.quota_config)
        await AgentQuotaManager.check_quota(
            tenant_id=request.tenant_id,
            agent_id=agent.id,
            config=quota_config,
        )

        # 3. Create BatchRun record via Repository / 通过 Repository 创建 BatchRun 记录
        batch_repo = BatchRunRepository(self.db, request.tenant_id)
        input_snapshot = [
            {"item_id": item.item_id, "input_variables": item.input_variables}
            for item in items
        ]
        batch_run = await batch_repo.create(
            {
                "agent_id": agent.id,
                "status": BatchRunStatusEnum.PENDING.value,
                "total_items": len(items),
                "completed_items": 0,
                "failed_items": 0,
                "max_workers": max_workers,
                "input_items": input_snapshot,
                "created_by": created_by,
            }
        )

        # 4. Submit Celery async task / 提交 Celery 异步任务
        from app.tasks.agent_batch import execute_batch_run

        celery_result = execute_batch_run.delay(
            batch_run_id=batch_run.id,
            tenant_id=request.tenant_id,
        )

        # Save celery_task_id via Repository / 通过 Repository 保存 celery_task_id
        await batch_repo.update(
            batch_run.id,
            {
                "celery_task_id": celery_result.id,
            },
        )
        await self.db.commit()

        logger.info(
            "Batch submitted: batch_run_id={} agent={} items={} celery_task={}",
            batch_run.id,
            agent.id,
            len(items),
            celery_result.id,
        )

        # 5. Return immediately (non-blocking) / 立即返回（非阻塞）
        return BatchResult(
            batch_run_id=batch_run.id,
            items=items,
            total=len(items),
            succeeded=0,
            failed=0,
        )


__all__ = ["ExecutionDispatcher"]
