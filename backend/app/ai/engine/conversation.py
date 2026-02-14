"""
对话执行引擎

支持多轮对话，维护会话上下文，处理 tool calling 循环
支持 SSE 流式输出
"""

import dataclasses
import json
import re
import time
from typing import Any, AsyncIterator, Awaitable, Callable

from fastapi.responses import StreamingResponse

from app.ai.adapters import AdapterRegistry
from app.ai.sse import SSEChunkEncoder
from app.ai.types import ChatChunk, ChatMessage, messages_to_dicts
from app.core.i18n import _
from app.core.logging import LogManager
from app.models.ai.agent import Agent
from app.enums.ai import RequestTypeEnum
from app.services.ai.metering_service import CostCalculator, TokenCounter

from .base import BaseEngine, MAX_TOOL_CALL_ROUNDS
from .types import ExecutionRequest, ExecutionResult

logger = LogManager.get_logger("ai.engine.conversation")


def _get_skill_info(
    tool_name: str,
    definitions: list,
) -> dict[str, str | None]:
    """从 ToolDefinition 列表中查找工具对应的 Skill 来源信息"""
    for td in definitions:
        if td.name == tool_name:
            return {
                "skill_name": td.source_skill_name,
                "skill_type": td.source_skill_type,
            }
    return {}

# DeepSeek 模型内部 function call 标记（｜DSML｜parameter, ｜DSML｜invoke 等）
_MODEL_FC_TOKEN_RE = re.compile(r'</?｜[A-Za-z]+｜[^>]*>')
# 完整 DSML function_calls 块（含嵌套内容）
_MODEL_FC_BLOCK_RE = re.compile(
    r'<｜DSML｜function_calls>.*?</｜DSML｜function_calls>',
    re.DOTALL,
)


def _strip_model_fc_tokens(text: str) -> str:
    """过滤模型泄漏的内部 function call 标记（DeepSeek ｜DSML｜ 等）"""
    if '｜' not in text:
        return text
    # 先移除完整块，再清理残留标签
    text = _MODEL_FC_BLOCK_RE.sub('', text)
    return _MODEL_FC_TOKEN_RE.sub('', text)


# 确认/拒绝文本（前端 i18n 对应 common.globalAiChat.confirmExecute / rejectExecute）
_CONFIRMATION_TEXTS = frozenset({"确认执行", "Confirm execution", "confirm execution"})
_REJECTION_TEXTS = frozenset({"取消操作，不执行", "Cancel, do not execute", "cancel, do not execute"})


def _find_pending_confirmation(
    messages: list[ChatMessage],
) -> dict[str, Any] | None:
    """从消息历史中查找最近的待确认工具调用

    向后搜索 role=tool 且内容含 requires_confirmation 的消息，
    再找到对应的 assistant tool_call，提取原始参数并注入 confirmed=True。

    Returns:
        {"name": str, "arguments": dict, "tool_call_id": str} 或 None
    """
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg.role != "tool" or not msg.content:
            continue
        try:
            parsed = json.loads(msg.content)
        except (ValueError, TypeError):
            continue
        if not isinstance(parsed, dict) or not parsed.get("requires_confirmation"):
            continue
        # 找到 requires_confirmation 的 tool 消息，查找对应的 assistant tool_call
        tool_call_id = msg.tool_call_id
        for j in range(i - 1, -1, -1):
            asst = messages[j]
            if asst.role != "assistant" or not asst.tool_calls:
                continue
            for tc in asst.tool_calls:
                if tc.get("id") == tool_call_id:
                    func = tc.get("function", {})
                    raw_args = func.get("arguments", "{}")
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                    args["confirmed"] = True
                    return {
                        "name": func.get("name", ""),
                        "arguments": args,
                        "tool_call_id": tool_call_id or f"confirm_{i}",
                    }
            break
        break
    return None


class ConversationEngine(BaseEngine):
    """
    对话执行引擎

    处理多轮对话场景：
    1. 构建 system 消息 + 历史消息 + 新用户消息
    2. 调用 LLM
    3. 如果返回 tool_calls，进入工具调用循环
    4. 返回最终 assistant 回复

    支持两种输出模式：
    - execute(): 非流式，一次性返回完整结果
    - stream_execute(): SSE 流式，逐 token 推送
    """

    async def execute(self, agent: Agent, request: ExecutionRequest) -> ExecutionResult:
        """执行对话模式"""
        start = time.perf_counter()

        try:
            # 1. 解析 Skill
            skill_result = await self._resolve_skills(agent, tenant_id=request.tenant_id)

            # 2. 构建消息列表
            messages: list[ChatMessage] = []

            # system 消息（注入 input_variables 到占位符）
            system_msg = self._build_system_message(agent, request.input_variables)
            messages.append(system_msg)

            # 历史消息（来自 request.messages）
            if request.messages:
                messages.extend(request.messages)

            # RAG 知识库注入
            rag_sources = None
            skill_kb_ids = skill_result.knowledge_base_ids if skill_result else None
            skill_rag_config = skill_result.rag_config if skill_result else None
            merged_kb_ids = self._merge_kb_ids(skill_kb_ids, request.knowledge_base_ids)
            if merged_kb_ids:
                messages, rag_sources = await self._build_messages_with_rag(
                    agent, messages, request.tenant_id,
                    override_kb_ids=merged_kb_ids,
                    rag_config=skill_rag_config,
                )

            # 3. 获取工具列表 + 优化
            tools = skill_result.tools if skill_result else []
            if tools:
                user_query = ""
                for _m in reversed(messages):
                    if _m.role == "user":
                        user_query = _m.content or ""
                        break
                from app.ai.tools.optimizer import optimize_tools
                opt = optimize_tools(tools, user_query)
                tools = opt.tools

            # 3.5 注入工具感知提示
            if tools:
                self._inject_tool_awareness(messages, tools)

            # 4. 调用 LLM
            response = await self._call_llm(
                agent=agent,
                messages=messages,
                tools=tools or None,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
            )

            total_tokens = response.total_tokens or 0

            # 4. 工具调用循环
            tool_results = []
            if response.tool_calls and tools:
                response, tool_results, total_tokens = await self._handle_tool_calls(
                    agent=agent,
                    messages=messages,
                    response=response,
                    tools=tools,
                    request=request,
                )

            # 5. 追加最终 assistant 消息
            output = response.message.content or ""
            messages.append(ChatMessage(role="assistant", content=output))

            duration_ms = int((time.perf_counter() - start) * 1000)

            result = ExecutionResult(
                success=True,
                output=output,
                messages=self._messages_to_dicts(messages),
                tool_results=tool_results,
                total_tokens=total_tokens,
                duration_ms=duration_ms,
                conversation_id=request.conversation_id,
            )
            # 附加 RAG 引用来源
            if rag_sources:
                result.rag_sources = rag_sources  # type: ignore[attr-defined]

            return result

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "Conversation execution failed: agent=%d error=%s",
                agent.id,
                str(exc),
                exc_info=True,
            )
            return ExecutionResult(
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
                conversation_id=request.conversation_id,
            )

    # ========================================
    # SSE 流式执行
    # ========================================

    async def stream_execute(
        self,
        agent: Agent,
        request: ExecutionRequest,
        on_complete: Callable[[ExecutionResult], Awaitable[None]] | None = None,
    ) -> StreamingResponse:
        """
        SSE 流式执行对话

        事件类型：
        - message: 内容增量 {"event": "message", "delta": "..."}
        - tool_call: 工具调用 {"event": "tool_call", "name": "...", "success": bool}
        - done: 完成 {"event": "done", "conversation_id": N, "total_tokens": N}
        - [DONE]: SSE 结束标记

        执行策略：
        - 无工具时：通过 adapter 真实流式推送 token
        - 有工具时：非流式处理工具调用，发送工具事件后推送最终内容

        Args:
            agent: 智能体模型实例
            request: 执行请求
            on_complete: 流式完成后的回调（用于持久化消息等）

        Returns:
            StreamingResponse (SSE)
        """
        start = time.perf_counter()

        # 1. 解析 Skill
        skill_result = await self._resolve_skills(agent, tenant_id=request.tenant_id)

        # 构建消息列表
        messages: list[ChatMessage] = []
        system_msg = self._build_system_message(agent, request.input_variables)
        messages.append(system_msg)

        if request.messages:
            messages.extend(request.messages)

        # RAG 知识库注入
        rag_sources = None
        skill_kb_ids = skill_result.knowledge_base_ids if skill_result else None
        skill_rag_config = skill_result.rag_config if skill_result else None
        merged_kb_ids = self._merge_kb_ids(skill_kb_ids, request.knowledge_base_ids)
        if merged_kb_ids:
            messages, rag_sources = await self._build_messages_with_rag(
                agent, messages, request.tenant_id,
                override_kb_ids=merged_kb_ids,
                rag_config=skill_rag_config,
            )

        # 获取工具列表 + 优化
        tools = skill_result.tools if skill_result else []
        _optimize_event: dict[str, Any] | None = None
        if tools:
            _user_q = ""
            for _m in reversed(messages):
                if _m.role == "user":
                    _user_q = _m.content or ""
                    break
            from app.ai.tools.optimizer import optimize_tools
            opt = optimize_tools(tools, _user_q)
            tools = opt.tools
            if not opt.skipped:
                _optimize_event = {"total": opt.total, "selected": opt.selected}

        # 注入工具感知提示
        if tools:
            self._inject_tool_awareness(messages, tools)

        async def _sse_generator() -> AsyncIterator[str]:
            """SSE 事件生成器（工具调用事件实时推送）"""
            total_tokens = 0
            all_tool_results: list[Any] = []
            output = ""

            try:
                # 推送工具优化事件
                if _optimize_event is not None:
                    yield sse.encode("optimizing_tools", _optimize_event)

                if tools:
                    # ---- 确认拦截：检测用户确认/拒绝文本，直接执行待确认的工具调用 ----
                    _last_user_text = ""
                    if request.messages:
                        _last = request.messages[-1]
                        if _last.role == "user":
                            _last_user_text = (_last.content or "").strip()

                    _pending = None
                    if _last_user_text in _CONFIRMATION_TEXTS:
                        _pending = _find_pending_confirmation(messages)

                    if _pending:
                        # 直接执行已确认的工具调用，不经过 LLM
                        _tc_id = _pending["tool_call_id"]
                        _func_name = _pending["name"]
                        _arguments = _pending["arguments"]

                        _conf_skill = _get_skill_info(_func_name, tools)
                        yield SSEChunkEncoder.encode({
                            "event": "tool_start",
                            "name": _func_name,
                            "arguments": _arguments,
                            **_conf_skill,
                        })

                        _tc_start = time.perf_counter()
                        _result = await self.sandbox.execute(
                            tool_call_id=_tc_id,
                            name=_func_name,
                            arguments=_arguments,
                            definitions=tools,
                            conversation_id=request.conversation_id or 0,
                        )
                        _tc_dur = int((time.perf_counter() - _tc_start) * 1000)
                        all_tool_results.append(_result)

                        _te: dict[str, Any] = {
                            "event": "tool_call",
                            "name": _result.name,
                            "success": _result.success,
                            "duration_ms": _tc_dur,
                            **_conf_skill,
                        }
                        if _result.success and _result.output:
                            _s = _result.output[:500]
                            if len(_result.output) > 500:
                                _s += "..."
                            _te["output"] = _s
                        elif not _result.success and _result.error:
                            _te["error"] = _result.error[:300]
                        yield SSEChunkEncoder.encode(_te)

                        # 将确认后的工具调用追加到消息中，供 LLM 生成后续回复
                        messages.append(ChatMessage(
                            role="assistant", content="",
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
                        messages.append(ChatMessage(
                            role="tool",
                            content=_result.output if _result.success else _(
                                "tool.error.prefix", error=_result.error,
                            ),
                            tool_call_id=_tc_id,
                        ))
                        # 继续正常 LLM 调用（LLM 看到执行结果后可能触发更多工具调用）

                    # ---- 有工具：实时推送工具调用事件，最终回复流式推送 ----
                    response = await self._call_llm(
                        agent=agent,
                        messages=messages,
                        tools=tools,
                        tenant_id=request.tenant_id,
                        user_id=request.user_id,
                    )
                    total_tokens += response.total_tokens or 0

                    if response.tool_calls:
                        # 通知前端 AI 正在执行工具
                        yield SSEChunkEncoder.encode({
                            "event": "thinking",
                        })

                        # 内联工具调用循环，实时推送每个工具的执行结果
                        current_response = response
                        has_confirmation = False
                        for _round in range(MAX_TOOL_CALL_ROUNDS):
                            tc_list = current_response.tool_calls
                            if not tc_list:
                                break

                            # 追加 assistant 消息（含 tool_calls）
                            messages.append(ChatMessage(
                                role="assistant",
                                content=current_response.message.content or "",
                                tool_calls=tc_list,
                            ))

                            # 逐个执行工具并立即推送 SSE 事件
                            for tc in tc_list:
                                tc_id = tc.get("id", "")
                                func = tc.get("function", {})
                                func_name = func.get("name", "")
                                raw_args = func.get("arguments", "{}")

                                try:
                                    arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                                except json.JSONDecodeError:
                                    arguments = {}

                                # 推送 tool_start 事件（工具开始执行）
                                _skill_info = _get_skill_info(func_name, tools)
                                yield SSEChunkEncoder.encode({
                                    "event": "tool_start",
                                    "name": func_name,
                                    "arguments": arguments,
                                    **_skill_info,
                                })

                                tc_start = time.perf_counter()
                                result = await self.sandbox.execute(
                                    tool_call_id=tc_id,
                                    name=func_name,
                                    arguments=arguments,
                                    definitions=tools,
                                    conversation_id=request.conversation_id or 0,
                                )
                                tc_duration = int((time.perf_counter() - tc_start) * 1000)
                                all_tool_results.append(result)

                                # 推送 tool_result 事件（工具执行完成）
                                tool_event: dict[str, Any] = {
                                    "event": "tool_call",
                                    "name": result.name,
                                    "success": result.success,
                                    "duration_ms": tc_duration,
                                    **_skill_info,
                                }
                                if result.success and result.output:
                                    # 截取输出摘要（避免过长）
                                    summary = result.output[:500]
                                    if len(result.output) > 500:
                                        summary += "..."
                                    tool_event["output"] = summary
                                elif not result.success and result.error:
                                    tool_event["error"] = result.error[:300]
                                yield SSEChunkEncoder.encode(tool_event)

                                # 检测 confirmation_request（CRUD 预览确认）
                                if result.success and result.output:
                                    try:
                                        _parsed = json.loads(result.output)
                                        if isinstance(_parsed, dict) and _parsed.get("requires_confirmation"):
                                            has_confirmation = True
                                            confirmation_event: dict[str, Any] = {
                                                "event": "confirmation_request",
                                                "action": _parsed.get("action", ""),
                                                "table": _parsed.get("table", ""),
                                                "preview": _parsed.get("preview") or _parsed.get("diff") or _parsed.get("record"),
                                            }
                                            # CRUD Generator 文件生成确认
                                            if _parsed.get("files"):
                                                confirmation_event["files"] = _parsed["files"]
                                                confirmation_event["message"] = _parsed.get("message", "")
                                                confirmation_event["total_new"] = _parsed.get("total_new", 0)
                                                confirmation_event["total_conflict"] = _parsed.get("total_conflict", 0)
                                            yield SSEChunkEncoder.encode(confirmation_event)
                                    except (ValueError, TypeError):
                                        pass

                                # 追加 tool 消息
                                messages.append(ChatMessage(
                                    role="tool",
                                    content=result.output if result.success else _("tool.error.prefix", error=result.error),
                                    tool_call_id=tc_id,
                                ))

                            # 有确认请求时中断多轮循环，等待用户点击确认按钮
                            if has_confirmation:
                                break

                            # 检查 LLM 是否还有更多 tool_calls（多轮）
                            if _round < MAX_TOOL_CALL_ROUNDS - 1:
                                peek_response = await self._call_llm(
                                    agent=agent,
                                    messages=messages,
                                    tools=tools,
                                    tenant_id=request.tenant_id,
                                    user_id=request.user_id,
                                )
                                total_tokens += peek_response.total_tokens or 0
                                if peek_response.tool_calls:
                                    current_response = peek_response
                                    continue
                                # peek_response 已包含最终回复（无更多工具调用）
                                # 直接使用其内容，避免重复调用 LLM 且防止模型泄漏内部 token
                                peek_content = peek_response.message.content or ""
                                if peek_content:
                                    peek_content = _strip_model_fc_tokens(peek_content).strip()
                                if peek_content:
                                    output = peek_content
                                    yield SSEChunkEncoder.encode({
                                        "event": "message",
                                        "delta": output,
                                    })
                                    break
                            # 无更多 tool_calls，跳出循环
                            break

                        # 最终回复兜底：仅在 peek_response 无内容且无待确认时流式推送
                        if not output and not has_confirmation:
                            async for chunk in self._stream_llm_chunks(
                                agent=agent,
                                messages=messages,
                                tenant_id=request.tenant_id,
                            ):
                                if chunk.delta:
                                    cleaned = _strip_model_fc_tokens(chunk.delta)
                                    if cleaned:
                                        output += cleaned
                                        yield SSEChunkEncoder.encode({
                                            "event": "message",
                                            "delta": cleaned,
                                        })
                                if chunk.total_tokens is not None:
                                    total_tokens += chunk.total_tokens
                                if chunk.finish_reason is not None:
                                    break
                    else:
                        # LLM 未调用工具，直接输出（已是非流式结果）
                        output = _strip_model_fc_tokens(
                            response.message.content or "",
                        ).strip()
                        if output:
                            yield SSEChunkEncoder.encode({
                                "event": "message",
                                "delta": output,
                            })

                    messages.append(ChatMessage(role="assistant", content=output))

                else:
                    # ---- 无工具：真实流式推送 ----
                    async for chunk in self._stream_llm_chunks(
                        agent=agent,
                        messages=messages,
                        tenant_id=request.tenant_id,
                    ):
                        if chunk.delta:
                            output += chunk.delta
                            yield SSEChunkEncoder.encode({
                                "event": "message",
                                "delta": chunk.delta,
                            })

                        # 累计 token（最后一个 chunk 包含完整统计）
                        if chunk.total_tokens is not None:
                            total_tokens = chunk.total_tokens

                        if chunk.finish_reason is not None:
                            break

                    messages.append(ChatMessage(role="assistant", content=output))

                # ---- 发送 RAG 引用来源事件 ----
                if rag_sources:
                    yield SSEChunkEncoder.encode({
                        "event": "rag_sources",
                        "sources": rag_sources,
                    })

                # ---- 发送完成事件 ----
                duration_ms = int((time.perf_counter() - start) * 1000)

                yield SSEChunkEncoder.encode({
                    "event": "done",
                    "conversation_id": request.conversation_id,
                    "total_tokens": total_tokens,
                    "duration_ms": duration_ms,
                })
                yield SSEChunkEncoder.done()

                # 构建结果并调用回调
                result = ExecutionResult(
                    success=True,
                    output=output,
                    messages=self._messages_to_dicts(messages),
                    tool_results=all_tool_results,
                    total_tokens=total_tokens,
                    duration_ms=duration_ms,
                    conversation_id=request.conversation_id,
                )

                if on_complete:
                    await on_complete(result)

            except Exception as exc:
                logger.error(
                    "Stream execution failed: agent=%d error=%s",
                    agent.id,
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

                # 异常路径也触发回调，确保上层可执行状态清理/持久化
                if on_complete:
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    failed_result = ExecutionResult(
                        success=False,
                        error=str(exc),
                        duration_ms=duration_ms,
                        conversation_id=request.conversation_id,
                    )
                    try:
                        await on_complete(failed_result)
                    except Exception as cb_exc:
                        logger.error(
                            "on_complete callback error: %s",
                            str(cb_exc),
                        )

            except BaseException as exc:
                # 捕获 CancelledError / GeneratorExit 等非 Exception 异常
                logger.error(
                    "Stream BaseException: agent=%d type=%s error=%s",
                    agent.id, type(exc).__name__, str(exc),
                    exc_info=True,
                )
                if on_complete:
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    try:
                        await on_complete(ExecutionResult(
                            success=False,
                            error=f"{type(exc).__name__}: {exc}",
                            duration_ms=duration_ms,
                            conversation_id=request.conversation_id,
                        ))
                    except Exception:
                        pass
                raise  # 必须重新抛出 BaseException

        return StreamingResponse(
            _sse_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ========================================
    # 内部方法：流式 LLM 调用
    # ========================================

    async def _stream_llm_chunks(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        tenant_id: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """
        通过 adapter 获取流式 ChatChunk（含限流/配额/计量保护）

        使用 adapter 实现真实流式推送，但在流前后执行 gateway 级别的
        限流检查、配额检查和用量计量，确保与非流式路径一致的安全保障。

        Args:
            agent: 智能体
            messages: 消息列表
            tenant_id: 租户 ID（用于获取 API Key）

        Yields:
            ChatChunk
        """
        model_obj = agent.model
        provider_code = (
            model_obj.provider.code if model_obj and model_obj.provider else ""
        )
        model_code = model_obj.code if model_obj else ""

        # 非视觉模型：移除图片附件，避免 API 报错
        if model_obj and not model_obj.supports_vision:
            for msg in messages:
                if msg.attachments:
                    msg.attachments = [
                        a for a in msg.attachments if a.get("type") != "image"
                    ]
                    if not msg.attachments:
                        msg.attachments = None

        # 通过 gateway 获取 provider 和 API Key
        provider, api_key = await self.gateway.get_provider_and_key(
            provider_code, tenant_id,
        )
        ai_model = model_obj

        # 限流 + 配额检查（复用 gateway 统一方法）
        estimated_input = 0
        if tenant_id and ai_model:
            estimated_input = TokenCounter.count_messages_tokens(
                messages_to_dicts(messages)
            )
            await self.gateway._check_rate_and_quota(
                tenant_id, ai_model.id, ai_model, estimated_input,
            )

        adapter = AdapterRegistry.create_adapter(
            provider_type=provider.type,
            api_key=api_key.decrypt_key(),
            base_url=provider.base_url,
        )

        total_tokens = 0
        input_tokens = 0
        output_tokens = 0
        async for chunk in adapter.stream_chat(
            messages=messages,
            model=model_code,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            top_p=agent.top_p or 1.0,
        ):
            if chunk.total_tokens is not None:
                total_tokens = chunk.total_tokens
            if chunk.input_tokens is not None:
                input_tokens = chunk.input_tokens
            if chunk.output_tokens is not None:
                output_tokens = chunk.output_tokens
            yield chunk

        # 流结束后：调整 TPM 和配额（复用 gateway 统一方法）
        if tenant_id and ai_model and estimated_input > 0:
            cost = CostCalculator.calculate_cost(ai_model, input_tokens, output_tokens)
            await self.gateway._record_usage_and_adjust(
                tenant_id=tenant_id,
                model_id=ai_model.id,
                request_type=RequestTypeEnum.CHAT.value,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost=cost,
                estimated_input=estimated_input,
                latency_ms=0,
            )


__all__ = ["ConversationEngine"]
