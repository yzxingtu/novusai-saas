"""页面操作端到端集成测试 / Test.

验证完整链路：
1. PageOperationExecutor — 成功/失败/缺参数/无 page_session_id/超时/用户取消
2. invoke_page_operation — WebSocket 下发 + Future 回传
3. PageSessionMixin — room join/leave/result 事件处理
4. Skill Resolver — invoke_page_operation tool schema 暴露
5. PageOperationExecutor.validate — 参数校验"""

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── 模块 stub（与 test_agent_chat_page_context.py 保持一致）──

redis_module = types.ModuleType("redis")
redis_asyncio_module = types.ModuleType("redis.asyncio")
redis_asyncio_client_module = types.ModuleType("redis.asyncio.client")
redis_exceptions_module = types.ModuleType("redis.exceptions")


class _RedisConnectionPool:
    @classmethod
    def from_url(cls, *args, **kwargs):
        return cls()

    async def aclose(self) -> None:
        return None


class _RedisClient:
    def __init__(self, *args, **kwargs) -> None:
        return None


class _RedisError(Exception):
    pass


class _RedisPipeline:
    pass


redis_asyncio_module.ConnectionPool = _RedisConnectionPool
redis_asyncio_module.Redis = _RedisClient
redis_asyncio_client_module.Pipeline = _RedisPipeline
redis_exceptions_module.RedisError = _RedisError
redis_module.Redis = _RedisClient
redis_module.from_url = lambda *a, **kw: MagicMock()
redis_module.asyncio = redis_asyncio_module
redis_module.exceptions = redis_exceptions_module
sys.modules.setdefault("redis", redis_module)
sys.modules.setdefault("redis.asyncio", redis_asyncio_module)
sys.modules.setdefault("redis.asyncio.client", redis_asyncio_client_module)
sys.modules.setdefault("redis.exceptions", redis_exceptions_module)

# Stub socketio_server 模块（避免 Redis Manager 初始化）
_mock_sio_instance = MagicMock()
_mock_sio_instance.emit = AsyncMock()

socketio_server_module = types.ModuleType("app.core.socketio_server")
socketio_server_module.get_sio = lambda: _mock_sio_instance
socketio_server_module.sio = _mock_sio_instance  # emit_force_logout 等使用 sio 直接导入
sys.modules.setdefault("app.core.socketio_server", socketio_server_module)

from app.ai.skills.resolver import SkillResolver
from app.ai.tools.executors.page_operation_executor import PageOperationExecutor
from app.ai.tools.types import ExecutionContext, ToolDefinition, to_openai_tools
from app.enums.agent import SkillTypeEnum


# ========================================
# PageOperationExecutor 测试
# ========================================


class TestPageOperationExecutor:
    """PageOperationExecutor 单元测试 / Test."""

    @pytest.fixture()
    def executor(self) -> PageOperationExecutor:
        return PageOperationExecutor()

    @pytest.fixture()
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="invoke_page_operation",
            description="Execute a page operation",
        )

    @pytest.mark.asyncio
    async def test_success(self, executor, definition):
        """操作执行成功 → success=True + 输出包含操作名和消息 / → success=True + ..."""
        context = ExecutionContext(
            tenant_id=1,
            agent_id=2,
            page_session_id="ps-123",
        )
        mock_result = {
            "invoke_id": "inv-1",
            "success": True,
            "message": "Dashboard refreshed",
        }

        with patch(
            "app.sio.page_session.invoke_page_operation",
            new=AsyncMock(return_value=mock_result),
        ):
            result = await executor.execute(
                definition,
                "call_1",
                {
                    "page_key": "admin.dashboard",
                    "operation_name": "refresh_dashboard",
                },
                context,
            )

        assert result.success is True
        assert "refresh_dashboard" in result.output
        assert "Dashboard refreshed" in result.output
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_no_page_session_id(self, executor, definition):
        """无 page_session_id → 立即失败 / page_session_id →"""
        context = ExecutionContext(tenant_id=1, agent_id=2)

        result = await executor.execute(
            definition,
            "call_2",
            {
                "page_key": "admin.dashboard",
                "operation_name": "refresh_dashboard",
            },
            context,
        )

        assert result.success is False
        assert "page_session_id" in result.error
        assert result.error_type == "session_not_found"

    @pytest.mark.asyncio
    async def test_no_context(self, executor, definition):
        """context=None → 立即失败 / context=None →"""
        result = await executor.execute(
            definition,
            "call_3",
            {
                "page_key": "admin.dashboard",
                "operation_name": "refresh_dashboard",
            },
            None,
        )

        assert result.success is False
        assert "page_session_id" in result.error

    @pytest.mark.asyncio
    async def test_missing_page_key(self, executor, definition):
        """缺少 page_key → 参数错误 / page_key →"""
        context = ExecutionContext(
            tenant_id=1, agent_id=2, page_session_id="ps-123",
        )

        result = await executor.execute(
            definition,
            "call_4",
            {"operation_name": "refresh_dashboard"},
            context,
        )

        assert result.success is False
        assert "page_key" in result.error
        assert result.error_type == "invalid_input"

    @pytest.mark.asyncio
    async def test_target_not_found_recovery_guidance(self, executor, definition):
        """replace_section target_not_found 时返回恢复指引 / target_not_found ..."""
        context = ExecutionContext(
            tenant_id=1, agent_id=2, page_session_id="ps-123",
        )
        mock_result = {
            "success": False,
            "message": "old_html not found in document",
            "error_type": "target_not_found",
        }

        with patch(
            "app.sio.page_session.invoke_page_operation",
            new=AsyncMock(return_value=mock_result),
        ):
            result = await executor.execute(
                definition,
                "call_tnf",
                {
                    "page_key": "doc.editor",
                    "operation_name": "replace_section",
                    "params": {"old_html": "<x>", "new_html": "<y>"},
                },
                context,
            )

        assert result.success is False
        assert result.error_type == "target_not_found"
        assert "get_editor_html" in result.error or "short" in result.error.lower() or "短" in result.error
        assert "HTML" in result.error and "JSON" in result.error

    @pytest.mark.asyncio
    async def test_missing_operation_name(self, executor, definition):
        """缺少 operation_name → 参数错误 / operation_name →"""
        context = ExecutionContext(
            tenant_id=1, agent_id=2, page_session_id="ps-123",
        )

        result = await executor.execute(
            definition,
            "call_5",
            {"page_key": "admin.dashboard"},
            context,
        )

        assert result.success is False
        assert "operation_name" in result.error
        assert result.error_type == "invalid_input"

    @pytest.mark.asyncio
    async def test_timeout(self, executor, definition):
        """操作超时 → error_type=timeout / → error_type=timeout"""
        context = ExecutionContext(
            tenant_id=1, agent_id=2, page_session_id="ps-123",
        )
        mock_result = {
            "invoke_id": "inv-timeout",
            "success": False,
            "message": "Operation 'refresh' timed out after 10s",
            "error_type": "timeout",
        }

        with patch(
            "app.sio.page_session.invoke_page_operation",
            new=AsyncMock(return_value=mock_result),
        ):
            result = await executor.execute(
                definition,
                "call_6",
                {
                    "page_key": "admin.dashboard",
                    "operation_name": "refresh",
                },
                context,
            )

        assert result.success is False
        assert "超时" in result.error or "timed out" in result.error

    @pytest.mark.asyncio
    async def test_user_cancelled(self, executor, definition):
        """用户取消 → error_type=user_cancelled / → error_type=user_cancell..."""
        context = ExecutionContext(
            tenant_id=1, agent_id=2, page_session_id="ps-123",
        )
        mock_result = {
            "invoke_id": "inv-cancel",
            "success": False,
            "message": "User cancelled the operation",
            "error_type": "user_cancelled",
        }

        with patch(
            "app.sio.page_session.invoke_page_operation",
            new=AsyncMock(return_value=mock_result),
        ):
            result = await executor.execute(
                definition,
                "call_7",
                {
                    "page_key": "admin.tenant.list",
                    "operation_name": "delete_tenant",
                    "requires_confirmation": True,
                },
                context,
            )

        assert result.success is False
        assert "failed" in result.error or "User cancelled" in result.error

    @pytest.mark.asyncio
    async def test_not_registered(self, executor, definition):
        """未注册操作 → 前端回传 not_registered / → not_registered"""
        context = ExecutionContext(
            tenant_id=1, agent_id=2, page_session_id="ps-123",
        )
        mock_result = {
            "invoke_id": "inv-noreg",
            "success": False,
            "message": "Operation 'foo' is not registered on page 'bar'",
            "error_type": "not_registered",
        }

        with patch(
            "app.sio.page_session.invoke_page_operation",
            new=AsyncMock(return_value=mock_result),
        ):
            result = await executor.execute(
                definition,
                "call_8",
                {
                    "page_key": "bar",
                    "operation_name": "foo",
                },
                context,
            )

        assert result.success is False
        assert "not registered" in result.error

    @pytest.mark.asyncio
    async def test_requires_confirmation_passed_to_invoke(self, executor, definition):
        """requires_confirmation 参数正确传递到 invoke_page_operation / requires_confirmation ..."""
        context = ExecutionContext(
            tenant_id=1, agent_id=2, page_session_id="ps-123",
        )
        mock_invoke = AsyncMock(return_value={
            "invoke_id": "inv-confirm",
            "success": True,
            "message": "Done",
        })

        with patch(
            "app.sio.page_session.invoke_page_operation",
            new=mock_invoke,
        ):
            await executor.execute(
                definition,
                "call_9",
                {
                    "page_key": "admin.tenant.list",
                    "operation_name": "export_data",
                    "requires_confirmation": True,
                },
                context,
            )

        mock_invoke.assert_called_once()
        call_kwargs = mock_invoke.call_args.kwargs
        assert call_kwargs["requires_confirmation"] is True
        assert call_kwargs["page_key"] == "admin.tenant.list"
        assert call_kwargs["operation_name"] == "export_data"

    @pytest.mark.asyncio
    async def test_params_passed_to_invoke(self, executor, definition):
        """params 参数正确传递 / params"""
        context = ExecutionContext(
            tenant_id=1, agent_id=2, page_session_id="ps-123",
        )
        mock_invoke = AsyncMock(return_value={
            "invoke_id": "inv-params",
            "success": True,
            "message": "OK",
        })

        with patch(
            "app.sio.page_session.invoke_page_operation",
            new=mock_invoke,
        ):
            await executor.execute(
                definition,
                "call_10",
                {
                    "page_key": "admin.tenant.list",
                    "operation_name": "update_status",
                    "params": {"status": "active"},
                },
                context,
            )

        call_kwargs = mock_invoke.call_args.kwargs
        assert call_kwargs["params"] == {"status": "active"}


# ========================================
# PageOperationExecutor.validate 测试
# ========================================


class TestPageOperationExecutorValidate:
    """PageOperationExecutor.validate 参数校验测试 / Test."""

    @pytest.fixture()
    def executor(self) -> PageOperationExecutor:
        return PageOperationExecutor()

    @pytest.fixture()
    def definition(self) -> ToolDefinition:
        return ToolDefinition(name="invoke_page_operation")

    @pytest.mark.asyncio
    async def test_valid_args(self, executor, definition):
        assert await executor.validate(definition, {
            "page_key": "admin.dashboard",
            "operation_name": "refresh",
        }) is True

    @pytest.mark.asyncio
    async def test_missing_page_key(self, executor, definition):
        assert await executor.validate(definition, {
            "operation_name": "refresh",
        }) is False

    @pytest.mark.asyncio
    async def test_missing_operation_name(self, executor, definition):
        assert await executor.validate(definition, {
            "page_key": "admin.dashboard",
        }) is False

    @pytest.mark.asyncio
    async def test_empty_args(self, executor, definition):
        assert await executor.validate(definition, {}) is False

    @pytest.mark.asyncio
    async def test_empty_page_key(self, executor, definition):
        assert await executor.validate(definition, {
            "page_key": "",
            "operation_name": "refresh",
        }) is False


# ========================================
# invoke_page_operation 函数测试
# ========================================


class TestInvokePageOperation:
    """invoke_page_operation 工具函数测试 / Test."""

    @pytest.fixture(autouse=True)
    def _reset_mock_sio(self):
        """每个测试前重置全局 mock sio / Test."""
        _mock_sio_instance.reset_mock()
        _mock_sio_instance.emit = AsyncMock()

    @pytest.mark.asyncio
    async def test_success_with_future_result(self):
        """前端回传结果 → Future 正确解析 / Parse."""
        import asyncio

        from app.sio.page_session import _pending_invocations, invoke_page_operation

        async def fake_emit(event, data, room=None, namespace=None):
            invoke_id = data["invoke_id"]
            await asyncio.sleep(0.01)
            future = _pending_invocations.get(invoke_id)
            if future and not future.done():
                future.set_result({
                    "invoke_id": invoke_id,
                    "success": True,
                    "message": "List refreshed",
                })

        _mock_sio_instance.emit = AsyncMock(side_effect=fake_emit)

        result = await invoke_page_operation(
            page_session_id="ps-test",
            page_key="admin.tenant.list",
            operation_name="refresh_list",
            timeout=5,
        )

        assert result["success"] is True
        assert result["message"] == "List refreshed"

    @pytest.mark.asyncio
    async def test_timeout_returns_error(self):
        """超时 → 返回 timeout error_type / → timeout error_type"""
        from app.sio.page_session import invoke_page_operation

        _mock_sio_instance.emit = AsyncMock()

        result = await invoke_page_operation(
            page_session_id="ps-dead",
            page_key="admin.dashboard",
            operation_name="refresh",
            timeout=0.05,
        )

        assert result["success"] is False
        assert result["error_type"] == "timeout"

    @pytest.mark.asyncio
    async def test_emits_to_all_namespaces_by_default(self):
        """默认向 /admin、/tenant、/user 三个 namespace 发送"""
        import asyncio

        from app.sio.page_session import _pending_invocations, invoke_page_operation

        async def fake_emit(event, data, room=None, namespace=None):
            invoke_id = data["invoke_id"]
            await asyncio.sleep(0.01)
            future = _pending_invocations.get(invoke_id)
            if future and not future.done():
                future.set_result({
                    "invoke_id": invoke_id,
                    "success": True,
                    "message": "OK",
                })

        _mock_sio_instance.emit = AsyncMock(side_effect=fake_emit)

        await invoke_page_operation(
            page_session_id="ps-multi",
            page_key="admin.dashboard",
            operation_name="refresh",
            timeout=5,
        )

        # emit 应被调用 3 次（/admin + /tenant + /user）
        assert _mock_sio_instance.emit.call_count == 3
        namespaces_called = {
            call.kwargs.get("namespace")
            for call in _mock_sio_instance.emit.call_args_list
        }
        assert "/admin" in namespaces_called
        assert "/tenant" in namespaces_called
        assert "/user" in namespaces_called

    @pytest.mark.asyncio
    async def test_emits_to_specific_namespace(self):
        """指定 namespace → 只向该 namespace 发送 / namespace → namespace ..."""
        import asyncio

        from app.sio.page_session import _pending_invocations, invoke_page_operation

        async def fake_emit(event, data, room=None, namespace=None):
            invoke_id = data["invoke_id"]
            await asyncio.sleep(0.01)
            future = _pending_invocations.get(invoke_id)
            if future and not future.done():
                future.set_result({
                    "invoke_id": invoke_id,
                    "success": True,
                    "message": "OK",
                })

        _mock_sio_instance.emit = AsyncMock(side_effect=fake_emit)

        await invoke_page_operation(
            page_session_id="ps-ns",
            page_key="tenant.dashboard",
            operation_name="refresh",
            namespace="/tenant",
            timeout=5,
        )

        assert _mock_sio_instance.emit.call_count == 1
        ns = _mock_sio_instance.emit.call_args.kwargs.get("namespace")
        assert ns == "/tenant"

    @pytest.mark.asyncio
    async def test_cleanup_after_timeout(self):
        """超时后 invoke_id 从 _pending_invocations 中清理 / invoke_id _pending_invoc..."""
        from app.sio.page_session import _pending_invocations, invoke_page_operation

        _mock_sio_instance.emit = AsyncMock()

        result = await invoke_page_operation(
            page_session_id="ps-cleanup",
            page_key="admin.dashboard",
            operation_name="refresh",
            timeout=0.05,
        )

        invoke_id = result["invoke_id"]
        assert invoke_id not in _pending_invocations


# ========================================
# PageSessionMixin 事件处理测试
# ========================================


class TestPageSessionMixin:
    """PageSessionMixin 事件处理测试 / Test."""

    @pytest.mark.asyncio
    async def test_join_room(self):
        """page_session_join → enter_room 调用 / page_session_join → enter_room..."""
        from app.sio.page_session import PageSessionMixin

        mixin = PageSessionMixin()
        mixin.namespace = "/admin"
        mixin.enter_room = AsyncMock()

        await mixin.on_page_session_join("sid-1", {"page_session_id": "ps-join"})

        mixin.enter_room.assert_called_once_with("sid-1", "page_session:ps-join")

    @pytest.mark.asyncio
    async def test_join_room_no_data(self):
        """page_session_join 无数据 → 不操作 / page_session_join →"""
        from app.sio.page_session import PageSessionMixin

        mixin = PageSessionMixin()
        mixin.enter_room = AsyncMock()

        await mixin.on_page_session_join("sid-1", None)
        mixin.enter_room.assert_not_called()

        await mixin.on_page_session_join("sid-1", {})
        mixin.enter_room.assert_not_called()

    @pytest.mark.asyncio
    async def test_leave_room(self):
        """page_session_leave → leave_room 调用 / page_session_leave → leave_roo..."""
        from app.sio.page_session import PageSessionMixin

        mixin = PageSessionMixin()
        mixin.namespace = "/admin"
        mixin.leave_room = AsyncMock()

        await mixin.on_page_session_leave("sid-1", {"page_session_id": "ps-leave"})

        mixin.leave_room.assert_called_once_with("sid-1", "page_session:ps-leave")

    @pytest.mark.asyncio
    async def test_leave_room_no_data(self):
        """page_session_leave 无数据 → 不操作 / page_session_leave →"""
        from app.sio.page_session import PageSessionMixin

        mixin = PageSessionMixin()
        mixin.leave_room = AsyncMock()

        await mixin.on_page_session_leave("sid-1", None)
        mixin.leave_room.assert_not_called()

    @pytest.mark.asyncio
    async def test_operation_result_resolves_future(self):
        """page_operation_result → Future 被 resolve / page_operation_result → Future..."""
        import asyncio

        from app.sio.page_session import PageSessionMixin, _pending_invocations

        mixin = PageSessionMixin()
        mixin.namespace = "/admin"

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        _pending_invocations["inv-result"] = future

        await mixin.on_page_operation_result("sid-1", {
            "invoke_id": "inv-result",
            "success": True,
            "message": "Done",
        })

        assert future.done()
        assert future.result()["success"] is True
        # cleanup
        _pending_invocations.pop("inv-result", None)

    @pytest.mark.asyncio
    async def test_operation_result_no_matching_future(self):
        """page_operation_result 无匹配 future → 静默忽略 / page_operation_result futu..."""
        from app.sio.page_session import PageSessionMixin

        mixin = PageSessionMixin()
        mixin.namespace = "/admin"

        # 不应抛出异常
        await mixin.on_page_operation_result("sid-1", {
            "invoke_id": "inv-nonexistent",
            "success": True,
            "message": "No matching future",
        })

    @pytest.mark.asyncio
    async def test_operation_result_no_data(self):
        """page_operation_result 无数据 → 不操作 / page_operation_result → ..."""
        from app.sio.page_session import PageSessionMixin

        mixin = PageSessionMixin()
        mixin.namespace = "/admin"

        # 不应抛出异常
        await mixin.on_page_operation_result("sid-1", None)
        await mixin.on_page_operation_result("sid-1", {})

    @pytest.mark.asyncio
    async def test_page_session_id_truncated(self):
        """超长 page_session_id 被截断到 64 字符 / page_session_id 64"""
        from app.sio.page_session import PageSessionMixin

        mixin = PageSessionMixin()
        mixin.namespace = "/admin"
        mixin.enter_room = AsyncMock()

        long_id = "x" * 100
        await mixin.on_page_session_join("sid-1", {"page_session_id": long_id})

        expected_room = f"page_session:{long_id[:64]}"
        mixin.enter_room.assert_called_once_with("sid-1", expected_room)


# ========================================
# Skill Resolver 集成测试
# ========================================


class TestSkillResolverPageOperation:
    """invoke_page_operation 技能 schema 解析测试 / Test."""

    @pytest.mark.asyncio
    async def test_resolver_exposes_invoke_page_operation_tool(self):
        """Skill resolver 正确解析 invoke_page_operation 工具 schema / Parse."""
        skill = MagicMock()
        skill.id = 501
        skill.package_id = 601
        skill.is_active = True
        skill.config = {
            "builtin_type": "page_operation",
            "tools": [
                {
                    "name": "invoke_page_operation",
                    "description": "Execute a page operation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_key": {
                                "type": "string",
                                "description": "Page identifier",
                            },
                            "operation_name": {
                                "type": "string",
                                "description": "Operation name",
                            },
                            "params": {
                                "type": "object",
                                "description": "Operation parameters",
                                "default": {},
                            },
                        },
                        "required": ["page_key", "operation_name"],
                    },
                }
            ],
        }
        skill.name = "invoke_page_operation"
        skill.description = "Execute a page operation"
        skill.type = SkillTypeEnum.BUILTIN.value
        skill.timeout = 15

        result = await SkillResolver().resolve([skill])

        assert len(result.tools) == 1
        assert result.tools[0].name == "invoke_page_operation"

        openai_tools = to_openai_tools(result.tools)
        fn = openai_tools[0]["function"]
        assert fn["name"] == "invoke_page_operation"
        assert "page_key" in fn["parameters"]["properties"]
        assert "operation_name" in fn["parameters"]["properties"]
        assert "params" in fn["parameters"]["properties"]
        assert fn["parameters"]["required"] == ["page_key", "operation_name"]

    @pytest.mark.asyncio
    async def test_resolver_with_both_page_skills(self):
        """同时包含 get_page_context + invoke_page_operation 两个技能 / get_page_context + invoke..."""
        context_skill = MagicMock()
        context_skill.id = 501
        context_skill.package_id = 601
        context_skill.is_active = True
        context_skill.config = {
            "builtin_type": "page_context",
            "tools": [{
                "name": "get_page_context",
                "description": "Read current page context",
                "parameters": {"type": "object", "properties": {}, "required": []},
            }],
        }
        context_skill.name = "get_page_context"
        context_skill.description = "Read current page context"
        context_skill.type = SkillTypeEnum.BUILTIN.value
        context_skill.timeout = 15

        operation_skill = MagicMock()
        operation_skill.id = 502
        operation_skill.package_id = 601
        operation_skill.is_active = True
        operation_skill.config = {
            "builtin_type": "page_operation",
            "tools": [{
                "name": "invoke_page_operation",
                "description": "Execute a page operation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_key": {"type": "string"},
                        "operation_name": {"type": "string"},
                    },
                    "required": ["page_key", "operation_name"],
                },
            }],
        }
        operation_skill.name = "invoke_page_operation"
        operation_skill.description = "Execute a page operation"
        operation_skill.type = SkillTypeEnum.BUILTIN.value
        operation_skill.timeout = 15

        result = await SkillResolver().resolve([context_skill, operation_skill])

        tool_names = {t.name for t in result.tools}
        assert tool_names == {"get_page_context", "invoke_page_operation"}

        openai_tools = to_openai_tools(result.tools)
        fn_names = {t["function"]["name"] for t in openai_tools}
        assert fn_names == {"get_page_context", "invoke_page_operation"}
