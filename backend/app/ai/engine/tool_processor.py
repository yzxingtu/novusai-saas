"""
Unified Tool Call Processor
统一工具调用处理器

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
from dataclasses import dataclass, field
from typing import Any

from app.ai.tools.sandbox import ToolSandbox
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage
from app.core.i18n import _
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.engine.tool_processor")

# User confirmation/rejection trigger words / 用户确认/拒绝触发词
_CONFIRMATION_TEXTS: frozenset[str] = frozenset({
    "确认执行", "确认", "执行", "好的", "是", "好", "可以",
    "confirm", "yes", "ok", "sure", "go ahead",
})
_REJECTION_TEXTS: frozenset[str] = frozenset({
    "取消", "拒绝", "不执行", "不", "算了",
    "cancel", "no", "reject", "abort", "stop",
})


@dataclass
class SingleToolResult:
    """Single tool call processing result / 单个工具调用处理结果"""

    tool_result: ToolResult | None = None
    duration_ms: int = 0
    tool_message: ChatMessage | None = None
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
        consent_modes: dict[str, str] | None = None,
    ):
        self.sandbox = sandbox
        self.tools = tools
        self.consent_modes = consent_modes or {}

    # ========================================
    # Core Methods / 核心方法
    # ========================================

    @staticmethod
    def parse_arguments(raw_args: str | dict) -> dict[str, Any]:
        """Parse tool call arguments (JSON string → dict) / 解析工具调用参数"""
        if isinstance(raw_args, dict):
            return raw_args
        try:
            return json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            return {}

    async def execute_tool(
        self,
        tc_id: str,
        func_name: str,
        arguments: dict[str, Any],
        conversation_id: int,
    ) -> tuple[ToolResult, int]:
        """
        Execute single tool call via sandbox.
        通过沙箱执行单个工具调用。

        Returns:
            (result, duration_ms)
        """
        tc_start = time.perf_counter()
        result = await self.sandbox.execute(
            tool_call_id=tc_id,
            name=func_name,
            arguments=arguments,
            definitions=self.tools,
            conversation_id=conversation_id,
        )
        duration_ms = int((time.perf_counter() - tc_start) * 1000)
        return result, duration_ms

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
    def build_assistant_tool_call_message(
        content: str,
        tool_calls: list[dict[str, Any]],
    ) -> ChatMessage:
        """Build assistant message containing tool_calls / 构建包含 tool_calls 的 assistant 消息"""
        return ChatMessage(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        )

    # ========================================
    # consent_mode Check / consent_mode 检查
    # ========================================

    def check_consent(self, func_name: str) -> str:
        """
        Check tool's consent_mode.
        检查工具的 consent_mode。

        Returns:
            "auto" | "ask" | "reject"
        """
        return self.consent_modes.get(func_name, "auto")

    def build_consent_reject_message(
        self, tc_id: str,
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
        payload = json.dumps({
            "requires_confirmation": True,
            "consent_required": True,
            "action": "tool_consent",
            "tool_name": func_name,
            "arguments": arguments,
        }, ensure_ascii=False)
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
        Search message history for pending tool call confirmation.
        搜索消息历史中待确认的工具调用。

        Searches backward, finds tool message with requires_confirmation,
        matches corresponding assistant tool_call, returns directly executable tool call info.
        从后往前搜索，找到 requires_confirmation 的 tool 消息后，
        匹配对应的 assistant tool_call。

        Returns:
            {"name", "arguments", "tool_call_id"} or None
        """
        pending_tc_id: str | None = None
        for msg in reversed(messages):
            if msg.role == "tool" and msg.content:
                try:
                    parsed = json.loads(msg.content)
                    if isinstance(parsed, dict) and parsed.get("requires_confirmation"):
                        pending_tc_id = msg.tool_call_id
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
                        # Inject confirmed=True / 注入 confirmed=True
                        arguments["confirmed"] = True
                        return {
                            "name": func.get("name", ""),
                            "arguments": arguments,
                            "tool_call_id": pending_tc_id,
                        }
        return None

    @staticmethod
    def is_confirmation_text(text: str) -> bool:
        """Check if text is a confirmation trigger word / 检查文本是否为确认触发词"""
        return text.strip() in _CONFIRMATION_TEXTS

    @staticmethod
    def is_rejection_text(text: str) -> bool:
        """Check if text is a rejection trigger word / 检查文本是否为拒绝触发词"""
        return text.strip() in _REJECTION_TEXTS

    # ========================================
    # SSE Event Building / SSE 事件构建
    # ========================================

    @staticmethod
    def build_tool_start_event(
        func_name: str,
        arguments: dict[str, Any],
        skill_info: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        """Build tool_start SSE event / 构建 tool_start SSE 事件"""
        event: dict[str, Any] = {
            "event": "tool_start",
            "name": func_name,
            "arguments": arguments,
        }
        if skill_info:
            event.update(skill_info)
        return event

    @staticmethod
    def build_tool_call_event(
        result: ToolResult,
        duration_ms: int,
        skill_info: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        """Build tool_call SSE event / 构建 tool_call SSE 事件"""
        event: dict[str, Any] = {
            "event": "tool_call",
            "name": result.name,
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
                parsed.get("preview")
                or parsed.get("diff")
                or parsed.get("record")
            ),
        }
        # CRUD Generator file generation confirmation / CRUD Generator 文件生成确认
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
    ) -> dict[str, Any]:
        """Build consent ask SSE event / 构建 consent 询问的 SSE 事件"""
        event: dict[str, Any] = {
            "event": "tool_consent_request",
            "name": func_name,
            "arguments": arguments,
        }
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

        arguments = self.parse_arguments(raw_args)

        result, duration_ms = await self.execute_tool(
            tc_id, func_name, arguments, conversation_id,
        )
        tool_message = self.build_tool_message(result, tc_id)

        return SingleToolResult(
            tool_result=result,
            duration_ms=duration_ms,
            tool_message=tool_message,
        )


__all__ = [
    "ToolCallProcessor",
    "SingleToolResult",
    "_CONFIRMATION_TEXTS",
    "_REJECTION_TEXTS",
]
