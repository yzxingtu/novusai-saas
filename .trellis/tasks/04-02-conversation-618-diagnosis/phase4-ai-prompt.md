# Phase 4 执行提示词：流式异常处理和错误消息持久化

## 任务目标

为对话 618 问题实施 Phase 4 修复：在流式响应过程中捕获异常，向用户返回友好的错误提示，并将失败消息持久化到数据库。

## 背景信息

**项目**: NovusAI SaaS 平台  
**当前任务**: `.trellis/tasks/04-02-conversation-618-diagnosis`  
**Phase 3 状态**: 已完成（call_type 字段已添加）  
**核心问题**: 对话 618 中 Responses API 失败后 fallback 到 chat.completions，流式响应异常未被捕获，用户看不到错误提示

## 核心改动概述

1. **StreamExecutionHandler**: 已有异常处理，需验证是否完整
2. **AgentChatService**: 需在 stream_chat 中增加错误消息持久化
3. **国际化文本**: 添加错误提示文本
4. **单元测试**: 覆盖流式异常场景
5. **集成测试**: 端到端验证

## 执行步骤

### Step 1: 验证 StreamExecutionHandler 异常处理

**文件**: `backend/app/ai/engine/stream_handler.py`

**任务**:
1. 读取 `stream_handler.py` 第 365-445 行（异常处理部分）
2. 确认以下内容：
   - 是否捕获了所有流式异常
   - 是否生成了用户友好的错误事件
   - 是否调用了 `on_complete` 回调传递失败结果
   - 错误事件格式是否符合前端需求

**验证点**:
- ✅ 已有 `except Exception as exc` 捕获
- ✅ 已有 `build_error_event` 生成错误事件
- ✅ 已有 `_schedule_on_complete(failed_result)` 传递失败结果
- ✅ 错误事件包含 `conversation_id`

**结论**: StreamExecutionHandler 的异常处理已经完整，无需修改。

### Step 2: 在 AgentChatService 中持久化错误消息

**文件**: `backend/app/services/ai/agent_chat_service.py`

**当前状态**:
- `stream_chat` 方法在第 944 行
- 调用 `engine.stream_execute` 返回 StreamingResponse
- 使用 `on_complete` 回调保存成功消息

**需要添加的代码**:

在 `stream_chat` 方法中，找到 `on_complete` 回调定义的位置（约 1100-1200 行），修改回调逻辑：

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

**新增辅助方法**:

```python
async def _save_error_message_to_conversation(
    conversation_id: int,
    error_text: str,
    user_message: str,
    result: ExecutionResult,
) -> None:
    """保存错误消息到对话（在 on_complete 回调中调用）"""
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
    logger.info(
        "Error message saved for conversation_id={} error={}",
        conversation_id,
        error_text[:100],
    )
```

**修改位置**:
- 在 `stream_chat` 方法内部，找到 `async def _on_stream_complete` 的定义
- 在该回调的开头添加失败检查和错误消息保存逻辑
- 在 `AgentChatService` 类中添加 `_save_error_message_to_conversation` 辅助方法

### Step 3: 添加国际化文本

**文件**: `backend/app/locales/zh_CN.json`

在 `ai` 部分添加：

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

### Step 4: 编写单元测试

**文件**: `backend/tests/services/test_agent_chat_stream_error.py`

```python
"""测试流式响应异常处理和错误消息持久化"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.ai.agent_chat_service import AgentChatService
from app.ai.engine.types import ExecutionResult
from app.enums.agent import MessageRoleEnum, AgentStatusEnum
from app.models.ai.agent import Agent
from app.models.ai.conversation import AgentConversation


@pytest.fixture
def test_agent(db_session):
    """创建测试智能体"""
    agent = Agent(
        id=1,
        tenant_id=1,
        name="Test Agent",
        status=AgentStatusEnum.PUBLISHED.value,
        quota_config={},
    )
    db_session.add(agent)
    return agent


@pytest.mark.asyncio
async def test_stream_error_saves_message(db_session, test_agent):
    """测试流式异常时保存错误消息"""
    service = AgentChatService(db_session, test_agent.tenant_id)
    
    # Mock engine.stream_execute 返回失败结果
    failed_result = ExecutionResult(
        success=False,
        error="Upstream API failed",
        output="",
        messages=[],
        total_tokens=0,
        duration_ms=1000,
        conversation_id=1,
    )
    
    # Mock _on_stream_complete 回调
    with patch.object(service, '_validate_agent', return_value=test_agent):
        with patch('app.ai.engine.dispatcher.ExecutionDispatcher.stream_execute') as mock_stream:
            # 模拟流式执行失败
            async def mock_generator():
                yield 'event: error\ndata: {"error_code": "stream_failed"}\n\n'
                # 触发 on_complete 回调
                # 注意：实际实现中 on_complete 会在 StreamExecutionHandler 中调用
            
            mock_stream.return_value = mock_generator()
            
            # 调用 stream_chat
            response = await service.stream_chat(
                agent_id=test_agent.id,
                message="test message",
                user_id=1,
            )
            
            # 读取流式响应（触发回调）
            events = []
            async for event in response.body_iterator:
                events.append(event.decode())
            
            # 验证错误消息已保存
            from app.repositories.ai.conversation_repository import ConversationRepository
            conv_repo = ConversationRepository(db_session, test_agent.tenant_id)
            
            # 查找对话
            conversations = await conv_repo.query_list(
                spec=MagicMock(page=1, size=10, filters=[], sorts=[]),
                forced_filters=[],
            )
            
            if conversations[1] > 0:
                conversation_id = conversations[0][0].id
                messages = await conv_repo.get_conversation_messages(conversation_id)
                
                # 验证有错误消息
                error_messages = [m for m in messages if m.metadata_.get('error')]
                assert len(error_messages) == 1
                assert error_messages[0].role == MessageRoleEnum.ASSISTANT.value
                assert '暂时不可用' in error_messages[0].content or 'unavailable' in error_messages[0].content


@pytest.mark.asyncio
async def test_stream_error_updates_conversation_metadata(db_session, test_agent):
    """测试流式异常时更新对话 metadata"""
    service = AgentChatService(db_session, test_agent.tenant_id)
    
    # 类似上面的测试，验证 conversation.metadata_['last_error'] 被正确设置
    # ... 实现细节 ...
```

### Step 5: 运行测试验证

**命令**:

```bash
# 运行新增的单元测试
pytest backend/tests/services/test_agent_chat_stream_error.py -v

# 运行相关的现有测试，确保没有破坏
pytest backend/tests/services/test_agent_chat_service.py -v
pytest backend/tests/ai/engine/test_stream_handler.py -v

# 代码检查
ruff check backend/app/services/ai/agent_chat_service.py
ruff check backend/app/ai/engine/stream_handler.py
```

### Step 6: 手动验证对话 618 场景

**步骤**:

1. 启动后端服务
2. 使用 Agent 59（猫娘智能体）
3. 发送消息："通过页面感知能力添加一个测试的智能体 具体里面的内容你来决定"
4. 观察流式响应
5. 验证：
   - 如果上游 API 失败，用户看到友好的错误提示
   - 对话记录中保存了错误消息
   - 对话 metadata 包含错误信息

**验证命令**:

```bash
# 查看对话消息
python -m app.cli ai conversation show <conversation_id>

# 查看调用日志
python -m app.cli ai call-log show <call_log_id>
```

## 验收清单

- [ ] StreamExecutionHandler 异常处理已验证完整
- [ ] AgentChatService 中添加了错误消息持久化逻辑
- [ ] `_save_error_message_to_conversation` 方法已实现
- [ ] 国际化文本已添加（中英文）
- [ ] 单元测试已编写并通过
- [ ] 现有测试没有被破坏
- [ ] 代码检查通过（ruff）
- [ ] 手动验证对话 618 场景成功
- [ ] 错误消息格式符合前端需求
- [ ] 对话 metadata 正确记录错误信息
- [ ] 日志包含足够的调试信息

## 注意事项

1. **回调时机**: `on_complete` 回调在 StreamExecutionHandler 中调用，无论成功或失败都会触发
2. **数据库事务**: 错误消息保存在 `on_complete` 回调中，使用当前 session，需要 commit
3. **幂等性**: 如果回调被多次调用，需要避免重复保存错误消息
4. **用户体验**: 错误提示要友好，不暴露技术细节
5. **日志记录**: 详细记录错误堆栈，便于排查

## 预计时间

2-3 小时（包含测试验证）

## 输出要求

完成后提交以下内容：

1. 修改的代码文件：
   - `backend/app/services/ai/agent_chat_service.py`
   - `backend/app/locales/zh_CN.json`
   - `backend/app/locales/en_US.json`

2. 新增的测试文件：
   - `backend/tests/services/test_agent_chat_stream_error.py`

3. 测试结果：
   - 单元测试通过截图或日志
   - 代码检查通过确认
   - 手动验证结果（对话截图或日志）

4. 更新任务状态：
   - 在 PRD 中标记 Phase 4 为已完成
   - 记录验证结果和发现的问题

## 相关文件

- PRD: `.trellis/tasks/04-02-conversation-618-diagnosis/prd.md`
- Phase 3 实施: `.trellis/tasks/04-02-conversation-618-diagnosis/phase3-ai-prompt.md`
- 现有代码:
  - `backend/app/ai/engine/stream_handler.py` (第 365-445 行)
  - `backend/app/services/ai/agent_chat_service.py` (第 944 行起)
  - `backend/app/ai/engine/types.py` (ExecutionResult 定义)

## 问题排查

如果遇到问题：

1. **错误消息未保存**: 检查 `on_complete` 回调是否被正确调用
2. **测试失败**: 检查 Mock 是否正确模拟了流式执行失败
3. **国际化文本不生效**: 检查 JSON 格式是否正确，路径是否匹配
4. **前端未显示错误**: 检查 SSE 事件格式是否符合前端期望

## 成功标准

- 所有测试通过
- 对话 618 场景能正确处理异常
- 用户看到友好的错误提示
- 错误消息正确保存到数据库
- 代码符合 Trellis 规范和项目质量标准
