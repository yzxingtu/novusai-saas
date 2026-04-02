# Conversation 618 Fix - AI Prompts

**任务**: 修复对话 618 的流式响应中断问题  
**Trellis 任务**: `.trellis/tasks/04-02-conversation-618-diagnosis/`

---

## Prompt 1: 诊断和重现问题

```
你是一个 Python 后端工程师，负责诊断对话 618 的流式响应中断问题。

**任务**: 诊断并重现对话 618 的问题

**背景**:
- 对话 618 只有用户输入，没有 AI 回复
- 日志显示 Responses API 返回 502，fallback 到 chat.completions
- Fallback 后流式响应中断，没有后续日志
- 详细分析: 见 `.trellis/tasks/04-02-conversation-618-diagnosis/prd.md`

**诊断步骤**:
1. 审查 `app/ai/adapters/openai_adapter.py` 的 fallback 逻辑
2. 查找 Responses API 失败后的异常处理
3. 检查流式响应处理代码
4. 尝试重现问题:
   - 使用 Agent 59
   - 输入: "通过页面感知能力添加一个测试的智能体 具体里面的内容你来决定"
   - 观察日志和行为

**输出**:
- 根因确认 (代码位置和问题描述)
- 重现步骤 (如果能重现)
- 相关代码片段
- 修复建议

**注意**:
- 重点关注 fallback 后的流式响应初始化
- 检查异常捕获是否完整
- 记录所有相关日志
```

---

## Prompt 2: 修复 Responses API Fallback

```
你是一个 Python 后端工程师，负责修复 Responses API fallback 的流式响应处理。

**任务**: 修复 Responses API 失败后 fallback 到 chat.completions 的流式响应处理

**背景**:
- Responses API 返回 502 后，fallback 到 chat.completions
- Fallback 后的流式响应处理有 bug，导致响应中断
- 详细方案: 见 `.trellis/tasks/04-02-conversation-618-diagnosis/prd.md` Solution 1

**修改文件**: `app/ai/adapters/openai_adapter.py`

**要求**:
1. 在 fallback 逻辑中增加完整的异常处理:
   ```python
   try:
       # Responses API
       async for chunk in responses_stream(...):
           yield chunk
   except InternalServerError as e:
       logger.warning(f"Responses API failed, fallback: {e}")
       try:
           # Fallback to chat.completions
           async for chunk in chat_completions_stream(...):
               yield chunk
       except Exception as fallback_error:
           logger.error(f"Fallback failed: {fallback_error}")
           raise StreamFallbackError(...)
   ```

2. 确保 fallback 后的流式响应正确初始化
3. 增加详细的日志记录
4. 定义 `StreamFallbackError` 异常类

**测试要求**:
1. 编写单元测试:
   - 测试 Responses API 失败 + fallback 成功
   - 测试 Responses API 失败 + fallback 失败
   - 测试正常流程
2. 运行 `ruff check`
3. 运行现有测试确保无回归

**输出**:
- 修改的代码
- 单元测试代码
- 测试结果
- 简短说明
```

---

## Prompt 3: 增强调用日志记录

```
你是一个 Python 后端工程师，负责增强调用日志记录，区分主调用和内部调用。

**任务**: 在调用日志中增加 call_type 字段，区分主对话调用和内部调用

**背景**:
- 对话 618 的调用日志 1071 是内部记忆提取调用，不是主对话调用
- 导致 CLI 显示误导性信息
- 详细方案: 见 `.trellis/tasks/04-02-conversation-618-diagnosis/prd.md` Solution 2

**实施步骤**:

1. **数据库迁移** (创建 `alembic/versions/xxx_add_call_type.py`):
   ```python
   def upgrade():
       op.add_column('ai_call_logs', 
           sa.Column('call_type', sa.String(50), 
           server_default='main_chat', nullable=False))
       op.create_index('idx_call_logs_call_type', 
           'ai_call_logs', ['call_type'])
   
   def downgrade():
       op.drop_index('idx_call_logs_call_type')
       op.drop_column('ai_call_logs', 'call_type')
   ```

2. **修改模型** (`app/models/ai/call_log.py`):
   - 添加 `call_type` 字段
   - 可选值: main_chat, internal_memory, internal_tool

3. **修改调用日志服务**:
   - 在创建日志时指定 call_type
   - 主对话调用: call_type='main_chat'
   - 内部记忆提取: call_type='internal_memory'
   - 内部工具调用: call_type='internal_tool'

4. **修改 CLI** (`app/cli.py`):
   - 查询对话调用日志时过滤 call_type='main_chat'
   - 显示调用类型

**测试要求**:
1. 运行迁移脚本
2. 验证字段和索引创建成功
3. 测试不同类型的调用日志
4. 验证 CLI 显示正确

**输出**:
- 迁移脚本
- 修改的模型代码
- 修改的服务代码
- 修改的 CLI 代码
- 测试结果
```

---

## Prompt 4: 增强错误处理和用户反馈

```
你是一个 Python 后端工程师，负责增强流式响应的错误处理和用户反馈。

**任务**: 当流式响应失败时，保存错误消息并给用户友好的提示

**背景**:
- 对话 618 流式响应中断后，用户没有收到任何提示
- 需要捕获异常并给用户明确的错误信息
- 详细方案: 见 `.trellis/tasks/04-02-conversation-618-diagnosis/prd.md` Solution 3

**修改文件**: `app/ai/engine/base.py` 或流式响应处理器

**要求**:
1. 捕获流式响应异常:
   ```python
   async def handle_stream_response(...):
       try:
           async for chunk in stream:
               yield chunk
       except StreamFallbackError as e:
           # 保存错误消息
           error_msg = "抱歉，AI 服务暂时不可用，请稍后重试。"
           await save_error_message(conversation_id, error_msg)
           # 返回错误提示
           yield {"type": "error", "content": error_msg}
       except Exception as e:
           logger.error(f"Unexpected stream error: {e}")
           error_msg = "系统错误，请联系管理员。"
           await save_error_message(conversation_id, error_msg)
           yield {"type": "error", "content": error_msg}
   ```

2. 实现 `save_error_message` 函数:
   - 创建 assistant 消息，role='assistant', content=error_msg
   - 标记消息为错误类型 (metadata)
   - 更新对话状态为 'failed' 或保持 'active'

3. 确保前端能正确显示错误消息

**测试要求**:
1. 模拟流式响应异常
2. 验证错误消息保存到数据库
3. 验证用户收到错误提示
4. 测试不同类型的异常

**输出**:
- 修改的代码
- 测试代码
- 测试结果
- 前端显示截图 (如果可能)
```

---

## Prompt 5: 端到端验证

```
你是一个 QA 工程师，负责验证对话 618 问题的修复效果。

**任务**: 端到端验证流式响应中断问题的修复

**背景**:
- 已修复 Responses API fallback 逻辑
- 已增强调用日志记录
- 已增强错误处理
- 需要验证修复效果

**测试场景**:

1. **正常场景**:
   - 使用 Agent 59
   - 输入: "通过页面感知能力添加一个测试的智能体 具体里面的内容你来决定"
   - 预期: 正常返回 AI 回复

2. **Responses API 失败场景** (需要模拟):
   - 模拟 Responses API 返回 502
   - 预期: Fallback 到 chat.completions，正常返回回复
   - 验证日志记录正确

3. **完全失败场景** (需要模拟):
   - 模拟 Responses API 和 chat.completions 都失败
   - 预期: 用户收到友好的错误提示
   - 验证错误消息保存到数据库

4. **调用日志验证**:
   - 创建对话并完成
   - 使用 CLI 查看调用日志
   - 预期: 只显示主对话调用，不显示内部调用

**验证点**:
- ✅ 正常场景工作正常
- ✅ Fallback 场景工作正常
- ✅ 错误场景有友好提示
- ✅ 调用日志正确区分类型
- ✅ CLI 显示正确
- ✅ 没有回归问题

**输出**:
- 测试结果表格
- 日志截图
- CLI 输出截图
- 发现的问题 (如有)
- 测试结论
```

---

## 使用顺序

1. **Prompt 1** - 诊断和重现 (30 分钟)
2. **Prompt 2** - 修复 fallback (1-2 小时)
3. **Prompt 3** - 增强日志 (1-2 小时)
4. **Prompt 4** - 增强错误处理 (1-2 小时)
5. **Prompt 5** - 端到端验证 (1 小时)

**总预计时间**: 5-8 小时

---

**创建日期**: 2026-04-02  
**任务**: Conversation 618 流式响应中断修复
