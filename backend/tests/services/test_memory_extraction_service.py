"""MemoryExtractionService 单元测试 / MemoryExtractionService tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


class _SessionManager:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _fake_response(content: str):
    return SimpleNamespace(message=SimpleNamespace(content=content))


@pytest.mark.asyncio
async def test_extract_turn_memory_uses_configured_model(mock_db):
    from app.services.ai.memory_extraction_service import MemoryExtractionService

    with patch(
        "app.services.ai.memory_extraction_service.async_session_factory",
        return_value=_SessionManager(mock_db),
    ), patch(
        "app.services.ai.memory_extraction_service.ConfigService",
    ) as mock_config_service, patch(
        "app.services.ai.memory_extraction_service.InternalAIService.chat",
        new_callable=AsyncMock,
        return_value=_fake_response(
            '{"preferences":["formal tone"],"constraints":[],"task_states":[],"verified_facts":[]}',
        ),
    ) as mock_chat:
        mock_config_service.return_value.get_platform_config = AsyncMock(
            side_effect=["openai_compatible", "gpt-4o-mini"],
        )

        result = await MemoryExtractionService(tenant_id=1).extract_turn_memory(
            agent_id=7,
            message="以后邮件正式一些",
            response="好的，我会使用更正式的语气。",
        )

    assert result["preferences"] == ["formal tone"]
    assert mock_chat.await_count == 1
    assert mock_chat.await_args.kwargs["provider_code"] == "openai_compatible"
    assert mock_chat.await_args.kwargs["model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_extract_turn_memory_falls_back_to_agent_model(mock_db):
    from app.services.ai.memory_extraction_service import MemoryExtractionService
    from tests.services.conftest import make_mock_model

    provider = make_mock_model(code="fallback-provider")
    model = make_mock_model(code="fallback-model", provider=provider)
    agent = make_mock_model(model=model)

    with patch(
        "app.services.ai.memory_extraction_service.async_session_factory",
        return_value=_SessionManager(mock_db),
    ), patch(
        "app.services.ai.memory_extraction_service.ConfigService",
    ) as mock_config_service, patch(
        "app.services.ai.memory_extraction_service.AgentRepository.get_by_id",
        new_callable=AsyncMock,
        return_value=agent,
    ), patch(
        "app.services.ai.memory_extraction_service.InternalAIService.chat",
        new_callable=AsyncMock,
        return_value=_fake_response(
            '{"preferences":[],"constraints":["avoid slang"],"task_states":[],"verified_facts":[]}',
        ),
    ) as mock_chat:
        mock_config_service.return_value.get_platform_config = AsyncMock(
            side_effect=["", ""],
        )

        result = await MemoryExtractionService(tenant_id=9).extract_turn_memory(
            agent_id=9,
            message="不要用口语化语气",
            response="明白，我会避免口语化表达。",
        )

    assert result["constraints"] == ["avoid slang"]
    assert mock_chat.await_args.kwargs["provider_code"] == "fallback-provider"
    assert mock_chat.await_args.kwargs["model"] == "fallback-model"


@pytest.mark.asyncio
async def test_extract_turn_memory_returns_empty_on_invalid_json(mock_db):
    from app.services.ai.memory_extraction_service import MemoryExtractionService

    with patch(
        "app.services.ai.memory_extraction_service.async_session_factory",
        return_value=_SessionManager(mock_db),
    ), patch(
        "app.services.ai.memory_extraction_service.ConfigService",
    ) as mock_config_service, patch(
        "app.services.ai.memory_extraction_service.InternalAIService.chat",
        new_callable=AsyncMock,
        return_value=_fake_response("not-json"),
    ):
        mock_config_service.return_value.get_platform_config = AsyncMock(
            side_effect=["openai_compatible", "gpt-4o-mini"],
        )

        result = await MemoryExtractionService(tenant_id=1).extract_turn_memory(
            agent_id=7,
            message="记住我的偏好",
            response="好的。",
        )

    assert result == MemoryExtractionService.EMPTY_DELTA
