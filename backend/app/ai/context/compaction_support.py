"""
Context compaction support / 上下文压缩辅助

Helpers extracted from context engine to centralize compaction and snapshot logic.
从 context engine 提取的压缩与快照辅助逻辑。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from app.ai.context.compaction_snapshot_store import ContextCompactionSnapshotStore
from app.ai.context.pruning import TransientPruner
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import (
    estimate_chat_message_tokens,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.ai.engine.types import ExecutionRequest


def messages_token_estimate(messages: list[ChatMessage]) -> int:
    return sum(estimate_chat_message_tokens(message) for message in messages)


def coerce_result_messages(raw_messages: Any) -> list[ChatMessage]:
    if not isinstance(raw_messages, list):
        return []
    normalized: list[ChatMessage] = []
    for raw in raw_messages:
        if isinstance(raw, ChatMessage):
            normalized.append(raw)
            continue
        if not isinstance(raw, dict):
            continue
        try:
            normalized.append(
                ChatMessage(
                    role=str(raw.get("role") or "assistant"),
                    content=str(raw.get("content") or ""),
                    metadata=raw.get("metadata"),
                    attachments=raw.get("attachments"),
                    reasoning_content=raw.get("reasoning_content"),
                    tool_calls=raw.get("tool_calls"),
                    tool_call_id=raw.get("tool_call_id"),
                )
            )
        except Exception:
            continue
    return normalized


def inject_system_prompt_additions(
    messages: list[ChatMessage],
    additions: list[str],
) -> list[ChatMessage]:
    if not messages or not additions:
        return messages
    merged = [part.strip() for part in additions if part.strip()]
    if not merged:
        return messages
    messages[0].content = (
        (messages[0].content or "").rstrip() + "\n\n" + "\n\n".join(merged)
    )
    return messages


def compaction_split_index(
    messages: list[ChatMessage],
    *,
    keep_last_assistants: int,
    pruner: Any | None = None,
) -> int | None:
    assistant_indexes = [
        idx for idx, message in enumerate(messages) if message.role == "assistant"
    ]
    if len(assistant_indexes) <= keep_last_assistants:
        return None

    split_index = assistant_indexes[-keep_last_assistants]

    unresolved_index = None
    for idx, message in enumerate(messages):
        if idx == 0:
            continue
        pruner_impl = pruner or TransientPruner
        if message.role == "tool" and pruner_impl._has_unresolved_tool_state(message):
            unresolved_index = idx
            break
        if (
            message.role == "assistant"
            and message.tool_calls
            and pruner_impl._assistant_has_unresolved_tool_state(message)
        ):
            unresolved_index = idx
            break

    if unresolved_index is not None:
        split_index = min(split_index, unresolved_index)

    return split_index if split_index > 1 else None


def build_compact_summary(
    messages: list[ChatMessage],
    *,
    max_chars: int,
) -> str:
    lines: list[str] = []
    remaining = max(300, max_chars)

    for message in messages:
        if message.role not in {"user", "assistant"}:
            continue

        content = (message.content or "").strip()
        if not content and message.reasoning_content:
            content = message.reasoning_content.strip()
        if not content:
            continue

        normalized = " ".join(content.split())
        if not normalized:
            continue

        prefix = "User" if message.role == "user" else "Assistant"
        line = f"- {prefix}: {normalized}"
        if len(line) > 220:
            line = line[:217].rstrip() + "..."

        projected = len(line) + (1 if lines else 0)
        if projected > remaining and lines:
            break
        lines.append(line)
        remaining -= projected

    return "\n".join(lines).strip()


async def load_compaction_snapshot(
    db: AsyncSession,
    request: ExecutionRequest,
) -> dict[str, Any] | None:
    if not request.conversation_id:
        return None
    store = ContextCompactionSnapshotStore(db, request.tenant_id)
    return await store.get_snapshot(request.conversation_id)


async def persist_compaction_snapshot(
    db: AsyncSession,
    request: ExecutionRequest,
    *,
    summary: str,
    source_message_count: int,
    source_token_estimate: int,
) -> None:
    if not request.conversation_id:
        return
    store = ContextCompactionSnapshotStore(db, request.tenant_id)
    existing = await store.get_snapshot(request.conversation_id)
    if existing and isinstance(existing, dict):
        prev_summary = (existing.get("summary") or "").strip()
        new_summary = (summary or "").strip()
        if prev_summary and prev_summary == new_summary:
            return
    await store.upsert_snapshot(
        request.conversation_id,
        summary=summary,
        source_message_count=source_message_count,
        source_token_estimate=source_token_estimate,
    )


async def compact_messages_if_needed(
    *,
    context_config: dict[str, Any],
    messages: list[ChatMessage],
    persist_snapshot: Callable[..., Awaitable[None]],
    pruner: Any | None = None,
    messages_token_estimate_fn: Callable[[list[ChatMessage]], int] | None = None,
    compaction_split_index_fn: Callable[..., int | None] | None = None,
    build_compact_summary_fn: Callable[..., str] | None = None,
) -> None:
    token_estimator = messages_token_estimate_fn or messages_token_estimate
    split_index_builder = compaction_split_index_fn or compaction_split_index
    compact_summary_builder = build_compact_summary_fn or build_compact_summary
    compact_threshold_tokens = int(
        context_config.get("compact_threshold_tokens", 0) or 0
    )
    if compact_threshold_tokens <= 0:
        return

    compact_keep_last_assistants = int(
        context_config.get("compact_keep_last_assistants", 3) or 3
    )
    compact_max_summary_chars = int(
        context_config.get("compact_max_summary_chars", 1600) or 1600
    )
    source_tokens = token_estimator(messages)
    if source_tokens <= compact_threshold_tokens:
        return

    split_index = split_index_builder(
        messages,
        keep_last_assistants=compact_keep_last_assistants,
        pruner=pruner,
    )
    if split_index is None or split_index <= 1:
        return

    prefix = messages[1:split_index]
    rebuilt_summary = compact_summary_builder(
        prefix,
        max_chars=compact_max_summary_chars,
    )
    if not rebuilt_summary:
        return

    await persist_snapshot(
        summary=rebuilt_summary,
        source_message_count=len(prefix),
        source_token_estimate=token_estimator(prefix),
    )


__all__ = [
    "build_compact_summary",
    "compact_messages_if_needed",
    "coerce_result_messages",
    "compaction_split_index",
    "inject_system_prompt_additions",
    "load_compaction_snapshot",
    "messages_token_estimate",
    "persist_compaction_snapshot",
]
