# Phase 5: 修复流式 Rescue 异常处理 Bug

## 问题描述

**新 Bug 发现** (2026-04-02 22:31 & 22:47):
```
ERROR | app.ai.adapters.openai_adapter | Stream chat error: model=gpt-5.4-xhigh error='str' object has no attribute 'choices'
ERROR | Sync rescue failed after stream failure: model=gpt-5.4-xhigh stream_error=None rescue_error='str' object has no attribute 'choices'
```

**错误链路**:
1. 流式请求失败 (`status_code=None` → 网络错误)
2. `_stream_chat_completions_with_sync_rescue` 尝试同步 rescue
3. 同步请求返回无效字符串（HTML/JSON 错误页面）
4. `_is_salvageable_raw_text_chat_response` 拒绝该字符串
5. 代码继续调用 `_convert_chat_response(response, model)`
6. 尝试访问 `response.choices` 时崩溃

## 根因分析

### 代码位置
`backend/app/ai/adapters/openai_adapter.py:352-394`

### 问题代码
```python
async def _chat_via_chat_completions(...) -> ChatResponse:
    response = await self.client.chat.completions.create(**request_params)
    
    if self._is_salvageable_raw_text_chat_response(response):
        # 处理可用的纯文本响应
        return ChatResponse(...)
    
    return self._convert_chat_response(response, model)  # ← 如果 response 是字符串会崩溃
```

### 问题分析
1. **某些网关在错误时返回字符串**（HTML 错误页面、JSON 错误对象等）
2. **`_is_salvageable_raw_text_chat_response` 正确拒绝了 HTML/JSON**
3. **但代码没有处理"被拒绝的字符串"场景**，直接传给 `_convert_chat_response`
4. **`_convert_chat_response` 期望 `ChatCompletion` 对象**，访问 `.choices` 时崩溃

## 修复方案

### 方案 1: 在 rescue 调用处添加异常处理 ✅
在 `_stream_chat_completions_with_sync_rescue` 中捕获同步 rescue 异常。

### 方案 2: 拒绝无效字符串响应 ✅
在 `_chat_via_chat_completions` 中，如果 `response` 是字符串但不是可用的纯文本，抛出 `ValueError`。

## 实施记录

### 修复 1: 同步 Rescue 异常处理
**位置**: `openai_adapter.py:495-543`

**修改**:
```python
try:
    response = await self._chat_via_chat_completions(...)
    yield self._chat_response_to_stream_chunk(response)
except Exception as rescue_error:
    logger.error(
        "Sync rescue failed after stream failure: model={} stream_error={} rescue_error={}",
        model,
        str(stream_error) if stream_error is not None else "None",
        str(rescue_error),
    )
    raise stream_error if stream_error is not None else rescue_error
```

### 修复 2: 拒绝无效字符串响应
**位置**: `openai_adapter.py:378-401`

**修改**:
```python
if self._is_salvageable_raw_text_chat_response(response):
    # 处理可用的纯文本
    return ChatResponse(...)

# 拒绝无效字符串（HTML/JSON 错误页面）
if isinstance(response, str):
    logger.error(
        "Chat response returned unsalvageable string payload: model={} preview={}",
        model,
        response[:200],
    )
    raise ValueError(f"Upstream returned invalid string response: {response[:100]}")

return self._convert_chat_response(response, model)
```

## 测试覆盖

### 新增测试
`backend/tests/ai/adapters/test_openai_adapter_rescue.py` (6 个测试用例):

1. ✅ `test_stream_rescue_success` - 流式失败 + 同步 rescue 成功
2. ✅ `test_stream_rescue_both_fail` - 流式失败 + 同步 rescue 失败（抛出原始错误）
3. ✅ `test_stream_rescue_no_stream_error` - 空流 + 同步 rescue 失败（抛出 rescue 错误）
4. ✅ `test_stream_rescue_partial_stream_success` - 部分流式输出后不需要 rescue
5. ✅ `test_stream_rescue_network_error` - 网络错误场景（status_code=None）
6. ✅ `test_stream_rescue_invalid_string_response` - 无效字符串响应（HTML/JSON）

## 验证结果

### 自动化测试
```bash
# 新测试
pytest tests/ai/adapters/test_openai_adapter_rescue.py -v
# ✅ 6 passed

# 回归测试
pytest tests/test_openai_adapter_responses.py -v
# ✅ 33 passed (包含新增的纯文本响应测试)

# Phase 4 测试
pytest tests/services/test_agent_chat_stream_error.py -v
# ✅ 5 passed

# 代码质量
ruff check app/ai/adapters/openai_adapter.py tests/ai/adapters/test_openai_adapter_rescue.py
# ✅ All checks passed
```

### 总计
- ✅ 6 个新测试
- ✅ 33 个回归测试
- ✅ 5 个 Phase 4 测试
- ✅ ruff check 通过

## 影响范围

### 修改文件
- `backend/app/ai/adapters/openai_adapter.py` (2 处修改)
  - 第 495-543 行：同步 rescue 异常处理
  - 第 378-401 行：拒绝无效字符串响应
- `backend/tests/ai/adapters/test_openai_adapter_rescue.py` (新文件，6 个测试)

### 影响功能
- 流式响应 rescue 机制
- 错误处理和日志记录
- 兼容网关返回纯文本响应

### 风险评估
- **低风险**: 仅修改异常处理逻辑，不影响正常流程
- **高收益**: 修复严重的崩溃 bug，提升系统稳定性

## 成功标准

1. ✅ 流式失败 + 同步 rescue 失败时，不再崩溃
2. ✅ 错误日志清晰，包含流式错误和 rescue 错误
3. ✅ 拒绝无效字符串响应（HTML/JSON），抛出明确错误
4. ✅ 单元测试覆盖新场景
5. ✅ 回归测试全部通过
6. ✅ ruff check 通过

## 完成状态

**Phase 5 已完成** ✅

所有修复已实施，测试全部通过，代码质量达标。
