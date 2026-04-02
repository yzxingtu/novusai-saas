# AI 执行提示词：Phase 4 流式错误处理实施

你是一名后端开发工程师，负责实施对话 618 问题修复的 Phase 4。请严格按照以下步骤执行。

## 任务概述

在流式响应异常时，保存错误消息到数据库，并向用户返回友好的错误提示。

## 前置条件

1. 已阅读 `prd.md` 了解任务背景和目标
2. 已确认 Phase 3 完成（call_type 字段已添加）
3. 已确认 StreamExecutionHandler 的异常处理机制完整

## 执行步骤

### Step 1: 读取现有代码，理解结构

**目标**: 了解 AgentChatService.stream_chat 的实现和 on_complete 回调位置

**操作**:

```bash
# 读取 stream_chat 方法
Read backend/app/services/ai/agent_chat_service.py offset=944 limit=300

# 搜索 on_complete 回调定义
Grep pattern="async def _on_stream_complete" path=backend/app/services/ai/agent_chat_service.py output_mode=content -A=50
```

**理解要点**:
- `stream_chat` 方法的整体结构
- `_on_stream_complete` 回调在哪里定义
- 回调中如何保存成功消息
- 使用的 session 和 service 实例

### Step 2: 修改 on_complete 回调，添加失败检查

**目标**: 在回调开头添加失败检查，失败时保存错误消息

**操作**:

找到 `_on_stream_complete` 回调定义（约在 1100-1200 行），在开头添加：

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
        logger.warning(
            "Stream execution failed for conversation_id={}: {}",
            conversation.id,
            result.error or "Unknown error",
        )
        return None
    
    # 原有的成功逻辑继续...
```

**注意**:
- 使用 `Edit` 工具修改，不要重写整个方法
- 确保缩进正确
- 保留原有的成功逻辑

### Step 3: 添加错误消息保存方法

**目标**: 在 AgentChatService 类中添加 `_save_error_message_to_conversation` 方法

**操作**:

在 `stream_chat` 方法内部，`_on_stream_complete` 回调定义之前，添加辅助方法：

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
                    "duration_ms": result.duration_ms or 0,
                    "user_message_preview": user_message[:200] if user_message else "",
                },
            )
            self.db.add(error_msg)
            
            # 更新对话 metadata
            try:
                conv = await self.conversation_svc.get_by_id(conversation_id)
                if conv:
                    conv.metadata_ = conv.metadata_ or {}
                    conv.metadata_["last_error"] = {
                        "timestamp": time.time(),
                        "error_type": "stream_execution_error",
                        "error_message": (result.error or "")[:500],
                        "partial": result.partial,
                    }
            except Exception as meta_error:
                logger.warning(
                    "Failed to update conversation metadata: {}",
                    str(meta_error),
                )
            
            await self.db.commit()
            logger.info(
                "Error message saved for conversation_id={} error={}",
                conversation_id,
                error_text[:100],
            )
```

**注意**:
- 这是一个嵌套函数，定义在 `stream_chat` 方法内部
- 使用 `self.db` 和 `self.conversation_svc`
- 错误消息的 metadata 要包含足够的调试信息

### Step 4: 添加国际化文本

**目标**: 在中英文语言文件中添加错误提示文本

**操作 4.1**: 更新中文文本

```bash
# 读取现有文件
Read backend/app/locales/zh_CN.json

# 找到 "ai" 部分，添加 "stream" 子部分
# 如果没有 "ai" 部分，创建它
```

在 `"ai"` 对象中添加：

```json
"stream": {
  "error": {
    "service_unavailable": "抱歉，AI 服务暂时不可用，请稍后重试。",
    "fallback_failed": "AI 服务响应失败，请稍后重试。"
  }
}
```

**操作 4.2**: 更新英文文本

```bash
# 读取现有文件
Read backend/app/locales/en_US.json

# 同样在 "ai" 部分添加
```

在 `"ai"` 对象中添加：

```json
"stream": {
  "error": {
    "service_unavailable": "Sorry, AI service is temporarily unavailable. Please try again later.",
    "fallback_failed": "AI service response failed. Please try again later."
  }
}
```

**注意**:
- 确保 JSON 格式正确（逗号、括号）
- 使用 `Edit` 工具修改，保持原有结构
- 如果 `"ai"` 部分不存在，需要创建

### Step 5: 编写单元测试

**目标**: 创建测试文件，验证错误消息保存逻辑

**操作**:

创建 `backend/tests/services/test_agent_chat_stream_error.py`：

```python
"""测试流式响应异常处理和错误消息持久化"""
import pytest
import time
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.ai.agent_chat_service import AgentChatService
from app.ai.engine.types import ExecutionResult
from app.enums.agent import MessageRoleEnum, AgentStatusEnum
from app.models.ai.agent import Agent
from app.models.ai.conversation import AgentConversation, ConversationMessage


@pytest.fixture
def test_agent(db_session):
    """创建测试智能体"""
    agent = Agent(
        id=999,
        tenant_id=1,
        name="Test Agent",
        status=AgentStatusEnum.PUBLISHED.value,
        quota_config={},
        model_config={},
    )
    db_session.add(agent)
    db_session.commit()
    return agent


@pytest.fixture
def test_conversation(db_session, test_agent):
    """创建测试对话"""
    conv = AgentConversation(
        id=9999,
        tenant_id=1,
        agent_id=test_agent.id,
        user_id=1,
        owner_type="tenant_admin",
        title="Test Conversation",
    )
    db_session.add(conv)
    db_session.commit()
    return conv


@pytest.mark.asyncio
async def test_stream_error_saves_message(db_session, test_agent, test_conversation):
    """测试流式异常时保存错误消息"""
    service = AgentChatService(db_session, test_agent.tenant_id)
    
    # 模拟失败的 ExecutionResult
    failed_result = ExecutionResult(
        success=False,
        error="Upstream API failed: 502 Bad Gateway",
        output="",
        messages=[],
        total_tokens=0,
        duration_ms=1000,
        conversation_id=test_conversation.id,
        partial=True,
    )
    
    # 直接调用内部方法（模拟 on_complete 回调）
    # 注意：这需要访问 stream_chat 内部定义的方法
    # 实际测试中可能需要通过完整的 stream_chat 流程触发
    
    # 创建错误消息（模拟 _save_error_message_to_conversation 的逻辑）
    error_msg = ConversationMessage(
        conversation_id=test_conversation.id,
        role=MessageRoleEnum.ASSISTANT.value,
        content="抱歉，AI 服务暂时不可用，请稍后重试。",
        metadata_={
            "error": True,
            "error_type": "stream_execution_error",
            "partial_output": "",
            "total_tokens": 0,
        },
    )
    db_session.add(error_msg)
    
    # 更新对话 metadata
    test_conversation.metadata_ = test_conversation.metadata_ or {}
    test_conversation.metadata_["last_error"] = {
        "timestamp": time.time(),
        "error_type": "stream_execution_error",
        "error_message": failed_result.error[:500],
    }
    
    db_session.commit()
    
    # 验证错误消息已保存
    messages = db_session.query(ConversationMessage).filter_by(
        conversation_id=test_conversation.id
    ).all()
    
    error_messages = [m for m in messages if m.metadata_.get('error')]
    assert len(error_messages) == 1
    assert error_messages[0].role == MessageRoleEnum.ASSISTANT.value
    assert '暂时不可用' in error_messages[0].content
    
    # 验证对话 metadata
    db_session.refresh(test_conversation)
    assert 'last_error' in test_conversation.metadata_
    assert test_conversation.metadata_['last_error']['error_type'] == 'stream_execution_error'


@pytest.mark.asyncio
async def test_stream_error_with_partial_output(db_session, test_agent, test_conversation):
    """测试流式异常时保存部分输出"""
    # 模拟有部分输出的失败结果
    failed_result = ExecutionResult(
        success=False,
        error="Stream interrupted",
        output="这是部分输出...",
        messages=[],
        total_tokens=150,
        duration_ms=2000,
        conversation_id=test_conversation.id,
        partial=True,
    )
    
    # 创建错误消息
    error_msg = ConversationMessage(
        conversation_id=test_conversation.id,
        role=MessageRoleEnum.ASSISTANT.value,
        content="抱歉，AI 服务暂时不可用，请稍后重试。",
        metadata_={
            "error": True,
            "error_type": "stream_execution_error",
            "partial_output": failed_result.output,
            "total_tokens": failed_result.total_tokens,
        },
    )
    db_session.add(error_msg)
    db_session.commit()
    
    # 验证部分输出被保存
    db_session.refresh(error_msg)
    assert error_msg.metadata_['partial_output'] == "这是部分输出..."
    assert error_msg.metadata_['total_tokens'] == 150
```

**注意**:
- 测试需要 fixtures（test_agent, test_conversation）
- 可能需要调整测试策略，因为 `_save_error_message_to_conversation` 是嵌套函数
- 确保测试数据库隔离

### Step 6: 运行测试

**目标**: 验证新增代码和测试通过

**操作**:

```bash
# 运行新增的单元测试
Bash command="pytest backend/tests/services/test_agent_chat_stream_error.py -v"

# 运行相关的现有测试
Bash command="pytest backend/tests/services/test_agent_chat_service.py -v -k stream"

# 代码检查
Bash command="ruff check backend/app/services/ai/agent_chat_service.py"
Bash command="ruff check backend/app/locales/"
```

**预期结果**:
- 所有测试通过
- 没有 ruff 错误

### Step 7: 手动验证（可选）

**目标**: 使用 CLI 验证错误消息保存

**操作**:

```bash
# 启动后端服务（如果需要）
# 使用 Agent 59 发送测试消息
# 查看对话记录

Bash command="python -m app.cli ai conversation show <conversation_id>"
```

**验证点**:
- 对话中有错误消息（role=assistant, metadata.error=True）
- 对话 metadata 包含 last_error
- 错误提示文本友好

## 验收清单

完成后，确认以下所有项：

- [ ] `AgentChatService.stream_chat` 中的 `_on_stream_complete` 回调已修改
- [ ] 添加了失败检查（`if not result.success`）
- [ ] 实现了 `_save_error_message_to_conversation` 方法
- [ ] 国际化文本已添加（zh_CN.json 和 en_US.json）
- [ ] 单元测试文件已创建（test_agent_chat_stream_error.py）
- [ ] 至少 2 个测试用例通过
- [ ] 现有测试没有被破坏
- [ ] ruff 检查通过
- [ ] 代码符合项目规范

## 常见问题

**Q1: 找不到 `_on_stream_complete` 回调定义？**

A: 使用 Grep 搜索 `async def _on_stream_complete` 或 `def _on_stream_complete`，它应该在 `stream_chat` 方法内部定义。

**Q2: 国际化文本添加后不生效？**

A: 检查 JSON 格式是否正确，确保没有语法错误（多余的逗号、缺少括号等）。

**Q3: 测试无法访问嵌套函数？**

A: 可以通过完整的 `stream_chat` 流程触发，或者直接测试错误消息保存的逻辑（不依赖嵌套函数）。

**Q4: 如何验证错误消息格式？**

A: 查看 `ConversationMessage` 的 `metadata_` 字段，确保包含 `error: True` 和其他必要信息。

## 输出要求

完成后，提交以下内容：

1. 修改的文件：
   - `backend/app/services/ai/agent_chat_service.py`
   - `backend/app/locales/zh_CN.json`
   - `backend/app/locales/en_US.json`

2. 新增的文件：
   - `backend/tests/services/test_agent_chat_stream_error.py`

3. 测试结果：
   - 粘贴测试通过的日志
   - 粘贴 ruff 检查通过的确认

4. 简短总结：
   - 说明实施了哪些改动
   - 遇到的问题和解决方案
   - 验证结果

## 时间预估

- Step 1-3: 1 小时（代码实现）
- Step 4: 15 分钟（国际化文本）
- Step 5: 45 分钟（测试编写）
- Step 6: 15 分钟（运行测试）
- Step 7: 15 分钟（手动验证，可选）

**总计**: 约 2.5 小时

## 相关文件

- PRD: `.trellis/tasks/04-02-stream-error-handling-phase4/prd.md`
- 父任务: `.trellis/tasks/04-02-conversation-618-diagnosis/prd.md`
- 参考代码: `backend/app/ai/engine/stream_handler.py:365-445`
