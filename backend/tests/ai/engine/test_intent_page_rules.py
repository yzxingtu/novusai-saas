from types import SimpleNamespace

from app.ai.engine.intent_page_rules import (
    detect_page_continuation_signal,
    detect_page_signal,
    looks_like_page_jump_request,
    looks_like_page_search_request,
    looks_like_read_only_form_instruction,
    looks_like_required_field_form_read,
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


def test_detect_page_continuation_signal_prefers_row_detail_with_ui_tools() -> None:
    signal = detect_page_continuation_signal(
        clause="看这个区域",
        offset=0,
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
        continuation_context=_continuation_context(),
    )

    assert signal is not None
    assert signal.kind == "page_row_detail"
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


def test_detect_page_signal_treats_required_field_probe_as_form_read() -> None:
    signal = detect_page_signal(
        clause="请帮我点击添加技能，看看表单里有哪些必填项，但不要提交",
        offset=0,
        input_variables={"page_context": {"page_key": "admin.ai.skills"}},
    )

    assert signal is not None
    assert signal.kind == "page_form_read"


def test_detect_page_signal_treats_skill_binding_as_form_write() -> None:
    signal = detect_page_signal(
        clause="帮我给这个页面的智能体绑定几个技能测试一下",
        offset=0,
        input_variables={"page_context": {"page_key": "admin.ai.agent.detail"}},
    )

    assert signal is not None
    assert signal.kind == "page_form_write"


def test_detect_page_signal_treats_active_form_field_listing_as_form_read() -> None:
    signal = detect_page_signal(
        clause="当前有哪些字段",
        offset=0,
        input_variables={
            "page_context": {
                "page_key": "admin.ai.skills",
                "active_form_session_id": "form-session-1",
            }
        },
    )

    assert signal is not None
    assert signal.kind == "page_form_read"


def test_detect_page_signal_ignores_explicit_external_url_request() -> None:
    signal = detect_page_signal(
        clause="请打开 https://docs.python.org/3/whatsnew/3.13.html 并概括重点",
        offset=0,
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
    )

    assert signal is None


def test_detect_page_signal_ignores_negated_page_reference_for_explicit_url_request() -> (
    None
):
    signal = detect_page_signal(
        clause=(
            "必须只使用 fetch_url 抓取 https://example.com ，"
            "不要联网搜索，也不要参考当前页面"
        ),
        offset=0,
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
    )

    assert signal is None


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
    assert looks_like_required_field_form_read("看看表单里有哪些必填项")
