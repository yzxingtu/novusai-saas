"""
Test type: behavioral
中文: 范围是运行时 prompt 附加块的最终归一化。
EN: Scope is final normalization for runtime prompt addition blocks.
中文: 无 mock，直接验证渲染前的防御性计数归一化。
EN: No mocks; assertions cover defensive count normalization before rendering.
"""

from app.ai.context.prompt_addition_support import build_runtime_capability_block


def test_runtime_capability_block_recomputes_omitted_count() -> None:
    rendered = build_runtime_capability_block(
        [
            {
                "category": "skills",
                "title": "General Skills",
                "items": ["intent_mapper: Map intents"],
                "displayed_count": 1,
                "total_count": 3,
                "omitted_count": 999,
            }
        ]
    )

    assert '"displayed_count":1' in rendered
    assert '"total_count":3' in rendered
    assert '"omitted_count":2' in rendered
    assert '"omitted_count":999' not in rendered
