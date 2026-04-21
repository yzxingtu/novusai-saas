"""Extraction helpers for turn-level research."""

from __future__ import annotations

from typing import Any

from app.ai.types import ChatMessage

from .base_helpers import (
    parse_tool_arguments,
    tool_call_name,
    tool_call_operation_name,
)


def extract_fetch_title_from_output(output: str) -> str:
    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()
        if line.startswith("Title: "):
            return line.removeprefix("Title: ").strip()
    return ""


def normalize_web_research_contract_text(text: str) -> str:
    value = " ".join(str(text or "").split())
    if not value:
        return ""
    if value.startswith("[") and "](" in value and value.endswith(")"):
        value = value[1 : value.index("](")].strip()
    for prefix in (
        "title:",
        "标题:",
        "标题是",
        "网页标题:",
        "页面标题:",
        "source:",
        "来源:",
    ):
        if value.casefold().startswith(prefix.casefold()):
            value = value[len(prefix) :].strip()
            break
    return value.strip(" \t\r\n\"'`[](){}<>.,;:!?。，；：！？、").casefold()


def collect_current_turn_fetch_titles(messages: list[ChatMessage]) -> list[str]:
    last_user_index = -1
    for index, msg in enumerate(messages):
        if msg.role == "user":
            last_user_index = index

    turn_messages = (
        messages[last_user_index + 1 :] if last_user_index >= 0 else messages
    )
    fetch_call_ids: set[str] = set()
    titles: list[str] = []
    seen_titles: set[str] = set()

    for msg in turn_messages:
        if msg.role != "assistant" or not msg.tool_calls:
            continue
        for tool_call in msg.tool_calls:
            if tool_call.get("success") is not True:
                continue
            if tool_call_name(tool_call) != "fetch_url":
                continue
            tool_call_id = str(
                tool_call.get("id") or tool_call.get("tool_call_id") or ""
            ).strip()
            if tool_call_id:
                fetch_call_ids.add(tool_call_id)

    for msg in turn_messages:
        if msg.role != "tool":
            continue
        tool_call_id = str(getattr(msg, "tool_call_id", "") or "").strip()
        if fetch_call_ids:
            if tool_call_id and tool_call_id not in fetch_call_ids:
                continue
            if not tool_call_id and "Content from " not in str(msg.content or ""):
                continue

        title = extract_fetch_title_from_output(msg.content or "")
        if not title:
            continue
        normalized = normalize_web_research_contract_text(title)
        if not normalized or normalized in seen_titles:
            continue
        titles.append(title)
        seen_titles.add(normalized)

    return titles


def looks_like_explicit_title_request(user_text: str) -> bool:
    normalized = " ".join(str(user_text or "").casefold().split())
    if not normalized:
        return False
    return any(
        term in normalized
        for term in (
            "标题",
            "headline",
            "page title",
            "article title",
            "title of",
            "what is the title",
        )
    )


def is_title_only_fetch_response(
    *,
    messages: list[ChatMessage],
    response_text: str,
    user_text: str,
) -> bool:
    if looks_like_explicit_title_request(user_text):
        return False

    normalized_response = normalize_web_research_contract_text(response_text)
    if not normalized_response:
        return False

    fetched_titles = collect_current_turn_fetch_titles(messages)
    if not fetched_titles:
        return False

    return any(
        normalized_response == normalize_web_research_contract_text(title)
        for title in fetched_titles
    )


def extract_last_user_text(messages: list[ChatMessage]) -> str:
    for msg in reversed(messages):
        if msg.role != "user":
            continue
        text = (msg.content or "").strip()
        if text:
            return text
    return ""


def extract_recent_research_instruction_texts(
    prior_messages: list[ChatMessage],
    current_user_text: str,
    *,
    limit: int = 3,
) -> list[str]:
    texts: list[str] = []
    if current_user_text:
        texts.append(current_user_text)

    for msg in reversed(prior_messages):
        if msg.role != "user":
            continue
        text = (msg.content or "").strip()
        if not text or text in texts:
            continue
        texts.append(text)
        if len(texts) >= limit:
            break

    return list(reversed(texts))


def extract_latest_turn_runtime_facts(messages: list[ChatMessage]) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "last_tool_name": "",
        "last_page_key": "",
        "last_page_op": "",
        "active_intent_kind": None,
    }

    def _candidate_text(
        candidates: list[dict[str, Any]],
        key: str,
    ) -> str:
        for candidate in candidates:
            value = str(candidate.get(key) or "").strip()
            if value:
                return value
        return ""

    def _candidate_dicts(message: ChatMessage) -> list[dict[str, Any]]:
        metadata = (
            dict(message.metadata or {}) if isinstance(message.metadata, dict) else {}
        )
        candidates = [metadata]
        for key in ("turn_record", "context_diagnostics", "last_run_summary"):
            value = metadata.get(key)
            if isinstance(value, dict):
                candidates.append(dict(value))
        turn_record = metadata.get("turn_record")
        if isinstance(turn_record, dict):
            turn_record_metadata = turn_record.get("metadata")
            if isinstance(turn_record_metadata, dict):
                candidates.append(dict(turn_record_metadata))
                diagnostics = turn_record_metadata.get("turn_diagnostics")
                if isinstance(diagnostics, dict):
                    candidates.append(dict(diagnostics))
        return candidates

    for message in reversed(messages):
        if message.role != "assistant":
            continue

        candidates = _candidate_dicts(message)
        if not facts["active_intent_kind"]:
            for candidate in candidates:
                tool_planner = candidate.get("tool_planner")
                if isinstance(tool_planner, dict):
                    intent_kind = str(tool_planner.get("intent") or "").strip()
                    if intent_kind:
                        facts["active_intent_kind"] = intent_kind
                        break
                intent_kind = str(candidate.get("active_intent_kind") or "").strip()
                if intent_kind:
                    facts["active_intent_kind"] = intent_kind
                    break
        if not facts["last_tool_name"]:
            facts["last_tool_name"] = _candidate_text(candidates, "last_tool_name")
        if not facts["last_page_key"]:
            facts["last_page_key"] = _candidate_text(candidates, "last_page_key")
        if not facts["last_page_op"]:
            facts["last_page_op"] = _candidate_text(candidates, "last_page_op")

        for tool_call in reversed(message.tool_calls or []):
            if tool_call.get("success") is not True:
                continue
            if not facts["last_tool_name"]:
                facts["last_tool_name"] = tool_call_name(tool_call)
            if not facts["last_page_op"]:
                facts["last_page_op"] = tool_call_operation_name(tool_call)
            if not facts["last_page_key"]:
                arguments = parse_tool_arguments(
                    (tool_call.get("function") or {}).get("arguments")
                )
                facts["last_page_key"] = str(arguments.get("page_key") or "").strip()
            if (
                facts["last_tool_name"]
                and facts["last_page_op"]
                and facts["last_page_key"]
                and facts["active_intent_kind"]
            ):
                return facts
        if facts["last_tool_name"] and facts["active_intent_kind"]:
            return facts

    return facts
