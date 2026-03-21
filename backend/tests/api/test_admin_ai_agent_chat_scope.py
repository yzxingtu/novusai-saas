from app.api.admin.ai_agent_chat import _build_platform_admin_chat_filters


def test_build_platform_admin_chat_filters_scopes_current_admin() -> None:
    filters = _build_platform_admin_chat_filters(77)

    assert len(filters) == 2
    assert filters[0].field == "user_id"
    assert filters[0].op.value == "eq"
    assert filters[0].value == 77
    assert filters[1].field == "owner_type"
    assert filters[1].op.value == "eq"
    assert filters[1].value == "platform_admin"
