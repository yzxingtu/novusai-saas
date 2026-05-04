"""
Builtin fetch_url provider adapter for WebResearchRuntime.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.web_research.contracts import FetchOptions
from app.ai.web_research.evidence import PageEvidence, PageStatus
from app.ai.web_research.normalization import normalize_page_evidence

FetchToolExecutor = Callable[[str, int], Awaitable[ToolResult]]

BUILTIN_FETCH_URL_PROVIDER_ID = "builtin:fetch_url"
_DEFAULT_MAX_LENGTH = 5000
_TOOL_DEFINITION = ToolDefinition(name="fetch_url", description="Fetch a webpage")


class BuiltinFetchUrlProvider:
    """Adapt builtin fetch_url ToolResult output into PageEvidence."""

    def __init__(
        self,
        *,
        fetch_executor: FetchToolExecutor | None = None,
        provider_id: str = BUILTIN_FETCH_URL_PROVIDER_ID,
    ) -> None:
        self._fetch_executor = fetch_executor or _execute_builtin_fetch_tool
        self._provider_id = provider_id

    @property
    def provider_id(self) -> str:
        return self._provider_id

    async def fetch(self, url: str, options: FetchOptions) -> PageEvidence:
        requested_url = str(url or "").strip()
        max_length = _max_length_from_options(options)
        result = await self._fetch_executor(requested_url, max_length)
        return page_evidence_from_fetch_tool_result(
            result,
            requested_url=requested_url,
            provider_id=self.provider_id,
        )


def page_evidence_from_fetch_tool_result(
    result: ToolResult,
    *,
    requested_url: str,
    provider_id: str = BUILTIN_FETCH_URL_PROVIDER_ID,
) -> PageEvidence:
    """Normalize a real fetch_url ToolResult shape into PageEvidence."""

    summary_payload = dict(result.summary_payload or {})
    parsed_output = _parse_fetch_output(result.output)
    final_url = _first_text(
        summary_payload.get("final_url"),
        parsed_output.get("final_url"),
        requested_url,
    )
    title = _first_text(summary_payload.get("title"), parsed_output.get("title"))
    description = _first_text(
        summary_payload.get("description"),
        parsed_output.get("description"),
    )
    summary = _first_text(summary_payload.get("summary"), result.summary)
    body_text = str(parsed_output.get("body_text") or "").strip()
    status = _page_status_from_tool_result(result)
    failure_kind = None if status == "completed" else _fetch_failure_kind(result)

    return normalize_page_evidence(
        url=final_url,
        status=status,
        title=title,
        body_text=body_text if result.success else "",
        summary=summary if result.success else "",
        description=description,
        provider=provider_id,
        failure_kind=failure_kind,
        raw={
            "builtin_tool": "fetch_url",
            "tool_call_id": result.tool_call_id,
            "success": result.success,
            "error": result.error,
            "error_type": result.error_type,
            "duration_ms": result.duration_ms,
            "requested_url": requested_url,
            "summary_payload": summary_payload,
        },
    )


async def _execute_builtin_fetch_tool(url: str, max_length: int) -> ToolResult:
    from app.ai.tools.executors.builtin_executor import BuiltinToolExecutor

    executor = BuiltinToolExecutor()
    return await executor.execute(
        _TOOL_DEFINITION,
        f"web_research_fetch:{url}",
        {"url": url, "max_length": max_length},
    )


def _max_length_from_options(options: FetchOptions) -> int:
    diagnostics = dict(options.diagnostics or {})
    raw_value = diagnostics.get("fetch_max_length", diagnostics.get("max_length"))
    try:
        return min(max(500, int(raw_value or _DEFAULT_MAX_LENGTH)), 20000)
    except (TypeError, ValueError):
        return _DEFAULT_MAX_LENGTH


def _parse_fetch_output(output: str) -> dict[str, str]:
    text = str(output or "").strip()
    if not text:
        return {}

    lines = text.splitlines()
    final_url = ""
    title = ""
    description = ""
    body_start: int | None = None
    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if body_start is None and not line:
            body_start = index + 1
            continue
        if not final_url and line.startswith("Content from "):
            final_url = line.removeprefix("Content from ").rstrip(":").strip()
            continue
        if not title and line.startswith("Title: "):
            title = line.removeprefix("Title: ").strip()
            continue
        if not description and line.startswith("Description: "):
            description = line.removeprefix("Description: ").strip()

    if body_start is None:
        body_lines = [
            line
            for line in lines
            if not line.strip().startswith(
                ("Content from ", "Redirected from: ", "Title: ", "Description: ")
            )
        ]
    else:
        body_lines = lines[body_start:]

    return {
        "final_url": final_url,
        "title": title,
        "description": description,
        "body_text": "\n".join(body_lines).strip(),
    }


def _page_status_from_tool_result(result: ToolResult) -> PageStatus:
    if result.success:
        return "completed"
    error_type = str(result.error_type or "").strip()
    payload_error_type = str(
        (result.summary_payload or {}).get("error_type") or ""
    ).strip()
    if error_type == "blocked_url" or payload_error_type == "blocked_url":
        return "blocked"
    return "failed"


def _fetch_failure_kind(result: ToolResult) -> str:
    error_type = str(result.error_type or "").strip()
    payload_error_type = str(
        (result.summary_payload or {}).get("error_type") or ""
    ).strip()
    return error_type or payload_error_type or "fetch_failed"


def _first_text(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


__all__ = [
    "BUILTIN_FETCH_URL_PROVIDER_ID",
    "BuiltinFetchUrlProvider",
    "page_evidence_from_fetch_tool_result",
]
