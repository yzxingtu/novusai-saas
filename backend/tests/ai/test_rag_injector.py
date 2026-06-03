"""
Test type: behavioral
中文: 覆盖 RAG 注入器的可选检索降级和预算处理。
EN: Covers optional retrieval degradation and budget handling in the RAG injector.
Scope: RAG injector optional retrieval behavior and budget handling.
Real dependencies: inject_rag_context control flow and business-exception handling.
Mocked dependencies: DB repositories, retriever, and context builder are local fakes
so no external embedding/provider call is made.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.rag_injector import inject_rag_context
from app.ai.types import ChatMessage
from app.core.i18n import _
from app.exceptions import BusinessException


@pytest.mark.asyncio
async def test_inject_rag_context_clamps_budget_to_canonical_limit(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class _FakeKnowledgeBaseRepository:
        def __init__(self, db, tenant_id=None) -> None:  # noqa: ANN001
            _ = (db, tenant_id)

        async def get_by_id(self, kid: int):
            return SimpleNamespace(id=kid, name=f"KB-{kid}")

    class _FakeRetriever:
        def __init__(self, db, tenant_id) -> None:  # noqa: ANN001
            _ = (db, tenant_id)

        async def search(self, **kwargs):
            captured["search_kwargs"] = kwargs
            return [
                SimpleNamespace(
                    chunk_id=10,
                    chunk_index=0,
                    content="retrieved content",
                    document_id=20,
                    document_name="Doc A",
                    knowledge_base_id=11,
                    metadata={},
                    score=0.9,
                )
            ]

    class _FakeBuilder:
        def __init__(self, context_token_ratio=0.6, output_reserve=500) -> None:
            captured["builder_init"] = {
                "context_token_ratio": context_token_ratio,
                "output_reserve": output_reserve,
            }

        def calculate_rag_budget(
            self,
            *,
            max_context_tokens: int,
            system_prompt_tokens: int,
            max_tokens: int | None = None,
        ) -> tuple[int, int]:
            captured["budget_inputs"] = {
                "max_context_tokens": max_context_tokens,
                "system_prompt_tokens": system_prompt_tokens,
                "max_tokens": max_tokens,
            }
            return 17_400, 11_600

        def build_rag_context(
            self,
            chunks,
            token_budget: int,
            kb_names=None,
        ):
            captured["token_budget"] = token_budget
            captured["kb_names"] = kb_names
            return SimpleNamespace(
                rag_text="Injected RAG context",
                sources=[
                    SimpleNamespace(
                        to_dict=lambda: {
                            "chunk_id": 10,
                            "doc_id": 20,
                        }
                    )
                ],
                chunk_count=len(chunks),
                token_count=321,
            )

    monkeypatch.setattr(
        "app.ai.rag.context_builder.RAGContextBuilder",
        _FakeBuilder,
    )
    monkeypatch.setattr(
        "app.ai.rag.retriever.HybridRetriever",
        _FakeRetriever,
    )
    monkeypatch.setattr(
        "app.repositories.ai.knowledge_base_repository.KnowledgeBaseRepository",
        _FakeKnowledgeBaseRepository,
    )
    monkeypatch.setattr(
        "app.repositories.ai.knowledge_base_repository.AdminKnowledgeBaseRepository",
        _FakeKnowledgeBaseRepository,
    )
    monkeypatch.setattr(
        "app.ai.utils.token_estimator.estimate_tokens",
        lambda content: 100 if content else 0,
    )

    agent = SimpleNamespace(
        id=5,
        max_tokens=2000,
        model=SimpleNamespace(context_window=32_000),
    )
    messages = [
        ChatMessage(role="system", content="You are helpful."),
        ChatMessage(role="user", content="What changed in the knowledge base?"),
    ]

    updated_messages, sources = await inject_rag_context(
        db=object(),  # noqa: PYI021
        agent=agent,
        messages=messages,
        tenant_id=9,
        kb_ids=[11],
        rag_config={},
        kb_weights={11: 1.0},
    )

    assert captured["token_budget"] == 2000
    assert captured["budget_inputs"] == {
        "max_context_tokens": 32_000,
        "system_prompt_tokens": 100,
        "max_tokens": 2000,
    }
    assert captured["kb_names"] == {11: "KB-11"}
    assert updated_messages[0].content.endswith("Injected RAG context")
    assert sources == [{"chunk_id": 10, "doc_id": 20}]


@pytest.mark.asyncio
async def test_inject_rag_context_skips_optional_no_api_key_without_warning_for_conversation_2345(
    monkeypatch,
) -> None:
    captured_logs: dict[str, list[tuple[object, ...]]] = {
        "info": [],
        "warning": [],
    }

    class _FakeLogger:
        @staticmethod
        def info(*args):
            captured_logs["info"].append(args)

        @staticmethod
        def warning(*args):
            captured_logs["warning"].append(args)

    class _FakeKnowledgeBaseRepository:
        def __init__(self, db, tenant_id=None) -> None:  # noqa: ANN001
            _ = (db, tenant_id)

        async def get_by_id(self, kid: int):
            return SimpleNamespace(id=kid, name=f"KB-{kid}")

    class _UnavailableRetriever:
        def __init__(self, db, tenant_id) -> None:  # noqa: ANN001
            _ = (db, tenant_id)

        async def search(self, **kwargs):
            assert kwargs["query"] == "你的知识库截止什么时候？"
            raise BusinessException(message=_("ai.no_api_key"))

    monkeypatch.setattr("app.ai.rag_injector.logger", _FakeLogger())
    monkeypatch.setattr(
        "app.ai.rag.retriever.HybridRetriever",
        _UnavailableRetriever,
    )
    monkeypatch.setattr(
        "app.repositories.ai.knowledge_base_repository.KnowledgeBaseRepository",
        _FakeKnowledgeBaseRepository,
    )
    monkeypatch.setattr(
        "app.repositories.ai.knowledge_base_repository.AdminKnowledgeBaseRepository",
        _FakeKnowledgeBaseRepository,
    )

    messages = [
        ChatMessage(role="system", content="You are helpful."),
        ChatMessage(role="user", content="你的知识库截止什么时候？"),
    ]
    updated_messages, sources = await inject_rag_context(
        db=object(),  # noqa: PYI021
        agent=SimpleNamespace(id=59, max_tokens=2000, model=None),
        messages=messages,
        tenant_id=0,
        kb_ids=[11],
        rag_config={},
        kb_weights={11: 1.0},
    )

    assert updated_messages == messages
    assert sources is None
    assert captured_logs["warning"] == []
    assert captured_logs["info"]
    assert captured_logs["info"][0][0] == "RAG injection skipped for agent {}: {}"
    assert captured_logs["info"][0][1:] == (59, _("ai.no_api_key"))
