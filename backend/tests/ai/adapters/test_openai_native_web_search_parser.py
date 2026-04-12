from __future__ import annotations

from app.ai.adapters.openai_compatible import native_web_search_parser as facade
from app.ai.adapters.openai_compatible.native_web_search_parser import (
    extract_native_web_search_items,
    extract_native_web_search_items_from_text,
    extract_native_web_search_usage,
)
from app.ai.adapters.openai_compatible.support import (
    native_web_search_parser as support,
)


def test_native_web_search_parser_facade_exports_support_symbols() -> None:
    assert (
        facade.extract_native_web_search_items
        is support.extract_native_web_search_items
    )
    assert (
        facade.extract_native_web_search_items_from_text
        is support.extract_native_web_search_items_from_text
    )
    assert (
        facade.extract_native_web_search_request_count
        is support.extract_native_web_search_request_count
    )
    assert facade.extract_native_web_search_usage is support.extract_native_web_search_usage
    assert facade.normalize_native_web_search_snippet is support.normalize_native_web_search_snippet


def test_extract_native_web_search_items_supports_dict_payloads() -> None:
    response = {
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "Example title body",
                        "annotations": [
                            {
                                "type": "url_citation",
                                "title": "Example",
                                "url": "https://example.com/article",
                                "start_index": 0,
                                "end_index": 7,
                            }
                        ],
                    }
                ],
            }
        ],
        "usage": {"input_tokens": 10, "output_tokens": 4},
    }

    items, saw_unverifiable_url = extract_native_web_search_items(
        response,
        provider_label="openai",
        backend_key="native:openai:gpt-5.4",
        max_results=5,
    )

    assert saw_unverifiable_url is False
    assert len(items) == 1
    assert items[0].title == "Example"
    assert items[0].url == "https://example.com/article"
    assert extract_native_web_search_usage(response) == (10, 4, 14)


def test_extract_native_web_search_items_from_text_reports_parse_error_candidate() -> None:
    items, saw_unverifiable_url = extract_native_web_search_items_from_text(
        "bad source javascript:alert(1) https://example.com/path",
        provider_label="openai",
        backend_key="native:openai:gpt-5.4",
        max_results=5,
    )

    assert saw_unverifiable_url is False
    assert [item.url for item in items] == ["https://example.com/path"]
