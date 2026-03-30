"""
Execution Dispatcher / 执行分发器

Routes to corresponding engine based on execution_mode,
orchestrates concurrency control, quota checks, and hook triggers.
根据 execution_mode 路由到对应引擎，编排并发控制、配额检查和钩子触发。
"""

import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent_quota import (
    AgentConcurrencyExceeded,
    AgentConcurrencyLimiter,
    AgentQuotaConfig,
    AgentQuotaExceeded,
    AgentQuotaManager,
)
from app.ai.events.hooks import HookPoint, get_hook_registry
from app.ai.skills.resolver import resolve_for_agent
from app.ai.tools.sandbox import SandboxConfig, ToolSandbox
from app.ai.utils.token_estimator import estimate_tokens
from app.configs.service import PLATFORM_TENANT_ID
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import build_public_error_text
from app.enums.agent import AgentExecutionModeEnum, AgentStatusEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent import Agent
from app.repositories.ai.agent_repository import AgentRepository

from .base import BaseEngine
from .conversation import ConversationEngine
from .task import TaskEngine
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
                    raise BusinessException(
                        message=_("agent.error.not_published")
                    )

            # Load quota config from agent / 从 agent 加载配额配置
            quota_config = AgentQuotaConfig.from_dict(agent.quota_config)

            # 2. Concurrency control / 并发控制
            if quota_config.max_concurrent > 0 or quota_config.tenant_max_concurrent > 0:
                lock_token = await AgentConcurrencyLimiter.acquire(
                    tenant_id=request.tenant_id,
                    agent_id=agent.id,
                    max_concurrent=quota_config.max_concurrent,
                    tenant_max_concurrent=quota_config.tenant_max_concurrent,
                )

            # 3. Quota check (API mode skipped, caller responsible) / 配额检查（API 模式跳过，由调用方负责）
            if not request.skip_quota:
                # Estimate input tokens for atomic pre-deduction, prevents exceeding under high concurrency
                # 估算输入 Token 以启用原子预扣减，防止高并发下超限
                estimated = 0
                if request.messages:
                    estimated = sum(
                        estimate_tokens(m.content or "")
                        for m in request.messages
                    )
                # At least 100 tokens estimate (system prompt + generation overhead) / 至少预估 100 tokens（system prompt + 生成开销）
                estimated = max(estimated, 100)

                await AgentQuotaManager.check_quota(
                    tenant_id=request.tenant_id,
                    agent_id=agent.id,
                    config=quota_config,
                    estimated_tokens=estimated,
                )

                # 3.5 User-level quota check / 用户级配额检查
                if request.user_id:
                    await AgentQuotaManager.check_user_quota(
                        tenant_id=request.tenant_id,
                        agent_id=agent.id,
                        user_id=request.user_id,
                        config=quota_config,
                    )

                # 3.6 Plan monthly API call quota check / 套餐月 API 调用次数配额检查
                if request.tenant_id:
                    from app.enums import ErrorCode
                    from app.services.tenant.quota_service import QuotaService
                    api_check = await QuotaService.check_api_quota_for_tenant_id(
                        self.db, request.tenant_id
                    )
                    if not api_check.allowed:
                        raise BusinessException(
                            message=api_check.message or _("quota.api_calls_exceeded"),
                            code=ErrorCode.CONFLICT,
                        )

            # 4. BEFORE_EXECUTE hook / BEFORE_EXECUTE 钩子
            hook_registry = get_hook_registry()
            hook_context = await hook_registry.trigger(
                HookPoint.BEFORE_EXECUTE,
                tenant_id=request.tenant_id,
                agent_id=agent.id,
                execution_mode=request.execution_mode,
                request=request,
            )

            # Hook can block execution / 钩子可阻止执行
            if hook_context.get("blocked"):
                reason = hook_context.get("block_reason", _("agent.error.blocked_by_hook"))
                return ExecutionResult(success=False, error=reason)

            # 4.5 Publish ExecutionStarted event / 发布 ExecutionStarted 事件
            await BaseEngine._publish_execution_started(request, agent)

            # 5. Resolve Skills (done at Dispatcher layer, not inside Engine DB queries) / 解析 Skill（在 Dispatcher 层完成，不在 Engine 内部查 DB）
            skill_result = await resolve_for_agent(
                self.db, agent,
                tenant_id=request.tenant_id,
                user_role=request.user_role,
            )

            # 5.5 Load platform Toolkit security config (consistent with stream_chat path) / 读取平台 Toolkit 安全配置（与 stream_chat 路径保持一致）
            from app.configs.service import ConfigService
            _cfg = ConfigService(self.db)
            _toolkit_security_level = str(await _cfg.get_platform_config(
                "toolkit_security_level", default="normal",
            ))
            _toolkit_memory_limit_mb = int(await _cfg.get_platform_config(
                "toolkit_memory_limit_mb", default=256,
            ))

            # 6. Create Engine and execute / 创建 Engine 并执行
            engine = self._create_engine(
                agent, request,
                toolkit_security_level=_toolkit_security_level,
                toolkit_memory_limit_mb=_toolkit_memory_limit_mb,
            )
            result = await engine.execute(agent, request, skill_result=skill_result)

            # 6. AFTER_EXECUTE hook / AFTER_EXECUTE 钩子
            await hook_registry.trigger(
                HookPoint.AFTER_EXECUTE,
                tenant_id=request.tenant_id,
                agent_id=agent.id,
                result=result,
            )

            # 7. Adjust quota usage: from estimated to actual (API mode skipped) / 调整配额用量：从预估调整为实际（API 模式跳过）
            if not request.skip_quota:
                actual_tokens = result.total_tokens or 0
                await AgentQuotaManager.adjust_usage(
                    tenant_id=request.tenant_id,
                    agent_id=agent.id,
                    estimated_tokens=estimated,
                    actual_tokens=actual_tokens,
                    config=quota_config,
                )
                # Record user-level usage / 记录用户级用量
                if request.user_id:
                    await AgentQuotaManager.record_user_usage(
                        tenant_id=request.tenant_id,
                        agent_id=agent.id,
                        user_id=request.user_id,
                        tokens=result.total_tokens,
                    )

            # 8. Publish events / 发布事件
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
                "Execution dispatch failed: agent={} error={}",
                request.agent_id,
                str(exc),
                exc_info=True,
            )

            # Rollback pre-deducted quota (release pre-deducted estimated_tokens on failure) / 回滚预扣配额（执行失败时释放已预扣的 estimated_tokens）
            if not request.skip_quota and estimated > 0:
                try:
                    await AgentQuotaManager.adjust_usage(
                        tenant_id=request.tenant_id,
                        agent_id=request.agent_id,
                        estimated_tokens=estimated,
                        actual_tokens=0,
                        config=quota_config,
                    )
                except Exception as rollback_exc:
                    logger.warning(
                        "Quota rollback failed: agent={} error={}",
                        request.agent_id, rollback_exc,
                    )

            if agent:
                public_error = build_public_error_text(
                    message=_("common.server_error"),
                    exc=exc,
                )
                await BaseEngine._publish_execution_failed(
                    request, agent, public_error, type(exc).__name__,
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
            raise BusinessException(
                message=_("agent.error.not_published"))

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

        # 4. Submit Celery async task / 提交 Celery 异步任务
        from app.tasks.agent_batch import execute_batch_run
        celery_result = execute_batch_run.delay(
            batch_run_id=batch_run.id,
            tenant_id=request.tenant_id,
        )

        # Save celery_task_id via Repository / 通过 Repository 保存 celery_task_id
        await batch_repo.update(batch_run.id, {
            "celery_task_id": celery_result.id,
        })
        await self.db.commit()

        logger.info(
            "Batch submitted: batch_run_id={} agent={} items={} celery_task={}",
            batch_run.id, agent.id, len(items), celery_result.id,
        )

        # 5. Return immediately (non-blocking) / 立即返回（非阻塞）
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
        toolkit_security_level: str = "normal",
        toolkit_memory_limit_mb: int = 256,
    ) -> BaseEngine:
        """Create corresponding engine based on execution mode / 根据执行模式创建对应引擎"""
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
            toolkit_security_level=toolkit_security_level,
            toolkit_memory_limit_mb=toolkit_memory_limit_mb,
            input_variables=request.input_variables,
            page_session_id=request.page_session_id,
            conversation_id=request.conversation_id,
            trust_policy_ref=request.trust_policy_ref,
        )
        # Pass frontend session-level authorization / 传递前端会话级授权
        if request.consented_actions:
            sandbox.consented_actions = set(request.consented_actions)

        mode = request.execution_mode

        # API mode auto-sets control flags / API 模式自动设置控制标志
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

        # batch mode handled by dispatch_batch() / batch 模式由 dispatch_batch() 处理
        # fallback default: conversation / fallback 默认 conversation
        return ConversationEngine(
            db=self.db,
            gateway=gateway,
            sandbox=sandbox,
        )


__all__ = ["ExecutionDispatcher"]
