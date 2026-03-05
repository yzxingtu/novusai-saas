"""
Text-to-SQL 工具执行器

串联 AI 数据智能完整安全链路：
1. TextToSQLGenerator: LLM 自然语言 → SQL
2. SQLSafetyValidator: 六重安全校验
3. TenantIsolationInjector: 自动注入 tenant_id
4. ReadOnlyExecutor: 只读连接执行
5. ResultFormatter: 结果格式化（number/chart/table）

需要 AIGateway 注入，在 ToolSandbox._init_executors() 中注册。
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

from app.ai.data_intelligence.readonly_executor import ReadOnlyExecutor
from app.ai.data_intelligence.result_formatter import ResultFormatter
from app.ai.data_intelligence.schema_provider import SchemaProvider
from app.ai.data_intelligence.sql_safety import SQLSafetyValidator
from app.ai.data_intelligence.tenant_isolation import (
    TenantIsolationError,
    TenantIsolationInjector,
)
from app.ai.data_intelligence.text_to_sql import (
    ConversationRound,
    TextToSQLGenerator,
)
from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.common import UserRoleEnum

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.ai.gateway import AIGateway
    from app.ai.tools.types import ExecutionContext
    from app.models.ai.agent import Agent

logger = LogManager.get_logger("ai.tool.text_to_sql")


class TextToSQLExecutor(BaseToolExecutor):
    """
    Text-to-SQL 工具执行器

    完整安全链路：
      LLM 生成 SQL → 安全校验 → 租户隔离注入 → 只读执行 → 结果格式化

    依赖：
    - AIGateway: 调用 LLM
    - AsyncSession: 获取 schema
    - Agent: 模型配置
    """

    def __init__(
        self,
        gateway: AIGateway,
        db: AsyncSession,
        agent: Agent | None = None,
    ):
        """
        Args:
            gateway: AI 网关
            db: 数据库会话
            agent: 智能体（可选，execute 时也可从 context 获取）
        """
        self.gateway = gateway
        self.db = db
        self.agent = agent
        self._generator = TextToSQLGenerator(gateway, db)
        self._schema_provider = SchemaProvider()
        self._readonly_executor = ReadOnlyExecutor()
        self._formatter = ResultFormatter()

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        """
        执行 Text-to-SQL 完整链路

        arguments:
            question: 用户的自然语言问题（必填）
            conversation_history: 多轮对话历史（可选，JSON 数组）

        Returns:
            ToolResult（output 为 JSON 格式的 FormattedResult）
        """
        start = time.perf_counter()

        question = arguments.get("question", "").strip()
        if not question:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("data_intelligence.executor.missing_question"),
            )

        tenant_id = context.tenant_id if context else 0
        user_role = context.user_role if context else UserRoleEnum.TENANT_ADMIN.value

        # platform_admin 可使用 tenant_id=0 查询平台级表
        if tenant_id is None or (not tenant_id and user_role != UserRoleEnum.PLATFORM_ADMIN.value):
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("data_intelligence.executor.missing_tenant"),
            )

        # 解析对话历史
        history = self._parse_conversation_history(
            arguments.get("conversation_history"),
        )

        # 提前提取权限信息（供 generator + schema 使用）
        user_permissions = context.permissions if context else set()

        _generated_sql: str | None = None
        _final_sql: str | None = None

        try:
            # 1. LLM 生成 SQL（含重试，RBAC 权限过滤可见表）
            generated = await self._generator.generate(
                question=question,
                tenant_id=tenant_id,
                agent=self.agent,
                conversation_history=history,
                permissions=user_permissions,
                user_role=user_role,
            )

            if not generated.success or not generated.sql:
                duration_ms = int((time.perf_counter() - start) * 1000)
                error_output = json.dumps(
                    {
                        "success": False,
                        "error": generated.error,
                        "explanation": generated.explanation,
                    },
                    ensure_ascii=False,
                )
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=False,
                    output=error_output,
                    error=generated.error,
                    duration_ms=duration_ms,
                )

            _generated_sql = generated.sql

            # 2. 获取 schema（按用户 RBAC 权限过滤可查表）
            schema = await self._schema_provider.get_schema(
                self.db, tenant_id,
                permissions=user_permissions,
                user_role=user_role,
            )

            if not schema:
                duration_ms = int((time.perf_counter() - start) * 1000)
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=False,
                    error=_("data_intelligence.executor.no_accessible_tables"),
                    duration_ms=duration_ms,
                )

            # 3. 租户隔离注入（按 user_role 决定隔离策略）
            user_id = context.user_id if context else None
            isolated_sql = TenantIsolationInjector.inject(
                generated.sql, tenant_id, schema,
                user_role=user_role,
                user_id=user_id,
            )

            # 4. LIMIT 注入
            final_sql = SQLSafetyValidator.inject_limit(isolated_sql)
            _final_sql = final_sql

            # 4.5 BEFORE_SQL_EXECUTE 钩子（插件可审计/修改 SQL、可阻止执行）
            from app.ai.events.hooks import HookPoint, get_hook_registry
            hook_registry = get_hook_registry()
            if hook_registry.has_hooks(HookPoint.BEFORE_SQL_EXECUTE):
                hook_ctx = await hook_registry.trigger(
                    HookPoint.BEFORE_SQL_EXECUTE,
                    tenant_id=tenant_id,
                    sql=final_sql,
                    datasource_id=None,
                )
                if hook_ctx.get("blocked"):
                    reason = hook_ctx.get("block_reason", _("data_intelligence.executor.blocked_by_hook"))
                    return ToolResult(
                        tool_call_id=tool_call_id,
                        name=definition.name,
                        success=False,
                        error=reason,
                    )
                final_sql = hook_ctx.get("sql", final_sql)
                _final_sql = final_sql

            # 5. 只读执行
            query_result = await self._readonly_executor.execute(final_sql)

            # 5.5 AFTER_SQL_EXECUTE 钩子（插件可过滤/脱敏结果）
            if hook_registry.has_hooks(HookPoint.AFTER_SQL_EXECUTE):
                hook_ctx = await hook_registry.trigger(
                    HookPoint.AFTER_SQL_EXECUTE,
                    tenant_id=tenant_id,
                    sql=final_sql,
                    rows=query_result.rows,
                    columns=query_result.columns,
                )
                query_result.rows = hook_ctx.get("rows", query_result.rows)

            # 6. 结果格式化
            formatted = self._formatter.format(query_result, generated)

            duration_ms = int((time.perf_counter() - start) * 1000)

            # 构建完整输出
            output = json.dumps(
                {
                    "success": True,
                    "sql": generated.sql,
                    "explanation": generated.explanation,
                    "confidence": generated.confidence,
                    "result": formatted.to_dict(),
                },
                ensure_ascii=False,
                default=str,
            )

            logger.info(
                "Text-to-SQL completed: tenant=%d question=%s "
                "rows=%d display=%s duration=%dms",
                tenant_id,
                question[:50],
                query_result.row_count,
                formatted.display_type,
                duration_ms,
            )

            # 审计日志（成功）
            await self._log_query(
                context=context,
                question=question,
                generated_sql=generated.sql,
                final_sql=final_sql,
                row_count=query_result.row_count,
                status="success",
                duration_ms=duration_ms,
                confidence=generated.confidence,
            )

            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=output,
                duration_ms=duration_ms,
            )

        except TenantIsolationError as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "Tenant isolation failed: %s", str(exc),
            )
            await self._log_query(
                context=context,
                question=question,
                status="rejected",
                error_message=str(exc),
                duration_ms=duration_ms,
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            # 提取核心错误信息（asyncpg 嵌套异常取 orig）
            core_msg = str(exc)
            if hasattr(exc, "orig") and exc.orig:
                core_msg = str(exc.orig)
            error_detail = f"{type(exc).__name__}: {core_msg[:300]}"
            logger.error(
                "Text-to-SQL execution error: %s | generated_sql=%s | final_sql=%s",
                error_detail,
                _generated_sql,
                _final_sql,
                exc_info=True,
            )
            await self._log_query(
                context=context,
                question=question,
                generated_sql=_generated_sql,
                final_sql=_final_sql,
                status="failed",
                error_message=error_detail,
                duration_ms=duration_ms,
            )
            # 返回含错误详情的输出，便于排查
            error_output = json.dumps(
                {
                    "success": False,
                    "error": f"{type(exc).__name__}: {core_msg[:200]}",
                    "generated_sql": _generated_sql,
                    "final_sql": _final_sql,
                },
                ensure_ascii=False,
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                output=error_output,
                error=f"{_('data_intelligence.executor.execution_error')} [{type(exc).__name__}: {core_msg[:100]}]",
                duration_ms=duration_ms,
            )

    async def _log_query(
        self,
        context: ExecutionContext | None,
        question: str,
        generated_sql: str | None = None,
        final_sql: str | None = None,
        row_count: int | None = None,
        status: str = "success",
        error_message: str | None = None,
        duration_ms: int = 0,
        confidence: str | None = None,
    ) -> None:
        """写入 AI 数据查询审计日志（独立 session，失败不影响主流程）"""
        if not context:
            return
        try:
            from app.core.database import async_session_factory
            from app.repositories.ai.query_log_repository import AIQueryLogRepository

            async with async_session_factory() as log_db:
                try:
                    repo = AIQueryLogRepository(log_db, context.tenant_id)
                    await repo.create({
                        "tenant_id": context.tenant_id,
                        "agent_id": context.agent_id,
                        "user_id": context.user_id,
                        "user_role": context.user_role,
                        "question": question[:2000],
                        "generated_sql": generated_sql,
                        "final_sql": final_sql,
                        "row_count": row_count,
                        "status": status,
                        "error_message": error_message[:2000] if error_message else None,
                        "duration_ms": duration_ms,
                        "confidence": confidence,
                    })
                    await log_db.commit()
                except Exception:
                    await log_db.rollback()
                    raise
        except Exception as log_exc:
            logger.warning(
                "Failed to write query audit log: %s", str(log_exc),
            )

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """校验参数"""
        _ = definition
        question = arguments.get("question", "")
        return bool(question and isinstance(question, str) and question.strip())

    @staticmethod
    def _parse_conversation_history(
        raw: Any,
    ) -> list[ConversationRound] | None:
        """解析对话历史参数"""
        if not raw:
            return None

        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                return None

        if not isinstance(raw, list):
            return None

        rounds: list[ConversationRound] = []
        for item in raw:
            if isinstance(item, dict) and "question" in item:
                rounds.append(
                    ConversationRound(
                        question=item["question"],
                        sql=item.get("sql", ""),
                        explanation=item.get("explanation", ""),
                    )
                )
        return rounds or None


__all__ = ["TextToSQLExecutor"]
