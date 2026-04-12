"""Evidence extraction helpers for turn-level research."""

from __future__ import annotations

from app.ai.types import ChatMessage

from .base_helpers import parse_tool_arguments, tool_call_name


def extract_recent_successful_tool_names(
    messages: list[ChatMessage],
    *,
    limit: int = 12,
) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    for msg in reversed(messages):
        if msg.role != "assistant" or not msg.tool_calls:
            continue

        for tool_call in reversed(msg.tool_calls):
            if tool_call.get("success") is not True:
                continue
            tool_name = tool_call_name(tool_call)
            if not tool_name or tool_name in seen:
                continue
            names.append(tool_name)
            seen.add(tool_name)
            if len(names) >= limit:
                return names

    return names


def extract_recent_web_queries(
    messages: list[ChatMessage],
    *,
    limit: int = 5,
) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()

    for msg in reversed(messages):
        if msg.role != "assistant" or not msg.tool_calls:
            continue

        for tool_call in reversed(msg.tool_calls):
            if tool_call.get("success") is not True:
                continue
            tool_name = tool_call_name(tool_call)
            if tool_name != "web_search":
                continue
            arguments = parse_tool_arguments(
                (tool_call.get("function") or {}).get("arguments")
            )
            query = str(arguments.get("query") or "").strip()
            if not query or query in seen:
                continue
            queries.append(query)
            seen.add(query)
            if len(queries) >= limit:
                return queries

    return queries


def collect_web_research_evidence(
    messages: list[ChatMessage],
) -> tuple[list[str], list[str]]:
    search_queries: list[str] = []
    fetched_urls: list[str] = []
    seen_queries: set[str] = set()
    seen_urls: set[str] = set()

    for msg in messages:
        if msg.role != "assistant" or not msg.tool_calls:
            continue

        for tool_call in msg.tool_calls:
            if tool_call.get("success") is not True:
                continue
            tool_name = tool_call_name(tool_call)
            arguments = parse_tool_arguments(
                (tool_call.get("function") or {}).get("arguments")
            )
            if tool_name == "web_search":
                query = str(arguments.get("query") or "").strip()
                if query and query not in seen_queries:
                    search_queries.append(query)
                    seen_queries.add(query)
            elif tool_name == "fetch_url":
                url = str(arguments.get("url") or "").strip()
                if url and url not in seen_urls:
                    fetched_urls.append(url)
                    seen_urls.add(url)

    return search_queries, fetched_urls
