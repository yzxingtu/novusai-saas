"""
AI 调用日志服务 / AI Call Log Service

使用 Celery 异步记录 AI 调用日志，不阻塞主请求
Uses Celery to asynchronously record AI call logs without blocking main requests.
"""

import hashlib
import json
from typing import Any

from app.core.base_model import utc_now
from app.core.base_service import BaseService
from app.core.logging import LogManager
from app.enums.ai import CallStatusEnum
from app.models.ai import AICallLog
from app.repositories.ai import AICallLogRepository

logger = LogManager.get_logger("ai.call_log")


def _normalize_trace_for_call_log(
    explicit_trace_id: str | None,
    *,
    use_context_var: bool,
) -> str | None:
    """Resolve trace_id for AICallLog (explicit arg or request context var)."""
    tid: str | None = None
    if explicit_trace_id is not None and str(explicit_trace_id).strip():
        tid = str(explicit_trace_id).strip()
    elif use_context_var:
        from app.middleware.trace import trace_id_var

        raw = trace_id_var.get()
        tid = str(raw).strip() if raw else None
    if not tid:
        return None
    return tid[:64] if len(tid) > 64 else tid


def _normalize_tool_call_id_for_call_log(tool_call_id: str | None) -> str | None:
    if not tool_call_id or not str(tool_call_id).strip():
        return None
    s = str(tool_call_id).strip()
    return s[:128] if len(s) > 128 else s


class CallLogService(BaseService[AICallLog, AICallLogRepository]):
    """
    AI 调用日志服务 / AI Call Log Service.

    异步记录 AI 调用日志，支持请求/响应脱敏和截断
    """

    model = AICallLog
    repository_class = AICallLogRepository

    # 响应体截断阈值 (10KB)
    RESPONSE_TRUNCATE_THRESHOLD = 10 * 1024
    TRUNCATED_MARKER = "...truncated"
    MAX_LATENCY_MS = 2_147_483_647

    @staticmethod
    def _sanitize_request(request_data: dict) -> dict:
        """
        请求体脱敏处理 / Request body sanitization.

        Args:
            request_data: 请求数据 / Request data

        Returns:
            脱敏后的请求数据 / Sanitized request data
        """
        if not request_data:
            return request_data

        sanitized = request_data.copy()

        # 脱敏 API Key
        if "api_key" in sanitized:
            api_key = str(sanitized["api_key"])
            if len(api_key) > 8:
                sanitized["api_key"] = f"{api_key[:4]}...{api_key[-4:]}"

        # 脱敏其他敏感字段 / Redact other sensitive fields
        sensitive_fields = ["password", "token", "secret", "authorization"]
        for field in sensitive_fields:
            if field in sanitized:
                value = str(sanitized[field])
                if len(value) > 8:
                    sanitized[field] = f"{value[:4]}...{value[-4:]}"

        return sanitized

    @staticmethod
    def _truncate_response(response_data: Any) -> Any:
        """
        响应体截断处理 / Response body truncation.

        超过阈值时截断，避免大字段影响性能

        Args:
            response_data: 响应数据

        Returns:
            截断后的响应数据
        """
        if not response_data:
            return response_data

        # 转换为字符串检查大小（default=str 处理 Decimal 等特殊类型）
        response_str = json.dumps(response_data, ensure_ascii=False, default=str)

        if len(response_str.encode("utf-8")) > CallLogService.RESPONSE_TRUNCATE_THRESHOLD:
            # 截断并添加标记 / Truncate and add marker
            return {
                "truncated": True,
                "size": len(response_str),
                "preview": response_str[:1024] + CallLogService.TRUNCATED_MARKER,
            }

        return response_data

    @staticmethod
    def _generate_request_hash(
        model_id: int,
        messages: list,
        temperature: float,
        tools: list | None,
        tool_choice: str | None = None,
    ) -> str:
        """
        生成请求哈希（用于缓存命中检测）/ Generate request hash for cache hit detection.

        Args:
            model_id: 模型 ID
            messages: 消息列表
            temperature: 温度
            tools: 工具列表

        Returns:
            SHA256 哈希
        """
        params = {
            "model_id": model_id,
            "messages": messages,
            "temperature": temperature,
            "tools": tools,
            "tool_choice": tool_choice,
        }

        params_str = json.dumps(params, sort_keys=True)
        return hashlib.sha256(params_str.encode()).hexdigest()

    @classmethod
    def _normalize_latency_ms(cls, latency_ms: Any) -> int | None:
        """Normalize latency for DB persistence / 标准化延迟字段以便安全落库。"""
        if latency_ms is None:
            return None

        try:
            value = int(latency_ms)
        except (TypeError, ValueError):
            logger.warning("Invalid AI call latency discarded: raw={}", latency_ms)
            return None

        if value < 0:
            logger.warning("Negative AI call latency discarded: raw={}", value)
            return None

        if value > cls.MAX_LATENCY_MS:
            logger.warning(
                "Overflow AI call latency discarded: raw={} max={}",
                value,
                cls.MAX_LATENCY_MS,
            )
            return None

        return value

    async def log_call(
        self,
        tenant_id: int,
        model_id: int,
        provider_id: int,
        request_type: str,
        request_data: dict,
        response_data: dict | None,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost: float,
        latency_ms: int,
        status: str = CallStatusEnum.SUCCESS.value,
        error_message: str | None = None,
        user_id: int | None = None,
        user_type: str | None = None,
        agent_id: int | None = None,
        conversation_id: int | None = None,
        billing_context: dict[str, Any] | None = None,
        routed_model_id: int | None = None,
        route_reason: str | None = None,
        trace_id: str | None = None,
        tool_call_id: str | None = None,
    ) -> AICallLog:
        """
        记录调用日志 / Record call log.

        Args:
            tenant_id: 企业 ID
            model_id: 模型 ID
            provider_id: 供应商 ID
            request_type: 请求类型
            request_data: 请求数据
            response_data: 响应数据
            input_tokens: 输入 tokens
            output_tokens: 输出 tokens
            total_tokens: 总 tokens
            cost: 费用
            latency_ms: 延迟
            status: 调用状态
            error_message: 错误信息
            user_id: 用户 ID
            user_type: 用户类型
            agent_id: 智能体 ID
            conversation_id: 对话 ID
            routed_model_id: 路由后模型 ID
            route_reason: 路由原因

        Returns:
            AICallLog 实例
        """
        # 脱敏和截断处理 / Redact and truncate
        sanitized_request = self._sanitize_request(request_data)
        truncated_response = self._truncate_response(response_data)

        # 生成请求哈希 / Generate request hash
        messages = request_data.get("messages", [])
        temperature = request_data.get("temperature", 0.7)
        tools = request_data.get("tools")
        tool_choice = request_data.get("tool_choice")
        request_hash = self._generate_request_hash(
            model_id,
            messages,
            temperature,
            tools,
            tool_choice=tool_choice,
        )

        # 创建日志记录 / Create log row
        billing_context = dict(billing_context or {})
        normalized_latency_ms = self._normalize_latency_ms(latency_ms)
        eff_trace = _normalize_trace_for_call_log(trace_id, use_context_var=True)
        eff_tool = _normalize_tool_call_id_for_call_log(tool_call_id)
        call_log = AICallLog(
            tenant_id=tenant_id,
            user_id=user_id,
            user_type=user_type,
            billing_tenant_id=billing_context.get("billing_tenant_id"),
            actor_user_id=billing_context.get("actor_user_id", user_id),
            actor_user_type=billing_context.get("actor_user_type", user_type),
            access_channel=billing_context.get("access_channel"),
            agent_id=agent_id,
            conversation_id=conversation_id,
            trace_id=eff_trace,
            tool_call_id=eff_tool,
            provider_id=provider_id,
            model_id=model_id,
            request_type=request_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=cost,
            latency_ms=normalized_latency_ms,
            status=status,
            error_message=error_message,
            request_hash=request_hash,
            request_metadata={
                "request": sanitized_request,
                "response": truncated_response,
                "timestamp": utc_now().isoformat(),
                "agent_id": agent_id,
                "conversation_id": conversation_id,
                "routed_model_id": routed_model_id,
                "route_reason": route_reason,
            },
            routed_model_id=routed_model_id,
            route_reason=route_reason,
            agent_owner_type=billing_context.get("agent_owner_type"),
            agent_owner_tenant_id=billing_context.get("agent_owner_tenant_id"),
            agent_resource_scope=billing_context.get("agent_resource_scope"),
            tenant_publication_id=billing_context.get("tenant_publication_id"),
            publication_enabled_snapshot=billing_context.get("publication_enabled_snapshot"),
            publication_access_type_snapshot=billing_context.get("publication_access_type_snapshot"),
            agent_id_snapshot=billing_context.get("agent_id_snapshot", agent_id),
            agent_name_snapshot=billing_context.get("agent_name_snapshot"),
            billing_tenant_name_snapshot=billing_context.get("billing_tenant_name_snapshot"),
            model_name_snapshot=billing_context.get("model_name_snapshot"),
            provider_name_snapshot=billing_context.get("provider_name_snapshot"),
        )

        self.db.add(call_log)
        await self.db.flush()

        logger.info(
            "AI call logged | tenant_id={} model_id={} total_tokens={} cost={} status={}",
            tenant_id,
            model_id,
            total_tokens,
            cost,
            status,
        )

        return call_log

    async def get_statistics(
        self,
        tenant_id: int | None = None,
        start_date=None,
        end_date=None,
        group_by: str = "daily",
    ):
        """获取调用统计信息（委托给 Repository） / Get call stats (delegate to repo)."""
        return await self.repo.get_statistics(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
        )

    async def get_overall_summary(
        self,
        tenant_id: int | None = None,
        start_date=None,
        end_date=None,
    ):
        """获取调用汇总统计（委托给 Repository） / Get call summary (delegate to repo)."""
        return await self.repo.get_overall_summary(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_failed_logs(
        self,
        tenant_id: int | None = None,
        start_date=None,
        limit: int = 100,
    ):
        """获取失败的调用日志（委托给 Repository） / Get failed call logs (delegate to repo)."""
        return await self.repo.get_failed_logs(
            tenant_id=tenant_id,
            start_date=start_date,
            limit=limit,
        )

    async def log_call_async(
        self,
        tenant_id: int,
        model_id: int,
        provider_id: int,
        request_type: str,
        request_data: dict,
        response_data: dict | None,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost: float,
        latency_ms: int,
        status: str = CallStatusEnum.SUCCESS.value,
        error_message: str | None = None,
        user_id: int | None = None,
        user_type: str | None = None,
        agent_id: int | None = None,
        conversation_id: int | None = None,
        billing_context: dict[str, Any] | None = None,
        routed_model_id: int | None = None,
        route_reason: str | None = None,
        trace_id: str | None = None,
        tool_call_id: str | None = None,
    ):
        """
        异步记录调用日志 (通过 Celery) / Record call log asynchronously via Celery.

        Args:
            同 log_call / Same as log_call.
        """
        from app.tasks.ai import log_ai_call_task

        normalized_latency_ms = self._normalize_latency_ms(latency_ms)
        eff_trace = _normalize_trace_for_call_log(trace_id, use_context_var=True)
        eff_tool = _normalize_tool_call_id_for_call_log(tool_call_id)

        # 发送 Celery 任务
        log_ai_call_task.delay(
            tenant_id=tenant_id,
            model_id=model_id,
            provider_id=provider_id,
            request_type=request_type,
            request_data=request_data,
            response_data=response_data,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=float(cost),
            latency_ms=normalized_latency_ms,
            status=status,
            error_message=error_message,
            user_id=user_id,
            user_type=user_type,
            agent_id=agent_id,
            conversation_id=conversation_id,
            billing_context=billing_context,
            routed_model_id=routed_model_id,
            route_reason=route_reason,
            trace_id=eff_trace,
            tool_call_id=eff_tool,
        )

        logger.debug(
            "AI call log queued | tenant_id={} model_id={}",
            tenant_id,
            model_id,
        )


__all__ = ["CallLogService"]
