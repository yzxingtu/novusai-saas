"""
Tool argument parse recovery tests / 工具参数解析恢复测试

验证富文本专用 tools 整改 P0 项：
- 非法 JSON 参数不再被伪装成缺少 operation_name
- parse_arguments 显式返回 invalid_tool_arguments_json
- invoke_page_operation 顶层字段白名单，未知字段报错
- 已移除 content->replace_content 危险推断
"""

import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

# Stub redis/bcrypt/socketio before app imports
redis_module = types.ModuleType("redis")
redis_asyncio_module = types.ModuleType("redis.asyncio")
redis_asyncio_client_module = types.ModuleType("redis.asyncio.client")
redis_exceptions_module = types.ModuleType("redis.exceptions")
bcrypt_module = types.ModuleType("bcrypt")


class _RedisConnectionPool:
    @classmethod
    def from_url(cls, *args, **kwargs):
        return cls()

    async def aclose(self) -> None:
        return None


class _RedisClient:
    def __init__(self, *args, **kwargs) -> None:
        return None


class _RedisPipeline:
    pass


redis_exceptions_module.RedisError = type("RedisError", (Exception,), {})
redis_asyncio_module.ConnectionPool = _RedisConnectionPool
redis_asyncio_module.Redis = _RedisClient
redis_asyncio_client_module.Pipeline = _RedisPipeline
redis_module.asyncio = redis_asyncio_module
redis_module.exceptions = redis_exceptions_module
bcrypt_module.checkpw = lambda *a, **k: True
bcrypt_module.gensalt = lambda: b"salt"
bcrypt_module.hashpw = lambda p, s: p + s
sys.modules.setdefault("redis", redis_module)
sys.modules.setdefault("redis.asyncio", redis_asyncio_module)
sys.modules.setdefault("redis.asyncio.client", redis_asyncio_client_module)
sys.modules.setdefault("redis.exceptions", redis_exceptions_module)
sys.modules.setdefault("bcrypt", bcrypt_module)

_mock_sio = MagicMock()
_mock_sio.emit = AsyncMock()
_sio_mod = types.ModuleType("app.core.socketio_server")
_sio_mod.get_sio = lambda: _mock_sio
sys.modules.setdefault("app.core.socketio_server", _sio_mod)

from app.ai.engine.tool_processor import ToolCallProcessor


class TestParseArguments:
    """parse_arguments 显式 parse failure 测试"""

    def test_valid_json_returns_dict_and_none(self) -> None:
        """有效 JSON 返回 (dict, None)"""
        args, err = ToolCallProcessor.parse_arguments('{"page_key":"p","operation_name":"op"}')
        assert err is None
        assert args == {"page_key": "p", "operation_name": "op"}

    def test_empty_string_returns_empty_dict_and_none(self) -> None:
        """空字符串返回 ({}, None)"""
        args, err = ToolCallProcessor.parse_arguments("")
        assert err is None
        assert args == {}

    def test_invalid_json_returns_invalid_tool_arguments_json(self) -> None:
        """非法 JSON 返回 (None, invalid_tool_arguments_json)，不再静默为 {}"""
        args, err = ToolCallProcessor.parse_arguments("{invalid json}")
        assert err == "invalid_tool_arguments_json"
        assert args is None

    def test_truncated_json_returns_error(self) -> None:
        """截断 JSON 返回错误"""
        args, err = ToolCallProcessor.parse_arguments('{"page_key":')
        assert err == "invalid_tool_arguments_json"
        assert args is None

    def test_dict_input_passthrough(self) -> None:
        """dict 输入直接透传"""
        d = {"a": 1, "b": "x"}
        args, err = ToolCallProcessor.parse_arguments(d)
        assert err is None
        assert args is d


class TestInvokePageOperationTopLevelWhitelist:
    """invoke_page_operation 顶层字段白名单测试"""

    @pytest.mark.asyncio
    async def test_unknown_top_level_fields_return_invalid_input(self) -> None:
        """
        顶层 content/old_html/new_html 等必须放入 params，否则返回 invalid_input。
        验证不再静默丢失业务参数。
        """
        from app.ai.tools.sandbox import SandboxConfig, ToolSandbox
        from app.ai.tools.types import ToolDefinition

        sandbox = ToolSandbox(tenant_id=1, agent_id=1, config=SandboxConfig())
        definition = ToolDefinition(
            name="invoke_page_operation",
            description="invoke",
        )
        definitions = [definition]

        # content at top level (should be in params) -> reject
        result = await sandbox.execute(
            tool_call_id="tc-1",
            name="invoke_page_operation",
            arguments={
                "page_key": "doc.editor",
                "operation_name": "replace_content",
                "content": "<p>wrong place</p>",  # must be in params
            },
            definitions=definitions,
        )

        assert result.success is False
        assert result.error_type == "invalid_input"
        assert "Invalid top-level fields" in result.error
        assert "content" in result.error


class TestPageToolExpander:
    """PageToolExpander 富文本专用 tools 展开测试"""

    def test_expands_editor_tools_when_available(self) -> None:
        """available_operations 含编辑操作时展开 pageop_* tools"""
        from app.ai.tools.page_tool_expander import PREFIX, expand_editor_tools
        from app.ai.tools.types import ToolDefinition

        base_tools = [
            ToolDefinition(name="invoke_page_operation", description="invoke"),
        ]
        input_vars = {
            "page_context": {
                "page_key": "doc.editor",
                "page_data": {
                    "available_operations": [
                        {"name": "get_editor_html", "label": "Get HTML", "description": "Read", "readonly": True},
                        {"name": "replace_content", "label": "Replace", "params": {"content": {"type": "string"}}},
                    ],
                },
            },
        }
        result = expand_editor_tools(base_tools, input_vars)
        expanded_names = [t.name for t in result if t.name.startswith(PREFIX)]
        assert "pageop_get_editor_html" in expanded_names
        assert "pageop_replace_content" in expanded_names
        assert len(expanded_names) == 2
        for t in result:
            if t.name == "pageop_replace_content":
                assert t.config.get("underlying_operation") == "replace_content"
                assert len(t.parameters) >= 1
                break

    def test_no_expansion_without_page_context(self) -> None:
        """无 page_context 时不展开"""
        from app.ai.tools.page_tool_expander import expand_editor_tools
        from app.ai.tools.types import ToolDefinition

        base = [ToolDefinition(name="invoke_page_operation", description="x")]
        result = expand_editor_tools(base, None)
        assert result == base
        result = expand_editor_tools(base, {})
        assert result == base

    def test_no_expansion_when_no_editor_ops(self) -> None:
        """available_operations 无编辑操作时不展开"""
        from app.ai.tools.page_tool_expander import expand_editor_tools
        from app.ai.tools.types import ToolDefinition

        base = [ToolDefinition(name="invoke_page_operation", description="x")]
        input_vars = {
            "page_context": {
                "page_key": "admin.dashboard",
                "page_data": {"available_operations": [{"name": "refresh_list", "label": "Refresh"}]},
            },
        }
        result = expand_editor_tools(base, input_vars)
        assert len(result) == 1
        assert result[0].name == "invoke_page_operation"


class TestOptimizerRetainsPageopTools:
    """工具优化后 pageop_* 仍被保留"""

    def test_pageop_tools_retained_after_optimization(self) -> None:
        """富文本 pageop_* tools 在工具优化后仍被保留"""
        from app.ai.tools.optimizer import optimize_tools
        from app.ai.tools.types import ToolDefinition

        tools = [
            ToolDefinition(name="get_page_context", description="Read page context"),
            ToolDefinition(name="pageop_get_editor_html", description="Get editor HTML"),
            ToolDefinition(name="pageop_replace_section", description="Replace section"),
            ToolDefinition(name="invoke_page_operation", description="Invoke page op"),
        ]
        for i in range(10):
            tools.append(ToolDefinition(name=f"filler_{i}", description=f"Filler {i}"))

        result = optimize_tools(
            tools,
            "帮我把文档里的第二节改成新的内容",
            max_after_optimization=6,
        )

        assert not result.skipped
        tool_names = [t.name for t in result.tools]
        assert "pageop_get_editor_html" in tool_names
        assert "pageop_replace_section" in tool_names
        assert "get_page_context" in tool_names
        assert "invoke_page_operation" in tool_names
