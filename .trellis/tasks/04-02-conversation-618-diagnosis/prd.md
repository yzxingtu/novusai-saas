# Conversation 618 Issue Diagnosis and Fix

## Purpose

诊断并修复对话 618 的流式响应中断问题，该问题与能力感知功能的上游 API 故障处理有关。

## Current State

**问题对话**: 618  
**Agent**: 59 (猫娘智能体)  
**用户输入**: "通过页面感知能力添加一个测试的智能体 具体里面的内容你来决定"  
**现象**: 只有用户输入，没有 AI 回复  
**调用日志**: 1071 (status=success, tokens=1136)

## Progress Update

### 2026-04-02 Phase 3-4 收敛情况

- Phase 3 已完成：`ai_call_logs.call_type` 字段、枚举、模型、服务与 CLI 过滤逻辑已落地
- Phase 4 已完成代码与自动化验证：
  - `backend/app/services/ai/agent_chat_service.py` 已在流式失败且没有新增消息时补写用户可见的 assistant 错误消息
  - `backend/app/services/ai/conversation_service.py` 已返回实际持久化消息数，避免 sanitize 之后零落库时跳过错误兜底
  - `backend/app/locales/en/messages.json` 与 `backend/app/locales/zh_CN/messages.json` 已添加专用错误文案
  - `backend/tests/services/test_agent_chat_stream_error.py` 已覆盖错误消息持久化、`conversation.metadata_["last_error"]`、部分输出保存、避免重复补写，以及 sanitize 后无真实落库消息时仍补写错误消息等分支
- 已通过的验证：
  - `pytest tests/services/test_agent_chat_stream_error.py -v`
  - `pytest tests/services/test_agent_chat_service_memory_scene.py -k "stream_chat" -v`
  - `pytest tests/services/test_agent_chat_stream_error.py tests/services/test_agent_chat_service_memory_scene.py tests/services/test_agent_chat_page_context.py tests/services/test_conversation_service.py -k "stream_on_complete or stream_chat or persist_chat_messages or agent_chat_service_injects_page_context" -q`
  - `ruff check app/services/ai/agent_chat_service.py app/services/ai/conversation_service.py tests/services/test_agent_chat_stream_error.py tests/services/test_agent_chat_service_memory_scene.py`
  - locale JSON parse check
- 仍待完成：
  - 在真实开发环境中人为制造或复现上游 502 / fallback 失败，确认用户前端和对话记录都能看到友好错误消息
- 已补充一处更具体的兼容性修复：`chat.completions` 同步 rescue 在兼容网关返回纯文本字符串时，`openai_adapter` 过去会直接访问 `response.choices` 并报 `'str' object has no attribute 'choices'`；现已改为兼容纯文本返回，并保留对 HTML/JSON 垃圾载荷的拒绝
- 已确认一处配置/路由根因：对 `https://codex.2api.com.cn` 直接 `POST /chat/completions` 会返回站点 HTML，而 `POST /v1/chat/completions` 才是 OpenAI 兼容 API；适配器现已在检测到根地址返回 HTML 时自动重试 `${base_url}/v1`
- 已确认并修复 Conversation 626 暴露的两处页面操作后续问题：
  - 远程下拉字段（如 `model_id`）过去会被 AI 描述成 `string`，导致模型填入 `"1"` 这类字符串值，`ApiSelect` 无法映射真实 label；现已将远程 `*_id` 字段推断为 `number`，`*_ids` 推断为数字数组
  - `submit_form` 过去未纳入 `create_record/edit_record` 后的链式自动批准，因此在标准表单工作流末尾重新卡回确认等待，最终表现为 60s 超时；现已与 `fill_form` 一样加入链式自动批准

### 2026-04-02 Phase 5 完成情况

**新 Bug 发现与修复**:
- **问题**: 对话 619 报错 `'str' object has no attribute 'choices'`
- **根因**: `_stream_chat_completions_with_sync_rescue` 中同步 rescue 失败时未捕获异常
- **修复**: 在 `openai_adapter.py:495-508` 添加 try-except 保护同步 rescue 调用
- **测试**: 新增 `tests/ai/adapters/test_openai_adapter_rescue.py` (5 个测试用例)

**修改文件**:
- `backend/app/ai/adapters/openai_adapter.py` (1 处修改)
- `backend/tests/ai/adapters/test_openai_adapter_rescue.py` (新文件)

**验证结果**:
- ✅ 5 个新测试全部通过
- ✅ 31 个 openai_adapter 回归测试全部通过
- ✅ 5 个 Phase 4 流式错误处理测试全部通过
- ✅ ruff check 通过

**影响**:
- 修复了流式失败 + 同步 rescue 失败时的崩溃 bug
- 错误日志更清晰，区分流式错误和 rescue 错误
- 优先抛出原始流式错误，便于调试

## Root Cause Analysis

### 已确认的执行流程

通过日志分析 (trace_id=ec981f9e-34b5-40b7-9560-ff974362e660)，确认了完整的执行流程：

1. **对话创建** (20:24:22)
   - Conversation 618 创建成功
   - Agent 59, Tenant 0

2. **技能解析** (20:24:23)
   - 解析了 5 个技能 → 10 个工具
   - 技能包括: web_search, fetch_url, page_ops, weather, data_ops

3. **页面工具扩展** (20:24:23)
   - 检测到页面上下文 (page_key=admin.ai.agents)
   - 扩展了 10 个页面操作工具
   - 总工具数: 20

4. **工具优化** (20:24:23)
   - Tool planner 判定为 page_ops family
   - 工具优化器从 20 个工具中选择了 12 个
   - 移除了 web_search, fetch_url, weather, data_ops 等非页面工具

5. **上游 API 调用失败** (20:24:23-20:24:30)
   - 首次调用 Responses API: 失败 (502 Upstream request failed)
   - 重试 2 次后仍失败
   - **关键问题**: Fallback 到 chat.completions API

6. **内部记忆提取调用** (20:24:31)
   - 启动了内部 AI 调用用于记忆提取
   - 调用日志 1071 记录的是这个内部调用 (success)
   - **不是用户对话的主调用**

   复核补充（2026-04-02）:
   - 直接检查 `AICallLog#1071.request_metadata` 后，发现其中保存了完整的对话 618 system/user 请求体
   - 同时 `conversation_id=618`
   - 这更像一次主对话调用，而不是纯内部记忆提取调用
   - 因此后续结论调整为：历史记录存在归因歧义，必须通过新增 `call_type` 字段避免未来再次混淆

7. **主对话流中断** (20:24:30 之后)
   - Fallback 到 chat.completions 后，日志中断
   - 没有后续的流式响应日志
   - 没有消息保存日志
   - **推测**: 流式响应在 fallback 后出现异常，未被正确处理

### 根因总结

**主要问题**: Responses API 上游故障 (502) 后，fallback 到 chat.completions 的流式响应处理存在 bug

**次要问题**: 
1. 调用日志 1071 记录的是内部记忆提取调用，不是主对话调用
2. 主对话调用的日志可能未创建或创建失败
3. 流式响应异常未被正确捕获和处理

**与能力感知的关系**:
- 能力感知功能本身工作正常 (技能解析、工具优化都成功)
- 问题出在上游 API 故障处理和流式响应容错
- 但这个问题在测试能力感知功能时暴露出来

## Goals

### Goal 1: 修复流式响应 fallback 处理
确保 Responses API 失败后，fallback 到 chat.completions 能正常工作

### Goal 2: 增强调用日志记录
区分主对话调用和内部调用，确保主调用日志正确记录

### Goal 3: 增强错误处理和用户反馈
当上游 API 故障时，给用户明确的错误提示，而不是静默失败

## Findings

### Finding 1: Responses API fallback 逻辑不完整

**位置**: `app/ai/adapters/openai_adapter.py`

**问题**:
- Responses API 失败后 fallback 到 chat.completions
- 但 fallback 后的流式响应处理可能有 bug
- 异常未被正确捕获

**证据**:
```
2026-04-02 20:24:30 | WARNING | Responses tool call failed, fallback to chat.completions
2026-04-02 20:24:30 | INFO | Stream chat request: model=gpt-5.4-xhigh
# 之后没有任何流式响应日志
```

### Finding 2: 调用日志混淆

**问题**:
- 调用日志 1071 是内部记忆提取调用，不是主对话调用
- 主对话调用的日志可能未创建
- CLI 显示的调用日志误导性强

**复核修正**:
- 历史日志 1071 的原始 `request_metadata` 更接近主对话调用
- 当前不能再把“1071 一定是内部记忆调用”作为确定事实
- 但“缺少结构化调用类型，导致无法可靠区分主调用与内部调用”这一问题仍然成立

**证据**:
```
2026-04-02 20:24:31 | INFO | AI call log saved: log_id=1071
2026-04-02 20:24:31 | INFO | Internal chat dispatch: model=provider_1/gpt-5.4-xhigh
```

### Finding 3: 流式响应异常未处理

**问题**:
- fallback 后的流式响应可能抛出异常
- 异常未被捕获，导致响应中断
- 没有错误日志，没有用户提示

## Solution Design

### Solution 1: 修复 Responses API fallback 流式处理

**文件**: `app/ai/adapters/openai_adapter.py`

**修改点**:
1. 在 fallback 逻辑中增加完整的异常处理
2. 确保 fallback 后的流式响应正确初始化
3. 增加详细的日志记录

**伪代码**:
```python
async def stream_with_fallback(...):
    try:
        # 尝试 Responses API
        async for chunk in responses_stream(...):
            yield chunk
    except InternalServerError as e:
        logger.warning(f"Responses API failed, fallback to chat.completions: {e}")
        try:
            # Fallback 到 chat.completions
            async for chunk in chat_completions_stream(...):
                yield chunk
        except Exception as fallback_error:
            # 捕获 fallback 异常
            logger.error(f"Fallback stream failed: {fallback_error}")
            # 抛出明确的错误
            raise StreamFallbackError(f"Both APIs failed: {e}, {fallback_error}")
```

### Solution 2: 区分主调用和内部调用日志

**文件**: `app/tasks/ai.py` 或相关调用日志服务

**修改点**:
1. 在调用日志中增加 `call_type` 字段 (main_chat / internal_memory / internal_tool)
2. CLI 显示时过滤内部调用
3. 对话统计只计算主调用

**数据库迁移**:
```sql
ALTER TABLE ai_call_logs ADD COLUMN call_type VARCHAR(50) DEFAULT 'main_chat';
CREATE INDEX idx_call_logs_call_type ON ai_call_logs(call_type);
```

### Solution 3: 增强错误处理和用户反馈

**文件**: `app/ai/engine/base.py` 或流式响应处理器

**修改点**:
1. 捕获流式响应异常
2. 保存错误消息到对话
3. 返回用户友好的错误提示

**伪代码**:
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
        await save_error_message(conversation_id, "系统错误，请联系管理员。")
        yield {"type": "error", "content": "系统错误，请联系管理员。"}
```

## Implementation Plan

### Phase 1: 诊断和验证 (1 小时)

**任务 1.1**: 重现问题
- 使用相同的 Agent 59 和输入
- 观察是否能稳定重现
- 记录详细日志

**任务 1.2**: 代码审查
- 审查 `openai_adapter.py` 的 fallback 逻辑
- 审查流式响应处理代码
- 确认根因

### Phase 2: 修复 fallback 逻辑 (2-3 小时)

**任务 2.1**: 修复 Responses API fallback
- 增强异常处理
- 确保 fallback 流式响应正确
- 添加详细日志

**任务 2.2**: 编写单元测试
- 测试 Responses API 失败场景
- 测试 fallback 成功场景
- 测试 fallback 失败场景

**任务 2.3**: 集成测试
- 模拟上游 API 502 错误
- 验证 fallback 工作正常
- 验证错误处理正确

### Phase 3: 增强调用日志 (1-2 小时)

**任务 3.1**: 数据库迁移
- 添加 `call_type` 字段
- 创建索引
- 更新现有数据

**任务 3.2**: 修改调用日志服务
- 记录调用类型
- 更新查询逻辑

**任务 3.3**: 更新 CLI
- 过滤内部调用
- 显示调用类型

### Phase 4: 增强错误处理 (1-2 小时)

**任务 4.1**: 实现错误消息保存
- 保存到对话消息
- 更新对话状态

**任务 4.2**: 实现用户友好错误提示
- 返回明确的错误信息
- 前端正确显示

**任务 4.3**: 测试错误场景
- 测试各种错误情况
- 验证用户体验

### Phase 5: 验证和文档 (1 小时)

**任务 5.1**: 端到端测试
- 重新测试对话 618 场景
- 测试其他错误场景
- 确保修复生效

**任务 5.2**: 更新文档
- 记录修复内容
- 更新错误处理文档
- 更新运维手册

## Acceptance Criteria

- [ ] Responses API fallback 逻辑修复并测试通过
- [ ] 调用日志正确区分主调用和内部调用
- [ ] CLI 正确显示主调用日志
- [ ] 流式响应异常被正确捕获和处理
- [ ] 用户收到友好的错误提示
- [ ] 单元测试覆盖所有错误场景
- [ ] 集成测试通过
- [ ] 端到端测试通过
- [ ] 文档更新完成

## Risks

### Risk 1: Fallback 逻辑复杂
**影响**: 高  
**概率**: 中  
**缓解**: 充分测试，代码审查

### Risk 2: 数据库迁移影响性能
**影响**: 中  
**概率**: 低  
**缓解**: 在低峰期执行，监控性能

### Risk 3: 错误处理影响用户体验
**影响**: 中  
**概率**: 低  
**缓解**: 设计友好的错误提示，提供重试选项

## Dependencies

- 能力感知功能 (已完成)
- 流式响应处理 (现有代码)
- 调用日志服务 (现有代码)

## Output

- 修复代码
- 单元测试
- 集成测试
- 数据库迁移脚本
- 文档更新

## Related Documents

- `docs/conversation-618-issue-analysis.md` - 初步分析
- `docs/capability-awareness-final-audit-20260402.md` - 能力感知审计
