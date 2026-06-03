from types import SimpleNamespace

from app.enums.rbac import PermissionScope
from app.models.auth.permission import Permission
from app.rbac.decorators import MenuAIConfig
from app.rbac.services.permission_service import PermissionService


def test_build_menu_tree_includes_backend_owned_ai_meta(monkeypatch) -> None:
    permission = Permission(
        id=1,
        code="menu:admin.ai_agent",
        name="menu.admin.ai_agent",
        description=None,
        type="menu",
        scope=PermissionScope.ADMIN.value,
        resource="menu",
        action="admin.ai_agent",
        parent_id=None,
        sort_order=10,
        icon="lucide:bot",
        path="/ai/agents",
        component="ai/agents/index",
        hidden=False,
        is_enabled=True,
    )

    monkeypatch.setattr(
        "app.rbac.services.permission_service.permission_registry.get",
        lambda _code, _scope=None: SimpleNamespace(
            ai=MenuAIConfig(
                description="Create, edit, publish, and manage AI agents",
                keywords=["智能体", "AI助手", "agent"],
                capabilities=["create_agent", "edit_agent"],
                category="ai",
            )
        ),
    )

    menu_tree = PermissionService._build_menu_tree(
        [permission], user_permission_codes=set()
    )  # noqa: SLF001

    assert len(menu_tree) == 1
    assert menu_tree[0].meta is not None
    assert menu_tree[0].meta.ai is not None
    assert (
        menu_tree[0].meta.ai.description
        == "Create, edit, publish, and manage AI agents"
    )
    assert menu_tree[0].meta.ai.keywords[:3] == ["智能体", "AI助手", "agent"]
    assert menu_tree[0].meta.ai.category == "ai"
