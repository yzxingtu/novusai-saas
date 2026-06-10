"""
Welcome message generator / 欢迎语生成器

Generates personalized welcome messages based on page context, user info, and memory.
基于页面上下文、用户信息和记忆生成个性化欢迎语。
"""

from __future__ import annotations

import json
from typing import Any

from app.ai.internal_ai_service import InternalAIService
from app.ai.types import ChatMessage
from app.core.logging import LogManager
from app.enums.ai import CallTypeEnum
from app.repositories.ai.agent_repository import AgentRepository

logger = LogManager.get_logger("ai.welcome_generator")

_WELCOME_SYSTEM_PROMPT = """\
你是一个智能助手的欢迎语生成模块。
根据以下信息生成一条简短、友好的欢迎语和 2-3 个操作建议。

要求：
1. 欢迎语要简短（1-2 句话），体现对用户昵称的称呼
2. 如果提供了页面上下文，欢迎语要结合当前页面场景
3. 如果提供了时间信息，可以适当问候（早上/下午/晚上好）
4. 操作建议要具体、可操作，帮助用户快速上手
5. **必须使用用户的语言偏好来生成欢迎语和建议操作**（如 zh-CN 用中文，en-US 用英文）
6. 严格返回 JSON 格式

返回格式（严格 JSON，不要包裹在 markdown 代码块中）：
{"welcome_message": "欢迎语内容", "suggested_actions": ["建议1", "建议2", "建议3"]}
"""


def _build_welcome_user_prompt(
    *,
    page_context: dict[str, Any] | None = None,
    user_context: dict[str, Any] | None = None,
    memory_summary: str | None = None,
    agent_name: str = "",
) -> str:
    parts: list[str] = []

    if agent_name:
        parts.append(f"智能体名称: {agent_name}")

    if user_context:
        nickname = str(user_context.get("user_nickname") or "").strip()
        current_time = str(user_context.get("current_time") or "").strip()
        locale = str(user_context.get("locale") or "").strip()
        if nickname:
            parts.append(f"用户昵称: {nickname}")
        if current_time:
            parts.append(f"当前时间: {current_time}")
        if locale:
            parts.append(f"用户语言偏好: {locale}")

    if page_context:
        page_title = str(page_context.get("page_title") or "").strip()
        route_path = str(page_context.get("route_path") or "").strip()
        page_desc = str(page_context.get("page_description") or "").strip()
        available_apis = page_context.get("available_apis") or []
        page_locale = str(page_context.get("locale") or "").strip()
        if page_title:
            parts.append(f"当前页面: {page_title}")
        if route_path:
            parts.append(f"页面路径: {route_path}")
        if page_desc:
            parts.append(f"页面描述: {page_desc}")
        if available_apis:
            parts.append(f"可用接口: {', '.join(available_apis)}")
        if page_locale:
            parts.append(f"语言偏好: {page_locale}")

    if memory_summary:
        parts.append(f"用户记忆摘要: {memory_summary}")

    if not parts:
        parts.append("无额外上下文信息")

    return "\n".join(parts)


def _parse_welcome_response(text: str) -> dict[str, Any]:
    """Parse the LLM response into structured welcome data."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (fences)
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
        welcome_message = str(data.get("welcome_message") or "").strip()
        suggested_actions = [
            str(a).strip()
            for a in (data.get("suggested_actions") or [])
            if isinstance(a, str) and str(a).strip()
        ]
        return {
            "welcome_message": welcome_message,
            "suggested_actions": suggested_actions[:5],
        }
    except (json.JSONDecodeError, TypeError):
        # Fallback: treat entire response as welcome message
        return {
            "welcome_message": text[:500],
            "suggested_actions": [],
        }


async def _resolve_agent_model(
    db: Any,
    agent_id: int,
    tenant_id: int,
) -> tuple[str | None, str | None]:
    """Resolve the agent's model provider and code."""
    try:
        agent_repo = AgentRepository(db, tenant_id)
        agent = await agent_repo.get_by_id(agent_id)
        logger.info(
            "Welcome generator: resolve agent_id={} tenant_id={} agent_found={}",
            agent_id,
            tenant_id,
            agent is not None,
        )
        if not agent:
            return None, None
        model = getattr(agent, "model", None)
        logger.info(
            "Welcome generator: agent.name={} model_found={}",
            getattr(agent, "name", None),
            model is not None,
        )
        if not model:
            return None, None
        provider = getattr(model, "provider", None)
        provider_code = getattr(provider, "code", None) if provider else None
        model_code = getattr(model, "code", None) if model else None
        logger.info(
            "Welcome generator: provider_code={} model_code={}",
            provider_code,
            model_code,
        )
        return provider_code, model_code
    except Exception as exc:
        logger.warning(
            "Welcome generator: failed to resolve agent model: agent_id={} error={}",
            agent_id,
            str(exc),
        )
        return None, None


async def generate_welcome_message(
    db: Any,
    *,
    agent_id: int,
    tenant_id: int,
    page_context: dict[str, Any] | None = None,
    user_context: dict[str, Any] | None = None,
    memory_summary: str | None = None,
) -> dict[str, Any]:
    """
    Generate a personalized welcome message via LLM.

    通过 LLM 生成个性化欢迎语。

    Args:
        db: Database session
        agent_id: Agent ID
        tenant_id: Tenant ID
        page_context: Page context from frontend
        user_context: User context (nickname + time)
        memory_summary: Optional memory summary

    Returns:
        Dict with welcome_message and suggested_actions
    """
    provider_code, model_code = await _resolve_agent_model(
        db, agent_id, tenant_id
    )

    if not provider_code or not model_code:
        # Fallback: return a generic welcome
        return _build_fallback_welcome(user_context)

    # Resolve agent name for context
    agent_name = ""
    try:
        agent_repo = AgentRepository(db, tenant_id)
        agent = await agent_repo.get_by_id(agent_id)
        if agent:
            agent_name = getattr(agent, "name", "") or ""
    except Exception:
        pass

    user_prompt = _build_welcome_user_prompt(
        page_context=page_context,
        user_context=user_context,
        memory_summary=memory_summary,
        agent_name=agent_name,
    )

    try:
        ai_service = InternalAIService(db)
        response = await ai_service.chat(
            provider_code=provider_code,
            messages=[
                ChatMessage(role="system", content=_WELCOME_SYSTEM_PROMPT),
                ChatMessage(role="user", content=user_prompt),
            ],
            model=model_code,
            temperature=0.7,
            max_tokens=300,
            call_type=CallTypeEnum.INTERNAL_MEMORY.value,
            tenant_id=tenant_id if tenant_id > 0 else None,
        )

        content = ""
        if hasattr(response, "message") and hasattr(response.message, "content"):
            content = response.message.content or ""
        elif hasattr(response, "content"):
            content = response.content or ""

        if not content:
            return _build_fallback_welcome(user_context)

        return _parse_welcome_response(content)

    except Exception as exc:
        logger.warning(
            "Welcome generator: LLM call failed: agent_id={} error={}",
            agent_id,
            str(exc),
        )
        return _build_fallback_welcome(user_context)


def _build_fallback_welcome(
    user_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a fallback welcome message when LLM is unavailable."""
    nickname = ""
    if user_context:
        nickname = str(user_context.get("user_nickname") or "").strip()

    greeting = f"你好，{nickname}！" if nickname else "你好！"
    return {
        "welcome_message": f"{greeting}我是你的 AI 助手，有什么可以帮你的吗？",
        "suggested_actions": [],
    }
