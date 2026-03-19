"""
SSE Streaming Execution Handler / SSE 流式执行处理器

Extracted from ConversationEngine._sse_generator, encapsulates the SSE event generation main loop.
Includes real-time tool call push, confirmation interception, DSML tag cleanup, error handling.
从 ConversationEngine._sse_generator 提取，封装 SSE 事件生成主循环。
包括工具调用实时推送、确认拦截、DSML 标签清理、错误处理。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING, Any

from app.ai.sse import SSEChunkEncoder
from app.ai.types import ChatMessage
from app.core.i18n import _
from app.core.logging import LogManager

from .base import MAX_TOOL_CALL_ROUNDS
from .types import ExecutionRequest, ExecutionResult, PreparedExecution

if TYPE_CHECKING:
    from app.ai.tools.types import ToolDefinition, ToolResult
    from app.models.ai.agent import Agent

    from .base import BaseEngine
    from .tool_processor import ToolCallProcessor

logger = LogManager.get_logger("ai.engine.stream_handler")


class StreamExecutionHandler:
    """
    SSE Streaming Execution Handler / SSE 流式执行处理器

    Encapsulates ConversationEngine._sse_generator logic as an independent class.
    Accesses _stream_llm_chunks / _messages_to_dicts via engine reference.
    将 ConversationEngine._sse_generator 的完整逻辑封装为独立类。

    Event types / 事件类型：
    - message: Content delta / 内容增量
    - tool_call: Tool call result / 工具调用结果
    - thinking: AI executing tool / AI 正在执行工具
    - optimizing_tools: Tool optimization event / 工具优化事件
    - rag_sources: RAG reference sources / RAG 引用来源
    - confirmation_request: User confirmation needed / 需要用户确认
    - done: Completion / 完成
    - [DONE]: SSE end marker / SSE 结束标记
    """

    def __init__(
        self,
        engine: BaseEngine,
        agent: Agent,
        request: ExecutionRequest,
        prep: PreparedExecution,
        start_time: float,
        on_complete: Callable[[ExecutionResult], Awaitable[dict[str, Any] | None]] | None = None,
    ):
        self.engine = engine
        self.agent = agent
        self.request = request
        self.prep = prep
        self.start_time = start_time
        self.on_complete = on_complete

    async def generate(self) -> AsyncIterator[str]:
        """SSE event generator main loop / SSE 事件生成器主循环"""
        from .conversation import _strip_model_fc_tokens
        from .tool_processor import ToolCallProcessor

        messages = self.prep.messages
        tools = self.prep.tools
        rag_sources = self.prep.rag_sources
        _optimize_event = self.prep.optimize_event
        _tool_consent_modes = self.prep.tool_consent_modes

        total_tokens = 0
        all_tool_results: list[ToolResult] = []
        output = ""
        self._output = ""  # Used for partial persist on interrupt
        self._reasoning_output = ""  # For chain-of-thought models, used in partial persist
        self._total_tokens = 0

        try:
            if self.request.conversation_id:
                # Publish conversation id early so frontend keeps the session
                # even when the stream is interrupted before the final done event.
                yield SSEChunkEncoder.encode({
                    "event": "conversation",
                    "conversation_id": self.request.conversation_id,
                })

            processor = ToolCallProcessor(
                sandbox=self.engine.sandbox,
                tools=tools,
                consent_modes=_tool_consent_modes,
            )

            # Push tool optimization event / 推送工具优化事件
            if _optimize_event is not None:
                yield SSEChunkEncoder.encode(
                    {"event": "optimizing_tools", **_optimize_event}
                    if isinstance(_optimize_event, dict)
                    else _optimize_event
                )

            if tools:
                # ---- With tools: tool call loop + final reply streaming ---- / 有工具：工具调用循环 + 最终回复流式推送
                async for event in self._generate_with_tools(
                    messages, tools, processor, all_tool_results,
                    _strip_model_fc_tokens,
                ):
                    yield event
                    # Extract output and total_tokens from events
                    # (shared state via self._output / self._total_tokens)
                    # 从事件中提取 output 和 total_tokens

                output = self._output
                total_tokens = self._total_tokens
            else:
                # ---- Without tools: real streaming push ---- / 无工具：真实流式推送
                self._reasoning_output = ""
                async for chunk in self.engine._stream_llm_chunks(
                    agent=self.agent,
                    messages=messages,
                    tenant_id=self.request.tenant_id,
                    route_result=self.prep.route_result,
                ):
                    if chunk.reasoning_delta:
                        self._reasoning_output += chunk.reasoning_delta
                        yield SSEChunkEncoder.encode({
                            "event": "thinking",
                            "delta": chunk.reasoning_delta,
                        })

                    if chunk.delta:
                        output += chunk.delta
                        yield SSEChunkEncoder.encode({
                            "event": "message",
                            "delta": chunk.delta,
                        })

                    if chunk.total_tokens is not None:
                        total_tokens = chunk.total_tokens

                    if chunk.finish_reason is not None:
                        break

                messages.append(ChatMessage(
                    role="assistant",
                    content=output,
                    reasoning_content=(self._reasoning_output or "").strip() or None,
                ))

            # ---- Parse and send Action Buttons ---- / 解析并发送 Action Buttons
            cleaned_output, action_buttons = self._extract_action_buttons(output)
            if action_buttons:
                output = cleaned_output
                yield SSEChunkEncoder.encode({
                    "event": "action_buttons",
                    "buttons": action_buttons,
                })

            # ---- Send RAG reference source event ---- / 发送 RAG 引用来源事件
            if rag_sources:
                yield SSEChunkEncoder.encode({
                    "event": "rag_sources",
                    "sources": rag_sources,
                })

            # ---- Build result and call callback (before done event) ---- / 构建结果并调用回调（在 done 事件之前）
            duration_ms = int((time.perf_counter() - self.start_time) * 1000)

            result = ExecutionResult(
                success=True,
                output=output,
                messages=self.engine._messages_to_dicts(messages),
                tool_results=all_tool_results,
                total_tokens=total_tokens,
                duration_ms=duration_ms,
                conversation_id=self.request.conversation_id,
            )

            extra_done_data: dict[str, Any] = {}
            if self.on_complete:
                try:
                    cb_result = await self.on_complete(result)
                    if isinstance(cb_result, dict):
                        extra_done_data = cb_result
                except Exception as cb_exc:
                    logger.error("on_complete callback error: {}", str(cb_exc))

            # ---- Send done event (with extra data from callback) ---- / 发送完成事件（含回调返回的额外数据）
            yield SSEChunkEncoder.encode({
                "event": "done",
                "conversation_id": self.request.conversation_id,
                "total_tokens": total_tokens,
                "duration_ms": duration_ms,
                **extra_done_data,
            })
            yield SSEChunkEncoder.done()

        except Exception as exc:
            logger.error(
                "Stream execution failed: agent={} error={}",
                self.agent.id,
                str(exc),
                exc_info=True,
            )
            try:
                yield SSEChunkEncoder.encode({
                    "error": True,
                    "message": str(exc),
                    "conversation_id": self.request.conversation_id,
                })
                yield SSEChunkEncoder.done()
            except Exception:
                pass  # Ignore yield error when connection is broken / 连接已断开时忽略 yield 错误

            # Partial persist: pass accumulated state so history is not lost / 中断时传递已累积状态，避免历史丢失
            if self.on_complete:
                duration_ms = int((time.perf_counter() - self.start_time) * 1000)
                partial_output = getattr(self, "_output", None) or output
                partial_tokens = getattr(self, "_total_tokens", None)
                if partial_tokens is None:
                    partial_tokens = total_tokens
                # Append partial assistant message when we have output but did not finish normally
                if partial_output:
                    reasoning = (getattr(self, "_reasoning_output", None) or "").strip() or None
                    messages.append(ChatMessage(
                        role="assistant",
                        content=partial_output,
                        reasoning_content=reasoning,
                    ))
                failed_result = ExecutionResult(
                    success=False,
                    output=partial_output,
                    messages=self.engine._messages_to_dicts(messages),
                    tool_results=all_tool_results,
                    total_tokens=partial_tokens,
                    duration_ms=duration_ms,
                    conversation_id=self.request.conversation_id,
                    error=str(exc),
                    partial=True,
                    interrupted=False,
                    completion_reason="error",
                )
                try:
                    await asyncio.shield(self.on_complete(failed_result))
                except Exception as cb_exc:
                    logger.error(
                        "on_complete callback error: {}",
                        str(cb_exc),
                    )

        except BaseException as exc:
            # Catch CancelledError / GeneratorExit and other non-Exception exceptions / 捕获 CancelledError / GeneratorExit 等非 Exception 异常
            logger.error(
                "Stream BaseException: agent={} type={} error={}",
                self.agent.id, type(exc).__name__, str(exc),
                exc_info=True,
            )
            if self.on_complete:
                duration_ms = int((time.perf_counter() - self.start_time) * 1000)
                partial_output = getattr(self, "_output", None) or output
                partial_tokens = getattr(self, "_total_tokens", None)
                if partial_tokens is None:
                    partial_tokens = total_tokens
                if partial_output:
                    reasoning = (getattr(self, "_reasoning_output", None) or "").strip() or None
                    messages.append(ChatMessage(
                        role="assistant",
                        content=partial_output,
                        reasoning_content=reasoning,
                    ))
                interrupted_result = ExecutionResult(
                    success=False,
                    output=partial_output,
                    messages=self.engine._messages_to_dicts(messages),
                    tool_results=all_tool_results,
                    total_tokens=partial_tokens,
                    duration_ms=duration_ms,
                    conversation_id=self.request.conversation_id,
                    error=f"{type(exc).__name__}: {exc}",
                    partial=True,
                    interrupted=True,
                    completion_reason="interrupted",
                )
                with contextlib.suppress(Exception):
                    await asyncio.shield(self.on_complete(interrupted_result))
            raise  # Must re-raise BaseException / 必须重新抛出 BaseException

    def _chunk_text_for_streaming(self, text: str, chunk_size: int = 32) -> list[str]:
        """Split text into chunks for simulated streaming (typing effect)."""
        if not text:
            return []
        chunks: list[str] = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i : i + chunk_size])
        return chunks

    async def _generate_with_tools(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        processor: ToolCallProcessor,
        all_tool_results: list[ToolResult],
        strip_fc_tokens: Callable[[str], str],
    ) -> AsyncIterator[str]:
        """
        Tool rounds use real streaming and incremental tool_call aggregation.
        工具轮次使用真实流式，并增量聚合 tool_call。
        """
        self._total_tokens = 0
        self._output = ""
        self._reasoning_output = ""
        _ = strip_fc_tokens  # unused in real streaming path
        append_final_assistant = True

        # ---- Confirmation interception ---- / 确认拦截
        _last_user_text = ""
        if self.request.messages:
            _last = self.request.messages[-1]
            if _last.role == "user":
                _last_user_text = (_last.content or "").strip()

        _pending = None
        if processor.is_confirmation_text(_last_user_text):
            _pending = processor.find_pending_confirmation(messages)

        if _pending:
            _tc_id = _pending["tool_call_id"]
            _func_name = _pending["name"]
            _arguments = _pending["arguments"]
            _conf_skill = processor.get_skill_info(_func_name)
            yield SSEChunkEncoder.encode(
                processor.build_tool_start_event(
                    _func_name, _arguments, _conf_skill,
                    tool_call_id=_tc_id,
                )
            )
            _result, _tc_dur = await processor.execute_tool(
                _tc_id, _func_name, _arguments,
                conversation_id=self.request.conversation_id or 0,
            )
            all_tool_results.append(_result)
            yield SSEChunkEncoder.encode(
                processor.build_tool_call_event(
                    _result, _tc_dur, _conf_skill,
                    name_override=_func_name,
                )
            )
            messages.append(processor.build_assistant_tool_call_message(
                content="",
                tool_calls=[{
                    "id": _tc_id,
                    "type": "function",
                    "function": {
                        "name": _func_name,
                        "arguments": json.dumps(_arguments, ensure_ascii=False),
                    },
                }],
            ))
            messages.append(processor.build_tool_message(_result, _tc_id))

        _consecutive_page_op_failures = 0
        _consecutive_data_op_failures = 0
        _page_op_aborted = False
        PAGE_OP_ABORT_THRESHOLD = 3

        for _round in range(MAX_TOOL_CALL_ROUNDS):
            round_output = ""
            round_reasoning_output = ""
            round_visible_thinking = ""
            round_tool_calls: list[dict[str, Any]] = []
            round_total_tokens = 0
            self._output = ""
            self._reasoning_output = ""

            async for chunk in self.engine._stream_llm_chunks(
                agent=self.agent,
                messages=messages,
                tenant_id=self.request.tenant_id,
                route_result=self.prep.route_result,
                tools=tools,
            ):
                if chunk.reasoning_delta:
                    round_reasoning_output += chunk.reasoning_delta
                    round_visible_thinking += chunk.reasoning_delta
                    self._reasoning_output = round_reasoning_output
                    yield SSEChunkEncoder.encode({
                        "event": "thinking",
                        "delta": chunk.reasoning_delta,
                    })

                if chunk.delta:
                    round_output += chunk.delta
                    round_visible_thinking += chunk.delta
                    self._output = round_output
                    yield SSEChunkEncoder.encode({
                        "event": "message",
                        "delta": chunk.delta,
                    })

                if chunk.tool_calls:
                    round_tool_calls = self._merge_stream_tool_calls(
                        round_tool_calls,
                        chunk.tool_calls,
                    )

                if chunk.total_tokens is not None:
                    round_total_tokens = chunk.total_tokens

            self._total_tokens += round_total_tokens
            tc_list = self._finalize_stream_tool_calls(round_tool_calls)

            if not tc_list:
                self._output = round_output
                self._reasoning_output = round_reasoning_output
                break

            messages.append(
                processor.build_assistant_tool_call_message(
                    content=round_output,
                    tool_calls=tc_list,
                    reasoning_content=round_visible_thinking or None,
                )
            )

            round_has_confirmation = False

            # Execute tools one by one and push SSE events immediately / 逐个执行工具并立即推送 SSE 事件
            for tc in tc_list:
                tc_id = tc.get("id", "")
                func = tc.get("function", {})
                func_name = func.get("name", "")
                raw_args = func.get("arguments", "{}")
                arguments, parse_error = processor.parse_arguments(raw_args)

                # JSON parse failure: do not execute, push error result instead / JSON 解析失败：不执行，推送错误结果
                # Parse error 也纳入连续 pageop/invoke 失败计数，达阈值后熔断
                if parse_error:
                    raw_snippet = (
                        (raw_args[:500] + "…")
                        if isinstance(raw_args, str) and len(raw_args) > 500
                        else raw_args
                    )
                    logger.warning(
                        "Tool JSON parse failed: tool={} error={} raw_args_snippet={}",
                        func_name,
                        parse_error,
                        repr(raw_snippet)[:600],
                    )
                    from app.ai.tools.types import ToolResult

                    err_msg = _("page_operation.error.json_parse_failed")
                    if func_name and func_name.startswith("data_"):
                        _consecutive_data_op_failures += 1
                        err_msg += " " + _("data_intelligence.crud.json_parse_guidance")
                        if _consecutive_data_op_failures >= 2:
                            err_msg += " " + _("data_intelligence.crud.json_parse_guidance_tip")
                    err_result = ToolResult(
                        tool_call_id=tc_id,
                        name=func_name or "unknown",
                        success=False,
                        error=err_msg,
                        error_type=parse_error,
                    )
                    all_tool_results.append(err_result)
                    yield SSEChunkEncoder.encode(
                        processor.build_tool_call_event(
                            err_result, 0, processor.get_skill_info(func_name),
                            name_override=func_name,
                        ),
                    )
                    messages.append(processor.build_tool_message(err_result, tc_id))

                    # Count parse error as page op failure (circuit breaking) / parse error 计入页面操作失败以触发熔断
                    _is_page_op = (
                        func_name == "invoke_page_operation"
                        or (func_name.startswith("pageop_") if func_name else False)
                    )
                    if _is_page_op:
                        _consecutive_page_op_failures += 1
                        if _consecutive_page_op_failures >= PAGE_OP_ABORT_THRESHOLD:
                            logger.warning(
                                "Aborting tool loop: {} consecutive page op failures (incl. parse errors) conversation={}",
                                _consecutive_page_op_failures,
                                self.request.conversation_id,
                            )
                            _page_op_aborted = True
                            self._output = (
                                round_output.strip()
                                + "\n\n"
                                + _("page_operation.error.multiple_failures_parse")
                            )

                    if _page_op_aborted:
                        break
                    continue

                _skill_info = processor.get_skill_info(func_name)

                # ---- consent_mode pre-check ---- / consent_mode 前置检查
                _consent = processor.check_consent(func_name)

                if _consent == "reject":
                    messages.append(processor.build_consent_reject_message(tc_id))
                    yield SSEChunkEncoder.encode(
                        processor.build_consent_reject_event(
                            func_name, _skill_info,
                        )
                    )
                    continue

                if _consent == "ask":
                    messages.append(
                        processor.build_consent_ask_message(
                            tc_id, func_name, arguments,
                        )
                    )
                    yield SSEChunkEncoder.encode(
                        processor.build_consent_ask_event(
                            func_name, arguments, _skill_info,
                        )
                    )
                    round_has_confirmation = True
                    continue

                # ---- auto: normal execution ---- / auto: 正常执行
                yield SSEChunkEncoder.encode(
                    processor.build_tool_start_event(
                        func_name, arguments, _skill_info,
                        tool_call_id=tc_id,
                    )
                )

                result, tc_duration = await processor.execute_tool(
                    tc_id, func_name, arguments,
                    conversation_id=self.request.conversation_id or 0,
                )
                all_tool_results.append(result)

                # Track consecutive page operation failures; abort to stop apology loops
                _is_page_op = (
                    func_name == "invoke_page_operation"
                    or (func_name.startswith("pageop_") if func_name else False)
                )
                if _is_page_op:
                    if result.success:
                        _consecutive_page_op_failures = 0
                    else:
                        _consecutive_page_op_failures += 1
                        if _consecutive_page_op_failures >= PAGE_OP_ABORT_THRESHOLD:
                            logger.warning(
                                "Aborting tool loop: {} consecutive page operation failures (conversation={})",
                                _consecutive_page_op_failures,
                                self.request.conversation_id,
                            )
                            _page_op_aborted = True
                            self._output = (
                                round_output.strip()
                                + "\n\n"
                                + _("page_operation.error.multiple_failures_sequence")
                            )
                elif func_name and func_name.startswith("data_") and result.success:
                    _consecutive_data_op_failures = 0

                # Push tool_result event / 推送 tool_result 事件（name_override 保持与 tool_start 一致，避免前端匹配失败）
                yield SSEChunkEncoder.encode(
                    processor.build_tool_call_event(
                        result, tc_duration, _skill_info,
                        name_override=func_name,
                    )
                )

                # Detect confirmation_request (CRUD preview confirmation) / 检测 confirmation_request（CRUD 预览确认）
                _conf_data = processor.check_confirmation_output(result)
                if _conf_data:
                    round_has_confirmation = True
                    yield SSEChunkEncoder.encode(
                        processor.build_confirmation_event(_conf_data)
                    )

                # Append tool message / 追加 tool 消息
                messages.append(processor.build_tool_message(result, tc_id))

                if _page_op_aborted:
                    break

            if round_has_confirmation or _page_op_aborted:
                if round_has_confirmation:
                    self._output = round_output.strip()
                    self._reasoning_output = round_reasoning_output.strip()
                    # The current round already has assistant(tool_calls) content;
                    # do not append a second plain assistant copy into history.
                    append_final_assistant = False
                break
        else:
            logger.warning(
                "Tool call rounds exceeded max: conversation={} max_rounds={}",
                self.request.conversation_id,
                MAX_TOOL_CALL_ROUNDS,
            )

        if append_final_assistant:
            messages.append(ChatMessage(
                role="assistant",
                content=self._output,
                reasoning_content=(self._reasoning_output or "").strip() or None,
            ))

    # ========================================
    # Tool Call Incremental Aggregation / 工具调用增量聚合
    # ========================================

    @staticmethod
    def _normalize_stream_tool_call(tool_call: Any) -> dict[str, Any] | None:
        """
        Normalize streaming tool_call delta, compatible with both dict and SDK object formats. / 归一化流式 tool_call 增量，兼容 dict 与 SDK 对象。
        """
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

    @classmethod
    def _merge_stream_tool_calls(
        cls,
        existing: list[dict[str, Any]],
        incoming: list[Any],
    ) -> list[dict[str, Any]]:
        """
        Merge streaming tool_call deltas, supports OpenAI-style index incremental concatenation. / 合并流式 tool_call 增量，支持 OpenAI 风格 index 增量拼接。
        """
        merged = existing[:]

        for raw_tc in incoming:
            tc = cls._normalize_stream_tool_call(raw_tc)
            if not tc:
                continue

            target: dict[str, Any] | None = None
            tc_index = tc.get("_index")
            tc_id = tc.get("id")

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
                merged.append(tc)
                target = merged[-1]
            else:
                if tc_id and not target.get("id"):
                    target["id"] = tc_id

            target_func = target.setdefault("function", {})
            tc_func = tc.get("function", {})

            tc_name = tc_func.get("name") or ""
            if tc_name:
                cur_name = target_func.get("name", "")
                if not cur_name or tc_name.startswith(cur_name):
                    target_func["name"] = tc_name
                elif not cur_name.startswith(tc_name):
                    target_func["name"] = cur_name + tc_name

            tc_args = tc_func.get("arguments") or ""
            if tc_args:
                cur_args = target_func.get("arguments", "")
                if not cur_args or tc_args.startswith(cur_args):
                    target_func["arguments"] = tc_args
                elif not cur_args.startswith(tc_args):
                    target_func["arguments"] = cur_args + tc_args

        return merged

    @staticmethod
    def _finalize_stream_tool_calls(
        calls: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        清理内部字段并补齐默认值，输出可执行的 tool_call 列表 / Clean internal fields and fill defaults, output executable tool_call list.
        """
        finalized: list[dict[str, Any]] = []

        for idx, tc in enumerate(calls):
            func = tc.get("function") or {}
            name = (func.get("name") or "").strip()
            if not name:
                logger.warning("Skip invalid streamed tool_call without name: {}", tc)
                continue

            arguments = func.get("arguments")
            if arguments in (None, ""):
                arguments = "{}"

            tc_id = tc.get("id") or f"stream_tool_{idx}"
            if isinstance(arguments, str) and len(arguments) > 200:
                logger.debug(
                    "Finalized tool_call: name={} args_len={} args_head={}",
                    name,
                    len(arguments),
                    repr(arguments[:300]),
                )
            finalized.append(
                {
                    "id": tc_id,
                    "type": tc.get("type") or "function",
                    "function": {
                        "name": name,
                        "arguments": arguments,
                    },
                }
            )

        return finalized

    # ========================================
    # Action Buttons Parsing / Action Buttons 解析
    # ========================================

    _ACTION_BUTTONS_RE = re.compile(
        r"\[ACTIONS\](.*?)\[/ACTIONS\]",
        re.DOTALL,
    )

    @staticmethod
    def _extract_action_buttons(
        output: str,
    ) -> tuple[str, list[dict[str, str]] | None]:
        """
        Extract button definitions from [ACTIONS]...[/ACTIONS] markers in LLM output.
        从 LLM 输出中提取 [ACTIONS]...[/ACTIONS] 标记中的按钮定义。

        Supported format / 支持格式:
            [ACTIONS]
            [{"label": "方案A", "value": "选择方案A", "style": "primary"}]
            [/ACTIONS]

        Returns:
            (cleaned_output, buttons) — Cleaned output and button list (None if no buttons)
            清理后的输出和按钮列表（无按钮时为 None）
        """
        match = StreamExecutionHandler._ACTION_BUTTONS_RE.search(output)
        if not match:
            return output, None

        raw = match.group(1).strip()
        try:
            buttons = json.loads(raw)
            if not isinstance(buttons, list):
                return output, None
            # Validate each button has at least label and value / 校验每个按钮至少有 label 和 value
            valid_buttons: list[dict[str, str]] = []
            for btn in buttons:
                if isinstance(btn, dict) and "label" in btn and "value" in btn:
                    item: dict[str, str] = {
                        "label": str(btn["label"]),
                        "value": str(btn["value"]),
                    }
                    if "style" in btn and btn["style"] in (
                        "primary", "default", "danger",
                    ):
                        item["style"] = btn["style"]
                    valid_buttons.append(item)
            if not valid_buttons:
                return output, None
            # Remove markers from output / 从输出中移除标记
            cleaned = StreamExecutionHandler._ACTION_BUTTONS_RE.sub(
                "", output,
            ).strip()
            return cleaned, valid_buttons
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning("Failed to parse action buttons from LLM output")
            return output, None


__all__ = ["StreamExecutionHandler"]
