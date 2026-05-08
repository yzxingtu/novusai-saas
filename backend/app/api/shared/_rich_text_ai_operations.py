"""Shared rich-text AI operation streaming helpers / 富文本 AI 操作流共享 helper。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from fastapi.responses import StreamingResponse

from app.ai.engine.stream_error_utils import (
    resolve_stream_public_error_message,
    trace_payload,
)
from app.ai.skills.rich_text_actions import (
    RICH_TEXT_AI_FEATURE_CODE,
)
from app.ai.sse import SSEChunkEncoder
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import MemoryChannelEnum, MemorySceneEnum
from app.enums.common import UserRoleEnum
from app.exceptions import BusinessException
from app.services.ai.agent_chat_service import AgentChatService
from app.services.ai.writing_service import (
    build_rich_text_agent_chat_message,
    get_rich_text_action_template,
    normalize_writing_action,
)
from app.services.system.agent_assignment_service import AgentAssignmentService

EnsureAgentAccess = Callable[[int], Awaitable[None]]
logger = LogManager.get_logger(__name__)

_FAILED_DONE_COMPLETION_REASONS = {
    "provider_unavailable",
    "provider_connection_error",
    "provider_timeout",
    "provider_rate_limit",
    "provider_error",
    "provider_http_5xx",
    "provider_bad_response",
    "stream_execution_error",
}
_FAILED_DONE_STAGE_STATUSES = {"error", "failed", "interrupted"}
_FAILED_DONE_TURN_OUTCOMES = {"failed"}


def _resolve_assignment_unavailable_error() -> BusinessException:
    return BusinessException(message=_("ai_writing.assignment_unavailable"))


def _payload_from_request(data: Any) -> dict[str, Any]:
    if hasattr(data, "model_dump"):
        return data.model_dump()
    return dict(data or {})


def _normalize_stream_payload(
    data: str,
    *,
    action_key: str,
    apply_strategy: str,
    output_contract: str,
    agent_id: int,
) -> dict[str, Any] | None:
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    event_name = str(payload.get("event") or "").strip()
    if payload.get("error") is True or event_name == "error":
        return {
            **payload,
            "event": "error",
            "code": payload.get("code") or payload.get("error_code") or "STREAM_ERROR",
            "message": str(payload.get("message") or _("common.server_error")),
            "action": action_key,
            "apply_strategy": apply_strategy,
            "output_contract": output_contract,
            "agent_id": agent_id,
        }

    if event_name == "done":
        done_failure_payload = _normalize_done_failure_payload(
            payload,
            action_key=action_key,
            apply_strategy=apply_strategy,
            output_contract=output_contract,
            agent_id=agent_id,
        )
        if done_failure_payload is not None:
            return done_failure_payload
        return {
            **payload,
            "event": "done",
            "action": action_key,
            "apply_strategy": apply_strategy,
            "output_contract": output_contract,
            "agent_id": agent_id,
        }

    if event_name == "message" or (not event_name and "delta" in payload):
        return {**payload, "event": "message"}

    return None


def _payload_text(payload: dict[str, Any], key: str) -> str:
    return str(payload.get(key) or "").strip().lower()


def _nested_payload_text(payload: dict[str, Any], *keys: str) -> str:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return str(current or "").strip().lower()


def _nested_payload_raw_text(payload: dict[str, Any], *keys: str) -> str:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return str(current or "").strip()


def _is_failed_done_payload(payload: dict[str, Any]) -> bool:
    completion_reason = _payload_text(payload, "completion_reason")
    termination_reason = _payload_text(payload, "termination_reason")
    final_stage_status = _payload_text(payload, "final_stage_status")
    turn_outcome = _payload_text(payload, "turn_outcome")
    turn_record_failure_kind = _nested_payload_text(
        payload, "turn_record", "failure_kind"
    )
    conversation_outcome = _nested_payload_text(
        payload,
        "turn_record",
        "conversation_outcome",
    )
    error_surface = _nested_payload_text(
        payload,
        "turn_record",
        "turn_flow",
        "error_surface",
        "error_type",
    )
    return bool(
        completion_reason in _FAILED_DONE_COMPLETION_REASONS
        or termination_reason in _FAILED_DONE_COMPLETION_REASONS
        or turn_record_failure_kind in _FAILED_DONE_COMPLETION_REASONS
        or final_stage_status in _FAILED_DONE_STAGE_STATUSES
        or turn_outcome in _FAILED_DONE_TURN_OUTCOMES
        or conversation_outcome == "failed"
        or error_surface
    )


def _done_failure_message(payload: dict[str, Any]) -> str:
    reason = (
        _payload_text(payload, "completion_reason")
        or _payload_text(payload, "termination_reason")
        or _nested_payload_text(payload, "turn_record", "failure_kind")
    )
    if reason in {"provider_unavailable", "provider_connection_error"}:
        return _("ai.error.provider_connection")
    if reason == "provider_timeout":
        return _("ai.error.provider_timeout")
    if reason == "provider_rate_limit":
        return _("ai.error.provider_rate_limit")
    if reason in {"provider_error", "provider_http_5xx"}:
        return _("ai.error.provider_server_error")
    if reason == "provider_bad_response":
        return _("ai.request_failed")

    error_surface_message = _nested_payload_raw_text(
        payload,
        "turn_record",
        "turn_flow",
        "error_surface",
        "message",
    )
    if error_surface_message:
        return error_surface_message
    return _("ai.request_failed")


def _normalize_done_failure_payload(
    payload: dict[str, Any],
    *,
    action_key: str,
    apply_strategy: str,
    output_contract: str,
    agent_id: int,
) -> dict[str, Any] | None:
    if not _is_failed_done_payload(payload):
        return None
    trace_id = str(payload.get("trace_id") or "").strip()
    return trace_payload(
        {
            "event": "error",
            "error": True,
            "code": (
                _payload_text(payload, "completion_reason")
                or _payload_text(payload, "termination_reason")
                or "STREAM_EXECUTION_ERROR"
            ),
            "message": _done_failure_message(payload),
            "conversation_id": payload.get("conversation_id"),
            "action": action_key,
            "apply_strategy": apply_strategy,
            "output_contract": output_contract,
            "agent_id": agent_id,
            **({"trace_id": trace_id} if trace_id else {}),
        }
    )


def _extract_sse_data(event_text: str) -> str | None:
    data_lines = []
    for raw_line in event_text.split("\n"):
        line = raw_line.strip()
        if line.startswith("data: "):
            data_lines.append(line[6:])
        elif line == "data:":
            data_lines.append("")
    if not data_lines:
        return None
    return "\n".join(data_lines)


def _rich_text_stream_error_payload(
    error: BaseException,
    *,
    action_key: str,
    apply_strategy: str,
    output_contract: str,
    agent_id: int,
) -> dict[str, Any]:
    return trace_payload(
        {
            "event": "error",
            "error": True,
            "code": getattr(error, "error_code", None) or "STREAM_EXECUTION_ERROR",
            "message": resolve_stream_public_error_message(error),
            "action": action_key,
            "apply_strategy": apply_strategy,
            "output_contract": output_contract,
            "agent_id": agent_id,
        }
    )


def _empty_rich_text_stream_error_payload(
    *,
    action_key: str,
    apply_strategy: str,
    output_contract: str,
    agent_id: int,
) -> dict[str, Any]:
    return trace_payload(
        {
            "event": "error",
            "error": True,
            "code": "STREAM_EMPTY_RESPONSE",
            "message": _("ai.stream.error.fallback_failed"),
            "action": action_key,
            "apply_strategy": apply_strategy,
            "output_contract": output_contract,
            "agent_id": agent_id,
        }
    )


async def _iter_normalized_rich_text_sse(
    response: StreamingResponse,
    *,
    action_key: str,
    apply_strategy: str,
    output_contract: str,
    agent_id: int,
) -> AsyncIterator[str]:
    buffer = ""
    terminal_event_emitted = False
    done_marker_emitted = False

    async def emit_event_text(event_text: str) -> AsyncIterator[str]:
        nonlocal terminal_event_emitted, done_marker_emitted

        if not event_text.strip():
            return
        if event_text.lstrip().startswith(":"):
            yield SSEChunkEncoder.keepalive()
            return

        data = _extract_sse_data(event_text)
        if data is None:
            return
        if data == "[DONE]":
            terminal_event_emitted = True
            done_marker_emitted = True
            yield SSEChunkEncoder.done()
            return

        payload = _normalize_stream_payload(
            data,
            action_key=action_key,
            apply_strategy=apply_strategy,
            output_contract=output_contract,
            agent_id=agent_id,
        )
        if payload is None:
            return

        if payload.get("event") in {"done", "error"}:
            terminal_event_emitted = True
        yield SSEChunkEncoder.encode(payload)

    try:
        async for chunk in response.body_iterator:
            text = (
                chunk.decode("utf-8", errors="replace")
                if isinstance(chunk, bytes)
                else str(chunk)
            )
            buffer += text.replace("\r\n", "\n")

            while "\n\n" in buffer:
                event_text, buffer = buffer.split("\n\n", 1)
                async for normalized_chunk in emit_event_text(event_text):
                    yield normalized_chunk
    except Exception as exc:
        logger.warning(
            "Rich-text AI operation stream failed: action={} agent_id={} error={}",
            action_key,
            agent_id,
            str(exc),
            exc_info=True,
        )
        if not terminal_event_emitted:
            yield SSEChunkEncoder.encode(
                _rich_text_stream_error_payload(
                    exc,
                    action_key=action_key,
                    apply_strategy=apply_strategy,
                    output_contract=output_contract,
                    agent_id=agent_id,
                )
            )
            terminal_event_emitted = True
        if not done_marker_emitted:
            yield SSEChunkEncoder.done()
        return

    tail = buffer.strip()
    if tail and not tail.startswith(":"):
        async for normalized_chunk in emit_event_text(tail):
            yield normalized_chunk

    if not terminal_event_emitted:
        yield SSEChunkEncoder.encode(
            _empty_rich_text_stream_error_payload(
                action_key=action_key,
                apply_strategy=apply_strategy,
                output_contract=output_contract,
                agent_id=agent_id,
            )
        )
        terminal_event_emitted = True

    if not done_marker_emitted:
        yield SSEChunkEncoder.done()


def normalize_rich_text_operation_stream(
    response: StreamingResponse,
    *,
    action_key: str,
    apply_strategy: str,
    output_contract: str,
    agent_id: int,
) -> StreamingResponse:
    """Return editor-domain SSE with message/done/error payloads.

    / 返回仅包含 message/done/error 的编辑器域 SSE。
    """

    return StreamingResponse(
        _iter_normalized_rich_text_sse(
            response,
            action_key=action_key,
            apply_strategy=apply_strategy,
            output_contract=output_contract,
            agent_id=agent_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def stream_rich_text_operation(
    *,
    db: Any,
    action: str,
    data: Any,
    execution_tenant_id: int,
    assignment_tenant_id: int | None,
    user_id: int | None,
    user_role: str,
    user_role_id: int | None,
    permissions: set[str] | None,
    memory_scene: str = MemorySceneEnum.AI_CHAT_PAGE.value,
    memory_channel: str = MemoryChannelEnum.TENANT_CHAT.value,
    ensure_agent_access: EnsureAgentAccess | None = None,
) -> StreamingResponse:
    """Resolve system.ai_writing and run the rich-text action through AgentChat.

    / 解析 system.ai_writing，并通过 AgentChat 执行富文本动作。
    """

    action_key = normalize_writing_action(action)
    template = get_rich_text_action_template(action_key)
    body = _payload_from_request(data)

    assignment_service = AgentAssignmentService(db)
    assignment = (
        await assignment_service.resolve(RICH_TEXT_AI_FEATURE_CODE)
        if assignment_tenant_id is None
        else await assignment_service.resolve_for_tenant(
            RICH_TEXT_AI_FEATURE_CODE,
            assignment_tenant_id,
        )
    )
    if (
        assignment is None
        or not getattr(assignment, "is_active", False)
        or not getattr(assignment, "agent_id", None)
    ):
        raise _resolve_assignment_unavailable_error()

    agent_id = int(assignment.agent_id)
    if ensure_agent_access is not None:
        await ensure_agent_access(agent_id)

    message = build_rich_text_agent_chat_message(action_key, body)
    chat_service = AgentChatService(db, execution_tenant_id)
    response = await chat_service.stream_chat(
        agent_id=agent_id,
        message=message,
        user_id=user_id,
        user_role=user_role or UserRoleEnum.TENANT_ADMIN.value,
        user_role_id=user_role_id,
        permissions=permissions,
        memory_scene=memory_scene,
        memory_channel=memory_channel,
        memory_source=RICH_TEXT_AI_FEATURE_CODE,
    )
    return normalize_rich_text_operation_stream(
        response,
        action_key=action_key,
        apply_strategy=template.apply_strategy,
        output_contract=template.output_contract,
        agent_id=agent_id,
    )


__all__ = [
    "normalize_rich_text_operation_stream",
    "stream_rich_text_operation",
]
