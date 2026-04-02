# 对话 618 - Phase 4 错误消息持久化修复

**日期**: 2026-04-02  
**状态**: ✅ 已完成

---

## 问题描述

对话 623 流式执行失败后，只有 1 条用户消息被持久化，没有 assistant 错误消息。

## 根本原因

**文件**: `backend/app/services/ai/agent_chat_service.py:1500`

**原始逻辑**:
```python
if not result.success and persisted_message_count == 0:
    await _save_error_message_to_conversation(...)
```

**问题**:
1. 流式失败时，`result.messages` 包含 system + user 消息（无 assistant）
2. `persist_chat_messages` 持久化了用户消息
3. `persisted_message_count = 1`（不是 0）
4. 条件不满足，错误消息未保存

## 修复方案

**新逻辑**: 判断是否有 assistant 消息被持久化

```python
# 计算新消息中的用户消息数量
new_start = system_count + history_count
new_messages_raw = (result.messages or [])[new_start:]
user_message_count = sum(
    1 for m in new_messages_raw
    if m.get("role") == "user"
)

# 如果持久化数量 > 用户消息数量，说明有 assistant 消息
has_assistant_persisted = persisted_message_count > user_message_count

if not result.success and not has_assistant_persisted:
    await _save_error_message_to_conversation(...)
```

## 测试场景

### 场景 1: 无消息持久化
- `result.messages = []`
- `persisted_message_count = 0`
- `user_message_count = 0`
- `has_assistant_persisted = False` ✅
- **期望**: 保存错误消息

### 场景 2: 只有用户消息
- `result.messages = [system, user]`
- `persisted_message_count = 1`
- `user_message_count = 1`
- `has_assistant_persisted = False` ✅
- **期望**: 保存错误消息

### 场景 3: 有 assistant 消息
- `result.messages = [system, user, assistant]`
- `persisted_message_count = 1`
- `user_message_count = 0`
- `has_assistant_persisted = True` ✅
- **期望**: 不保存错误消息

## 验证结果

```bash
$ pytest tests/services/test_agent_chat_stream_error.py -v
============================= test session starts =============================
tests/services/test_agent_chat_stream_error.py::test_stream_on_complete_persists_error_message_when_failed_without_new_messages PASSED [ 20%]
tests/services/test_agent_chat_stream_error.py::test_stream_on_complete_updates_conversation_last_error_metadata PASSED [ 40%]
tests/services/test_agent_chat_stream_error.py::test_stream_on_complete_preserves_partial_output_in_error_metadata PASSED [ 60%]
tests/services/test_agent_chat_stream_error.py::test_stream_on_complete_skips_extra_error_message_when_partial_assistant_already_exists PASSED [ 80%]
tests/services/test_agent_chat_stream_error.py::test_stream_on_complete_persists_error_message_when_sanitized_messages_are_empty PASSED [100%]
============================== 5 passed in 2.40s ==============================

$ ruff check app/services/ai/agent_chat_service.py
All checks passed!
```

## 影响范围

- **修改文件**: `backend/app/services/ai/agent_chat_service.py`
- **修改行数**: 1500-1513 (14 行)
- **测试文件**: `backend/tests/services/test_agent_chat_stream_error.py`
- **测试通过**: 5/5

---

**修复人**: Kiro  
**完成时间**: 2026-04-02 23:08
