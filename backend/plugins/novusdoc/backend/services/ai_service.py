"""
NovusDoc AI 服务层

负责 prompt 模板构建、上下文收集、调用 ctx.call_ai_feature_stream()。
所有 AI handler 共用此服务，避免重复构建 messages 逻辑。
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from app.core.logging import get_logger

logger = get_logger("plugin.novusdoc.ai")

# ── 上下文长度限制 ──
MAX_BEFORE_TEXT = 2000
MAX_AFTER_TEXT = 500
MAX_SELECTED_TEXT = 5000
MAX_INSTRUCTION = 1000


# ── Prompt 模板 ──
# 每个 feature 对应一个 system prompt + user prompt 模板
# {selected_text} / {before_text} / {after_text} / {doc_title} / {instruction} / {target_lang}

_PROMPTS: dict[str, dict[str, str]] = {
    "ai_writer": {
        "system": (
            "You are an AI writing assistant integrated into a document editor. "
            "Continue writing naturally based on the context provided. "
            "Match the style, tone, and language of the existing content. "
            "Output ONLY the continuation text, no explanations."
        ),
        "user": "Document title: {doc_title}\n\nContext before cursor:\n{before_text}\n\nContext after cursor:\n{after_text}\n\nContinue writing from where the text ends:",
    },
    "ai_translator": {
        "system": (
            "You are a professional translator. Translate the selected text to {target_lang}. "
            "Preserve formatting, tone, and meaning. Output ONLY the translated text."
        ),
        "user": "Translate the following text to {target_lang}:\n\n{selected_text}",
    },
    "ai_proofreader": {
        "system": (
            "You are a professional proofreader. Fix grammar, spelling, punctuation, and style issues. "
            "Preserve the original meaning and tone. Output ONLY the corrected text."
        ),
        "user": "Proofread and correct the following text:\n\n{selected_text}",
    },
    "ai_summarizer": {
        "system": (
            "You are a summarization expert. Create a concise summary of the provided text. "
            "Capture key points and main ideas. Output ONLY the summary."
        ),
        "user": "Summarize the following text:\n\n{selected_text}",
    },
    "optimize": {
        "system": (
            "You are a writing optimization expert. Improve the clarity, conciseness, and readability "
            "of the selected text while preserving its meaning. Output ONLY the optimized text."
        ),
        "user": "Optimize the following text for clarity and readability:\n\n{selected_text}",
    },
    "expand": {
        "system": (
            "You are a writing assistant. Expand the selected text with more details, examples, "
            "and elaboration while maintaining the original style. Output ONLY the expanded text."
        ),
        "user": "Expand the following text with more details:\n\n{selected_text}",
    },
    "rewrite": {
        "system": (
            "You are a writing assistant. Rewrite the selected text in a different way while "
            "preserving the core meaning. Improve structure and expression. Output ONLY the rewritten text."
        ),
        "user": "Rewrite the following text:\n\n{selected_text}",
    },
    "custom": {
        "system": (
            "You are an AI writing assistant. Follow the user's instruction precisely. "
            "Output ONLY the result, no explanations."
        ),
        "user": "Document title: {doc_title}\n\nSelected text:\n{selected_text}\n\nInstruction: {instruction}",
    },
    "chat": {
        "system": (
            "You are an AI writing assistant embedded in a document editor sidebar. "
            "Help the user with questions about their document. "
            "Be concise and helpful. You can reference the document content provided."
        ),
        "user": "{instruction}",
    },
}

# feature_code → prompt key mapping
_FEATURE_MAP: dict[str, str] = {
    "continue": "ai_writer",
    "optimize": "optimize",
    "proofread": "ai_proofreader",
    "translate": "ai_translator",
    "summarize": "ai_summarizer",
    "expand": "expand",
    "rewrite": "rewrite",
    "custom": "custom",
    "chat": "chat",
}

# feature → ai_requirements feature_code mapping (for ctx.call_ai_feature_stream)
_AI_FEATURE_CODE: dict[str, str] = {
    "continue": "ai_writer",
    "optimize": "ai_writer",
    "proofread": "ai_proofreader",
    "translate": "ai_translator",
    "summarize": "ai_summarizer",
    "expand": "ai_writer",
    "rewrite": "ai_writer",
    "custom": "ai_writer",
    "chat": "ai_writer",
    "image": "ai_image",
}


def build_ai_messages(
    feature: str,
    *,
    selected_text: str = "",
    before_text: str = "",
    after_text: str = "",
    doc_title: str = "",
    instruction: str = "",
    target_lang: str = "English",
    chat_history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """
    Build AI messages for a given feature.

    Returns list of {role, content} dicts ready for ctx.call_ai_feature_stream().
    """
    prompt_key = _FEATURE_MAP.get(feature, feature)
    templates = _PROMPTS.get(prompt_key)
    if not templates:
        templates = _PROMPTS["custom"]

    # Truncate inputs
    selected_text = selected_text[:MAX_SELECTED_TEXT]
    before_text = before_text[-MAX_BEFORE_TEXT:]  # keep last N chars
    after_text = after_text[:MAX_AFTER_TEXT]
    instruction = instruction[:MAX_INSTRUCTION]

    fmt_vars = {
        "selected_text": selected_text or "(no selection)",
        "before_text": before_text or "(beginning of document)",
        "after_text": after_text or "(end of document)",
        "doc_title": doc_title or "Untitled",
        "instruction": instruction or "",
        "target_lang": target_lang,
    }

    system_content = templates["system"].format(**fmt_vars)
    user_content = templates["user"].format(**fmt_vars)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_content},
    ]

    # For chat, include conversation history
    if feature == "chat" and chat_history:
        for msg in chat_history[-10:]:  # limit to last 10 messages
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

    messages.append({"role": "user", "content": user_content})

    return messages


def get_ai_feature_code(feature: str) -> str:
    """Get the ai_requirements feature_code for calling ctx.call_ai_feature_stream()."""
    return _AI_FEATURE_CODE.get(feature, "ai_writer")


async def stream_ai_feature(
    ctx: Any,
    feature: str,
    body: dict[str, Any],
    doc_title: str = "",
) -> AsyncIterator[str]:
    """
    High-level helper: build messages → call ctx.call_ai_feature_stream() → yield deltas.

    Args:
        ctx: PluginContext
        feature: AI feature name (continue/optimize/proofread/translate/summarize/expand/rewrite/custom/chat)
        body: Request body containing selected_text, before_text, after_text, instruction, target_lang, history
        doc_title: Document title for context
    """
    feature_code = get_ai_feature_code(feature)

    messages = build_ai_messages(
        feature,
        selected_text=body.get("selected_text", ""),
        before_text=body.get("before_text", ""),
        after_text=body.get("after_text", ""),
        doc_title=doc_title,
        instruction=body.get("instruction", ""),
        target_lang=body.get("target_lang", "English"),
        chat_history=body.get("history"),
    )

    logger.info(
        "novusdoc AI: feature=%s feature_code=%s doc_title=%s msg_count=%d",
        feature, feature_code, doc_title[:50], len(messages),
    )

    async for delta in ctx.call_ai_feature_stream(feature_code, messages):
        yield delta
