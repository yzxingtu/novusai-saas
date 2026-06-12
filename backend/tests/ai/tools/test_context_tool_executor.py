"""Test type: behavioral
Scope: system context tool executor argument and provider behavior.
Mocked dependencies: long-term memory provider and KB binding loader.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.ai.context_tools.tools import (
    TOOL_RECALL_LONG_TERM_MEMORY,
    TOOL_SAVE_LONG_TERM_MEMORY,
    TOOL_SEARCH_AGENT_KNOWLEDGE_BASE,
    build_context_tool_definitions,
)
from app.ai.tools.executors.context_tool_executor import ContextToolExecutor
from app.ai.tools.types import ExecutionContext


def _definition(name: str):
    return next(tool for tool in build_context_tool_definitions() if tool.name == name)


def _context() -> ExecutionContext:
    return ExecutionContext(
        tenant_id=7,
        agent_id=11,
        user_id=3,
        db=object(),
        conversation_id=99,
        agent=SimpleNamespace(rag_config={"top_k": 3}),
    )


@pytest.mark.asyncio
async def test_context_tool_search_reports_no_bound_kb() -> None:
    executor = ContextToolExecutor()

    with patch(
        "app.ai.tools.executors.context_tool_executor.load_agent_kb_bindings",
        new=AsyncMock(return_value=(None, {})),
    ):
        result = await executor.execute(
            _definition(TOOL_SEARCH_AGENT_KNOWLEDGE_BASE),
            "tc-1",
            {"query": "仓库地址"},
            _context(),
        )

    assert result.success is True
    assert "no_effective_knowledge_base" in result.output


@pytest.mark.asyncio
async def test_context_tool_search_treats_zero_tenant_as_platform_context() -> None:
    executor = ContextToolExecutor()
    kb = SimpleNamespace(
        id=5,
        name="NovusAI SaaS框架知识库",
        rag_config={},
    )
    chunk = SimpleNamespace(
        chunk_id=91,
        knowledge_base_id=5,
        document_id=17,
        document_name="NovusAI SaaS框架官网.txt",
        chunk_index=0,
        score=1.0,
        content="官网：https://nvuai.cc",
        recall_sources=["keyword"],
    )
    kb_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=kb))
    retriever = SimpleNamespace(search=AsyncMock(return_value=[chunk]))
    context = ExecutionContext(
        tenant_id=0,
        agent_id=11,
        user_id=3,
        db=object(),
        conversation_id=99,
        agent=SimpleNamespace(rag_config={"top_k": 3}),
    )

    with (
        patch(
            "app.ai.tools.executors.context_tool_executor.load_agent_kb_bindings",
            new=AsyncMock(return_value=([5], {5: 1.0})),
        ),
        patch(
            "app.repositories.ai.knowledge_base_repository.AdminKnowledgeBaseRepository",
            return_value=kb_repo,
        ) as admin_repo_cls,
        patch(
            "app.repositories.ai.knowledge_base_repository.KnowledgeBaseRepository",
        ) as tenant_repo_cls,
        patch("app.ai.rag.retriever.HybridRetriever", return_value=retriever) as retriever_cls,
    ):
        result = await executor.execute(
            _definition(TOOL_SEARCH_AGENT_KNOWLEDGE_BASE),
            "tc-platform",
            {"query": "NovusAI SaaS框架官网"},
            context,
        )

    assert result.success is True
    output = json.loads(result.output)
    assert output["status"] == "ok"
    assert output["snippets"][0]["content"] == "官网：https://nvuai.cc"
    admin_repo_cls.assert_called_once_with(context.db)
    tenant_repo_cls.assert_not_called()
    retriever_cls.assert_called_once_with(context.db, None)
    retriever.search.assert_awaited_once()


@pytest.mark.asyncio
async def test_context_tool_save_memory_uses_provider() -> None:
    executor = ContextToolExecutor()
    provider = SimpleNamespace(
        capture=AsyncMock(
            return_value=[
                SimpleNamespace(
                    id=1,
                    memory_type="fact",
                    summary="用户喜欢简洁回复",
                    content="用户喜欢简洁回复",
                    importance=60,
                    confidence=70,
                    updated_at=None,
                )
            ]
        )
    )

    with patch(
        "app.services.ai.long_term_memory_provider.get_long_term_memory_provider",
        return_value=provider,
    ):
        result = await executor.execute(
            _definition(TOOL_SAVE_LONG_TERM_MEMORY),
            "tc-2",
            {"content": "用户喜欢简洁回复", "memory_type": "fact"},
            _context(),
        )

    assert result.success is True
    assert "saved" in result.output
    provider.capture.assert_awaited_once()


@pytest.mark.asyncio
async def test_context_tool_recall_memory_uses_provider() -> None:
    executor = ContextToolExecutor()
    provider = SimpleNamespace(
        recall=AsyncMock(
            return_value=[
                SimpleNamespace(
                    id=2,
                    memory_type="preference",
                    summary="用户偏好中文",
                    content="用户偏好中文",
                    importance=60,
                    confidence=70,
                    updated_at=None,
                )
            ]
        )
    )

    with patch(
        "app.services.ai.long_term_memory_provider.get_long_term_memory_provider",
        return_value=provider,
    ):
        result = await executor.execute(
            _definition(TOOL_RECALL_LONG_TERM_MEMORY),
            "tc-3",
            {"query": "语言偏好"},
            _context(),
        )

    assert result.success is True
    assert "用户偏好中文" in result.output
    provider.recall.assert_awaited_once()
