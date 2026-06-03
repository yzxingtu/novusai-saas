"""中文: AI 测试模块分类标记。

EN: AI test module classification marker.

Test type: structural / behavioral
Scope: Existing AI tests in this module; no real-dialogue smoke acceptance is claimed.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.engine_bootstrap_support import (
    build_engine_bootstrap_bundle,
)
from app.ai.engine.image_generation import ImageGenerationEngine
from app.ai.engine.types import ExecutionRequest
from app.enums.agent import AgentExecutionModeEnum


@pytest.mark.asyncio
async def test_build_engine_bootstrap_bundle_allows_image_engine_for_stream_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = object()
    resolve_for_agent = AsyncMock()

    monkeypatch.setattr(
        "app.ai.engine.engine_bootstrap_support.AIGateway",
        lambda _db: gateway,
    )
    monkeypatch.setattr(
        "app.ai.skills.resolver.resolve_for_agent",
        resolve_for_agent,
    )

    request = ExecutionRequest(
        agent_id=7,
        tenant_id=11,
        execution_mode=AgentExecutionModeEnum.CONVERSATION.value,
        stream=True,
    )
    agent = SimpleNamespace(
        id=7,
        model=SimpleNamespace(type="image"),
    )

    bundle = await build_engine_bootstrap_bundle(
        db=MagicMock(),
        agent=agent,
        request=request,
        allow_image_engine=True,
    )

    assert isinstance(bundle.engine, ImageGenerationEngine)
    assert bundle.gateway is gateway
    assert bundle.skill_result is None
    assert bundle.sandbox is None
    assert bundle.is_image_model is True
    resolve_for_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_build_engine_bootstrap_bundle_tolerates_stream_skill_resolution_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = object()

    monkeypatch.setattr(
        "app.ai.engine.engine_bootstrap_support.AIGateway",
        lambda _db: gateway,
    )
    monkeypatch.setattr(
        "app.ai.skills.resolver.resolve_for_agent",
        AsyncMock(side_effect=RuntimeError("resolver boom")),
    )
    monkeypatch.setattr(
        "app.configs.service.ConfigService.get_platform_config",
        AsyncMock(side_effect=["normal", 256]),
    )

    request = ExecutionRequest(
        agent_id=7,
        tenant_id=11,
        execution_mode=AgentExecutionModeEnum.CONVERSATION.value,
        stream=True,
        user_role="tenant_admin",
    )
    agent = SimpleNamespace(
        id=7,
        model=SimpleNamespace(type="chat"),
    )

    bundle = await build_engine_bootstrap_bundle(
        db=MagicMock(),
        agent=agent,
        request=request,
        tolerate_skill_resolution_failure=True,
    )

    assert isinstance(bundle.engine, ConversationEngine)
    assert bundle.gateway is gateway
    assert bundle.skill_result is None
    assert bundle.sandbox is bundle.engine.sandbox
    assert bundle.is_image_model is False
