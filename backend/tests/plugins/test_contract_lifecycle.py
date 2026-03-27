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

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from socketio.exceptions import ConnectionRefusedError as SocketConnectionRefusedError

from app.plugins.event_bus import PluginEventBus
from app.plugins.registry import ExtensionRegistry


def _noop_handler(_event_name: str, _payload: dict) -> None:
    """测试用空处理器，避免 lambda 触发 lint 警告。 / Test."""


class _ScalarsResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


@pytest.fixture(autouse=True)
def _reset_singletons():
    """每个测试前重置单例状态 / Test."""
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
        """确保 _DISPATCH 包含所有已知扩展类型 / _DISPATCH"""
        reg = ExtensionRegistry.get_instance()
        core_types = {
            "adapter", "hook", "storage", "skill", "event",
            "webhook", "task", "notification", "permission", "socketio",
        }
        actual = set(reg._DISPATCH.keys())
        # 允许新增扩展类型，但核心生命周期类型必须始终覆盖。
        assert core_types.issubset(actual)


class TestPluginMenuI18n:
    """插件菜单标题 i18n 回退契约测试 / Plugin."""

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
            # i18n key 格式为 {safe_name}.{name}.title，即 demo_plugin.docs.title
            i18n_key = "demo_plugin.docs.title"

            set_locale("zh_CN")
            assert PermissionService._translate_name(i18n_key) == "文档管理"

            set_locale("en")
            assert PermissionService._translate_name(i18n_key) == "Documents"
        finally:
            # 清理 registry + permission_registry 侧影响
            reg.unregister_all("demo-plugin")
            set_locale("zh_CN")

    def test_menu_i18n_key_is_unique_per_menu(self):
        from app.core.i18n import set_locale

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
            # i18n key 格式为 {safe_name}.{name}.title；resolve_plugin_menu_title 使用 get_locale()
            set_locale("en")
            assert reg.resolve_plugin_menu_title("demo_plugin.list.title") == "List"
            assert reg.resolve_plugin_menu_title("demo_plugin.detail.title") == "Detail"
            assert reg.resolve_plugin_menu_title("demo_plugin.title") is None
        finally:
            reg.unregister_all("demo-plugin")

    def test_menu_title_fallback_tolerates_hyphen_underscore_drift(self):
        from app.core.i18n import set_locale
        from app.rbac.services.permission_service import PermissionService

        reg = ExtensionRegistry.get_instance()
        try:
            reg.register_menu(
                plugin_name="demo-plugin",
                name="docs-list",
                path="/admin/plugins/demo-plugin/docs",
                title={"zh-CN": "文档管理", "en": "Documents"},
            )

            set_locale("zh_CN")
            assert PermissionService._translate_name("demo_plugin.docs_list.title") == "文档管理"
        finally:
            reg.unregister_all("demo-plugin")
            set_locale("zh_CN")

    def test_menu_title_fallback_never_returns_literal_title(self):
        from app.rbac.services.permission_service import PermissionService

        assert PermissionService._translate_name("demo_plugin.missing_entry.title") == "missing entry"

    def test_build_menu_tree_hides_plugin_component_from_menu_response(self):
        from app.models.auth.permission import Permission
        from app.rbac.services.permission_service import PermissionService

        menu = Permission(
            id=1,
            code="menu:admin.plugin_demo_plugin_docs",
            name="demo_plugin.docs.title",
            type="menu",
            scope="admin",
            resource="menu",
            action="admin.plugin_demo_plugin_docs",
            sort_order=10,
            path="/admin/plugins/demo-plugin/docs",
            component="DemoPluginDocsPage",
            hidden=False,
            is_enabled=True,
        )

        result = PermissionService._build_menu_tree([menu])

        assert len(result) == 1
        assert result[0].path == "/admin/plugins/demo-plugin/docs"
        assert result[0].component is None

    def test_build_menu_tree_deduplicates_plugin_entries_with_same_path(self):
        from app.models.auth.permission import Permission
        from app.rbac.services.permission_service import PermissionService

        old_menu = Permission(
            id=1,
            code="menu:admin.plugin_demo_plugin_docs_old",
            name="demo_plugin.docs_old.title",
            type="menu",
            scope="admin",
            resource="menu",
            action="admin.plugin_demo_plugin_docs_old",
            sort_order=10,
            path="/admin/plugins/demo-plugin/docs",
            component="OldDemoPluginDocsPage",
            hidden=False,
            is_enabled=True,
        )
        current_menu = Permission(
            id=2,
            code="menu:admin.plugin_demo_plugin_docs",
            name="demo_plugin.docs.title",
            type="menu",
            scope="admin",
            resource="menu",
            action="admin.plugin_demo_plugin_docs",
            sort_order=10,
            path="/admin/plugins/demo-plugin/docs",
            component="DemoPluginDocsPage",
            hidden=False,
            is_enabled=True,
        )

        result = PermissionService._build_menu_tree([old_menu, current_menu])

        assert len(result) == 1
        assert result[0].path == "/admin/plugins/demo-plugin/docs"


class TestPluginPermissionI18n:
    """插件动作权限 i18n 回退契约测试 / Plugin action permission i18n fallback tests."""

    def test_permission_title_fallback_uses_manifest_name_by_locale(self):
        from app.core.i18n import set_locale
        from app.rbac.services.permission_service import PermissionService
        from app.rbac.sync import PermissionSyncService

        reg = ExtensionRegistry.get_instance()
        try:
            reg.register_permission(
                plugin_name="demo-plugin",
                code="docs",
                name={"zh-CN": "文档管理", "en": "Documents"},
                scope="admin",
                actions=["view", "edit"],
            )
            i18n_key = PermissionSyncService._resolve_plugin_permission_name(
                {"zh-CN": "文档管理", "en": "Documents"},
                "plugin.demo-plugin.docs",
                "view",
            )

            set_locale("zh_CN")
            assert i18n_key == "demo_plugin.permission.docs.view"
            assert PermissionService._translate_name(i18n_key) == "文档管理 - 查看"

            set_locale("en")
            assert PermissionService._translate_name(i18n_key) == "Documents - View"
        finally:
            reg.unregister_all("demo-plugin")
            set_locale("zh_CN")

    def test_permission_title_fallback_tolerates_unknown_action(self):
        from app.core.i18n import set_locale
        from app.rbac.services.permission_service import PermissionService

        reg = ExtensionRegistry.get_instance()
        try:
            reg.register_permission(
                plugin_name="demo-plugin",
                code="docs",
                name={"zh-CN": "文档管理", "en": "Documents"},
                scope="admin",
                actions=["archive_item"],
            )

            set_locale("en")
            assert (
                PermissionService._translate_name(
                    "demo_plugin.permission.docs.archive_item"
                )
                == "Documents - Archive Item"
            )
        finally:
            reg.unregister_all("demo-plugin")
            set_locale("zh_CN")


class TestTenantMenuRuntimeVisibility:
    @pytest.mark.asyncio
    async def test_tenant_admin_menus_filter_out_runtime_invisible_plugin_menus(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.enums.rbac import PermissionScope
        from app.rbac.services.permission_service import PermissionService

        db = AsyncMock()
        service = PermissionService(db)

        root_menu = SimpleNamespace(
            id=10,
            code="menu:tenant.platform_root",
            name="menu.tenant.root",
            type="menu",
            parent_id=None,
            sort_order=1,
            icon=None,
            path="/tenant",
            component=None,
            hidden=False,
        )
        visible_plugin_menu = SimpleNamespace(
            id=11,
            code="menu:tenant.plugin_visible_plugin_home",
            name="visible_plugin.home.title",
            type="menu",
            parent_id=10,
            sort_order=10,
            icon=None,
            path="/tenant/plugins/visible-plugin/home",
            component="VisiblePluginHomePage",
            hidden=False,
        )
        hidden_plugin_menu = SimpleNamespace(
            id=12,
            code="menu:tenant.plugin_hidden_plugin_home",
            name="hidden_plugin.home.title",
            type="menu",
            parent_id=10,
            sort_order=20,
            icon=None,
            path="/tenant/plugins/hidden-plugin/home",
            component="HiddenPluginHomePage",
            hidden=False,
        )
        visible_op = SimpleNamespace(
            id=13,
            code="plugin.visible_plugin.home.view",
            name="visible_plugin.permission.home.view",
            type="operation",
            parent_id=11,
            sort_order=1,
            icon=None,
            path=None,
            component=None,
            hidden=False,
        )
        hidden_op = SimpleNamespace(
            id=14,
            code="plugin.hidden_plugin.home.view",
            name="hidden_plugin.permission.home.view",
            type="operation",
            parent_id=12,
            sort_order=1,
            icon=None,
            path=None,
            component=None,
            hidden=False,
        )

        all_permissions = [
            root_menu,
            visible_plugin_menu,
            hidden_plugin_menu,
            visible_op,
            hidden_op,
        ]
        user_permissions = [
            visible_plugin_menu,
            hidden_plugin_menu,
            visible_op,
            hidden_op,
        ]

        service.get_enabled_permissions_by_scope = AsyncMock(return_value=all_permissions)
        service.get_tenant_admin_effective_permission_ids = AsyncMock(
            return_value={11, 12, 13, 14}
        )
        db.execute = AsyncMock(return_value=_ScalarsResult(user_permissions))

        class _PluginService:
            def __init__(self, _db):
                self._db = _db

            async def get_tenant_visible_plugin_names(self, tenant_id: int) -> set[str]:
                assert tenant_id == 42
                return {"visible-plugin"}

        monkeypatch.setattr(
            "app.services.system.plugin_service.PluginService",
            _PluginService,
        )

        tenant_admin = SimpleNamespace(tenant_id=42, role_id=7)

        menus = await service.get_tenant_admin_menus(tenant_admin)
        menu_paths: set[str] = set()

        def _collect(nodes):
            for node in nodes:
                if node.path:
                    menu_paths.add(node.path)
                _collect(node.children)

        _collect(menus)

        assert "/tenant/plugins/visible-plugin/home" in menu_paths
        assert "/tenant/plugins/hidden-plugin/home" not in menu_paths
        service.get_enabled_permissions_by_scope.assert_awaited_once_with(
            PermissionScope.TENANT.value
        )


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
        """订阅者按 priority 排序执行 / priority"""
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
    """plugin_sse_response 契约测试 / Test."""

    @pytest.mark.asyncio
    async def test_sse_message_done_sequence(self):
        """正常流：message chunks → done → [DONE] / ：message chunks → done → [D..."""
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
        """异常流：error → [DONE] / ：error → [DONE]"""
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
        """空生成器：直接 done → [DONE] / ： done → [DONE]"""
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
        """heartbeat=True 时，空闲超时会发送心跳 / heartbeat=True ，"""
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
    """RequestContext 注入契约测试 / Test."""

    def test_request_context_frozen(self):
        """RequestContext 是 frozen dataclass，不可修改 / RequestContext frozen datacl..."""
        from app.plugins.context import RequestContext

        ctx = RequestContext(tenant_id=1, user_id=2, user_role="tenant_admin")
        with pytest.raises(AttributeError):
            ctx.tenant_id = 99  # type: ignore[misc]

    def test_plugin_context_with_request_context(self):
        """PluginContext 注入 RequestContext 后，getter 返回正确值 / PluginContext RequestContex..."""
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
        """无 RequestContext 时（lifecycle hook 场景），返回安全默认值 / RequestContext （lifecycle h..."""
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
    """API Dispatcher 辅助函数契约测试 / API."""

    def test_handler_accepts_ctx_positive(self):
        """handler 签名含 ctx → True / handler ctx → True"""
        from app.plugins.api_dispatcher import _handler_accepts_param

        async def handler_with_ctx(request, db, ctx):
            pass

        assert _handler_accepts_param(handler_with_ctx, "ctx") is True

    def test_handler_accepts_ctx_negative(self):
        """handler 签名不含 ctx → False / handler ctx → False"""
        from app.plugins.api_dispatcher import _handler_accepts_param

        async def handler_without_ctx(request, db):
            pass

        assert _handler_accepts_param(handler_without_ctx, "ctx") is False

    def test_handler_accepts_ctx_kwargs(self):
        """handler 用 **kwargs → False（不自动注入） / handler **kwargs → False（ ..."""
        from app.plugins.api_dispatcher import _handler_accepts_param

        async def handler_kwargs(**kwargs):
            pass

        assert _handler_accepts_param(handler_kwargs, "ctx") is False


class TestPluginContextAIStream:
    """PluginContext.call_ai_feature_stream 契约测试 / Test."""

    @pytest.mark.asyncio
    async def test_call_ai_feature_stream_yields_deltas(self, monkeypatch):
        """解析 SSE data JSON → yield delta / Parse."""
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
        """SSE error 事件 → 抛 PluginError / SSE error → PluginError"""
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
        """stream_chat 异常 → fallback 为非流式单 chunk / stream_chat → fallback ..."""
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
        import socketio  # noqa: I001

        # Third-party imports above, project imports below / 第三方导入在上，项目导入在下
        # 确保 app.core.socketio_server 已导入，以便 monkeypatch 能解析路径
        import app.core.socketio_server as socketio_server_module

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
        monkeypatch.setattr(socketio_server_module, "get_sio", lambda: fake_sio)

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
    """PluginAuthNamespaceWrapper early-fail auth 契约测试 / Test."""

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

        with pytest.raises(SocketConnectionRefusedError) as exc:
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

        with pytest.raises(SocketConnectionRefusedError) as exc:
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

        with pytest.raises(SocketConnectionRefusedError) as exc:
            await wrapper.on_connect("sid", {}, auth={"token": "invalid"})
        assert exc.value.args and exc.value.args[0] == "authentication_failed"

    @pytest.mark.asyncio
    async def test_trigger_event_restores_trace_from_plugin_session(self):
        import socketio

        from app.middleware.trace import trace_id_var
        from app.plugins.sio_auth import PluginAuthNamespaceWrapper

        class DelegateNamespace(socketio.AsyncNamespace):
            def __init__(self):
                super().__init__("/plugin/test/collab")

            async def on_custom(self, sid, data):
                return {
                    "sid": sid,
                    "payload": data,
                    "seen_trace_id": trace_id_var.get(),
                }

        delegate = DelegateNamespace()
        wrapper = PluginAuthNamespaceWrapper(
            delegate=delegate,
            plugin_name="test",
            auth_scopes=["tenant_admin"],
        )
        wrapper._sid_sessions["sid-1"] = {
            "user_id": 1,
            "user_type": "tenant_admin",
            "tenant_id": 9,
            "username": "tester",
            "plugin_name": "test",
            "trace_id": "trace-plugin-session",
        }

        result = await wrapper.trigger_event(
            "custom",
            "sid-1",
            {"hello": "world"},
        )

        assert result["sid"] == "sid-1"
        assert result["payload"] == {"hello": "world"}
        assert result["seen_trace_id"] == "trace-plugin-session"
        assert trace_id_var.get() == ""

    @pytest.mark.asyncio
    async def test_trigger_event_prefers_payload_trace_and_updates_session(self):
        from unittest.mock import AsyncMock  # noqa: I001

        import socketio

        from app.middleware.trace import trace_id_var
        from app.plugins.sio_auth import PluginAuthNamespaceWrapper

        class DelegateNamespace(socketio.AsyncNamespace):
            def __init__(self):
                super().__init__("/plugin/test/collab")

            async def on_custom(self, sid, data):
                return {
                    "sid": sid,
                    "payload": data,
                    "seen_trace_id": trace_id_var.get(),
                }

        delegate = DelegateNamespace()
        wrapper = PluginAuthNamespaceWrapper(
            delegate=delegate,
            plugin_name="test",
            auth_scopes=["tenant_admin"],
        )
        wrapper.save_session = AsyncMock()
        wrapper._sid_sessions["sid-2"] = {
            "user_id": 2,
            "user_type": "tenant_admin",
            "tenant_id": 9,
            "username": "tester",
            "plugin_name": "test",
            "trace_id": "trace-stale",
        }

        result = await wrapper.trigger_event(
            "custom",
            "sid-2",
            {"hello": "world", "trace_id": "trace-from-payload"},
        )

        assert result["sid"] == "sid-2"
        assert result["seen_trace_id"] == "trace-from-payload"
        assert wrapper._sid_sessions["sid-2"]["trace_id"] == "trace-from-payload"
        wrapper.save_session.assert_awaited_once()
        assert trace_id_var.get() == ""
