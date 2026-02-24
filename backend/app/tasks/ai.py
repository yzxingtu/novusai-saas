"""
AI 相关的 Celery 任务

异步处理 AI 调用日志记录等耗时操作。
Celery Worker 是同步进程，使用同步 DB Session 直接写入。
"""

import json
import hashlib
from typing import Optional

from app.core.database import sync_session_factory
from app.core.logging import LogManager
from app.core.i18n import _
from app.core.base_model import utc_now
from app.tasks.base import register_task, BaseTask


logger = LogManager.get_logger("tasks.ai")


def _sanitize_request(request_data: dict) -> dict:
    """请求体脱敏处理"""
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


def _truncate_response(response_data) -> Optional[dict]:
    """响应体截断处理（超过 10KB 截断）"""
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
    tools: Optional[list],
) -> str:
    """生成请求哈希（用于缓存命中检测）"""
    params = {
        "model_id": model_id,
        "messages": messages,
        "temperature": temperature,
        "tools": tools,
    }
    params_str = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(params_str.encode()).hexdigest()


@register_task(
    name="tasks.ai.log_ai_call",
    queue="ai_gateway",
    description="异步记录 AI 调用日志",
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
):
    """
    异步记录 AI 调用日志（同步写入）

    Celery Worker 是同步进程，直接用同步 Session 写入 AICallLog。
    不使用异步 Service，避免 asyncio 在同步环境中的问题。

    Args:
        tenant_id: 租户 ID
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
    """
    from app.models.ai.call_log import AICallLog

    db = sync_session_factory()
    try:
        logger.info(
            "AI call log start: task=%s tenant=%s model=%s",
            self.request.id, tenant_id, model_id,
        )

        # 脱敏和截断处理
        sanitized_request = _sanitize_request(request_data)
        truncated_response = _truncate_response(response_data)

        # 生成请求哈希
        messages = request_data.get("messages", []) if request_data else []
        temperature = request_data.get("temperature", 0.7) if request_data else 0.7
        tools = request_data.get("tools") if request_data else None
        request_hash = _generate_request_hash(model_id, messages, temperature, tools)

        # 直接创建 AICallLog 记录（同步写入）
        call_log = AICallLog(
            tenant_id=tenant_id,
            user_id=user_id,
            user_type=user_type,
            provider_id=provider_id,
            model_id=model_id,
            request_type=request_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=cost,
            latency_ms=latency_ms,
            status=status,
            error_message=error_message,
            request_hash=request_hash,
            request_metadata={
                "request": sanitized_request,
                "response": truncated_response,
                "timestamp": utc_now().isoformat(),
            },
        )

        db.add(call_log)
        db.commit()

        logger.info(
            "AI call log saved: task=%s tenant=%s model=%s log_id=%s",
            self.request.id, tenant_id, model_id, call_log.id,
        )

    except Exception as e:
        db.rollback()
        logger.error(
            "AI call log failed: task=%s error=%s",
            self.request.id, str(e),
            exc_info=True,
        )
        raise
    finally:
        db.close()


__all__ = ["log_ai_call_task"]
