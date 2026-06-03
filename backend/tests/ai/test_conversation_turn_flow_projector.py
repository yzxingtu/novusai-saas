"""中文: 对话 turn-flow 服务投影治理测试。

EN: Governance tests for service-side conversation turn-flow projection.

Test type: behavioral
Scope: ConversationTurnFlowProjector evidence normalization for persisted
assistant metadata.
Mocked dependencies: None.
"""

from __future__ import annotations

from app.services.ai.conversation_turn_flow_projector import (
    ConversationTurnFlowProjector,
)


def test_service_turn_flow_projection_drops_retired_page_and_web_evidence() -> None:
    """Test type: behavioral.

    中文: 历史 page/web/search 来源不能被投影成知识库引用证据。
    EN: Historical page/web/search sources must not be projected as knowledge-base
    evidence.
    """

    turn_flow = ConversationTurnFlowProjector.project_from_metadata(
        {
            "turn_flow": {
                "timeline": [
                    {
                        "id": "retrieval",
                        "type": "retrieval",
                        "status": "completed",
                        "title": "Retrieval",
                        "source_refs": [
                            "page-source",
                            "web-source",
                            "kb-source",
                        ],
                    }
                ],
                "evidence": [
                    {
                        "id": "page-source",
                        "kind": "page",
                        "title": "Rendered page",
                        "snippet": "Current page text",
                    },
                    {
                        "id": "web-source",
                        "source_kind": "page_search",
                        "title": "Page search",
                        "url": "https://example.test/source",
                    },
                    {
                        "id": "kb-source",
                        "kind": "knowledge_base",
                        "title": "Knowledge evidence",
                        "snippet": "Knowledge-base citation",
                        "source_kind": "formal_kb",
                        "knowledge_base_id": 7,
                        "knowledge_base_name": "Product KB",
                    },
                ],
                "answer_card": {
                    "summary": "Knowledge-base answer",
                    "source_chip_ids": [
                        "page-source",
                        "web-source",
                        "kb-source",
                    ],
                },
            }
        },
        content="Knowledge-base answer",
    )

    evidence_ids = [item["id"] for item in turn_flow["evidence"]]
    retrieval_stage = next(
        stage for stage in turn_flow["timeline"] if stage["type"] == "retrieval"
    )

    assert evidence_ids == ["kb-source"]
    assert turn_flow["evidence"][0]["kind"] == "knowledge_base"
    assert turn_flow["evidence"][0]["source_kind"] == "formal_kb"
    assert retrieval_stage["source_refs"] == ["kb-source"]
    assert turn_flow["answer_card"]["source_chip_ids"] == ["kb-source"]
