"""
插件能力契约测试 — 生命周期（enable/disable/uninstall/restart）

契约矩阵：
┌─────────────────┬───────────┬───────────┬─────────────┬──────────────┐
│ 能力模块         │ enable    │ disable   │ uninstall   │ restart      │
├─────────────────┼───────────┼───────────┼─────────────┼──────────────┤
│ Skill Resolver  │ 注册      │ 反注册    │ 反注册+清DB │ 恢复注册     │
│ Hook            │ 注册      │ 反注册    │ 反注册      │ 恢复注册     │
│ EventBus Sub    │ 注册      │ 反注册    │ 反注册      │ 恢复注册     │
│ Socket.IO NS    │ 注册      │ 反注册    │ 反注册      │ 恢复注册     │
│ Webhook         │ 注册      │ 反注册    │ 反注册      │ 恢复注册     │
│ Task            │ beat注册  │ beat移除  │ beat移除    │ beat恢复     │
│ Notification    │ 内存注册  │ 内存移除  │ 内存移除    │ 内存恢复     │
│ Permission      │ 内存注册  │ 内存移除  │ 内存移除    │ 内存恢复     │
│ PluginEventBus  │ 订阅注册  │ 订阅清理  │ 订阅清理    │ 声明式恢复   │
└─────────────────┴───────────┴───────────┴─────────────┴──────────────┘

运行：pytest tests/plugins/test_contract_lifecycle.py -v
"""

import pytest

from app.plugins.event_bus import PluginEventBus
from app.plugins.registry import ExtensionRegistry


def _noop_handler(_event_name: str, _payload: dict) -> None:
    """测试用空处理器，避免 lambda 触发 lint 警告。"""


@pytest.fixture(autouse=True)
def _reset_singletons():
    """每个测试前重置单例状态"""
    ExtensionRegistry.reset()
    PluginEventBus.reset()
    yield
    ExtensionRegistry.reset()
    PluginEventBus.reset()


class TestRegistryLifecycle:
    """ExtensionRegistry 注册/反注册契约"""

    def test_track_and_count(self):
        reg = ExtensionRegistry.get_instance()
        assert reg.get_registered_count("test-plugin") == 0

        reg._track("test-plugin", "hook", "before_execute")
        assert reg.get_registered_count("test-plugin") == 1

    def test_unregister_all_clears_tracking(self):
        reg = ExtensionRegistry.get_instance()
        reg._track("test-plugin", "hook", "before_execute")
        reg._track("test-plugin", "skill", "test-plugin")

        reg.unregister_all("test-plugin")
        # hook 和 skill 类型有 _unregister_* 方法，即使实际资源不存在也会尝试
        assert reg.get_registered_count("test-plugin") == 0

    def test_unregister_all_idempotent(self):
        reg = ExtensionRegistry.get_instance()
        reg.unregister_all("nonexistent")  # 不应报错
        assert reg.get_registered_count("nonexistent") == 0

    def test_dispatch_table_covers_all_types(self):
        """确保 _DISPATCH 包含所有已知扩展类型"""
        reg = ExtensionRegistry.get_instance()
        core_types = {
            "adapter", "hook", "storage", "skill", "event",
            "webhook", "task", "notification", "permission", "socketio",
        }
        actual = set(reg._DISPATCH.keys())
        # 允许新增扩展类型，但核心生命周期类型必须始终覆盖。
        assert core_types.issubset(actual)


class TestPluginMenuI18n:
    """插件菜单标题 i18n 回退契约测试"""

    def test_menu_title_fallback_uses_manifest_title_by_locale(self):
        from app.core.i18n import set_locale
        from app.rbac.services.permission_service import PermissionService

        reg = ExtensionRegistry.get_instance()
        try:
            reg.register_menu(
                plugin_name="demo-plugin",
                name="docs",
                path="/admin/plugins/demo-plugin/docs",
                title={"zh-CN": "文档管理", "en": "Documents"},
            )

            set_locale("zh_CN")
            assert PermissionService._translate_name(
                "plugin.demo-plugin.menu.docs.title"
            ) == "文档管理"

            set_locale("en")
            assert PermissionService._translate_name(
                "plugin.demo-plugin.menu.docs.title"
            ) == "Documents"
        finally:
            # 清理 registry + permission_registry 侧影响
            reg.unregister_all("demo-plugin")
            set_locale("zh_CN")

    def test_menu_i18n_key_is_unique_per_menu(self):
        reg = ExtensionRegistry.get_instance()
        try:
            reg.register_menu(
                plugin_name="demo-plugin",
                name="list",
                path="/admin/plugins/demo-plugin/list",
                title={"zh-CN": "列表", "en": "List"},
            )
            reg.register_menu(
                plugin_name="demo-plugin",
                name="detail",
                path="/admin/plugins/demo-plugin/detail",
                title={"zh-CN": "详情", "en": "Detail"},
            )

            assert reg.resolve_plugin_menu_title(
                "plugin.demo-plugin.menu.list.title", locale="en"
            ) == "List"
            assert reg.resolve_plugin_menu_title(
                "plugin.demo-plugin.menu.detail.title", locale="en"
            ) == "Detail"
            assert reg.resolve_plugin_menu_title(
                "plugin.demo-plugin.menu.title", locale="en"
            ) is None
        finally:
            reg.unregister_all("demo-plugin")


class TestPluginEventBusLifecycle:
    """PluginEventBus 注册/反注册契约"""

    def test_subscribe_and_count(self):
        bus = PluginEventBus.get_instance()
        bus.subscribe("plugin.a.doc_saved", _noop_handler, plugin_name="a")
        assert bus.get_subscriber_count("plugin.a.doc_saved") == 1

    def test_subscribe_dedup(self):
        bus = PluginEventBus.get_instance()
        handler = _noop_handler
        bus.subscribe("plugin.a.doc_saved", handler, plugin_name="a")
        bus.subscribe("plugin.a.doc_saved", handler, plugin_name="a")
        assert bus.get_subscriber_count("plugin.a.doc_saved") == 1

    def test_unsubscribe_by_plugin(self):
        bus = PluginEventBus.get_instance()
        bus.subscribe("plugin.a.doc_saved", _noop_handler, plugin_name="plugin-b")
        bus.subscribe("plugin.a.event2", _noop_handler, plugin_name="plugin-b")

        removed = bus.unsubscribe_all("plugin-b")
        assert removed == 2
        assert bus.get_subscriber_count("plugin.a.doc_saved") == 0

    def test_unsubscribe_does_not_affect_other_plugins(self):
        bus = PluginEventBus.get_instance()
        bus.subscribe("plugin.a.doc_saved", _noop_handler, plugin_name="plugin-b")
        bus.subscribe("plugin.a.doc_saved", _noop_handler, plugin_name="plugin-c")

        bus.unsubscribe_all("plugin-b")
        assert bus.get_subscriber_count("plugin.a.doc_saved") == 1

    @pytest.mark.asyncio
    async def test_publish_delivers_to_subscribers(self):
        bus = PluginEventBus.get_instance()
        received = []

        async def handler(event_name: str, payload: dict):
            received.append(payload.get("doc_id"))

        bus.subscribe("plugin.novusdoc.doc_saved", handler, plugin_name="pro")
        result = await bus.publish(
            "plugin.novusdoc.doc_saved",
            {"doc_id": 42},
            source_plugin="novusdoc",
        )

        assert result["delivered"] == 1
        assert result["failed"] == 0
        assert received == [42]

    @pytest.mark.asyncio
    async def test_publish_isolates_handler_errors(self):
        bus = PluginEventBus.get_instance()

        async def bad_handler(event_name: str, payload: dict):
            raise ValueError("oops")

        async def good_handler(event_name: str, payload: dict):
            pass

        bus.subscribe("test.event", bad_handler, plugin_name="bad")
        bus.subscribe("test.event", good_handler, plugin_name="good")

        result = await bus.publish("test.event", {})
        assert result["delivered"] == 1
        assert result["failed"] == 1

    @pytest.mark.asyncio
    async def test_publish_no_subscribers_returns_zero(self):
        bus = PluginEventBus.get_instance()
        result = await bus.publish("nobody.listens", {})
        assert result["delivered"] == 0
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_publish_priority_ordering(self):
        """订阅者按 priority 排序执行"""
        bus = PluginEventBus.get_instance()
        order: list[str] = []

        async def handler_a(event_name: str, payload: dict):
            order.append("a")

        async def handler_b(event_name: str, payload: dict):
            order.append("b")

        bus.subscribe("test.order", handler_b, plugin_name="b", priority=200)
        bus.subscribe("test.order", handler_a, plugin_name="a", priority=50)

        await bus.publish("test.order", {})
        # 虽然并行执行，但 subscriber 列表按 priority 排序
        subs = bus._subscribers["test.order"]
        assert subs[0].plugin_name == "a"
        assert subs[1].plugin_name == "b"


class TestSSEResponse:
    """plugin_sse_response 契约测试"""

    @pytest.mark.asyncio
    async def test_sse_message_done_sequence(self):
        """正常流：message chunks → done → [DONE]"""
        from app.plugins.sse import _done, _encode, plugin_sse_response

        async def gen():
            yield "hello"
            yield "world"

        resp = plugin_sse_response(gen(), heartbeat=False, plugin_name="test")
        chunks = []
        async for chunk in resp.body_iterator:
            chunks.append(chunk)

        assert chunks[0] == _encode({"event": "message", "delta": "hello"})
        assert chunks[1] == _encode({"event": "message", "delta": "world"})
        assert chunks[2] == _encode({"event": "done"})
        assert chunks[3] == _done()

    @pytest.mark.asyncio
    async def test_sse_error_sequence(self):
        """异常流：error → [DONE]"""
        from app.plugins.sse import plugin_sse_response

        async def gen():
            yield "ok"
            raise ValueError("boom")

        resp = plugin_sse_response(gen(), heartbeat=False, plugin_name="test")
        chunks = []
        async for chunk in resp.body_iterator:
            chunks.append(chunk)

        # chunk 0: message "ok"
        assert '"delta": "ok"' in chunks[0]
        # error chunk contains error=true
        error_chunk = chunks[1]
        assert '"error": true' in error_chunk
        assert '"boom"' in error_chunk
        # last chunk is [DONE]
        assert chunks[-1] == "data: [DONE]\n\n"

    @pytest.mark.asyncio
    async def test_sse_empty_generator(self):
        """空生成器：直接 done → [DONE]"""
        from app.plugins.sse import _done, _encode, plugin_sse_response

        async def gen():
            if False:
                yield ""

        resp = plugin_sse_response(gen(), heartbeat=False, plugin_name="test")
        chunks = []
        async for chunk in resp.body_iterator:
            chunks.append(chunk)

        assert chunks[0] == _encode({"event": "done"})
        assert chunks[1] == _done()

    @pytest.mark.asyncio
    async def test_sse_heartbeat_emitted(self):
        """heartbeat=True 时，空闲超时会发送心跳"""
        import asyncio

        import app.plugins.sse as sse_module
        from app.plugins.sse import _HEARTBEAT_LINE, plugin_sse_response

        # 临时缩短心跳间隔以加速测试
        original = sse_module._HEARTBEAT_INTERVAL
        sse_module._HEARTBEAT_INTERVAL = 0.1

        try:
            async def slow_gen():
                yield "first"
                await asyncio.sleep(0.3)  # 超过 0.1s 心跳间隔
                yield "second"

            resp = plugin_sse_response(slow_gen(), heartbeat=True, plugin_name="test")
            chunks = []
            async for chunk in resp.body_iterator:
                chunks.append(chunk)

            # 应包含至少一个心跳
            heartbeats = [c for c in chunks if c == _HEARTBEAT_LINE]
            assert len(heartbeats) >= 1, f"Expected heartbeat, got chunks: {chunks}"
        finally:
            sse_module._HEARTBEAT_INTERVAL = original


class TestRequestContext:
    """RequestContext 注入契约测试"""

    def test_request_context_frozen(self):
        """RequestContext 是 frozen dataclass，不可修改"""
        from app.plugins.context import RequestContext

        ctx = RequestContext(tenant_id=1, user_id=2, user_role="tenant_admin")
        with pytest.raises(AttributeError):
            ctx.tenant_id = 99  # type: ignore[misc]

    def test_plugin_context_with_request_context(self):
        """PluginContext 注入 RequestContext 后，getter 返回正确值"""
        from unittest.mock import MagicMock

        from app.plugins.context import PluginContext, RequestContext

        mock_manifest = MagicMock()
        mock_db = MagicMock()

        req_ctx = RequestContext(
            tenant_id=42,
            user_id=7,
            user_role="tenant_admin",
            request_id="req-123",
        )
        ctx = PluginContext(
            plugin_name="test",
            manifest=mock_manifest,
            db=mock_db,
            granted_capabilities=["ai:call"],
            request_context=req_ctx,
        )

        assert ctx.get_current_tenant_id() == 42
        assert ctx.get_current_user_id() == 7
        assert ctx.get_current_user_role() == "tenant_admin"
        assert ctx.get_request_id() == "req-123"

    def test_plugin_context_without_request_context(self):
        """无 RequestContext 时（lifecycle hook 场景），返回安全默认值"""
        from unittest.mock import MagicMock

        from app.plugins.context import PluginContext

        mock_manifest = MagicMock()
        mock_db = MagicMock()

        ctx = PluginContext(
            plugin_name="test",
            manifest=mock_manifest,
            db=mock_db,
        )

        assert ctx.get_current_tenant_id() is None
        assert ctx.get_current_user_id() is None
        assert ctx.get_current_user_role() == ""
        assert ctx.get_request_id() == ""


class TestApiDispatcherHelpers:
    """API Dispatcher 辅助函数契约测试"""

    def test_handler_accepts_ctx_positive(self):
        """handler 签名含 ctx → True"""
        from app.plugins.api_dispatcher import _handler_accepts_ctx

        async def handler_with_ctx(request, db, ctx):
            pass

        assert _handler_accepts_ctx(handler_with_ctx) is True

    def test_handler_accepts_ctx_negative(self):
        """handler 签名不含 ctx → False"""
        from app.plugins.api_dispatcher import _handler_accepts_ctx

        async def handler_without_ctx(request, db):
            pass

        assert _handler_accepts_ctx(handler_without_ctx) is False

    def test_handler_accepts_ctx_kwargs(self):
        """handler 用 **kwargs → False（不自动注入）"""
        from app.plugins.api_dispatcher import _handler_accepts_ctx

        async def handler_kwargs(**kwargs):
            pass

        assert _handler_accepts_ctx(handler_kwargs) is False


class TestPluginContextAIStream:
    """PluginContext.call_ai_feature_stream 契约测试"""

    @pytest.mark.asyncio
    async def test_call_ai_feature_stream_yields_deltas(self, monkeypatch):
        """解析 SSE data JSON → yield delta"""
        from unittest.mock import MagicMock

        from app.plugins.context import PluginContext, RequestContext

        mock_manifest = MagicMock()
        mock_db = MagicMock()

        ctx = PluginContext(
            plugin_name="test",
            manifest=mock_manifest,
            db=mock_db,
            granted_capabilities=["ai:call"],
            request_context=RequestContext(tenant_id=1),
        )

        async def fake_resolve(_feature_code: str):
            return 123, 1

        # 避免触发真实 DB 查询
        ctx._resolve_ai_assignment = fake_resolve  # type: ignore[method-assign]

        class _FakeStreamingResponse:
            @staticmethod
            async def body_iter():
                yield b'data: {"event":"message","delta":"hello"}\n\n'
                yield b'data: {"event":"message","delta":"world"}\n\n'
                yield b"data: [DONE]\n\n"

            @property
            def body_iterator(self):
                return self.body_iter()

        class _FakeAgentChatService:
            def __init__(self, db, tenant_id):
                self.db = db
                self.tenant_id = tenant_id

            async def stream_chat(self, *, agent_id: int, message: str):
                _ = agent_id, message
                return _FakeStreamingResponse()

        monkeypatch.setattr(
            "app.services.ai.agent_chat_service.AgentChatService",
            _FakeAgentChatService,
        )

        deltas: list[str] = []
        async for delta in ctx.call_ai_feature_stream(
            "ai_writer",
            [{"role": "user", "content": "hi"}],
        ):
            deltas.append(delta)

        assert deltas == ["hello", "world"]

    @pytest.mark.asyncio
    async def test_call_ai_feature_stream_error_event_raises(self, monkeypatch):
        """SSE error 事件 → 抛 PluginError"""
        from unittest.mock import MagicMock

        from app.plugins.context import PluginContext, RequestContext
        from app.plugins.exceptions import PluginError

        ctx = PluginContext(
            plugin_name="test",
            manifest=MagicMock(),
            db=MagicMock(),
            granted_capabilities=["ai:call"],
            request_context=RequestContext(tenant_id=1),
        )

        async def fake_resolve(_feature_code: str):
            return 123, 1

        ctx._resolve_ai_assignment = fake_resolve  # type: ignore[method-assign]

        class _FakeStreamingResponse:
            @staticmethod
            async def body_iter():
                yield b'data: {"error":true,"message":"boom"}\n\n'
                yield b"data: [DONE]\n\n"

            @property
            def body_iterator(self):
                return self.body_iter()

        class _FakeAgentChatService:
            def __init__(self, db, tenant_id):
                self.db = db
                self.tenant_id = tenant_id

            async def stream_chat(self, *, agent_id: int, message: str):
                _ = agent_id, message
                return _FakeStreamingResponse()

        monkeypatch.setattr(
            "app.services.ai.agent_chat_service.AgentChatService",
            _FakeAgentChatService,
        )

        with pytest.raises(PluginError):
            async for _ in ctx.call_ai_feature_stream(
                "ai_writer",
                [{"role": "user", "content": "hi"}],
            ):
                pass

    @pytest.mark.asyncio
    async def test_call_ai_feature_stream_fallback_to_non_stream(self, monkeypatch):
        """stream_chat 异常 → fallback 为非流式单 chunk"""
        from unittest.mock import MagicMock

        from app.plugins.context import PluginContext, RequestContext

        ctx = PluginContext(
            plugin_name="test",
            manifest=MagicMock(),
            db=MagicMock(),
            granted_capabilities=["ai:call"],
            request_context=RequestContext(tenant_id=1),
        )

        async def fake_resolve(_feature_code: str):
            return 123, 1

        ctx._resolve_ai_assignment = fake_resolve  # type: ignore[method-assign]

        class _FakeAgentChatService:
            def __init__(self, db, tenant_id):
                self.db = db
                self.tenant_id = tenant_id

            async def stream_chat(self, *, agent_id: int, message: str):
                _ = agent_id, message
                raise RuntimeError("stream not supported")

        monkeypatch.setattr(
            "app.services.ai.agent_chat_service.AgentChatService",
            _FakeAgentChatService,
        )

        async def fake_call_ai_feature(_feature_code: str, _messages: list[dict]) -> str:
            return "fallback"

        # 让 fallback 分支不依赖真实 AgentChatService.chat
        ctx.call_ai_feature = fake_call_ai_feature

        deltas: list[str] = []
        async for delta in ctx.call_ai_feature_stream(
            "ai_writer",
            [{"role": "user", "content": "hi"}],
        ):
            deltas.append(delta)

        assert deltas == ["fallback"]


class TestSocketIONamespaceRegistry:
    """Socket.IO namespace 动态注册/反注册契约测试"""

    def test_register_and_unregister_socketio_namespace(self, monkeypatch):
        import socketio

        from app.plugins.registry import ExtensionRegistry

        class DummyNS(socketio.AsyncNamespace):
            pass

        class FakeSIO:
            def __init__(self):
                self.namespace_handlers: dict[str, object] = {}

            def register_namespace(self, namespace_handler: object) -> None:
                ns = getattr(namespace_handler, "namespace", "")
                self.namespace_handlers[str(ns)] = namespace_handler

        fake_sio = FakeSIO()
        monkeypatch.setattr(
            "app.core.socketio_server.get_sio",
            lambda: fake_sio,
        )

        reg = ExtensionRegistry.get_instance()
        reg.register_socketio(
            "test-plugin",
            "collab",
            DummyNS,
            auth_required=False,
        )

        full_ns = "/plugin/test-plugin/collab"
        assert full_ns in fake_sio.namespace_handlers

        reg.unregister_all("test-plugin")
        assert full_ns not in fake_sio.namespace_handlers


class TestPluginAuthNamespaceWrapper:
    """PluginAuthNamespaceWrapper early-fail auth 契约测试"""

    @pytest.mark.asyncio
    async def test_token_required(self, monkeypatch):
        async def fake_get_ws_configs(*_args):
            return {"ws_enabled": True, "ws_max_connections_per_user": 5}

        monkeypatch.setattr(
            "app.sio.ws_config.get_ws_configs",
            fake_get_ws_configs,
        )

        import socketio

        from app.plugins.sio_auth import PluginAuthNamespaceWrapper

        wrapper = PluginAuthNamespaceWrapper(
            delegate=socketio.AsyncNamespace("/plugin/test/collab"),
            plugin_name="test",
            auth_scopes=["tenant_admin"],
        )

        with pytest.raises(ConnectionRefusedError) as exc:
            await wrapper.on_connect("sid", {}, auth=None)
        assert exc.value.args and exc.value.args[0] == "token_required"

    @pytest.mark.asyncio
    async def test_token_expired(self, monkeypatch):
        async def fake_get_ws_configs(*_args):
            return {"ws_enabled": True, "ws_max_connections_per_user": 5}

        monkeypatch.setattr(
            "app.sio.ws_config.get_ws_configs",
            fake_get_ws_configs,
        )

        from app.core import security as security_module

        def fake_verify_token_with_scope(*_args, **_kwargs):
            raise security_module.TokenExpiredError()

        monkeypatch.setattr(
            "app.core.security.verify_token_with_scope",
            fake_verify_token_with_scope,
        )

        import socketio

        from app.plugins.sio_auth import PluginAuthNamespaceWrapper

        wrapper = PluginAuthNamespaceWrapper(
            delegate=socketio.AsyncNamespace("/plugin/test/collab"),
            plugin_name="test",
            auth_scopes=["tenant_admin"],
        )

        with pytest.raises(ConnectionRefusedError) as exc:
            await wrapper.on_connect("sid", {}, auth={"token": "expired"})
        assert exc.value.args and exc.value.args[0] == "token_expired"

    @pytest.mark.asyncio
    async def test_authentication_failed(self, monkeypatch):
        async def fake_get_ws_configs(*_args):
            return {"ws_enabled": True, "ws_max_connections_per_user": 5}

        monkeypatch.setattr(
            "app.sio.ws_config.get_ws_configs",
            fake_get_ws_configs,
        )

        def fake_verify_token_with_scope(*_args, **_kwargs):
            return None, None

        monkeypatch.setattr(
            "app.core.security.verify_token_with_scope",
            fake_verify_token_with_scope,
        )

        import socketio

        from app.plugins.sio_auth import PluginAuthNamespaceWrapper

        wrapper = PluginAuthNamespaceWrapper(
            delegate=socketio.AsyncNamespace("/plugin/test/collab"),
            plugin_name="test",
            auth_scopes=["tenant_admin"],
        )

        with pytest.raises(ConnectionRefusedError) as exc:
            await wrapper.on_connect("sid", {}, auth={"token": "invalid"})
        assert exc.value.args and exc.value.args[0] == "authentication_failed"
