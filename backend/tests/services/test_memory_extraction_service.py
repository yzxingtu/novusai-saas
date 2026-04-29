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


def _fake_response(content: str, *, reasoning_content: str | None = None):
    return SimpleNamespace(
        message=SimpleNamespace(
            content=content,
            reasoning_content=reasoning_content,
        )
    )


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
    assert mock_chat.await_args.kwargs["call_type"] == "internal_memory"


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
    assert mock_chat.await_args.kwargs["call_type"] == "internal_memory"


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


@pytest.mark.asyncio
async def test_extract_turn_memory_uses_reasoning_content_when_primary_content_is_invalid(
    mock_db,
):
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
            "not-json",
            reasoning_content='{"preferences":[],"constraints":[],"task_states":[],"verified_facts":["preferred locale: zh-CN"]}',
        ),
    ):
        mock_config_service.return_value.get_platform_config = AsyncMock(
            side_effect=["openai_compatible", "gpt-4o-mini"],
        )

        result = await MemoryExtractionService(tenant_id=1).extract_turn_memory(
            agent_id=7,
            message="remember my preferred locale",
            response="ok",
        )

    assert result == {
        "preferences": [],
        "constraints": [],
        "task_states": [],
        "verified_facts": ["preferred locale: zh-CN"],
    }


@pytest.mark.asyncio
async def test_extract_turn_memory_falls_back_to_explicit_name_fact_on_empty_content(
    mock_db,
):
    from app.services.ai.memory_extraction_service import MemoryExtractionService

    with patch(
        "app.services.ai.memory_extraction_service.async_session_factory",
        return_value=_SessionManager(mock_db),
    ), patch(
        "app.services.ai.memory_extraction_service.ConfigService",
    ) as mock_config_service, patch(
        "app.services.ai.memory_extraction_service.InternalAIService.chat",
        new_callable=AsyncMock,
        return_value=_fake_response(""),
    ):
        mock_config_service.return_value.get_platform_config = AsyncMock(
            side_effect=["openai_compatible", "gpt-4o-mini"],
        )

        result = await MemoryExtractionService(tenant_id=1).extract_turn_memory(
            agent_id=7,
            message="我叫大致坡，请把这个信息存入长期记忆",
            response="好的，我会记住。",
        )

    assert result == {
        "preferences": [],
        "constraints": [],
        "task_states": [],
        "verified_facts": ["用户名字是大致坡"],
    }


@pytest.mark.asyncio
async def test_extract_turn_memory_falls_back_to_explicit_memory_fact_on_empty_content(
    mock_db,
):
    from app.services.ai.memory_extraction_service import MemoryExtractionService

    with patch(
        "app.services.ai.memory_extraction_service.async_session_factory",
        return_value=_SessionManager(mock_db),
    ), patch(
        "app.services.ai.memory_extraction_service.ConfigService",
    ) as mock_config_service, patch(
        "app.services.ai.memory_extraction_service.InternalAIService.chat",
        new_callable=AsyncMock,
        return_value=_fake_response(""),
    ):
        mock_config_service.return_value.get_platform_config = AsyncMock(
            side_effect=["openai_compatible", "gpt-4o-mini"],
        )

        result = await MemoryExtractionService(tenant_id=1).extract_turn_memory(
            agent_id=7,
            message=(
                "请把“跨对话暗号是 蓝莓雨伞 418J”存入长期记忆。"
                "只有在真正写入跨对话长期记忆时才回答 STORED，否则只回答 NO_STORE。"
            ),
            response="NO_STORE",
        )

    assert result == {
        "preferences": [],
        "constraints": [],
        "task_states": [],
        "verified_facts": ["跨对话暗号是 蓝莓雨伞 418J"],
    }


@pytest.mark.asyncio
async def test_extract_turn_memory_falls_back_to_explicit_fact_when_model_missing(
    mock_db,
):
    """Test type: behavioral
    Verifies explicit memory-save requests still persist a concrete delta when
    the internal extraction model is unavailable.
    """
    from app.services.ai.memory_extraction_service import MemoryExtractionService

    with patch(
        "app.services.ai.memory_extraction_service.async_session_factory",
        return_value=_SessionManager(mock_db),
    ), patch(
        "app.services.ai.memory_extraction_service.ConfigService",
    ) as mock_config_service, patch(
        "app.services.ai.memory_extraction_service.AgentRepository.get_by_id",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.services.ai.memory_extraction_service.InternalAIService.chat",
        new_callable=AsyncMock,
    ) as mock_chat:
        mock_config_service.return_value.get_platform_config = AsyncMock(
            side_effect=["", ""],
        )

        result = await MemoryExtractionService(tenant_id=9).extract_turn_memory(
            agent_id=9,
            message="请记住：我的项目代号是 Phoenix",
            response="好的，我会记住。",
        )

    assert result == {
        "preferences": [],
        "constraints": [],
        "task_states": [],
        "verified_facts": ["我的项目代号是 Phoenix"],
    }
    mock_chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_turn_memory_falls_back_to_explicit_fact_on_internal_error(
    mock_db,
):
    """Test type: behavioral
    Verifies the user-visible memory contract does not silently drop explicit
    remember requests when the internal extraction call fails.
    """
    from app.services.ai.memory_extraction_service import MemoryExtractionService

    with patch(
        "app.services.ai.memory_extraction_service.async_session_factory",
        return_value=_SessionManager(mock_db),
    ), patch(
        "app.services.ai.memory_extraction_service.ConfigService",
    ) as mock_config_service, patch(
        "app.services.ai.memory_extraction_service.InternalAIService.chat",
        new_callable=AsyncMock,
        side_effect=RuntimeError("provider unavailable"),
    ):
        mock_config_service.return_value.get_platform_config = AsyncMock(
            side_effect=["openai_compatible", "gpt-4o-mini"],
        )

        result = await MemoryExtractionService(tenant_id=1).extract_turn_memory(
            agent_id=7,
            message="帮我记住：跨对话暗号是 蓝莓雨伞 418J",
            response="好的，我会记住。",
        )

    assert result == {
        "preferences": [],
        "constraints": [],
        "task_states": [],
        "verified_facts": ["跨对话暗号是 蓝莓雨伞 418J"],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected_fact"),
    [
        ("记住：我的项目代号是 Phoenix", "我的项目代号是 Phoenix"),
        ("帮我记一下：跨对话暗号是 蓝莓雨伞 418J", "跨对话暗号是 蓝莓雨伞 418J"),
        ("以后记得我的默认语言是中文", "我的默认语言是中文"),
    ],
)
async def test_extract_turn_memory_fallback_accepts_plain_remember_phrasing(
    mock_db,
    message,
    expected_fact,
):
    """Test type: behavioral
    Verifies common explicit remember phrasings still persist when extraction
    model resolution fails.
    """
    from app.services.ai.memory_extraction_service import MemoryExtractionService

    with patch(
        "app.services.ai.memory_extraction_service.async_session_factory",
        return_value=_SessionManager(mock_db),
    ), patch(
        "app.services.ai.memory_extraction_service.ConfigService",
    ) as mock_config_service, patch(
        "app.services.ai.memory_extraction_service.AgentRepository.get_by_id",
        new_callable=AsyncMock,
        return_value=None,
    ):
        mock_config_service.return_value.get_platform_config = AsyncMock(
            side_effect=["", ""],
        )

        result = await MemoryExtractionService(tenant_id=9).extract_turn_memory(
            agent_id=9,
            message=message,
            response="好的，我会记住。",
        )

    assert result == {
        "preferences": [],
        "constraints": [],
        "task_states": [],
        "verified_facts": [expected_fact],
    }
