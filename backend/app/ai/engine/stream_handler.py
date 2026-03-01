"""
SSE 流式执行处理器

从 ConversationEngine._sse_generator 提取，封装 SSE 事件生成主循环。
包括工具调用实时推送、确认拦截、DSML 标签清理、错误处理。
"""

from __future__ import annotations

import json
import re
import time
from typing import TYPE_CHECKING, Any, AsyncIterator, Awaitable, Callable

from app.ai.sse import SSEChunkEncoder
from app.ai.types import ChatMessage
from app.core.logging import LogManager

from .base import MAX_TOOL_CALL_ROUNDS
from .types import ExecutionRequest, ExecutionResult, PreparedExecution

if TYPE_CHECKING:
    from app.ai.tools.types import ToolResult
    from app.models.ai.agent import Agent

    from .base import BaseEngine
    from .tool_processor import ToolCallProcessor

logger = LogManager.get_logger("ai.engine.stream_handler")


class StreamExecutionHandler:
    """
    SSE 流式执行处理器

    将 ConversationEngine._sse_generator 的完整逻辑封装为独立类。
    通过 engine 引用访问 _call_llm / _stream_llm_chunks / _messages_to_dicts。

    事件类型：
    - message: 内容增量
    - tool_call: 工具调用结果
    - thinking: AI 正在执行工具
    - optimizing_tools: 工具优化事件
    - rag_sources: RAG 引用来源
    - confirmation_request: 需要用户确认
    - done: 完成
    - [DONE]: SSE 结束标记
    """

    def __init__(
        self,
        engine: BaseEngine,
        agent: Agent,
        request: ExecutionRequest,
        prep: PreparedExecution,
        start_time: float,
        on_complete: Callable[[ExecutionResult], Awaitable[None]] | None = None,
    ):
        self.engine = engine
        self.agent = agent
        self.request = request
        self.prep = prep
        self.start_time = start_time
        self.on_complete = on_complete

    async def generate(self) -> AsyncIterator[str]:
        """SSE 事件生成器主循环"""
        from .conversation import _strip_model_fc_tokens
        from .tool_processor import ToolCallProcessor

        messages = self.prep.messages
        tools = self.prep.tools
        rag_sources = self.prep.rag_sources
        _optimize_event = self.prep.optimize_event
        _tool_consent_modes = self.prep.tool_consent_modes

        processor = ToolCallProcessor(
            sandbox=self.engine.sandbox,
            tools=tools,
            consent_modes=_tool_consent_modes,
        )

        total_tokens = 0
        all_tool_results: list[ToolResult] = []
        output = ""

        try:
            # 推送工具优化事件
            if _optimize_event is not None:
                yield SSEChunkEncoder.encode(
                    {"event": "optimizing_tools", **_optimize_event}
                    if isinstance(_optimize_event, dict)
                    else _optimize_event
                )

            if tools:
                # ---- 有工具：工具调用循环 + 最终回复流式推送 ----
                async for event in self._generate_with_tools(
                    messages, tools, processor, all_tool_results,
                    _strip_model_fc_tokens,
                ):
                    yield event
                    # 从事件中提取 output 和 total_tokens
                    # (通过 self._output / self._total_tokens 共享状态)

                output = self._output
                total_tokens = self._total_tokens
            else:
                # ---- 无工具：真实流式推送 ----
                async for chunk in self.engine._stream_llm_chunks(
                    agent=self.agent,
                    messages=messages,
                    tenant_id=self.request.tenant_id,
                    route_result=self.prep.route_result,
                ):
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

                messages.append(ChatMessage(role="assistant", content=output))

            # ---- 解析并发送 Action Buttons ----
            cleaned_output, action_buttons = self._extract_action_buttons(output)
            if action_buttons:
                output = cleaned_output
                yield SSEChunkEncoder.encode({
                    "event": "action_buttons",
                    "buttons": action_buttons,
                })

            # ---- 发送 RAG 引用来源事件 ----
            if rag_sources:
                yield SSEChunkEncoder.encode({
                    "event": "rag_sources",
                    "sources": rag_sources,
                })

            # ---- 发送完成事件 ----
            duration_ms = int((time.perf_counter() - self.start_time) * 1000)

            yield SSEChunkEncoder.encode({
                "event": "done",
                "conversation_id": self.request.conversation_id,
                "total_tokens": total_tokens,
                "duration_ms": duration_ms,
            })
            yield SSEChunkEncoder.done()

            # 构建结果并调用回调
            result = ExecutionResult(
                success=True,
                output=output,
                messages=self.engine._messages_to_dicts(messages),
                tool_results=all_tool_results,
                total_tokens=total_tokens,
                duration_ms=duration_ms,
                conversation_id=self.request.conversation_id,
            )

            if self.on_complete:
                await self.on_complete(result)

        except Exception as exc:
            logger.error(
                "Stream execution failed: agent=%d error=%s",
                self.agent.id,
                str(exc),
                exc_info=True,
            )
            try:
                yield SSEChunkEncoder.encode({
                    "error": True,
                    "message": str(exc),
                })
                yield SSEChunkEncoder.done()
            except Exception:
                pass  # 连接已断开时忽略 yield 错误

            # 异常路径也触发回调
            if self.on_complete:
                duration_ms = int((time.perf_counter() - self.start_time) * 1000)
                failed_result = ExecutionResult(
                    success=False,
                    error=str(exc),
                    duration_ms=duration_ms,
                    conversation_id=self.request.conversation_id,
                )
                try:
                    await self.on_complete(failed_result)
                except Exception as cb_exc:
                    logger.error(
                        "on_complete callback error: %s",
                        str(cb_exc),
                    )

        except BaseException as exc:
            # 捕获 CancelledError / GeneratorExit 等非 Exception 异常
            logger.error(
                "Stream BaseException: agent=%d type=%s error=%s",
                self.agent.id, type(exc).__name__, str(exc),
                exc_info=True,
            )
            if self.on_complete:
                duration_ms = int((time.perf_counter() - self.start_time) * 1000)
                try:
                    await self.on_complete(ExecutionResult(
                        success=False,
                        error=f"{type(exc).__name__}: {exc}",
                        duration_ms=duration_ms,
                        conversation_id=self.request.conversation_id,
                    ))
                except Exception:
                    pass
            raise  # 必须重新抛出 BaseException

    async def _generate_with_tools(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
        processor: ToolCallProcessor,
        all_tool_results: list[ToolResult],
        strip_fc_tokens: Callable[[str], str],
    ) -> AsyncIterator[str]:
        """有工具时的 SSE 事件生成（确认拦截 + 工具调用循环 + 最终回复）

        通过 self._output / self._total_tokens 共享最终状态给调用者。
        """
        self._total_tokens = 0
        self._output = ""

        # ---- 确认拦截：检测用户确认/拒绝文本 ----
        _last_user_text = ""
        if self.request.messages:
            _last = self.request.messages[-1]
            if _last.role == "user":
                _last_user_text = (_last.content or "").strip()

        _pending = None
        if processor.is_confirmation_text(_last_user_text):
            _pending = processor.find_pending_confirmation(messages)

        if _pending:
            # 直接执行已确认的工具调用，不经过 LLM
            _tc_id = _pending["tool_call_id"]
            _func_name = _pending["name"]
            _arguments = _pending["arguments"]

            _conf_skill = processor.get_skill_info(_func_name)
            yield SSEChunkEncoder.encode(
                processor.build_tool_start_event(
                    _func_name, _arguments, _conf_skill,
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
                )
            )

            # 将确认后的工具调用追加到消息中
            messages.append(processor.build_assistant_tool_call_message(
                content="",
                tool_calls=[{
                    "id": _tc_id,
                    "type": "function",
                    "function": {
                        "name": _func_name,
                        "arguments": json.dumps(
                            _arguments, ensure_ascii=False,
                        ),
                    },
                }],
            ))
            messages.append(
                processor.build_tool_message(_result, _tc_id)
            )

        # ---- 有工具：实时推送工具调用事件 ----
        response = await self.engine._call_llm(
            agent=self.agent,
            messages=messages,
            tools=tools,
            tenant_id=self.request.tenant_id,
            user_id=self.request.user_id,
            route_result=self.prep.route_result,
        )
        self._total_tokens += response.total_tokens or 0

        if response.tool_calls:
            # 通知前端 AI 正在执行工具
            yield SSEChunkEncoder.encode({
                "event": "thinking",
            })

            # 内联工具调用循环
            current_response = response
            has_confirmation = False
            for _round in range(MAX_TOOL_CALL_ROUNDS):
                tc_list = current_response.tool_calls
                if not tc_list:
                    break

                # 追加 assistant 消息（含 tool_calls）
                messages.append(processor.build_assistant_tool_call_message(
                    content=current_response.message.content or "",
                    tool_calls=tc_list,
                ))

                # 逐个执行工具并立即推送 SSE 事件
                for tc in tc_list:
                    tc_id = tc.get("id", "")
                    func = tc.get("function", {})
                    func_name = func.get("name", "")
                    raw_args = func.get("arguments", "{}")
                    arguments = processor.parse_arguments(raw_args)

                    _skill_info = processor.get_skill_info(func_name)

                    # ---- consent_mode 前置检查 ----
                    _consent = processor.check_consent(func_name)

                    if _consent == "reject":
                        messages.append(
                            processor.build_consent_reject_message(tc_id)
                        )
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
                        has_confirmation = True
                        continue

                    # ---- auto: 正常执行 ----
                    yield SSEChunkEncoder.encode(
                        processor.build_tool_start_event(
                            func_name, arguments, _skill_info,
                        )
                    )

                    result, tc_duration = await processor.execute_tool(
                        tc_id, func_name, arguments,
                        conversation_id=self.request.conversation_id or 0,
                    )
                    all_tool_results.append(result)

                    # 推送 tool_result 事件
                    yield SSEChunkEncoder.encode(
                        processor.build_tool_call_event(
                            result, tc_duration, _skill_info,
                        )
                    )

                    # 检测 confirmation_request（CRUD 预览确认）
                    _conf_data = processor.check_confirmation_output(result)
                    if _conf_data:
                        has_confirmation = True
                        yield SSEChunkEncoder.encode(
                            processor.build_confirmation_event(_conf_data)
                        )

                    # 追加 tool 消息
                    messages.append(
                        processor.build_tool_message(result, tc_id)
                    )

                # 有确认请求时中断多轮循环
                if has_confirmation:
                    break

                # 检查 LLM 是否还有更多 tool_calls（多轮）
                if _round < MAX_TOOL_CALL_ROUNDS - 1:
                    peek_response = await self.engine._call_llm(
                        agent=self.agent,
                        messages=messages,
                        tools=tools,
                        tenant_id=self.request.tenant_id,
                        user_id=self.request.user_id,
                        route_result=self.prep.route_result,
                    )
                    self._total_tokens += peek_response.total_tokens or 0
                    if peek_response.tool_calls:
                        current_response = peek_response
                        continue
                    # peek_response 已包含最终回复
                    peek_content = peek_response.message.content or ""
                    if peek_content:
                        peek_content = strip_fc_tokens(peek_content).strip()
                    if peek_content:
                        self._output = peek_content
                        yield SSEChunkEncoder.encode({
                            "event": "message",
                            "delta": self._output,
                        })
                        break
                # 无更多 tool_calls，跳出循环
                break

            # 最终回复兜底：仅在 peek_response 无内容且无待确认时流式推送
            if not self._output and not has_confirmation:
                async for chunk in self.engine._stream_llm_chunks(
                    agent=self.agent,
                    messages=messages,
                    tenant_id=self.request.tenant_id,
                    route_result=self.prep.route_result,
                ):
                    if chunk.delta:
                        cleaned = strip_fc_tokens(chunk.delta)
                        if cleaned:
                            self._output += cleaned
                            yield SSEChunkEncoder.encode({
                                "event": "message",
                                "delta": cleaned,
                            })
                    if chunk.total_tokens is not None:
                        self._total_tokens += chunk.total_tokens
                    if chunk.finish_reason is not None:
                        break
        else:
            # LLM 未调用工具，直接输出
            self._output = strip_fc_tokens(
                response.message.content or "",
            ).strip()
            if self._output:
                yield SSEChunkEncoder.encode({
                    "event": "message",
                    "delta": self._output,
                })

        messages.append(ChatMessage(role="assistant", content=self._output))

    # ========================================
    # Action Buttons 解析
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
        从 LLM 输出中提取 [ACTIONS]...[/ACTIONS] 标记中的按钮定义。

        支持格式:
            [ACTIONS]
            [{"label": "方案A", "value": "选择方案A", "style": "primary"}]
            [/ACTIONS]

        Returns:
            (cleaned_output, buttons) — 清理后的输出和按钮列表（无按钮时为 None）
        """
        match = StreamExecutionHandler._ACTION_BUTTONS_RE.search(output)
        if not match:
            return output, None

        raw = match.group(1).strip()
        try:
            buttons = json.loads(raw)
            if not isinstance(buttons, list):
                return output, None
            # 校验每个按钮至少有 label 和 value
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
            # 从输出中移除标记
            cleaned = StreamExecutionHandler._ACTION_BUTTONS_RE.sub(
                "", output,
            ).strip()
            return cleaned, valid_buttons
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning("Failed to parse action buttons from LLM output")
            return output, None


__all__ = ["StreamExecutionHandler"]
