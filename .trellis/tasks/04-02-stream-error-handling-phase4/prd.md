# Stream Error Handling Phase 4

## Purpose

实施对话 618 问题修复的 Phase 4：在流式响应过程中捕获异常，向用户返回友好的错误提示，并将失败消息持久化到数据库。

## Current State

**父任务**: `04-02-conversation-618-diagnosis`  
**Phase 3 状态**: 已完成（call_type 字段已添加，main_chat/internal_memory/internal_tool 枚举就绪）  
**当前问题**: 对话 618 中 Responses API 失败后 fallback 到 chat.completions，流式响应异常未被捕获，用户看不到错误提示，对话记录中没有失败消息

**状态更新（2026-04-02）**:
- 代码实现已完成：`AgentChatService.stream_chat` 在失败且没有新消息时会持久化一条面向用户的错误 assistant 消息
- 联动修复已完成：`ConversationService.persist_chat_messages()` 现在会返回“实际持久化消息数”，避免 sanitize 之后没有真正落库消息时漏掉错误兜底
- 国际化文案已完成：`ai.stream.error.service_unavailable` 与 `ai.stream.error.fallback_failed` 已写入真实 locale 文件
- 自动化验证已完成：新增 5 个单元测试，相关回归测试、`ruff check` 和 locale JSON 校验均已通过
- 手动端到端复现仍待完成：当前尚未在真实上游 502 场景下重新跑通 Agent 59 / Conversation 618 类似链路

**已确认的执行流程**（来自 Phase 1-3 分析）:
1. Responses API 上游故障 (502)
2. Fallback 到 chat.completions
3. 流式响应中断，没有后续日志
4. 用户看不到任何回复或错误提示

## Goals

### Goal 1: 验证现有异常处理机制
确认 StreamExecutionHandler 的异常捕获是否完整

### Goal 2: 实现错误消息持久化
在 AgentChatService 的 on_complete 回调中保存错误消息到数据库

### Goal 3: 添加用户友好的错误提示
通过国际化文本提供中英文错误提示

### Goal 4: 完善测试覆盖
编写单元测试和集成测试，验证异常场景

## Findings

### Finding 1: StreamExecutionHandler 已有完整异常处理

**位置**: `backend/app/ai/engine/stream_handler.py:365-445`

**现有机制**:
- ✅ `except Exception as exc` 捕获所有流式异常
- ✅ `build_error_event` 生成用户友好的错误事件
- ✅ `_schedule_on_complete(failed_result)` 传递失败结果给回调
- ✅ 错误事件包含 `conversation_id`
- ✅ 部分输出会被保存（partial persist）

**结论**: StreamExecutionHandler 的异常处理已经完整，无需修改。

### Finding 2: AgentChatService 缺少错误消息持久化

**位置**: `backend/app/services/ai/agent_chat_service.py:944+`

**问题**:
- `on_complete` 回调只处理成功场景
- 失败时（`result.success == False`）没有保存错误消息
- 对话 metadata 没有记录错误信息

**需要补充**:
1. 在 `on_complete` 回调中检查 `result.success`
2. 失败时创建 ConversationMessage（role=assistant, metadata.error=True）
3. 更新 Conversation.metadata_ 记录错误信息

### Finding 3: 缺少国际化错误文本

**问题**:
- 当前使用通用的 `common.server_error`
- 没有针对流式异常的专用错误提示

**需要添加**:
- `ai.stream.error.service_unavailable`: "抱歉，AI 服务暂时不可用，请稍后重试。"
- `ai.stream.error.fallback_failed`: "AI 服务响应失败，请稍后重试。"

## Solution Design

### Solution 1: 在 AgentChatService 中持久化错误消息

**文件**: `backend/app/services/ai/agent_chat_service.py`

**修改点**:

1. 在 `stream_chat` 方法的 `_on_stream_complete` 回调中添加失败检查：

```python
async def _on_stream_complete(result: ExecutionResult) -> dict[str, Any] | None:
    """流式完成回调：保存消息、更新统计、触发记忆提取"""
    
    # 如果执行失败，保存错误消息
    if not result.success:
        await _save_error_message_to_conversation(
            conversation_id=conversation.id,
            error_text=result.error or _("ai.stream.error.service_unavailable"),
            user_message=first_message,
            result=result,
        )
        return None
    
    # 原有的成功逻辑
    # ... 保存用户消息和助手消息 ...
```

2. 添加辅助方法 `_save_error_message_to_conversation`：

```python
async def _save_error_message_to_conversation(
    conversation_id: int,
    error_text: str,
    user_message: str,
    result: ExecutionResult,
) -> None:
    """保存错误消息到对话"""
    from app.models.ai.conversation import ConversationMessage
    from app.enums.agent import MessageRoleEnum
    
    # 创建错误消息
    error_msg = ConversationMessage(
        conversation_id=conversation_id,
        role=MessageRoleEnum.ASSISTANT.value,
        content=error_text,
        metadata_={
            "error": True,
            "error_type": "stream_execution_error",
            "partial_output": result.output or "",
            "total_tokens": result.total_tokens or 0,
            "user_message_preview": user_message[:200],
        },
    )
    self.db.add(error_msg)
    
    # 更新对话 metadata
    conversation = await self.conversation_svc.get_by_id(conversation_id)
    if conversation:
        conversation.metadata_ = conversation.metadata_ or {}
        conversation.metadata_["last_error"] = {
            "timestamp": time.time(),
            "error_type": "stream_execution_error",
            "error_message": (result.error or "")[:500],
        }
    
    await self.db.commit()
```

### Solution 2: 添加国际化文本

**文件**: `backend/app/locales/zh_CN.json`

```json
{
  "ai": {
    "stream": {
      "error": {
        "service_unavailable": "抱歉，AI 服务暂时不可用，请稍后重试。",
        "fallback_failed": "AI 服务响应失败，请稍后重试。"
      }
    }
  }
}
```

**文件**: `backend/app/locales/en_US.json`

```json
{
  "ai": {
    "stream": {
      "error": {
        "service_unavailable": "Sorry, AI service is temporarily unavailable. Please try again later.",
        "fallback_failed": "AI service response failed. Please try again later."
      }
    }
  }
}
```

### Solution 3: 编写单元测试

**文件**: `backend/tests/services/test_agent_chat_stream_error.py`

**测试用例**:
1. `test_stream_error_saves_message`: 验证错误消息保存
2. `test_stream_error_updates_conversation_metadata`: 验证对话 metadata 更新
3. `test_stream_error_with_partial_output`: 验证部分输出被保存

## Implementation Plan

### Phase 1: 代码实现 (1.5 小时)

**任务 1.1**: 修改 AgentChatService
- 在 `_on_stream_complete` 回调中添加失败检查
- 实现 `_save_error_message_to_conversation` 方法
- 确保在正确的位置调用

**任务 1.2**: 添加国际化文本
- 更新 `zh_CN.json`
- 更新 `en_US.json`
- 验证 JSON 格式正确

### Phase 2: 测试实现 (1 小时)

**任务 2.1**: 编写单元测试
- 创建 `test_agent_chat_stream_error.py`
- 实现 3 个测试用例
- Mock 流式执行失败场景

**任务 2.2**: 运行测试
- 执行新增测试
- 执行现有相关测试
- 确保没有破坏现有功能

### Phase 3: 验证和文档 (0.5 小时)

**任务 3.1**: 代码检查
- 运行 ruff check
- 修复代码风格问题

**任务 3.2**: 手动验证
- 使用 Agent 59 重现对话 618 场景
- 验证错误提示和消息保存
- 使用 CLI 查看对话记录

**任务 3.3**: 更新文档
- 在父任务 PRD 中标记 Phase 4 完成
- 记录验证结果

## Acceptance Criteria

- [x] AgentChatService 中添加了错误消息持久化逻辑
- [x] `_save_error_message_to_conversation` 方法已实现
- [x] 国际化文本已添加（中英文）
- [x] 单元测试已编写（至少 3 个用例）
- [x] 所有测试通过（新增 + 现有）
- [x] 代码检查通过（ruff）
- [ ] 手动验证对话 618 场景成功
- [x] 错误消息格式符合前端需求
- [x] 对话 metadata 正确记录错误信息
- [x] 日志包含足够的调试信息
- [x] 父任务 PRD 已更新

## Risks

### Risk 1: 回调时机不确定
**影响**: 中  
**概率**: 低  
**缓解**: 仔细阅读 StreamExecutionHandler 代码，确认 on_complete 调用时机

### Risk 2: 数据库事务问题
**影响**: 中  
**概率**: 低  
**缓解**: 在回调中使用当前 session，确保 commit 正确

### Risk 3: 测试 Mock 复杂
**影响**: 低  
**概率**: 中  
**缓解**: 参考现有测试，使用简单的 Mock 策略

## Dependencies

- Phase 3 已完成（call_type 字段）
- StreamExecutionHandler 现有异常处理机制
- ConversationService 和 ConversationMessage 模型

## Output

- 修改的代码文件：
  - `backend/app/services/ai/agent_chat_service.py`
  - `backend/app/services/ai/conversation_service.py`
  - `backend/app/locales/zh_CN/messages.json`
  - `backend/app/locales/en/messages.json`

- 新增的测试文件：
  - `backend/tests/services/test_agent_chat_stream_error.py`

- 测试结果：
  - `pytest tests/services/test_agent_chat_stream_error.py -v` -> 5 passed
  - `pytest tests/services/test_agent_chat_service_memory_scene.py -k "stream_chat" -v` -> 1 passed
  - `pytest tests/services/test_agent_chat_stream_error.py tests/services/test_agent_chat_service_memory_scene.py tests/services/test_agent_chat_page_context.py tests/services/test_conversation_service.py -k "stream_on_complete or stream_chat or persist_chat_messages or agent_chat_service_injects_page_context" -q` -> 15 passed
  - `ruff check app/services/ai/agent_chat_service.py app/services/ai/conversation_service.py tests/services/test_agent_chat_stream_error.py tests/services/test_agent_chat_service_memory_scene.py` -> passed
  - locale JSON 校验 -> passed
  - 手动验证结果 -> pending（需要可控地复现真实上游 502 / fallback 失败场景）

- 更新的文档：
  - 父任务 PRD Phase 4 状态

## Related Documents

- 父任务 PRD: `.trellis/tasks/04-02-conversation-618-diagnosis/prd.md`
- Phase 3 实施: `.trellis/tasks/04-02-conversation-618-diagnosis/phase3-ai-prompt.md`
- 对话 618 分析: `docs/conversation-618-issue-analysis.md`

## Notes

- StreamExecutionHandler 的异常处理已经完整，本任务只需补充持久化逻辑
- 错误消息保存在 on_complete 回调中，使用当前 session
- 国际化文本要简洁友好，不暴露技术细节
- 测试要覆盖失败场景，确保错误消息正确保存
