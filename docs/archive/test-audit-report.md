# 后端测试全面审计报告

**审计日期**: 2026-03-17  
**测试框架**: pytest 9.0.2, pytest-asyncio  
**审计范围**: `backend/tests/` 全部测试

---

## 一、总体状态

| 指标 | 数值 |
|------|------|
| **通过** | 676 |
| **失败** | 11 |
| **警告** | 2 |
| **通过率** | 98.4% |

---

## 二、失败测试清单

### 2.1 插件契约测试（4 个）— 顺序依赖

| 测试 | 文件 | 单独运行 | 全量运行 |
|------|------|----------|----------|
| `test_register_and_unregister_socketio_namespace` | `test_contract_lifecycle.py` | ✅ | ❌ |
| `test_token_required` | `test_contract_lifecycle.py` | ✅ | ❌ |
| `test_token_expired` | `test_contract_lifecycle.py` | ✅ | ❌ |
| `test_authentication_failed` | `test_contract_lifecycle.py` | ✅ | ❌ |

**根因**: 全量运行早期，`test_tool_argument_recovery` / `test_stream_handler_real_stream` 等通过 `sys.modules.setdefault` 替换了 `redis`、`app.core.socketio_server`。契约测试依赖真实或可 patch 的 `socketio_server`，在 stub 环境下 monkeypatch 目标缺失或行为异常。

### 2.2 页面操作 InvokePageOperation（3 个）— 顺序依赖

| 测试 | 文件 | 单独运行 | 全量运行 |
|------|------|----------|----------|
| `test_success_with_future_result` | `test_page_operation.py` | ✅ | ❌ |
| `test_emits_to_all_namespaces_by_default` | `test_page_operation.py` | ✅ | ❌ |
| `test_emits_to_specific_namespace` | `test_page_operation.py` | ✅ | ❌ |

**现象**: 全量时 `emit.call_count == 0`，`page_operation:invoke timed out`。

**根因**: 同一 `_mock_sio_instance` 被多个 stub 模块共享，全量运行下测试顺序与 mock 使用顺序不一致，导致 Future 未按预期解析、emit 未被正确调用或 mock 被其他测试重置。

### 2.3 模型注册表同步（4 个）— redis stub 污染

| 测试 | 文件 | 单独运行 | 全量运行 |
|------|------|----------|----------|
| `test_first_url_fails_second_succeeds` | `test_registry_sync.py` | ✅ | ❌ |
| `test_llmring_provider_fail_task_still_succeeds` | `test_registry_sync.py` | ✅ | ❌ |
| `test_all_litellm_fail_raises` | `test_registry_sync.py` | ✅ | ❌ |
| `test_return_fields_present` | `test_registry_sync.py` | ✅ | ❌ |

**错误**: `ImportError: cannot import name 'CredentialProvider' from 'redis' (unknown location)`

**根因**: pytest 按目录收集时，`tests/ai/test_tool_argument_recovery.py` 会先于 `tests/tasks/test_registry_sync.py` 加载。前者在模块级 `sys.modules.setdefault("redis", redis_module)` 安装了简化 redis stub，Celery 在执行 `sync_litellm_registry.apply().get()` 时尝试导入 `redis.CredentialProvider`，stub 中无此符号，导致失败。

---

## 三、sys.modules 污染源

以下文件在**模块导入时**对 `sys.modules` 做全局 stub：

| 文件 | 替换模块 | 影响 |
|------|----------|------|
| `tests/ai/test_tool_argument_recovery.py` | redis, redis.asyncio*, app.core.socketio_server | 最先加载（按路径），污染后续所有测试 |
| `tests/services/test_stream_handler_real_stream.py` | redis*, app.core.socketio_server | 依赖 redis 的测试受影响 |
| `tests/services/test_page_operation.py` | redis*, app.core.socketio_server | 同上 |
| `tests/services/test_agent_chat_page_context.py` | redis* | 同上 |

*\* redis stub 不包含 `CredentialProvider` 等，导致 Celery backend 导入失败*

---

## 四、已完成的修复（本轮）

### 4.1 应用代码

| 文件 | 修改 |
|------|------|
| `app/plugins/api_dispatcher.py` | `_handler_accepts_param` 对 `**kwargs` 不再自动注入参数 |
| `app/services/ai/conversation_service.py` | `_to_json` 中 `self._format_dt` → `ConversationService._format_dt` |

### 4.2 测试代码

| 文件 | 修改 |
|------|------|
| `tests/plugins/test_contract_lifecycle.py` | 使用 `_handler_accepts_param`；修正 menu i18n key；补充 `import app.core.socketio_server` |
| `tests/tasks/test_registry_sync.py` | 日志格式改为 `{}` 风格 |
| `tests/test_plugin_api_dispatcher_security.py` | `test_handler_accepts_param_by_kwargs` 期望改为 `False` |
| `tests/test_plugin_loader.py` | manifest `name` 简化为 ASCII |
| `tests/test_toolkit_parser.py` | 去掉 docstring 中文避免编码问题 |
| `tests/test_toolkit_sandbox.py` | 去掉 ` / 说明` 等非法 Python 语法 |
| `tests/services/test_page_operation.py` | 移除 bcrypt stub；为 socketio_server 增加 `sio` |
| `tests/services/test_agent_chat_page_context.py` | 移除 bcrypt stub |
| `tests/services/test_stream_handler_real_stream.py` | 移除 bcrypt stub；为 socketio_server 增加 `sio` |
| `tests/ai/test_tool_argument_recovery.py` | 移除 bcrypt stub；为 socketio_server 增加 `sio` |

---

## 五、待处理问题

### 5.1 RuntimeWarning（2 个）

```
tests/services/test_audience_access.py::TestCheckUserAccess::test_target_audience_allows_tenant_admin
tests/services/test_audience_access.py::TestCheckUserAccess::test_public_agent_all_audience_allows_any_user
  RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
```

**原因**: `service.repo.get_by_id = AsyncMock(return_value=...)` 被当作协程调用时未 await。

### 5.2 建议的修复方向

1. **registry_sync**
   - 选项 A: `test_registry_sync.py` 使用 `pytest_collection_modifyitems` 或 marker 确保先于 redis-stub 测试执行。
   - 选项 B: 将 redis stub 从模块级改为 fixture/`conftest`，仅在需要的测试中应用。
   - 选项 C: 单独命令运行：`pytest tests/tasks/test_registry_sync.py`。

2. **contract_lifecycle / page_operation**
   - 统一 socketio_server 的 stub 策略，避免多个文件各自安装不同 stub。
   - 使用 `pytest.fixture(autouse=True)` 或 `conftest` 管理 stub 作用域，并在测试结束后恢复 `sys.modules`。

3. **audience_access 的 AsyncMock**
   - 将 `get_by_id = AsyncMock(return_value=...)` 调整为 `get_by_id = AsyncMock(return_value=...)` 且确保在 `await` 链路上使用，或改为 `AsyncMock(side_effect=...)` 返回可 await 的结果。

---

## 六、推荐运行方式

| 场景 | 命令 | 预期 |
|------|------|------|
| **全量（当前）** | `pytest tests/ -v` | 11 失败 |
| **仅 registry_sync** | `pytest tests/tasks/test_registry_sync.py -v` | 全部通过 |
| **仅 contract_lifecycle** | `pytest tests/plugins/test_contract_lifecycle.py -v` | 全部通过 |
| **仅 page_operation** | `pytest tests/services/test_page_operation.py -v` | 全部通过 |
| **排除污染源后全量** | 先运行非 stub 测试，再运行 stub 相关测试 | 待实现 |

---

## 七、附录：测试文件分布

```
tests/
├── ai/                      # 含 test_tool_argument_recovery（redis stub）
├── core/
├── plugins/                 # 含 contract_lifecycle
├── services/                # 含 page_operation, agent_chat_page_context, stream_handler
├── tasks/                   # 含 registry_sync
├── test_*.py                # 根目录测试
└── conftest.py
```

Pytest 默认收集顺序大致为：根目录 → ai → core → plugins → services → tasks，因此 `tests/ai/` 中的 stub 会优先影响后续所有测试。
