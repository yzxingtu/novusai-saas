from types import SimpleNamespace

from app.ai.engine.intent_page_rules import (
    detect_page_continuation_signal,
    detect_page_signal,
    looks_like_page_jump_request,
    looks_like_page_search_request,
    looks_like_read_only_form_instruction,
)


def _continuation_context(**overrides):
    payload = {
        "continuation_capable_families": ["page_ops"],
        "family": "page_ops",
        "active_intent_kind": "page_summary",
        "last_tool_name": "ui_get_snapshot",
        "tool_families": ["page_ops"],
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_detect_page_continuation_signal_returns_page_summary() -> None:
    signal = detect_page_continuation_signal(
        clause="继续看看",
        offset=0,
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
        continuation_context=_continuation_context(),
    )

    assert signal is not None
    assert signal.kind == "page_summary"
    assert signal.shortcircuit is True
    assert signal.metadata.get("continuation_source") == "page_ops"


def test_detect_page_continuation_signal_prefers_screenshot() -> None:
    signal = detect_page_continuation_signal(
        clause="截个图看",
        offset=0,
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
        continuation_context=_continuation_context(),
    )

    assert signal is not None
    assert signal.kind == "page_screenshot"
    assert signal.shortcircuit is False


def test_detect_page_signal_selects_page_search() -> None:
    signal = detect_page_signal(
        clause="在页面里搜索张三",
        offset=0,
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
    )

    assert signal is not None
    assert signal.kind == "page_search"


def test_detect_page_signal_respects_readonly_form_hint() -> None:
    signal = detect_page_signal(
        clause="先不要创建，查看表单状态",
        offset=0,
        input_variables={"page_context": {"page_key": "admin.ai.form"}},
    )

    assert signal is not None
    assert signal.kind == "page_form_read"


def test_detect_page_signal_selects_page_pagination() -> None:
    signal = detect_page_signal(
        clause="下一页",
        offset=0,
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
    )

    assert signal is not None
    assert signal.kind == "page_pagination"


def test_page_rule_helpers_cover_jump_search_readonly() -> None:
    assert looks_like_page_jump_request("下一页")
    assert looks_like_page_search_request("在页面里搜索")
    assert looks_like_read_only_form_instruction("先不要创建")
