"""
Unified Tool Call Processor / 统一工具调用处理器

Extracts shared tool call core logic for execute() and stream_execute():
提取 execute() 和 stream_execute() 共享的工具调用核心逻辑：
- Argument parsing / 参数解析
- Sandbox execution / 沙箱执行
- Message building / 消息构建
- Confirmation interception / 确认拦截
- consent_mode checking / consent_mode 检查
- SSE event building / SSE 事件构建
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, replace
from typing import Any

from app.ai.text_semantics import (
    is_confirmation_reply,
    is_rejection_reply,
    remove_trailing_json_commas,
    strip_model_function_call_markup,
)
from app.ai.tools.sandbox import ToolSandbox
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage
from app.core.i18n import _
from app.core.logging import LogManager
from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY

from .execution_state_machine import get_current_execution_state_machine

logger = LogManager.get_logger("ai.engine.tool_processor")

# Readonly ops safe to dedupe within one assistant turn / 同轮可安全去重的只读页面操作名
# Excludes view-changing ops (search, paging, refresh): same name+args can advance UI state.
# 不含会改变表格/检索视图的操作（翻页、搜索、刷新）：同参重复调用应再次执行而非命中缓存。
_READONLY_PAGE_OPERATION_NAMES = frozenset(
    {
        "read_current_view",
        "read_current_sections",
        "read_visible_rows",
        "get_form_state",
        "get_form_options",
        "list_available_menus",
        "capture_screenshot",
        "get_editor_html",
        "validate_form",
    }
)


def is_trusted_auto_read_only_tool_call(
    func_name: str,
    arguments: dict[str, Any] | None = None,
) -> bool:
    """Readonly tools that can skip consent in trusted_auto mode."""
    name = (func_name or "").strip()
    if not name:
        return False
    if name in {
        "get_current_weather",
        "get_weather_forecast",
        "get_current_time",
        "web_search",
        "fetch_url",
        "get_page_context",
        "list_page_operations",
    }:
        return True
    if name.startswith("pageop_"):
        return name.removeprefix("pageop_") in _READONLY_PAGE_OPERATION_NAMES
    if name == "invoke_page_operation":
        op = str((arguments or {}).get("operation_name") or "").strip()
        return op in _READONLY_PAGE_OPERATION_NAMES
    return False


def _strip_dsml_from_args(s: str) -> str:
    """Remove leaked DSML markers from tool arguments (DeepSeek etc.)."""
    return strip_model_function_call_markup(s)


def _fix_unescaped_control_chars(s: str) -> str:
    """Replace unescaped control chars inside JSON string values (with look-ahead
    quote disambiguation to handle embedded quotes like "她叫"小喵"的猫").
    """
    chars = list(s)
    n = len(chars)
    result: list[str] = []
    in_string = False
    escape_next = False
    i = 0
    while i < n:
        ch = chars[i]
        if in_string:
            if escape_next:
                result.append(ch)
                escape_next = False
            elif ch == "\\":
                result.append(ch)
                escape_next = True
            elif ch == '"':
                # Look-ahead: next non-ws JSON structural char ends string; else embedded quote / 前瞻：下一非空白为 JSON 结构符则闭串，否则为内嵌引号
                j = i + 1
                while j < n and chars[j] in " \t\r\n":
                    j += 1
                if j >= n or chars[j] in ":,}]":
                    in_string = False
                    result.append(ch)
                else:
                    result.append('\\"')
            elif ch == "\n":
                result.append("\\n")
            elif ch == "\r":
                result.append("\\r")
            elif ch == "\t":
                result.append("\\t")
            else:
                result.append(ch)
        else:
            if ch == '"':
                in_string = True
            result.append(ch)
        i += 1
    return "".join(result)


def _brute_force_control_chars(s: str) -> str:
    """Replace ALL literal control characters (\n, \r, \t) with spaces
    as a last-resort fix when context-aware repair fails."""
    return (
        s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("\t", " ")
    )


def _try_convert_single_quotes(s: str) -> str | None:
    """Try converting Python-style single-quoted dict to JSON (only when appropriate)."""
    s = s.strip()
    if not s.startswith("{") or "'" not in s:
        return None
    try:
        import ast

        parsed = ast.literal_eval(s)
        if isinstance(parsed, dict):
            return json.dumps(parsed, ensure_ascii=False)
    except (ValueError, SyntaxError):
        pass
    return None


def _try_fix_truncation(s: str) -> str:
    """Try closing truncated string and brackets with look-ahead quote handling."""
    chars = list(s)
    n = len(chars)
    result: list[str] = []
    in_string = False
    escape_next = False
    brace_stack: list[str] = []
    i = 0
    while i < n:
        ch = chars[i]
        if in_string:
            if escape_next:
                result.append(ch)
                escape_next = False
            elif ch == "\\":
                result.append(ch)
                escape_next = True
            elif ch == '"':
                j = i + 1
                while j < n and chars[j] in " \t\r\n":
                    j += 1
                if j >= n or chars[j] in ":,}]":
                    in_string = False
                    result.append(ch)
                else:
                    result.append('\\"')
            elif ch == "\n":
                result.append("\\n")
            elif ch == "\r":
                result.append("\\r")
            elif ch == "\t":
                result.append("\\t")
            else:
                result.append(ch)
        else:
            if ch == '"':
                in_string = True
            if ch == "{":
                brace_stack.append("}")
            elif ch == "[":
                brace_stack.append("]")
            elif ch in "}]" and brace_stack:
                brace_stack.pop()
            result.append(ch)
        i += 1
    if in_string:
        result.append('"')
    while brace_stack:
        result.append(brace_stack.pop())
    return "".join(result)


def _try_repair_json(raw: str) -> dict[str, Any] | None:
    """
    Attempt to repair common JSON malformations.
    尝试修复常见 JSON 畸形：DSML 泄漏、尾部逗号、缺失括号、
    未转义控制字符、Python 风格单引号、截断。
    """
    s = raw.strip()
    # Phase A: DSML cleanup / 阶段 A：去除 DSML
    s = _strip_dsml_from_args(s)

    # Trailing commas and missing brackets / 尾部逗号与补全括号
    s = remove_trailing_json_commas(s)
    s_before_braces = s
    opens = s.count("{") - s.count("}")
    if opens > 0:
        s += "}" * opens
    opens = s.count("[") - s.count("]")
    if opens > 0:
        s += "]" * opens

    try:
        parsed = json.loads(s)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    # Phase B: unescaped control chars in strings / 阶段 B：字符串内未转义控制字符
    s2 = _fix_unescaped_control_chars(s)
    if s2 != s:
        try:
            parsed = json.loads(s2)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            s = s2

    # Phase C: Python-style single-quoted dict / 阶段 C：Python 单引号字典
    s3 = _try_convert_single_quotes(s)
    if s3:
        try:
            parsed = json.loads(s3)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

    # Phase D: truncation repair — use s before brace padding so } does not close inside string / 阶段 D：截断修复（补括号前字符串，避免 } 误入未闭合串）
    s4 = _try_fix_truncation(s_before_braces)
    if s4 != s:
        try:
            parsed = json.loads(s4)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

    # Phase E: replace control chars with spaces (last resort; may lose newlines) / 阶段 E：控制符替换为空格（最后手段，可能丢失换行语义）
    s5 = _brute_force_control_chars(s)
    if s5 != s:
        # Again strip trailing commas and balance braces on cleaned string / 清理后再次去尾部逗号并补括号
        s5 = remove_trailing_json_commas(s5)
        opens = s5.count("{") - s5.count("}")
        if opens > 0:
            s5 += "}" * opens
        opens = s5.count("[") - s5.count("]")
        if opens > 0:
            s5 += "]" * opens
        try:
            parsed = json.loads(s5)
            if isinstance(parsed, dict):
                logger.info("JSON repaired via brute-force control-char replacement")
                return parsed
        except json.JSONDecodeError:
            pass

    return None


@dataclass
class SingleToolResult:
    """Single tool call processing result / 单个工具调用处理结果"""

    tool_result: ToolResult | None = None
    duration_ms: int = 0
    tool_message: ChatMessage | None = None
    follow_up_message: ChatMessage | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    has_confirmation: bool = False
    skipped: bool = False


class ToolCallProcessor:
    """
    Unified Tool Call Processor / 统一工具调用处理器

    Encapsulates core tool call logic, shared by execute() and stream_execute().
    封装工具调用的核心逻辑，供 execute() 和 stream_execute() 共用。
    """

    def __init__(
        self,
        sandbox: ToolSandbox,
        tools: list[ToolDefinition],
        all_tools: list[ToolDefinition] | None = None,
        consent_modes: dict[str, str] | None = None,
        approved_pending_consent_tools: set[str] | None = None,
        interaction_mode: str = "confirm",
    ):
        self.sandbox = sandbox
        self.tools = tools
        self.all_tools = all_tools or tools
        self.consent_modes = consent_modes or {}
        self._interaction_mode = str(interaction_mode or "confirm").strip() or "confirm"
        self.approved_pending_consent_tools = {
            str(name).strip()
            for name in (approved_pending_consent_tools or set())
            if str(name).strip()
        }
        # Same-turn dedupe for idempotent readonly tools (665-style repeat calls).
        self._readonly_success_cache: dict[str, tuple[ToolResult, int]] = {}
        self._page_context_cache: dict[str, tuple[ToolResult, int]] = {}
        self._search_query_cache: dict[str, tuple[ToolResult, int]] = {}

    # ========================================
    # Core Methods / 核心方法
    # ========================================

    # Readonly tools safe to run concurrently / 可安全并发执行的只读工具
    _PARALLEL_SAFE_TOOLS: frozenset[str] = frozenset(
        {
            "web_search",
            "fetch_url",
            "get_current_time",
            "get_current_weather",
            "get_weather_forecast",
            "calculate",
            "format_json",
        }
    )

    @staticmethod
    def is_parallel_safe_tool_call(
        func_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> bool:
        """Allow readonly batches to run concurrently."""
        _ = arguments
        return str(func_name or "").strip() in ToolCallProcessor._PARALLEL_SAFE_TOOLS

    @staticmethod
    def _live_page_session_id(sandbox: ToolSandbox | None, iv: dict[str, Any]) -> str:
        """Prefer sandbox session id (updated after navigation); else variables['page_session_id']."""
        if sandbox is not None:
            sid = getattr(sandbox, "_page_session_id", None)
            if isinstance(sid, str) and sid.strip():
                return sid.strip()
        raw = iv.get("page_session_id")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        return ""

    def _page_identity_cache_segment(self) -> str:
        """Narrow dedupe to current page so navigation cannot replay stale snapshots."""
        sb = self.sandbox
        iv: dict[str, Any] = {}
        if sb is not None:
            raw_iv = getattr(sb, "input_variables", None)
            if isinstance(raw_iv, dict):
                iv = raw_iv
        pc = iv.get(PAGE_CONTEXT_KEY)
        if not isinstance(pc, dict):
            pc = iv.get("page_context")
        page_key = ""
        if isinstance(pc, dict):
            page_key = str(pc.get("page_key") or "").strip()
        session_id = self._live_page_session_id(sb, iv)
        epoch = 0
        if sb is not None:
            try:
                epoch = int(getattr(sb, "_page_readonly_cache_epoch", 0) or 0)
            except (TypeError, ValueError):
                epoch = 0
        return f"|pk={page_key}|sid={session_id}|e={epoch}"

    @staticmethod
    def _invalidates_same_page_readonly_cache(
        func_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        """True after successful runs that can change same-page UI state (invalidates read snapshots)."""
        name = (func_name or "").strip()
        if name == "get_page_context":
            return False
        if name.startswith("pageop_"):
            op = name.removeprefix("pageop_")
            return op not in _READONLY_PAGE_OPERATION_NAMES
        if name == "invoke_page_operation":
            op = str(arguments.get("operation_name") or "").strip()
            return op not in _READONLY_PAGE_OPERATION_NAMES
        return False

    def _bump_page_readonly_cache_epoch_if_needed(
        self,
        func_name: str,
        arguments: dict[str, Any],
        result: ToolResult,
    ) -> None:
        if not result.success or not self._invalidates_same_page_readonly_cache(
            func_name, arguments
        ):
            return
        sb = self.sandbox
        if sb is None:
            return
        try:
            cur = int(getattr(sb, "_page_readonly_cache_epoch", 0) or 0)
        except (TypeError, ValueError):
            cur = 0
        sb._page_readonly_cache_epoch = cur + 1

    def _normalized_readonly_cache_key(
        self,
        func_name: str,
        arguments: dict[str, Any],
        conversation_id: int | None,
    ) -> str | None:
        """Return cache key for dedupe, or None if tool should never be deduped."""
        name = (func_name or "").strip()
        if not name:
            return None
        page_suffix = ""
        if name in {
            "get_current_weather",
            "get_weather_forecast",
            "get_current_time",
            "web_search",
            "fetch_url",
        }:
            pass
        elif name == "get_page_context":
            page_suffix = self._page_identity_cache_segment()
        elif name.startswith("pageop_"):
            op = name.removeprefix("pageop_")
            if op not in _READONLY_PAGE_OPERATION_NAMES:
                return None
            page_suffix = self._page_identity_cache_segment()
        elif name == "invoke_page_operation":
            op = str(arguments.get("operation_name") or "").strip()
            if op not in _READONLY_PAGE_OPERATION_NAMES:
                return None
            page_suffix = self._page_identity_cache_segment()
        else:
            return None
        try:
            payload = json.dumps(arguments, sort_keys=True, ensure_ascii=False)
        except (TypeError, ValueError):
            payload = str(arguments)
        conv_segment = f"|cid={int(conversation_id or 0)}"
        return f"{name}|{payload}{page_suffix}{conv_segment}"

    def _cache_kind_for_tool(self, func_name: str) -> str:
        name = (func_name or "").strip()
        if name == "web_search":
            return "search_query"
        if name == "get_page_context":
            return "page_context"
        return "readonly"

    def _cache_signature(
        self,
        func_name: str,
        arguments: dict[str, Any],
        conversation_id: int | None,
    ) -> tuple[str, str] | None:
        key = self._normalized_readonly_cache_key(
            func_name,
            arguments,
            conversation_id,
        )
        if not key:
            return None
        kind = self._cache_kind_for_tool(func_name)
        return kind, key

    def _cache_store_for_kind(self, kind: str) -> dict[str, tuple[ToolResult, int]]:
        state = get_current_execution_state_machine()
        if state is not None:
            return state.cache_for_kind(kind)
        if kind == "search_query":
            return self._search_query_cache
        if kind == "page_context":
            return self._page_context_cache
        return self._readonly_success_cache

    @staticmethod
    def _active_intent() -> Any | None:
        state = get_current_execution_state_machine()
        if state is None:
            return None
        for intent in state.intent_plan:
            if intent.status in {"completed", "failed", "skipped"}:
                continue
            if intent.family == "none" or not intent.requires_tools:
                continue
            return intent
        return None

    @staticmethod
    def _normalized_url_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for item in value:
            url = str(item or "").strip()
            if url and url not in normalized:
                normalized.append(url)
        return normalized

    @classmethod
    def _intent_url_list(cls, intent: Any | None, key: str) -> list[str]:
        metadata = dict(getattr(intent, "metadata", {}) or {}) if intent is not None else {}
        return cls._normalized_url_list(metadata.get(key))

    @classmethod
    def _set_intent_url_list(cls, intent: Any | None, key: str, values: list[str]) -> None:
        if intent is None:
            return
        metadata = dict(getattr(intent, "metadata", {}) or {})
        metadata[key] = cls._normalized_url_list(values)
        intent.metadata = metadata

    @classmethod
    def _mark_fetch_url_attempt(
        cls,
        intent: Any | None,
        url: str,
        *,
        blocked: bool = False,
    ) -> None:
        normalized_url = str(url or "").strip()
        if not normalized_url or intent is None:
            return
        attempted_urls = cls._intent_url_list(intent, "fetch_url_attempted_urls")
        if normalized_url not in attempted_urls:
            attempted_urls.append(normalized_url)
        cls._set_intent_url_list(intent, "fetch_url_attempted_urls", attempted_urls)
        if blocked:
            blocked_urls = cls._intent_url_list(intent, "fetch_url_blocked_urls")
            if normalized_url not in blocked_urls:
                blocked_urls.append(normalized_url)
            cls._set_intent_url_list(intent, "fetch_url_blocked_urls", blocked_urls)

    @staticmethod
    def _is_blocked_fetch_url_result(result: ToolResult) -> bool:
        if str(result.error_type or "").strip() == "blocked_url":
            return True
        error_text = str(result.error or "").lower()
        if not error_text:
            return False
        return any(marker in error_text for marker in ("http 401", "http 403", "http 429")) or (
            "page may block automated access" in error_text
            or "该页面可能被站点拦截" in error_text
        )

    @classmethod
    def _resolve_fetch_url_candidates(
        cls,
        *,
        intent: Any | None,
        requested_url: str,
    ) -> tuple[str | None, list[str], str]:
        normalized_requested_url = str(requested_url or "").strip()
        candidate_urls = cls._intent_url_list(intent, "fetch_url_candidate_urls")
        if not candidate_urls:
            return None, [], normalized_requested_url

        attempted_urls = set(cls._intent_url_list(intent, "fetch_url_attempted_urls"))
        requested_is_candidate = normalized_requested_url in candidate_urls
        remaining_urls = [url for url in candidate_urls if url not in attempted_urls]
        selected_url = normalized_requested_url
        fallback_urls: list[str] = []

        if requested_is_candidate and normalized_requested_url not in attempted_urls:
            selected_url = normalized_requested_url
            fallback_urls = [url for url in remaining_urls if url != normalized_requested_url]
        elif remaining_urls:
            selected_url = remaining_urls[0]
            fallback_urls = remaining_urls[1:]
        elif requested_is_candidate:
            selected_url = normalized_requested_url
            fallback_urls = [url for url in candidate_urls if url != normalized_requested_url]
        else:
            selected_url = ""
            fallback_urls = []

        return (
            selected_url or None,
            fallback_urls,
            normalized_requested_url,
        )

    def _try_readonly_cache_hit(
        self,
        func_name: str,
        arguments: dict[str, Any],
        conversation_id: int | None,
        tool_call_id: str,
    ) -> tuple[ToolResult, int] | None:
        signature = self._cache_signature(
            func_name,
            arguments,
            conversation_id,
        )
        if not signature:
            return None
        kind, key = signature
        cache_store = self._cache_store_for_kind(kind)
        hit = cache_store.get(key)
        if not hit:
            return None
        cached_result, cached_ms = hit
        if not cached_result.success:
            return None
        state = get_current_execution_state_machine()
        if state is not None:
            state.register_cache_hit(kind)
        return replace(cached_result, tool_call_id=tool_call_id, duration_ms=0), cached_ms

    async def _execute_tool_once(
        self,
        tc_id: str,
        func_name: str,
        arguments: dict[str, Any],
        conversation_id: int,
    ) -> tuple[ToolResult, int]:
        cached = self._try_readonly_cache_hit(
            func_name,
            arguments,
            conversation_id,
            tc_id,
        )
        if cached is not None:
            result, _prev_ms = cached
            return result, 0

        tc_start = time.perf_counter()
        execution_definitions = self.tools
        if not any(tool.name == func_name for tool in self.tools):
            execution_definitions = self.all_tools
        result = await self.sandbox.execute(
            tool_call_id=tc_id,
            name=func_name,
            arguments=arguments,
            definitions=execution_definitions,
            conversation_id=conversation_id,
        )
        duration_ms = int((time.perf_counter() - tc_start) * 1000)
        self._bump_page_readonly_cache_epoch_if_needed(func_name, arguments, result)
        self._store_readonly_cache(
            func_name,
            arguments,
            conversation_id,
            result,
            duration_ms,
            tc_id,
        )
        return result, duration_ms

    def _store_readonly_cache(
        self,
        func_name: str,
        arguments: dict[str, Any],
        conversation_id: int | None,
        result: ToolResult,
        duration_ms: int,
        tool_call_id: str,
    ) -> None:
        signature = self._cache_signature(
            func_name,
            arguments,
            conversation_id,
        )
        if not signature or not result.success:
            return
        kind, key = signature
        cache_store = self._cache_store_for_kind(kind)
        cache_store[key] = (
            replace(result, tool_call_id=tool_call_id, duration_ms=duration_ms),
            duration_ms,
        )

    @staticmethod
    def parse_arguments(
        raw_args: str | dict,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Parse tool call arguments (JSON string → dict).
        解析工具调用参数（JSON 字符串 → dict）

        Returns:
            (args, error_type): On success (dict, None). On JSON parse failure (None, "invalid_tool_arguments_json").
            成功返回 (dict, None)；JSON 解析失败返回 (None, "invalid_tool_arguments_json")。
        """
        if isinstance(raw_args, dict):
            return raw_args, None
        if not raw_args:
            return {}, None
        try:
            parsed = json.loads(raw_args)
            if not isinstance(parsed, dict):
                return None, "invalid_tool_arguments_json"
            return parsed, None
        except json.JSONDecodeError:
            repaired = _try_repair_json(raw_args)
            if repaired is not None:
                return repaired, None
            raw_snippet = (
                (raw_args[:500] + "…")
                if isinstance(raw_args, str) and len(raw_args) > 500
                else raw_args
            )
            logger.warning(
                "Tool arguments JSON parse failed: raw_args_snippet={} error=invalid_tool_arguments_json",
                repr(raw_snippet)[:600],
            )
            return None, "invalid_tool_arguments_json"

    async def execute_tool(
        self,
        tc_id: str,
        func_name: str,
        arguments: dict[str, Any],
        conversation_id: int,
    ) -> tuple[ToolResult, int]:
        """
        Execute single tool call via sandbox. / 通过沙箱执行单个工具调用。

        Returns:
            (result, duration_ms)
        """
        active_intent = self._active_intent()
        if (
            func_name == "fetch_url"
            and active_intent is not None
            and str(getattr(active_intent, "family", "") or "").strip() == "web_research"
            and bool(self._intent_url_list(active_intent, "fetch_url_candidate_urls"))
        ):
            selected_url, fallback_urls, requested_url = self._resolve_fetch_url_candidates(
                intent=active_intent,
                requested_url=str(arguments.get("url") or ""),
            )
            if not selected_url:
                logger.warning(
                    "fetch_url candidate URLs exhausted: intent_id={} requested_url={}",
                    getattr(active_intent, "intent_id", None),
                    requested_url,
                )
                return (
                    ToolResult(
                        tool_call_id=tc_id,
                        name=func_name,
                        success=False,
                        error=(
                            "fetch_url must use a candidate URL returned by the previous "
                            "web_search, but no untried candidate URLs remain."
                        ),
                        error_type="search_candidates_exhausted",
                    ),
                    0,
                )

            if requested_url and requested_url != selected_url:
                logger.info(
                    "Repairing fetch_url URL to search candidate: intent_id={} requested_url={} selected_url={}",
                    getattr(active_intent, "intent_id", None),
                    requested_url,
                    selected_url,
                )

            total_duration_ms = 0
            attempt_urls = [selected_url] + [url for url in fallback_urls if url != selected_url]
            last_result: ToolResult | None = None
            for index, attempt_url in enumerate(attempt_urls):
                attempt_arguments = dict(arguments)
                attempt_arguments["url"] = attempt_url
                result, duration_ms = await self._execute_tool_once(
                    tc_id,
                    func_name,
                    attempt_arguments,
                    conversation_id,
                )
                total_duration_ms += duration_ms
                blocked_result = not result.success and self._is_blocked_fetch_url_result(result)
                self._mark_fetch_url_attempt(
                    active_intent,
                    attempt_url,
                    blocked=blocked_result,
                )
                last_result = result
                if result.success or not blocked_result:
                    return result, total_duration_ms
                if index < len(attempt_urls) - 1:
                    logger.warning(
                        "Blocked fetch_url candidate, rotating to next candidate: intent_id={} blocked_url={} next_url={}",
                        getattr(active_intent, "intent_id", None),
                        attempt_url,
                        attempt_urls[index + 1],
                    )
            if last_result is not None:
                return last_result, total_duration_ms

        return await self._execute_tool_once(
            tc_id,
            func_name,
            arguments,
            conversation_id,
        )

    @staticmethod
    def build_tool_message(result: ToolResult, tc_id: str) -> ChatMessage:
        """Build tool role message / 构建 tool 角色消息"""
        content = (
            result.output
            if result.success
            else _("tool.error.prefix", error=result.error)
        )
        return ChatMessage(role="tool", content=content, tool_call_id=tc_id)

    @staticmethod
    def build_attachment_relay_message(result: ToolResult) -> ChatMessage | None:
        """Build a minimal internal attachment relay when tool output includes media. / 工具输出包含媒体时构建最小内部附件承载消息。"""
        if not result.success or not result.attachments:
            return None

        return ChatMessage(
            role="user",
            content="",
            attachments=result.attachments,
            internal_only=True,
        )

    @staticmethod
    def annotate_tool_call(
        tool_call: dict[str, Any],
        *,
        duration_ms: int | None = None,
        pending_confirmation: dict[str, Any] | None = None,
        pending_consent: dict[str, Any] | None = None,
        result: ToolResult | None = None,
        skill_info: dict[str, str | None] | None = None,
    ) -> None:
        """Attach recoverable runtime metadata onto assistant tool_calls / 将可恢复的运行态元数据挂到 assistant.tool_calls。"""
        if skill_info:
            if skill_info.get("skill_name"):
                tool_call["skill_name"] = skill_info["skill_name"]
            if skill_info.get("package_name"):
                tool_call["package_name"] = skill_info["package_name"]

        if duration_ms is not None:
            tool_call["duration_ms"] = duration_ms

        if pending_confirmation:
            tool_call["pending_confirmation"] = pending_confirmation

        if pending_consent:
            tool_call["pending_consent"] = pending_consent

        if result:
            tool_call["success"] = result.success
            if result.display_name:
                tool_call["display_name"] = result.display_name
            if result.summary:
                tool_call["summary"] = result.summary
            if result.summary_payload:
                tool_call["summary_payload"] = result.summary_payload
            if result.result_link:
                tool_call["result_link"] = result.result_link
            if result.error_type:
                tool_call["error_type"] = result.error_type

    @staticmethod
    def build_pending_confirmation_payload(parsed: dict[str, Any]) -> dict[str, Any]:
        """Build recoverable pending confirmation payload / 构建可恢复的待确认信息。"""
        return {
            "action": parsed.get("action", ""),
            "table": parsed.get("table", ""),
            "preview": (
                parsed.get("preview") or parsed.get("diff") or parsed.get("record")
            ),
        }

    @staticmethod
    def build_pending_consent_payload(
        func_name: str,
        arguments: dict[str, Any],
        skill_info: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        """Build recoverable pending consent payload / 构建可恢复的待授权信息。"""
        payload: dict[str, Any] = {
            "tool_name": func_name,
            "arguments": arguments,
        }
        if skill_info:
            if skill_info.get("skill_name"):
                payload["skill_name"] = skill_info["skill_name"]
            if skill_info.get("package_name"):
                payload["package_name"] = skill_info["package_name"]
        return payload

    @staticmethod
    def build_assistant_tool_call_message(
        content: str,
        tool_calls: list[dict[str, Any]],
        reasoning_content: str | None = None,
    ) -> ChatMessage:
        """Build assistant message containing tool_calls / 构建包含 tool_calls 的 assistant 消息"""
        return ChatMessage(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
            reasoning_content=reasoning_content,
        )

    # ========================================
    # consent_mode Check / consent_mode 检查
    # ========================================

    def check_consent(
        self,
        func_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> str:
        """
        Check tool's consent_mode. / 检查工具的 consent_mode。

        Returns:
            "auto" | "ask" | "reject"
        """
        consent_mode = self.consent_modes.get(func_name, "auto")
        if consent_mode != "ask":
            return consent_mode
        normalized_name = str(func_name or "").strip()
        if normalized_name and normalized_name in self.approved_pending_consent_tools:
            return "auto"
        if (
            self._interaction_mode == "trusted_auto"
            and is_trusted_auto_read_only_tool_call(func_name, arguments)
        ):
            return "auto"
        return consent_mode

    @staticmethod
    def approved_pending_consent_tool_names(
        interaction_updates: list[dict[str, Any]] | None,
    ) -> set[str]:
        approved: set[str] = set()
        for update in interaction_updates or []:
            if str(update.get("kind") or "").strip() != "pending_consent":
                continue
            if bool(update.get("rejected")):
                continue
            tool_name = str(update.get("tool_name") or "").strip()
            if tool_name:
                approved.add(tool_name)
        return approved

    def build_consent_reject_message(
        self,
        tc_id: str,
    ) -> ChatMessage:
        """Build tool message for consent rejection / 构建 consent 被拒绝的 tool 消息"""
        return ChatMessage(
            role="tool",
            content=_("tool.error.consent_rejected"),
            tool_call_id=tc_id,
        )

    def build_consent_ask_message(
        self,
        tc_id: str,
        func_name: str,
        arguments: dict[str, Any],
    ) -> ChatMessage:
        """Build tool message for consent requiring user confirmation / 构建 consent 需要用户确认的 tool 消息"""
        payload = json.dumps(
            {
                "requires_confirmation": True,
                "consent_required": True,
                "action": "tool_consent",
                "tool_name": func_name,
                "arguments": arguments,
            },
            ensure_ascii=False,
        )
        return ChatMessage(role="tool", content=payload, tool_call_id=tc_id)

    # ========================================
    # Confirmation Interception / 确认拦截
    # ========================================

    @staticmethod
    def check_confirmation_output(result: ToolResult) -> dict[str, Any] | None:
        """
        Check if tool output contains requires_confirmation (CRUD preview confirmation).
        检查工具输出是否包含 requires_confirmation（CRUD 预览确认）。

        Returns:
            Parsed confirmation data dict, or None / 解析后的确认数据 dict，或 None
        """
        if not (result.success and result.output):
            return None
        try:
            parsed = json.loads(result.output)
            if isinstance(parsed, dict) and parsed.get("requires_confirmation"):
                return parsed
        except (ValueError, TypeError):
            pass
        return None

    @staticmethod
    def find_pending_confirmation(
        messages: list[ChatMessage],
    ) -> dict[str, Any] | None:
        """
        Search message history for pending tool call confirmation. / 搜索消息历史中待确认的工具调用。

        Searches backward, finds tool message with requires_confirmation,
        matches corresponding assistant tool_call, returns directly executable tool call info.
        从后往前搜索，找到 requires_confirmation 的 tool 消息后，
        匹配对应的 assistant tool_call。

        Returns:
            {"name", "arguments", "tool_call_id"} or None
        """
        pending_tc_id: str | None = None
        inject_confirmed = False
        for msg in reversed(messages):
            if msg.role == "tool" and msg.content:
                try:
                    parsed = json.loads(msg.content)
                    if isinstance(parsed, dict) and parsed.get("requires_confirmation"):
                        pending_tc_id = msg.tool_call_id
                        inject_confirmed = not bool(
                            parsed.get("consent_required")
                            or parsed.get("action") == "tool_consent"
                        )
                        break
                except (ValueError, TypeError):
                    continue

        if not pending_tc_id:
            return None

        # Find corresponding assistant tool_call / 找到对应的 assistant tool_call
        for msg in reversed(messages):
            if msg.role == "assistant" and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc.get("id") == pending_tc_id:
                        func = tc.get("function", {})
                        raw_args = func.get("arguments", "{}")
                        try:
                            arguments = (
                                json.loads(raw_args)
                                if isinstance(raw_args, str)
                                else raw_args
                            )
                        except json.JSONDecodeError:
                            arguments = {}
                        # Only mutation-preview injects confirmed=True; consent_mode=ask replays args / 仅变更预览注入 confirmed；询问模式原样重放参数
                        if inject_confirmed:
                            arguments["confirmed"] = True
                        return {
                            "name": func.get("name", ""),
                            "arguments": arguments,
                            "tool_call_id": pending_tc_id,
                        }
        return None

    @staticmethod
    def is_confirmation_text(text: str) -> bool:
        """Check if text is a short confirmation reply / 检查是否为简短确认回复"""
        return is_confirmation_reply(text)

    @staticmethod
    def is_rejection_text(text: str) -> bool:
        """Check if text is a short rejection reply / 检查是否为简短拒绝回复"""
        return is_rejection_reply(text)

    # ========================================
    # SSE Event Building / SSE 事件构建
    # ========================================

    @staticmethod
    def build_tool_start_event(
        func_name: str,
        arguments: dict[str, Any],
        skill_info: dict[str, str | None] | None = None,
        tool_call_id: str | None = None,
    ) -> dict[str, Any]:
        """Build tool_start SSE event / 构建 tool_start SSE 事件"""
        event: dict[str, Any] = {
            "event": "tool_start",
            "name": func_name,
            "arguments": arguments,
        }
        if tool_call_id:
            event["id"] = tool_call_id
        if skill_info:
            event.update(skill_info)
        return event

    @staticmethod
    def build_tool_call_event(
        result: ToolResult,
        duration_ms: int,
        skill_info: dict[str, str | None] | None = None,
        name_override: str | None = None,
    ) -> dict[str, Any]:
        """
        Build tool_call SSE event / 构建 tool_call SSE 事件

        name_override: Use original func_name when sandbox redirects (e.g. pageop_* -> invoke_page_operation).
        当 sandbox 重定向时使用原始 func_name（如 pageop_* -> invoke_page_operation），避免前端匹配失败。
        """
        event: dict[str, Any] = {
            "event": "tool_call",
            "name": name_override or result.name,
            "success": result.success,
            "duration_ms": duration_ms,
        }
        if skill_info:
            event.update(skill_info)

        if result.display_name:
            event["display_name"] = result.display_name
        if result.summary:
            event["summary"] = result.summary
        if result.result_link:
            event["result_link"] = result.result_link
        if result.summary_payload:
            event["summary_payload"] = result.summary_payload

        if result.success and result.output:
            if '"__crud_form_fill__"' in result.output:
                event["output"] = result.output
            else:
                truncated = result.output[:500]
                if len(result.output) > 500:
                    truncated += "..."
                event["output"] = truncated
        elif not result.success and result.error:
            event["error"] = result.error[:300]
            if result.error_type:
                event["error_type"] = result.error_type

        return event

    @staticmethod
    def build_confirmation_event(
        parsed: dict[str, Any],
    ) -> dict[str, Any]:
        """Build confirmation_request SSE event / 构建 confirmation_request SSE 事件"""
        event: dict[str, Any] = {
            "event": "confirmation_request",
            "action": parsed.get("action", ""),
            "table": parsed.get("table", ""),
            "preview": (
                parsed.get("preview") or parsed.get("diff") or parsed.get("record")
            ),
        }
        # File-generation confirmation (e.g. plugin codegen) / 文件生成类确认（如插件 codegen）
        if parsed.get("files"):
            event["files"] = parsed["files"]
            event["message"] = parsed.get("message", "")
            event["total_new"] = parsed.get("total_new", 0)
            event["total_conflict"] = parsed.get("total_conflict", 0)
        return event

    @staticmethod
    def build_consent_reject_event(
        func_name: str,
        skill_info: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        """Build consent rejection tool_call SSE event / 构建 consent 拒绝的 tool_call SSE 事件"""
        event: dict[str, Any] = {
            "event": "tool_call",
            "name": func_name,
            "success": False,
            "duration_ms": 0,
            "error": _("tool.error.consent_rejected"),
        }
        if skill_info:
            event.update(skill_info)
        return event

    @staticmethod
    def build_consent_ask_event(
        func_name: str,
        arguments: dict[str, Any],
        skill_info: dict[str, str | None] | None = None,
        interaction_mode_effective: str | None = None,
    ) -> dict[str, Any]:
        """Build consent ask SSE event / 构建 consent 询问的 SSE 事件"""
        event: dict[str, Any] = {
            "event": "tool_consent_request",
            "name": func_name,
            "arguments": arguments,
        }
        if interaction_mode_effective:
            event["interaction_mode_effective"] = interaction_mode_effective
        if skill_info:
            event.update(skill_info)
        return event

    # ========================================
    # Skill Info Lookup / Skill 信息查找
    # ========================================

    def get_skill_info(self, tool_name: str) -> dict[str, str | None]:
        """Find tool's Skill source info from ToolDefinition list / 从 ToolDefinition 列表中查找工具对应的 Skill 来源信息"""
        for td in self.tools:
            if td.name == tool_name:
                return {
                    "skill_name": td.source_skill_name,
                    "package_name": td.source_package_name,
                }
        for td in self.all_tools:
            if td.name == tool_name:
                return {
                    "skill_name": td.source_skill_name,
                    "package_name": td.source_package_name,
                }
        return {"skill_name": None, "package_name": None}

    # ========================================
    # Complete Single Tool Processing (for execute path) / 完整单工具处理（execute 路径使用）
    # ========================================

    async def process_single(
        self,
        tc: dict[str, Any],
        conversation_id: int,
    ) -> SingleToolResult:
        """
        Process single tool call (parse + execute + build message).
        处理单个工具调用（解析 + 执行 + 构建消息）。

        Used by _handle_tool_calls to simplify non-streaming path code.
        供 _handle_tool_calls 使用，简化非流式路径代码。

        Args:
            tc: tool_call dict returned by LLM / LLM 返回的 tool_call dict
            conversation_id: Conversation ID / 对话 ID

        Returns:
            SingleToolResult
        """
        tc_id = tc.get("id", "")
        func = tc.get("function", {})
        func_name = func.get("name", "")
        raw_args = func.get("arguments", "{}")

        arguments, parse_error = self.parse_arguments(raw_args)
        if parse_error:
            result = ToolResult(
                tool_call_id=tc_id,
                name=func_name or "unknown",
                success=False,
                error=(
                    "Tool arguments JSON parse failed. "
                    "Ensure arguments are valid JSON. Do not retry with the same invalid input."
                ),
                error_type=parse_error,
            )
            tool_message = self.build_tool_message(result, tc_id)
            return SingleToolResult(
                tool_result=result,
                duration_ms=0,
                tool_message=tool_message,
                follow_up_message=self.build_attachment_relay_message(result),
            )

        result, duration_ms = await self.execute_tool(
            tc_id,
            func_name,
            arguments,
            conversation_id,
        )
        tool_message = self.build_tool_message(result, tc_id)

        return SingleToolResult(
            tool_result=result,
            duration_ms=duration_ms,
            tool_message=tool_message,
            follow_up_message=self.build_attachment_relay_message(result),
        )


__all__ = [
    "ToolCallProcessor",
    "SingleToolResult",
    "is_trusted_auto_read_only_tool_call",
]
