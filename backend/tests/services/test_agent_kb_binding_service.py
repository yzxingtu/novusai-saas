from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_get_agent_kb_bindings_with_metadata_normalizes_binding_payload() -> None:
    from app.services.ai.agent_kb_binding_service import AgentKBBindingService

    service = AgentKBBindingService.__new__(AgentKBBindingService)
    service.get_agent_kb_bindings = AsyncMock(
        return_value=[
            {
                "id": 9,
                "agent_id": 59,
                "knowledge_base_id": 101,
                "kb_name": "Product Docs",
                "kb_description": "Guides and API references",
                "kb_document_count": "12",
                "binding_scope": "tenant",
            }
        ]
    )

    result = await service.get_agent_kb_bindings_with_metadata(
        59,
        merge_platform_bindings=True,
    )

    service.get_agent_kb_bindings.assert_awaited_once_with(
        59,
        merge_platform_bindings=True,
    )
    assert result == [
        {
            "id": 9,
            "agent_id": 59,
            "knowledge_base_id": 101,
            "kb_id": 101,
            "kb_name": "Product Docs",
            "kb_description": "Guides and API references",
            "kb_document_count": 12,
            "binding_scope": "tenant",
        }
    ]


@pytest.mark.asyncio
async def test_get_agent_kb_bindings_with_metadata_skips_rows_without_kb_id() -> None:
    from app.services.ai.agent_kb_binding_service import AgentKBBindingService

    service = AgentKBBindingService.__new__(AgentKBBindingService)
    service.get_agent_kb_bindings = AsyncMock(
        return_value=[
            {"id": 1, "agent_id": 2, "kb_name": "Missing ID"},
            {"id": 2, "agent_id": 2, "kb_id": 88, "kb_name": "Usable"},
        ]
    )

    result = await service.get_agent_kb_bindings_with_metadata(2)

    assert result == [
        {
            "id": 2,
            "agent_id": 2,
            "kb_id": 88,
            "knowledge_base_id": 88,
            "kb_name": "Usable",
            "kb_description": "",
            "kb_document_count": 0,
        }
    ]


@pytest.mark.asyncio
async def test_unbind_kb_hard_deletes_active_binding() -> None:
    from app.services.ai.agent_kb_binding_service import AgentKBBindingService

    service = AgentKBBindingService.__new__(AgentKBBindingService)
    service.db = AsyncMock()
    service.tenant_id = None
    service.binding_repo = AsyncMock()
    service.binding_repo.get_binding = AsyncMock(
        return_value=SimpleNamespace(id=2, agent_id=59, knowledge_base_id=1),
    )
    service.binding_repo.delete = AsyncMock(return_value=True)

    await service.unbind_kb(agent_id=59, knowledge_base_id=1)

    service.binding_repo.get_binding.assert_awaited_once_with(59, 1)
    service.binding_repo.delete.assert_awaited_once_with(2, soft=False)


@pytest.mark.asyncio
async def test_unbind_kb_raises_when_hard_delete_fails() -> None:
    from app.exceptions import BusinessException
    from app.services.ai.agent_kb_binding_service import AgentKBBindingService

    service = AgentKBBindingService.__new__(AgentKBBindingService)
    service.db = AsyncMock()
    service.tenant_id = None
    service.binding_repo = AsyncMock()
    service.binding_repo.get_binding = AsyncMock(
        return_value=SimpleNamespace(id=2, agent_id=59, knowledge_base_id=1),
    )
    service.binding_repo.delete = AsyncMock(return_value=False)

    with pytest.raises(BusinessException):
        await service.unbind_kb(agent_id=59, knowledge_base_id=1)

    service.binding_repo.delete.assert_awaited_once_with(2, soft=False)
