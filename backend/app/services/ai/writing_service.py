"""
Platform-level AI writing service / 平台级 AI 写作服务

Provides unified AI writing capabilities (continue, optimize, proofread, translate, etc.)
for any editor context. Resolves system.ai_writing agent via SystemAgentAssignment.
/ 为任何编辑器上下文提供统一的 AI 写作能力（续写、优化、校对、翻译等）。
通过 SystemAgentAssignment 解析 system.ai_writing 智能体。
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from app.configs.service import PLATFORM_TENANT_ID
from app.core.logging import LogManager

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = LogManager.get_logger("app")

MAX_BEFORE_TEXT = 2000
MAX_AFTER_TEXT = 500
MAX_SELECTED_TEXT = 5000
MAX_INSTRUCTION = 1000

FEATURE_CODE = "system.ai_writing"

_PROMPTS: dict[str, dict[str, str]] = {
    "continue": {
        "system": (
            "你是 NovusDoc 写作助手，嵌入在一个富文本文档编辑器中。\n"
            "你的任务是根据上下文自然续写文档内容。\n\n"
            "规则：\n"
            "1. 严格匹配用户文档的风格、语气和语言（中文文档用中文续写，英文文档用英文续写）\n"
            "2. 只输出续写的文本内容，不要添加任何解释、说明、前缀或标签\n"
            "3. 续写内容要与前文逻辑连贯，语义通顺\n"
            "4. 保持专业、简洁、准确\n"
            "5. 续写长度适中，约 100-300 字（或 50-150 英文单词）\n"
            "6. 不要重复前文已有的内容\n"
            "7. 如果光标后还有内容，续写要能自然衔接后文"
        ),
        "user": (
            "文档标题: {context_title}\n\n"
            "光标前的内容:\n{before_text}\n\n"
            "光标后的内容:\n{after_text}\n\n"
            "请从前文结束处开始续写:"
        ),
    },
    "optimize": {
        "system": (
            "你是 NovusDoc 写作助手，专注于文本优化。\n"
            "你的任务是提升选中文本的清晰度、简洁性和可读性，同时保持原意不变。\n\n"
            "规则：\n"
            "1. 保持原文的核心含义和信息完整性\n"
            "2. 优化句式结构，消除冗余和歧义\n"
            "3. 改善措辞，使表达更精准、更有力\n"
            "4. 保持原文的语言（中文输入输出中文，英文输入输出英文）\n"
            "5. 只输出优化后的完整文本，不要解释修改了什么\n"
            "6. 不要改变原文的语气（正式/非正式）和人称视角"
        ),
        "user": "请优化以下文本的表达和可读性:\n\n{selected_text}",
    },
    "proofread": {
        "system": (
            "你是 NovusDoc 写作助手，专注于文本校对。\n"
            "你的任务是修正文本中的错误，但不改变原文风格和表达方式。\n\n"
            "规则：\n"
            "1. 修正语法错误、拼写错误、标点符号问题\n"
            "2. 修正明显的用词不当或搭配错误\n"
            "3. 不要改写句子结构或优化措辞——只做纠错\n"
            "4. 如果原文没有错误，原样输出\n"
            "5. 保持原文的语言，不要翻译\n"
            "6. 只输出校对后的文本，不要标注或解释修改内容"
        ),
        "user": "请校对并修正以下文本中的错误:\n\n{selected_text}",
    },
    "translate": {
        "system": (
            "你是 NovusDoc 写作助手，专注于翻译。\n"
            "你的任务是将文本翻译为目标语言。\n\n"
            "规则：\n"
            "1. 如果目标语言未指定，自动检测：中文翻译为英文，英文翻译为中文\n"
            "2. 保留专业术语的准确性，必要时在括号内标注原文\n"
            "3. 保持原文的语气、风格和格式结构\n"
            "4. 保留原文中的代码、数字、URL 等不可翻译内容\n"
            "5. 只输出翻译结果，不要添加解释或注释\n"
            "6. 翻译要自然流畅，避免机翻痕迹"
        ),
        "user": "请将以下文本翻译为 {target_lang}:\n\n{selected_text}",
    },
    "summarize": {
        "system": (
            "你是 NovusDoc 写作助手，专注于文本摘要。\n"
            "你的任务是提炼文本的核心内容，生成简洁的摘要。\n\n"
            "规则：\n"
            "1. 使用与原文相同的语言输出摘要\n"
            "2. 输出格式：先用一句话概括核心要点，然后用要点列表（- 开头）列出关键信息\n"
            "3. 摘要长度应为原文的 20%-30%\n"
            "4. 保持客观，不添加原文没有的信息\n"
            "5. 只输出摘要内容，不要添加【摘要：】等前缀"
        ),
        "user": "请为以下文本生成摘要:\n\n{selected_text}",
    },
    "expand": {
        "system": (
            "你是 NovusDoc 写作助手，专注于内容扩写。\n"
            "你的任务是在保持原文风格和结构的基础上，丰富和扩展内容。\n\n"
            "规则：\n"
            "1. 保持原文的语言、风格、语气和人称视角\n"
            "2. 增加具体的细节、数据、举例或论据来支撑原文观点\n"
            "3. 扩写后的内容应是原文的 2-3 倍长度\n"
            "4. 保持段落结构的逻辑性和连贯性\n"
            "5. 不要偏离原文的主题和论点\n"
            "6. 只输出扩写后的完整文本"
        ),
        "user": "请扩写以下文本，增加更多细节和论据:\n\n{selected_text}",
    },
    "rewrite": {
        "system": (
            "你是 NovusDoc 写作助手，专注于文本重写。\n"
            "你的任务是用不同的表达方式重写文本，同时保持核心含义不变。\n\n"
            "规则：\n"
            "1. 保持原文的核心语义和信息完整性\n"
            "2. 使用不同的句式结构和词汇选择\n"
            "3. 保持原文的语言（中文输入输出中文，英文输入输出英文）\n"
            "4. 重写后的文本应更清晰、更有条理\n"
            "5. 保持与原文相近的篇幅\n"
            "6. 只输出重写后的完整文本"
        ),
        "user": "请用不同的方式重写以下文本:\n\n{selected_text}",
    },
    "custom": {
        "system": (
            "你是 NovusDoc 写作助手，嵌入在一个富文本文档编辑器中。\n"
            "你的任务是根据用户的自定义指令处理文档内容。\n\n"
            "规则：\n"
            "1. 严格按照用户的指令执行操作\n"
            "2. 匹配用户文档的风格、语气和语言\n"
            "3. 只输出处理结果，不要添加解释或说明\n"
            "4. 如果指令不明确，根据上下文做最合理的推断\n"
            "5. 保持专业、简洁、准确"
        ),
        "user": (
            "文档标题: {context_title}\n\n"
            "选中的文本:\n{selected_text}\n\n"
            "用户指令: {instruction}"
        ),
    },
    "chat": {
        "system": (
            "你是 NovusDoc 写作助手，嵌入在文档编辑器的侧边栏中。\n"
            "帮助用户解答关于文档内容的问题，提供写作建议。\n\n"
            "规则：\n"
            "1. 回答要简洁实用，直接解决用户问题\n"
            "2. 可以引用用户提供的文档内容来回答\n"
            "3. 匹配用户的语言进行回复"
        ),
        "user": "{instruction}",
    },
}

VALID_FEATURES = frozenset(_PROMPTS.keys())


def build_ai_messages(
    feature: str,
    *,
    selected_text: str = "",
    before_text: str = "",
    after_text: str = "",
    context_title: str = "",
    instruction: str = "",
    target_lang: str = "English",
    chat_history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Build messages list for AgentChatService. / 构建消息列表。"""
    templates = _PROMPTS.get(feature, _PROMPTS["custom"])

    selected_text = selected_text[:MAX_SELECTED_TEXT]
    before_text = before_text[-MAX_BEFORE_TEXT:]
    after_text = after_text[:MAX_AFTER_TEXT]
    instruction = instruction[:MAX_INSTRUCTION]

    fmt_vars = {
        "selected_text": selected_text or "(no selection)",
        "before_text": before_text or "(beginning of document)",
        "after_text": after_text or "(end of document)",
        "context_title": context_title or "Untitled",
        "instruction": instruction or "",
        "target_lang": target_lang,
    }

    system_content = templates["system"].format(**fmt_vars)
    user_content = templates["user"].format(**fmt_vars)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_content},
    ]

    if feature == "chat" and chat_history:
        for msg in chat_history[-10:]:
            messages.append(
                {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                }
            )

    messages.append({"role": "user", "content": user_content})
    return messages


async def _resolve_writing_agent(
    db: AsyncSession,
    tenant_id: int | None,
) -> int:
    """
    通过 AgentAssignmentService 解析 system.ai_writing 智能体 / Resolve system.ai_writing agent via AgentAssignmentService.
    Priority: tenant override -> global default.
    """
    from sqlalchemy import select

    from app.enums.agent import AgentStatusEnum
    from app.exceptions import BusinessException
    from app.models.ai.agent import Agent
    from app.services.system.agent_assignment_service import AgentAssignmentService

    service = AgentAssignmentService(db)

    if tenant_id:
        assignment = await service.resolve_for_tenant(FEATURE_CODE, tenant_id)
    else:
        assignment = await service.resolve(FEATURE_CODE)

    if not assignment or not assignment.agent_id:
        raise BusinessException(
            message="AI writing feature is not configured. "
            "Please bind an agent to 'system.ai_writing' in admin settings.",
        )

    agent_id = assignment.agent_id

    agent_check = await db.execute(
        select(Agent.id).where(
            Agent.id == agent_id,
            Agent.is_deleted.is_(False),
            Agent.status == AgentStatusEnum.PUBLISHED.value,
        )
    )
    if not agent_check.scalar_one_or_none():
        raise BusinessException(
            message=f"AI writing agent #{agent_id} is no longer available (deleted or unpublished).",
        )

    return agent_id


async def stream_writing_feature(
    db: AsyncSession,
    tenant_id: int | None,
    feature: str,
    body: dict[str, Any],
) -> AsyncGenerator[str, None]:
    """
    High-level entry: build messages -> resolve agent -> stream via AgentChatService -> yield deltas.
    / 高层入口：构建消息 -> 解析智能体 -> 通过 AgentChatService 流式调用 -> 产出增量文本。
    """
    from app.services.ai.agent_chat_service import AgentChatService

    start_time = time.perf_counter()
    chunk_count = 0

    agent_id = await _resolve_writing_agent(db, tenant_id)

    messages = build_ai_messages(
        feature,
        selected_text=body.get("selected_text", ""),
        before_text=body.get("before_text", ""),
        after_text=body.get("after_text", ""),
        context_title=body.get("context_title", ""),
        instruction=body.get("instruction", ""),
        target_lang=body.get("target_lang", "English"),
        chat_history=body.get("history"),
    )

    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    user_parts = [m["content"] for m in messages if m["role"] == "user"]
    combined_message = ""
    if system_parts:
        combined_message += f"[Task Instructions]\n{system_parts[0]}\n\n"

    format_instruction = body.get("format_instruction")
    if format_instruction:
        combined_message += f"[Format Requirement]\n{format_instruction}\n\n"

    if user_parts:
        combined_message += f"[User Request]\n{user_parts[-1]}"
    else:
        combined_message = system_parts[0] if system_parts else ""

    effective_tenant_id = tenant_id or PLATFORM_TENANT_ID
    chat_service = AgentChatService(db, effective_tenant_id)

    try:
        sse_response = await chat_service.stream_chat_ephemeral(
            agent_id=agent_id,
            message=combined_message,
        )

        async for raw_chunk in sse_response.body_iterator:
            text = (
                raw_chunk if isinstance(raw_chunk, str) else raw_chunk.decode("utf-8")
            )
            for line in text.split("\n"):
                line = line.strip()
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    return
                try:
                    event = json.loads(payload)
                except (json.JSONDecodeError, ValueError):
                    continue

                if event.get("error"):
                    from app.exceptions import BusinessException

                    raise BusinessException(
                        message=event.get("message", "AI execution error")
                    )

                if event.get("event") == "message":
                    delta = event.get("delta", "")
                    if delta:
                        chunk_count += 1
                        yield delta

    finally:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(
            "ai_writing_stream: feature={} agent_id={} tenant_id={} chunks={} latency_ms={}",
            feature,
            agent_id,
            tenant_id,
            chunk_count,
            latency_ms,
        )


__all__ = [
    "VALID_FEATURES",
    "build_ai_messages",
    "stream_writing_feature",
]
