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

import time
from dataclasses import dataclass, field
from typing import Any

from app.ai.tools.sandbox import ToolSandbox
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage

from .tool_processor_args import parse_tool_arguments as _parse_tool_arguments
from .tool_processor_args import try_repair_json as _try_repair_json
from .tool_processor_cache import ToolProcessorCache
from .tool_processor_cache import (
    is_parallel_safe_tool_call as _is_parallel_safe_tool_call,
)
from .tool_processor_events import (
    build_confirmation_event as _build_confirmation_event,
)
from .tool_processor_events import (
    build_consent_ask_event as _build_consent_ask_event,
)
from .tool_processor_events import (
    build_consent_reject_event as _build_consent_reject_event,
)
from .tool_processor_events import (
    build_tool_call_event as _build_tool_call_event,
)
from .tool_processor_events import (
    build_tool_start_event as _build_tool_start_event,
)
from .tool_processor_messages import (
    annotate_tool_call as _annotate_tool_call,
)
from .tool_processor_messages import (
    approved_pending_consent_tool_names as _approved_pending_consent_tool_names,
)
from .tool_processor_messages import (
    build_assistant_tool_call_message as _build_assistant_tool_call_message,
)
from .tool_processor_messages import (
    build_attachment_relay_message as _build_attachment_relay_message,
)
from .tool_processor_messages import (
    build_consent_ask_message as _build_consent_ask_message,
)
from .tool_processor_messages import (
    build_consent_reject_message as _build_consent_reject_message,
)
from .tool_processor_messages import (
    build_pending_confirmation_payload as _build_pending_confirmation_payload,
)
from .tool_processor_messages import (
    build_pending_consent_payload as _build_pending_consent_payload,
)
from .tool_processor_messages import (
    build_tool_message as _build_tool_message,
)
from .tool_processor_messages import (
    check_confirmation_output as _check_confirmation_output,
)
from .tool_processor_messages import (
    find_pending_confirmation as _find_pending_confirmation,
)
from .tool_processor_messages import (
    is_confirmation_text as _is_confirmation_text,
)
from .tool_processor_messages import (
    is_rejection_text as _is_rejection_text,
)


def is_trusted_auto_read_only_tool_call(
    func_name: str,
    arguments: dict[str, Any] | None = None,
) -> bool:
    """Readonly tools that can skip consent in the fixed trusted-auto mode."""
    _ = arguments
    name = (func_name or "").strip()
    if not name:
        return False
    return name == "get_current_time"


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
        interaction_mode: str = "trusted_auto",
    ) -> None:
        self.sandbox = sandbox
        self.tools = tools
        self.all_tools = all_tools or tools
        self.consent_modes = consent_modes or {}
        self._interaction_mode = (
            str(interaction_mode or "trusted_auto").strip() or "trusted_auto"
        )
        self.approved_pending_consent_tools = {
            str(name).strip()
            for name in (approved_pending_consent_tools or set())
            if str(name).strip()
        }
        self._cache = ToolProcessorCache(self.sandbox)

    # ========================================
    # Static helpers wired to support modules
    # ========================================
    is_parallel_safe_tool_call = staticmethod(_is_parallel_safe_tool_call)
    parse_arguments = staticmethod(_parse_tool_arguments)
    build_tool_message = staticmethod(_build_tool_message)
    build_attachment_relay_message = staticmethod(_build_attachment_relay_message)
    annotate_tool_call = staticmethod(_annotate_tool_call)
    build_pending_confirmation_payload = staticmethod(
        _build_pending_confirmation_payload
    )
    build_pending_consent_payload = staticmethod(_build_pending_consent_payload)
    build_assistant_tool_call_message = staticmethod(_build_assistant_tool_call_message)
    approved_pending_consent_tool_names = staticmethod(
        _approved_pending_consent_tool_names
    )
    build_consent_reject_message = staticmethod(_build_consent_reject_message)
    build_consent_ask_message = staticmethod(_build_consent_ask_message)
    check_confirmation_output = staticmethod(_check_confirmation_output)
    find_pending_confirmation = staticmethod(_find_pending_confirmation)
    is_confirmation_text = staticmethod(_is_confirmation_text)
    is_rejection_text = staticmethod(_is_rejection_text)
    build_tool_start_event = staticmethod(_build_tool_start_event)
    build_tool_call_event = staticmethod(_build_tool_call_event)
    build_confirmation_event = staticmethod(_build_confirmation_event)
    build_consent_reject_event = staticmethod(_build_consent_reject_event)
    build_consent_ask_event = staticmethod(_build_consent_ask_event)

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

    async def _execute_tool_once(
        self,
        tc_id: str,
        func_name: str,
        arguments: dict[str, Any],
        conversation_id: int,
    ) -> tuple[ToolResult, int]:
        cached = self._cache.try_readonly_cache_hit(
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
        self._cache.bump_readonly_cache_epoch_if_needed(func_name, arguments, result)
        self._cache.store_readonly_cache(
            func_name,
            arguments,
            conversation_id,
            result,
            duration_ms,
            tc_id,
        )
        return result, duration_ms

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
        return await self._execute_tool_once(
            tc_id,
            func_name,
            arguments,
            conversation_id,
        )

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
    "_try_repair_json",
]
