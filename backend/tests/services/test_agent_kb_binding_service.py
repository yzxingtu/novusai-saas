from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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
                "kb_owner_tenant_id": 9,
                "kb_owner_tenant_name": "Tenant B",
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
            "kb_owner_tenant_id": 9,
            "kb_owner_tenant_name": "Tenant B",
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


@pytest.mark.asyncio
async def test_get_agent_kb_bindings_filters_kbs_hidden_by_scope_change() -> None:
    from app.services.ai.agent_kb_binding_service import AgentKBBindingService

    visible_binding = SimpleNamespace(
        id=1,
        agent_id=59,
        knowledge_base_id=101,
        weight=1.0,
        enabled=True,
        sort_order=0,
        tenant_id=None,
        knowledge_base=SimpleNamespace(
            name="Visible KB",
            description="Still visible",
            scope="global_shared",
            visibility="shared",
            document_count=4,
            chunk_strategy="recursive",
            embedding_model_id=8,
            embedding_dimensions=1536,
            embedding_model=SimpleNamespace(name="text-embedding"),
        ),
    )
    hidden_binding = SimpleNamespace(
        id=2,
        agent_id=59,
        knowledge_base_id=202,
        weight=0.8,
        enabled=True,
        sort_order=1,
        tenant_id=None,
        knowledge_base=SimpleNamespace(
            name="Hidden KB",
            description="Now admin only",
            scope="admin_only",
            visibility="private",
            document_count=2,
            chunk_strategy="recursive",
            embedding_model_id=8,
            embedding_dimensions=1536,
            embedding_model=SimpleNamespace(name="text-embedding"),
        ),
    )

    service = AgentKBBindingService.__new__(AgentKBBindingService)
    service.db = AsyncMock()
    service.tenant_id = 7
    service.binding_repo = AsyncMock()
    service.binding_repo.list_merged_platform_and_tenant = AsyncMock(
        return_value=[visible_binding, hidden_binding]
    )
    service.binding_repo.get_by_agent_id = AsyncMock()
    service._get_kb_repo = AsyncMock(
        return_value=SimpleNamespace(
            filter_accessible_ids=AsyncMock(return_value={101}),
        )
    )
    service._load_owner_tenant_name_map = AsyncMock(return_value={})

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.services.ai.agent_kb_binding_service.load_suppressed_platform_kb_ids",
            AsyncMock(return_value=set()),
        )
        result = await service.get_agent_kb_bindings(
            59,
            merge_platform_bindings=True,
        )

    assert [item["knowledge_base_id"] for item in result] == [101]
    assert result[0]["kb_name"] == "Visible KB"
    service._get_kb_repo.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_agent_kb_bindings_includes_owner_tenant_metadata() -> None:
    from app.services.ai.agent_kb_binding_service import AgentKBBindingService

    binding = SimpleNamespace(
        id=1,
        agent_id=59,
        knowledge_base_id=101,
        weight=1.0,
        enabled=True,
        sort_order=0,
        tenant_id=None,
        knowledge_base=SimpleNamespace(
            name="Tenant Docs",
            description="Owned by tenant B",
            scope="selected_tenants",
            visibility="private",
            document_count=4,
            chunk_strategy="recursive",
            embedding_model_id=8,
            embedding_dimensions=1536,
            owner_tenant_id=9,
            embedding_model=SimpleNamespace(name="text-embedding"),
        ),
    )
    owner_rows = MagicMock()
    owner_rows.all.return_value = [(9, "Tenant B")]

    service = AgentKBBindingService.__new__(AgentKBBindingService)
    service.db = SimpleNamespace(execute=AsyncMock(return_value=owner_rows))
    service.tenant_id = None
    service.binding_repo = SimpleNamespace(get_by_agent_id=AsyncMock(return_value=[binding]))

    result = await service.get_agent_kb_bindings(59)

    assert result == [
        {
            "id": 1,
            "agent_id": 59,
            "knowledge_base_id": 101,
            "weight": 1.0,
            "enabled": True,
            "sort_order": 0,
            "platform_suppressed": False,
            "binding_scope": "platform",
            "kb_name": "Tenant Docs",
            "kb_description": "Owned by tenant B",
            "kb_scope": "selected_tenants",
            "kb_visibility": "private",
            "kb_document_count": 4,
            "kb_chunk_strategy": "recursive",
            "kb_embedding_model_id": 8,
            "kb_embedding_dimensions": 1536,
            "kb_embedding_model_name": "text-embedding",
            "kb_owner_tenant_id": 9,
            "kb_owner_tenant_name": "Tenant B",
        }
    ]
