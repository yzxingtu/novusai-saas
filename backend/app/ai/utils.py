"""
AI 网关通用工具函数

提供 admin/tenant 网关控制器共享的解析函数
"""

from app.ai.types import ChatMessage as AIChatMessage


def parse_provider_and_model(model_code: str) -> tuple[str, str]:
    """
    从 model_code 解析供应商代码和模型名称

    支持格式:
    - "provider:model" → (provider, model)
    - "model" → ("openai", model)

    Args:
        model_code: 模型代码

    Returns:
        (provider_code, model_name) 元组
    """
    if ":" in model_code:
        provider_code, model = model_code.split(":", 1)
    else:
        provider_code = "openai"
        model = model_code
    return provider_code, model


def parse_messages(messages: list) -> list[AIChatMessage]:
    """
    将 Pydantic 消息列表转换为 AI 网关消息列表

    Args:
        messages: Pydantic ChatMessage 列表

    Returns:
        AI 网关 ChatMessage 列表
    """
    return [
        AIChatMessage(
            role=msg.role,
            content=msg.content or "",
            tool_calls=[tc.model_dump() for tc in msg.tool_calls] if msg.tool_calls else None,
            tool_call_id=msg.tool_call_id,
        )
        for msg in messages
    ]


__all__ = ["parse_provider_and_model", "parse_messages"]
