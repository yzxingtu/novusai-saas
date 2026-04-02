# Phase 4: 流式异常处理和错误消息持久化

## 目标

在流式响应过程中捕获异常，向用户返回友好的错误提示，并将失败消息持久化到数据库。

## 背景

Phase 3 已完成 call_type 字段添加，现在需要处理对话 618 暴露的核心问题：
- Responses API 失败后 fallback 到 chat.completions
- fallback 后的流式响应可能抛出异常
- 异常未被捕获，导致响应中断
- 用户看不到任何错误提示
- 对话记录中没有失败消息

## 核心改动

### 1. 流式异常捕获（StreamExecutionHandler）

**文件**: `backend/app/ai/engine/stream_handler.py`

**改动点**:
- 在 `_stream_generator` 中增加异常捕获
- 捕获所有流式响应异常
- 生成用户友好的错误事件
- 记录详细错误日志

### 2. 错误消息持久化（AgentChatService）

**文件**: `backend/app/services/ai/agent_chat_service.py`

**改动点**:
- 在 `stream_chat` 的流式回调中捕获异常
- 保存错误消息到 ConversationMessage
- 更新对话状态为 failed
- 记录失败原因到 metadata

### 3. 错误事件格式（SSE）

**新增事件类型**: `error`

**格式**:
```json
{
  "event": "error",
  "data": {
    "error_code": "stream_failed",
    "message": "抱歉，AI 服务暂时不可用，请稍后重试。",
    "details": "Fallback stream failed after Responses API error"
  }
}
```

## 实施步骤

### Step 1: 增强 StreamExecutionHandler 异常处理

**文件**: `backend/app/ai/engine/stream_handler.py`

**修改内容**:

```python
# 在 _stream_generator 方法中增加异常捕获
async def _stream_generator(...):
    try:
        # 现有流式逻辑
        async for chunk in stream:
            # ... 处理 chunk
            yield event_data
    
    except Exception as stream_error:
        # 记录详细错误
        logger.error(
            "Stream execution failed: conversation_id={} error={}",
            conversation_id,
            str(stream_error),
            exc_info=True,
        )
        
        # 生成用户友好的错误事件
        error_message = _("ai.stream.error.service_unavailable")
        error_event = {
            "event": "error",
            "data": json.dumps({
                "error_code": "stream_failed",
                "message": error_message,
                "conversation_id": conversation_id,
            }, ensure_ascii=False),
        }
        yield f"event: error\ndata: {error_event['data']}\n\n"
        
        # 重新抛出异常，让上层处理持久化
        raise
```

### Step 2: 在 AgentChatService 中持久化错误消息

**文件**: `backend/app/services/ai/agent_chat_service.py`

**修改内容**:

在 `stream_chat` 方法中，包装 engine.stream_execute 调用：

```python
async def stream_chat(...):
    # ... 现有代码 ...
    
    # 包装流式执行，捕获异常
    try:
        return await self._stream_with_error_handling(
            engine=engine,
            request=request,
            conversation=conversation,
            agent=agent,
            # ... 其他参数
        )
    except Exception as e:
        # 保存错误消息
        await self._save_error_message(
            conversation_id=conversation.id,
            error=e,
            user_message=first_message,
        )
        raise

async def _stream_with_error_handling(
    self,
    engine: BaseEngine,
    request: ExecutionRequest,
    conversation: Any,
    agent: Any,
    # ... 其他参数
) -> StreamingResponse:
    """包装流式执行，捕获异常并持久化错误"""
    
    async def error_aware_generator():
        try:
            async for event in engine.stream_execute(agent, request):
                yield event
        except Exception as stream_error:
            # 记录错误
            logger.error(
                "Stream failed for conversation_id={}: {}",
                conversation.id,
                str(stream_error),
                exc_info=True,
            )
            
            # 保存错误消息（在独立 session 中）
            await self._save_error_message_async(
                conversation_id=conversation.id,
                error=stream_error,
                user_message=request.messages[-1].content if request.messages else "",
            )
            
            # 生成错误事件
            error_message = _("ai.stream.error.service_unavailable")
            error_data = json.dumps({
                "error_code": "stream_failed",
                "message": error_message,
                "conversation_id": conversation.id,
            }, ensure_ascii=False)
            yield f"event: error\ndata: {error_data}\n\n"
            yield "event: done\ndata: [DONE]\n\n"
    
    return StreamingResponse(
        error_aware_generator(),
        media_type="text/event-stream",
    )

async def _save_error_message(
    self,
    conversation_id: int,
    error: Exception,
    user_message: str,
) -> None:
    """保存错误消息到数据库（同步版本）"""
    from app.models.ai.conversation import ConversationMessage
    from app.enums.agent import MessageRoleEnum
    
    # 创建错误消息
    error_msg = ConversationMessage(
        conversation_id=conversation_id,
        role=MessageRoleEnum.ASSISTANT.value,
        content=_("ai.stream.error.service_unavailable"),
        metadata_={
            "error": True,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "user_message": user_message[:200],  # 截断避免过长
        },
    )
    self.db.add(error_msg)
    
    # 更新对话状态
    conversation = await self.conversation_svc.get_by_id(conversation_id)
    if conversation:
        conversation.metadata_ = conversation.metadata_ or {}
        conversation.metadata_["last_error"] = {
            "timestamp": time.time(),
            "error_type": type(error).__name__,
            "error_message": str(error)[:500],
        }
    
    await self.db.commit()

async def _save_error_message_async(
    self,
    conversation_id: int,
    error: Exception,
    user_message: str,
) -> None:
    """保存错误消息（异步版本，使用独立 session）"""
    async with async_session_factory() as session:
        service = AgentChatService(session, self.tenant_id)
        await service._save_error_message(
            conversation_id=conversation_id,
            error=error,
            user_message=user_message,
        )
```

### Step 3: 添加国际化文本

**文件**: `backend/app/locales/zh_CN.json`

```json
{
  "ai.stream.error.service_unavailable": "抱歉，AI 服务暂时不可用，请稍后重试。",
  "ai.stream.error.fallback_failed": "AI 服务响应失败，请稍后重试。"
}
```

**文件**: `backend/app/locales/en_US.json`

```json
{
  "ai.stream.error.service_unavailable": "Sorry, AI service is temporarily unavailable. Please try again later.",
  "ai.stream.error.fallback_failed": "AI service response failed. Please try again later."
}
```

### Step 4: 编写单元测试

**文件**: `backend/tests/services/test_agent_chat_stream_error.py`

```python
"""测试流式响应异常处理"""
import pytest
from unittest.mock import AsyncMock, patch
from app.services.ai.agent_chat_service import AgentChatService
from app.enums.agent import MessageRoleEnum

@pytest.mark.asyncio
async def test_stream_chat_handles_exception(db_session, test_agent, test_user):
    """测试流式响应异常被正确捕获和持久化"""
    service = AgentChatService(db_session, test_agent.tenant_id)
    
    # Mock engine.stream_execute 抛出异常
    with patch.object(
        ConversationEngine,
        'stream_execute',
        side_effect=Exception("Upstream API failed"),
    ):
        # 调用 stream_chat
        response = await service.stream_chat(
            agent_id=test_agent.id,
            message="test message",
            user_id=test_user.id,
        )
        
        # 读取流式响应
        events = []
        async for event in response.body_iterator:
            events.append(event.decode())
        
        # 验证包含错误事件
        error_events = [e for e in events if 'event: error' in e]
        assert len(error_events) > 0
        assert 'stream_failed' in error_events[0]
        
        # 验证错误消息已保存
        from app.repositories.ai.conversation_repository import ConversationRepository
        conv_repo = ConversationRepository(db_session, test_agent.tenant_id)
        messages = await conv_repo.get_conversation_messages(conversation_id=...)
        
        error_messages = [m for m in messages if m.metadata_.get('error')]
        assert len(error_messages) == 1
        assert error_messages[0].role == MessageRoleEnum.ASSISTANT.value
        assert '暂时不可用' in error_messages[0].content

@pytest.mark.asyncio
async def test_stream_chat_error_metadata(db_session, test_agent, test_user):
    """测试错误元数据正确记录"""
    service = AgentChatService(db_session, test_agent.tenant_id)
    
    with patch.object(
        ConversationEngine,
        'stream_execute',
        side_effect=ValueError("Invalid model response"),
    ):
        await service.stream_chat(
            agent_id=test_agent.id,
            message="test",
            user_id=test_user.id,
        )
        
        # 验证对话 metadata 包含错误信息
        conversation = await service.conversation_svc.get_by_id(...)
        assert 'last_error' in conversation.metadata_
        assert conversation.metadata_['last_error']['error_type'] == 'ValueError'
        assert 'Invalid model response' in conversation.metadata_['last_error']['error_message']
```

### Step 5: 集成测试

**文件**: `backend/tests/integration/test_stream_error_e2e.py`

```python
"""端到端测试流式错误处理"""
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_stream_error_e2e(async_client: AsyncClient, test_agent, auth_headers):
    """端到端测试：模拟上游 API 失败，验证用户收到错误提示"""
    
    # Mock 上游 API 失败
    with patch('app.ai.adapters.openai_adapter.OpenAIAdapter.stream_chat') as mock_stream:
        mock_stream.side_effect = Exception("502 Bad Gateway")
        
        # 发起流式请求
        response = await async_client.post(
            f"/api/tenant/ai/agent-chat/{test_agent.id}/chat/stream",
            json={"message": "test"},
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        
        # 读取 SSE 流
        events = []
        async for line in response.aiter_lines():
            if line:
                events.append(line)
        
        # 验证包含错误事件
        error_events = [e for e in events if 'event: error' in e]
        assert len(error_events) > 0
        
        # 验证错误消息格式
        import json
        for event in error_events:
            if event.startswith('data: '):
                data = json.loads(event[6:])
                assert 'error_code' in data
                assert 'message' in data
                assert data['error_code'] == 'stream_failed'
```

### Step 6: 更新前端错误处理

**文件**: `frontend/src/services/ai/chatService.ts`

```typescript
// 处理 SSE 错误事件
eventSource.addEventListener('error', (event) => {
  const data = JSON.parse(event.data);
  
  if (data.error_code === 'stream_failed') {
    // 显示用户友好的错误提示
    showErrorNotification(data.message);
    
    // 在对话界面显示错误消息
    addMessageToConversation({
      role: 'assistant',
      content: data.message,
      isError: true,
    });
  }
});
```

## 验收清单

- [ ] StreamExecutionHandler 正确捕获流式异常
- [ ] 异常时生成 error 事件
- [ ] 错误消息保存到 ConversationMessage
- [ ] 对话 metadata 记录错误信息
- [ ] 国际化文本已添加（中英文）
- [ ] 单元测试覆盖异常场景
- [ ] 集成测试验证端到端流程
- [ ] 前端正确显示错误提示
- [ ] 错误日志包含足够的调试信息
- [ ] 对话 618 场景可以正确处理
- [ ] 所有测试通过

## 注意事项

1. **独立 Session**: 错误消息持久化使用独立 session，避免影响主流程
2. **异常传播**: 捕获异常后仍需向上传播，确保上层感知失败
3. **用户体验**: 错误提示要友好，不暴露技术细节
4. **日志记录**: 详细记录错误堆栈，便于排查
5. **幂等性**: 错误消息保存要考虑重试场景，避免重复

## 预计时间

2-3 小时（包含测试验证）

## 相关文件

- `backend/app/ai/engine/stream_handler.py` - 流式处理器
- `backend/app/services/ai/agent_chat_service.py` - 对话服务
- `backend/app/locales/*.json` - 国际化文本
- `backend/tests/services/test_agent_chat_stream_error.py` - 单元测试
- `backend/tests/integration/test_stream_error_e2e.py` - 集成测试
- `frontend/src/services/ai/chatService.ts` - 前端服务
