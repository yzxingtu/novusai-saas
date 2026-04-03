"""
AI-related Celery tasks / AI 相关的 Celery 任务

Asynchronously handles time-consuming operations like AI call log recording.
异步处理 AI 调用日志记录等耗时操作。
Celery Worker is a synchronous process, writing directly with sync DB Session.
Celery Worker 是同步进程，使用同步 DB Session 直接写入。
"""

import hashlib
import json

from app.core.base_model import utc_now
from app.core.database import sync_session_factory
from app.core.logging import LogManager
from app.enums.ai import CallTypeEnum
from app.tasks.base import BaseTask, register_task

logger = LogManager.get_logger("tasks.ai")


def _sanitize_request(request_data: dict) -> dict:
    """Sanitize request body / 请求体脱敏处理"""
    if not request_data:
        return request_data

    sanitized = request_data.copy()
    sensitive_fields = ["api_key", "password", "token", "secret", "authorization"]
    for field in sensitive_fields:
        if field in sanitized:
            value = str(sanitized[field])
            if len(value) > 8:
                sanitized[field] = f"{value[:4]}...{value[-4:]}"
    return sanitized


def _truncate_response(response_data) -> dict | None:
    """Truncate response body (truncate if > 10KB) / 响应体截断处理（超过 10KB 截断）"""
    if not response_data:
        return response_data

    try:
        response_str = json.dumps(response_data, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return {"error": "not serializable"}

    if len(response_str.encode("utf-8")) > 10 * 1024:
        return {
            "truncated": True,
            "size": len(response_str),
            "preview": response_str[:1024] + "...truncated",
        }
    return response_data


def _generate_request_hash(
    model_id: int,
    messages: list,
    temperature: float,
    tools: list | None,
    tool_choice: str | None = None,
) -> str:
    """Generate request hash (for cache hit detection) / 生成请求哈希（用于缓存命中检测）"""
    params = {
        "model_id": model_id,
        "messages": messages,
        "temperature": temperature,
        "tools": tools,
        "tool_choice": tool_choice,
    }
    params_str = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(params_str.encode()).hexdigest()


@register_task(
    name="tasks.ai.log_ai_call",
    queue="ai_gateway",
    description="Async AI call log recording / 异步记录 AI 调用日志",
    max_retries=3,
)
def log_ai_call_task(
    self: BaseTask,
    tenant_id: int,
    model_id: int,
    provider_id: int,
    request_type: str,
    request_data: dict,
    response_data: dict,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    cost: float,
    latency_ms: int,
    status: str,
    error_message: str = None,
    user_id: int = None,
    user_type: str = None,
    agent_id: int = None,
    conversation_id: int = None,
    billing_context: dict | None = None,
    routed_model_id: int = None,
    route_reason: str = None,
    trace_id: str | None = None,
    tool_call_id: str | None = None,
    call_type: str = CallTypeEnum.MAIN_CHAT.value,
):
    """
    Async AI call log recording (sync write) / 异步记录 AI 调用日志（同步写入）

    Celery Worker is a synchronous process, writing directly with sync Session to AICallLog.
    Celery Worker 是同步进程，直接用同步 Session 写入 AICallLog。
    Does not use async Service to avoid asyncio issues in sync environment.
    不使用异步 Service，避免 asyncio 在同步环境中的问题。

    Args:
        tenant_id: Tenant ID / 企业 ID
        model_id: Model ID / 模型 ID
        provider_id: Provider ID / 供应商 ID
        request_type: Request type / 请求类型
        request_data: Request data / 请求数据
        response_data: Response data / 响应数据
        input_tokens: Input tokens / 输入 tokens
        output_tokens: Output tokens / 输出 tokens
        total_tokens: Total tokens / 总 tokens
        cost: Cost / 费用
        latency_ms: Latency / 延迟
        status: Call status / 调用状态
        error_message: Error message / 错误信息
        user_id: User ID / 用户 ID
        user_type: User type / 用户类型
        agent_id: Agent ID / 智能体 ID
        conversation_id: Conversation ID / 对话 ID
        routed_model_id: Routed model ID / 路由后模型 ID
        route_reason: Route reason / 路由原因
    """
    from app.models.ai.call_log import AICallLog
    from app.services.ai.call_log_service import CallLogService

    db = sync_session_factory()
    try:
        logger.info(
            "AI call log start: task={} tenant={} model={}",
            self.request.id,
            tenant_id,
            model_id,
        )

        normalized_latency_ms = CallLogService._normalize_latency_ms(latency_ms)

        # Sanitize and truncate / 脱敏和截断处理
        sanitized_request = _sanitize_request(request_data)
        truncated_response = _truncate_response(response_data)

        # Generate request hash / 生成请求哈希
        messages = request_data.get("messages", []) if request_data else []
        temperature = request_data.get("temperature", 0.7) if request_data else 0.7
        tools = request_data.get("tools") if request_data else None
        tool_choice = request_data.get("tool_choice") if request_data else None
        request_hash = _generate_request_hash(
            model_id,
            messages,
            temperature,
            tools,
            tool_choice=tool_choice,
        )

        # Create AICallLog record directly (sync write) / 直接创建 AICallLog 记录（同步写入）
        call_log = AICallLog(
            tenant_id=tenant_id,
            user_id=user_id,
            user_type=user_type,
            billing_tenant_id=(billing_context or {}).get("billing_tenant_id"),
            actor_user_id=(billing_context or {}).get("actor_user_id", user_id),
            actor_user_type=(billing_context or {}).get("actor_user_type", user_type),
            access_channel=(billing_context or {}).get("access_channel"),
            agent_id=agent_id,
            conversation_id=conversation_id,
            trace_id=trace_id,
            tool_call_id=tool_call_id,
            provider_id=provider_id,
            model_id=model_id,
            request_type=request_type,
            call_type=call_type or CallTypeEnum.MAIN_CHAT.value,
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
            agent_owner_type=(billing_context or {}).get("agent_owner_type"),
            agent_owner_tenant_id=(billing_context or {}).get("agent_owner_tenant_id"),
            agent_resource_scope=(billing_context or {}).get("agent_resource_scope"),
            tenant_publication_id=(billing_context or {}).get("tenant_publication_id"),
            publication_enabled_snapshot=(billing_context or {}).get(
                "publication_enabled_snapshot"
            ),
            publication_access_type_snapshot=(billing_context or {}).get(
                "publication_access_type_snapshot"
            ),
            agent_id_snapshot=(billing_context or {}).get(
                "agent_id_snapshot", agent_id
            ),
            agent_name_snapshot=(billing_context or {}).get("agent_name_snapshot"),
            billing_tenant_name_snapshot=(billing_context or {}).get(
                "billing_tenant_name_snapshot"
            ),
            model_name_snapshot=(billing_context or {}).get("model_name_snapshot"),
            provider_name_snapshot=(billing_context or {}).get(
                "provider_name_snapshot"
            ),
        )

        db.add(call_log)
        db.commit()

        logger.info(
            "AI call log saved: task={} tenant={} model={} log_id={}",
            self.request.id,
            tenant_id,
            model_id,
            call_log.id,
        )

    except Exception as e:
        db.rollback()
        logger.error(
            "AI call log failed: task={} error={}",
            self.request.id,
            str(e),
            exc_info=True,
        )
        raise
    finally:
        db.close()


__all__ = ["log_ai_call_task"]
