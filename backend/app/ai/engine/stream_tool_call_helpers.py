"""Helpers for streamed tool-call aggregation and action parsing."""

from __future__ import annotations

import json
from typing import Any


def chunk_text_for_streaming(text: str, chunk_size: int = 32) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    for index in range(0, len(text), chunk_size):
        chunks.append(text[index : index + chunk_size])
    return chunks


def normalize_stream_tool_call(tool_call: Any) -> dict[str, Any] | None:
    if not tool_call:
        return None

    if isinstance(tool_call, dict):
        index = tool_call.get("index")
        tc_id = tool_call.get("id") or ""
        tc_type = tool_call.get("type") or "function"
        func = tool_call.get("function") or {}
        if not isinstance(func, dict):
            func = {}
        func_name = func.get("name") or ""
        func_arguments = func.get("arguments") or ""
    else:
        index = getattr(tool_call, "index", None)
        tc_id = getattr(tool_call, "id", None) or ""
        tc_type = getattr(tool_call, "type", None) or "function"
        func_obj = getattr(tool_call, "function", None)
        if isinstance(func_obj, dict):
            func_name = func_obj.get("name") or ""
            func_arguments = func_obj.get("arguments") or ""
        else:
            func_name = getattr(func_obj, "name", None) or ""
            func_arguments = getattr(func_obj, "arguments", None) or ""

    if isinstance(index, str) and index.isdigit():
        index = int(index)
    if not isinstance(index, int):
        index = None

    return {
        "_index": index,
        "id": tc_id,
        "type": tc_type,
        "function": {
            "name": func_name,
            "arguments": func_arguments,
        },
    }


def _merge_stream_fragment(current: str, incoming: str) -> str:
    if not incoming:
        return current
    if not current:
        return incoming
    if incoming == current or incoming in current:
        return current
    if incoming.startswith(current):
        return incoming
    max_overlap = min(len(current), len(incoming))
    for overlap in range(max_overlap, 0, -1):
        if current.endswith(incoming[:overlap]):
            return current + incoming[overlap:]
    return current + incoming


def _is_complete_json_value(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    try:
        json.loads(normalized)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    return True


def _merge_stream_arguments(current: str, incoming: str) -> str:
    current_text = str(current or "")
    incoming_text = str(incoming or "")
    if not incoming_text:
        return current_text
    if not current_text:
        return incoming_text
    if incoming_text == current_text or incoming_text in current_text:
        return current_text
    if _is_complete_json_value(current_text) and _is_complete_json_value(incoming_text):
        return incoming_text
    if incoming_text.startswith(current_text):
        return incoming_text
    return _merge_stream_fragment(current_text, incoming_text)


def merge_stream_tool_calls(
    existing: list[dict[str, Any]],
    incoming: list[Any],
) -> list[dict[str, Any]]:
    merged = existing[:]

    for raw_tool_call in incoming:
        normalized = normalize_stream_tool_call(raw_tool_call)
        if not normalized:
            continue

        target: dict[str, Any] | None = None
        tc_index = normalized.get("_index")
        tc_id = normalized.get("id")

        if tc_index is not None:
            for item in merged:
                if item.get("_index") == tc_index:
                    target = item
                    break

        if target is None and tc_id:
            for item in merged:
                if item.get("id") == tc_id:
                    target = item
                    break

        if target is None:
            merged.append(normalized)
            target = merged[-1]
        else:
            if tc_id and not target.get("id"):
                target["id"] = tc_id

        target_func = target.setdefault("function", {})
        normalized_func = normalized.get("function", {})

        tc_name = normalized_func.get("name") or ""
        if tc_name:
            current_name = target_func.get("name", "")
            target_func["name"] = _merge_stream_fragment(current_name, tc_name)

        tc_args = normalized_func.get("arguments") or ""
        if tc_args:
            current_args = target_func.get("arguments", "")
            target_func["arguments"] = _merge_stream_arguments(
                current_args,
                tc_args,
            )

    return merged


def finalize_stream_tool_calls(
    calls: list[dict[str, Any]],
    *,
    logger: Any | None = None,
) -> list[dict[str, Any]]:
    finalized: list[dict[str, Any]] = []

    for idx, tool_call in enumerate(calls):
        func = tool_call.get("function") or {}
        name = (func.get("name") or "").strip()
        if not name:
            if logger is not None:
                logger.warning(
                    "Skip invalid streamed tool_call without name: {}", tool_call
                )
            continue

        arguments = func.get("arguments")
        if arguments in (None, ""):
            arguments = "{}"

        tool_call_id = tool_call.get("id") or f"stream_tool_{idx}"
        if isinstance(arguments, str) and len(arguments) > 200 and logger is not None:
            logger.debug(
                "Finalized tool_call: name={} args_len={} args_head={}",
                name,
                len(arguments),
                repr(arguments[:300]),
            )
        finalized.append(
            {
                "id": tool_call_id,
                "type": tool_call.get("type") or "function",
                "function": {
                    "name": name,
                    "arguments": arguments,
                },
            }
        )

    return finalized


def extract_action_buttons(
    output: str,
    *,
    action_start: str = "[ACTIONS]",
    action_end: str = "[/ACTIONS]",
    logger: Any | None = None,
) -> tuple[str, list[dict[str, str]] | None]:
    start_idx = output.find(action_start)
    if start_idx < 0:
        return output, None

    end_idx = output.find(action_end, start_idx + len(action_start))
    if end_idx < 0:
        return output, None

    raw = output[start_idx + len(action_start) : end_idx].strip()
    try:
        buttons = json.loads(raw)
        if not isinstance(buttons, list):
            return output, None
        valid_buttons: list[dict[str, str]] = []
        for btn in buttons:
            if isinstance(btn, dict) and "label" in btn and "value" in btn:
                item: dict[str, str] = {
                    "label": str(btn["label"]),
                    "value": str(btn["value"]),
                }
                if "style" in btn and btn["style"] in (
                    "primary",
                    "default",
                    "danger",
                ):
                    item["style"] = btn["style"]
                valid_buttons.append(item)
        if not valid_buttons:
            return output, None
        cleaned = (output[:start_idx] + output[end_idx + len(action_end) :]).strip()
        return cleaned, valid_buttons
    except (json.JSONDecodeError, TypeError, ValueError):
        if logger is not None:
            logger.warning("Failed to parse action buttons from LLM output")
        return output, None
